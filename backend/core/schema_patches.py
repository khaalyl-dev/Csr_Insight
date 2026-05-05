"""
Additive schema fixes for existing MySQL databases when models gain columns before formal migrations.

Runs safe ALTER TABLE ... ADD COLUMN only when information_schema shows the column is missing.
"""
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _column_exists(connection, table: str, column: str) -> bool:
    row = connection.execute(
        text(
            """
            SELECT COUNT(*) AS n
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
              AND COLUMN_NAME = :column
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    return bool(row and row[0])


def apply_schema_patches(db) -> None:
    """Call from create_app after db.create_all()."""
    dialect = (getattr(db.engine.dialect, "name", "") or "").lower()
    if dialect not in ("mysql", "mariadb"):
        return
    def _apply_patch(conn, table: str, column: str, sql: str, label: str) -> None:
        try:
            if _column_exists(conn, table, column):
                return
            conn.execute(text(sql))
            conn.commit()
            logger.info("Applied schema patch: %s", label)
        except Exception as exc:
            logger.warning("Schema patch failed (%s): %s", label, exc)
            try:
                conn.rollback()
            except Exception:
                pass
    try:
        with db.engine.connect() as conn:
            _apply_patch(
                conn,
                "change_requests",
                "validation_step",
                "ALTER TABLE change_requests "
                "ADD COLUMN validation_step INT NULL "
                "COMMENT '1=niveau 1 site, 2=corporate (déverrouillage)' "
                "AFTER validation_mode",
                "change_requests.validation_step",
            )
            _apply_patch(
                conn,
                "planned_activity",
                "edition_year",
                "ALTER TABLE planned_activity "
                "ADD COLUMN edition_year INT NULL "
                "COMMENT 'Année de l\\'édition (colonne Year du fichier consolidé CSR)' "
                "AFTER edition",
                "planned_activity.edition_year",
            )
            _apply_patch(
                conn,
                "planned_activity",
                "off_plan_validation_mode",
                "ALTER TABLE planned_activity "
                "ADD COLUMN off_plan_validation_mode VARCHAR(10) NULL "
                "COMMENT 'Mode validation modification in-plan: 101 ou 111' "
                "AFTER unlock_since",
                "planned_activity.off_plan_validation_mode",
            )
            _apply_patch(
                conn,
                "planned_activity",
                "off_plan_validation_step",
                "ALTER TABLE planned_activity "
                "ADD COLUMN off_plan_validation_step INT NULL "
                "COMMENT 'Étape validation modification in-plan' "
                "AFTER off_plan_validation_mode",
                "planned_activity.off_plan_validation_step",
            )
            _apply_patch(
                conn,
                "realized_activity",
                "off_plan_validation_mode",
                "ALTER TABLE realized_activity "
                "ADD COLUMN off_plan_validation_mode VARCHAR(10) NULL "
                "COMMENT 'Mode validation hors plan: 101 ou 111' "
                "AFTER is_off_plan",
                "realized_activity.off_plan_validation_mode",
            )
            _apply_patch(
                conn,
                "realized_activity",
                "off_plan_validation_step",
                "ALTER TABLE realized_activity "
                "ADD COLUMN off_plan_validation_step INT NULL "
                "COMMENT 'Étape validation hors plan (111: 1=L1, 2=corporate)' "
                "AFTER off_plan_validation_mode",
                "realized_activity.off_plan_validation_step",
            )
            _apply_patch(
                conn,
                "planned_activity",
                "organization",
                "ALTER TABLE planned_activity "
                "ADD COLUMN organization VARCHAR(255) NULL "
                "COMMENT 'Organisation'",
                "planned_activity.organization",
            )
            _apply_patch(
                conn,
                "planned_activity",
                "contract_type",
                "ALTER TABLE planned_activity "
                "ADD COLUMN contract_type VARCHAR(100) NULL "
                "COMMENT 'Type de contrat' "
                "AFTER organization",
                "planned_activity.contract_type",
            )
            _apply_patch(
                conn,
                "planned_activity",
                "employees_planned",
                "ALTER TABLE planned_activity "
                "ADD COLUMN employees_planned INT NULL "
                "COMMENT 'Employés impliqués (prévu)' "
                "AFTER action_impact_duration",
                "planned_activity.employees_planned",
            )
            _apply_patch(
                conn,
                "realized_activity",
                "corporate_image_improved",
                "ALTER TABLE realized_activity "
                "ADD COLUMN corporate_image_improved TINYINT(1) NULL "
                "COMMENT 'Image corporate améliorée'",
                "realized_activity.corporate_image_improved",
            )
            _apply_patch(
                conn,
                "realized_activity",
                "incidents_number",
                "ALTER TABLE realized_activity "
                "ADD COLUMN incidents_number INT NULL "
                "COMMENT 'Nombre d\\'incidents'",
                "realized_activity.incidents_number",
            )
            _apply_patch(
                conn,
                "realized_activity",
                "contact_department",
                "ALTER TABLE realized_activity "
                "ADD COLUMN contact_department VARCHAR(255) NULL "
                "COMMENT 'Département du contact'",
                "realized_activity.contact_department",
            )
            _apply_patch(
                conn,
                "user_sites",
                "access_types_json",
                "ALTER TABLE user_sites "
                "ADD COLUMN access_types_json LONGTEXT NULL "
                "COMMENT 'Types d\\'accès accordés pour ce site (JSON array)'",
                "user_sites.access_types_json",
            )
            _apply_patch(
                conn,
                "csr_plans",
                "total_hc",
                "ALTER TABLE csr_plans "
                "ADD COLUMN total_hc INT NULL "
                "COMMENT 'Effectif total (HC) commun aux activités du plan' "
                "AFTER status",
                "csr_plans.total_hc",
            )
            _apply_patch(
                conn,
                "csr_plans",
                "allocated_budget",
                "ALTER TABLE csr_plans "
                "ADD COLUMN allocated_budget DECIMAL(15,2) NULL "
                "COMMENT 'Budget alloué du plan (€)' "
                "AFTER status",
                "csr_plans.allocated_budget",
            )
            try:
                if _column_exists(conn, "csr_plans", "total_budget"):
                    conn.execute(
                        text(
                            "UPDATE csr_plans "
                            "SET allocated_budget = total_budget "
                            "WHERE allocated_budget IS NULL AND total_budget IS NOT NULL"
                        )
                    )
                    conn.commit()
            except Exception as exc:
                logger.warning("Schema patch failed (csr_plans.allocated_budget backfill): %s", exc)
                try:
                    conn.rollback()
                except Exception:
                    pass
            try:
                if _column_exists(conn, "csr_plans", "total_budget"):
                    conn.execute(text("ALTER TABLE csr_plans DROP COLUMN total_budget"))
                    conn.commit()
                    logger.info("Applied schema patch: csr_plans.drop_total_budget")
            except Exception as exc:
                logger.warning("Schema patch failed (csr_plans.drop_total_budget): %s", exc)
                try:
                    conn.rollback()
                except Exception:
                    pass
            try:
                if _column_exists(conn, "planned_activity", "number_external_partners"):
                    conn.execute(text("ALTER TABLE planned_activity DROP COLUMN number_external_partners"))
                    conn.commit()
                    logger.info("Applied schema patch: planned_activity.drop_number_external_partners")
            except Exception as exc:
                logger.warning("Schema patch failed (planned_activity.drop_number_external_partners): %s", exc)
                try:
                    conn.rollback()
                except Exception:
                    pass
            try:
                if _column_exists(conn, "realized_activity", "number_external_partners"):
                    conn.execute(text("ALTER TABLE realized_activity DROP COLUMN number_external_partners"))
                    conn.commit()
                    logger.info("Applied schema patch: realized_activity.drop_number_external_partners")
            except Exception as exc:
                logger.warning("Schema patch failed (realized_activity.drop_number_external_partners): %s", exc)
                try:
                    conn.rollback()
                except Exception:
                    pass
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_permissions (
                        id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        user_id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        resource VARCHAR(64) NOT NULL,
                        action VARCHAR(64) NOT NULL,
                        is_allowed TINYINT(1) NOT NULL DEFAULT 1,
                        created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        KEY idx_user_permissions_user_id (user_id),
                        CONSTRAINT uq_user_permissions_user_resource_action UNIQUE (user_id, resource, action),
                        CONSTRAINT fk_user_permissions_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS csr_objectives (
                        id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        activity_id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        objective TEXT NOT NULL,
                        created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        KEY idx_csr_objectives_activity_id (activity_id),
                        CONSTRAINT fk_csr_objectives_activity
                          FOREIGN KEY (activity_id) REFERENCES planned_activity(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            try:
                conn.execute(text("DROP TABLE IF EXISTS csr_activity_planned"))
                conn.commit()
                logger.info("Applied schema patch: drop_table.csr_activity_planned")
            except Exception as exc:
                logger.warning("Schema patch failed (drop_table.csr_activity_planned): %s", exc)
                try:
                    conn.rollback()
                except Exception:
                    pass
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS csr_completed_objectives (
                        id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        activity_id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        objective TEXT NOT NULL,
                        achieved TINYINT(1) NOT NULL DEFAULT 1,
                        created_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        KEY idx_csr_completed_objectives_activity_id (activity_id),
                        CONSTRAINT fk_csr_completed_objectives_activity
                          FOREIGN KEY (activity_id) REFERENCES planned_activity(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS csr_attachments (
                        id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        activity_id CHAR(36) COLLATE utf8mb4_unicode_ci NOT NULL,
                        file_path LONGTEXT NOT NULL,
                        uploaded_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        KEY idx_csr_attachments_activity_id (activity_id),
                        CONSTRAINT fk_csr_attachments_activity
                          FOREIGN KEY (activity_id) REFERENCES planned_activity(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                    """
                )
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Schema patches skipped or failed: %s", exc)
        try:
            db.session.rollback()
        except Exception:
            pass
