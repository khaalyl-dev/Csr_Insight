#!/usr/bin/env python
"""
Initialize the database - creates all tables and loads test data.

Run this script once when setting up a new database:
    python init_db.py

What it does:
1. Drops all existing tables
2. Creates all tables (users, sites, categories, etc.)
2. Adds default CSR categories (Environment, Social, Gouvernance, etc.)
3. Adds sample users (admin@test.com, user@test.com, john@example.com, user@level0.com, user@level1.com, user@level2.com, user@level3.com)
4. Adds sample sites (Tianjin, Durrango, etc.)
5. Assigns sites to users with validation grades (level_0, level_1, level_2, level_3)
6. Seeds CSR plans (150 activities): past 40 with reports (COMPLETED), current 50 (PENDING), future 60 (PLANNED) once plan is approved and KPIs recomputed
"""
from datetime import datetime, UTC, date

from sqlalchemy import text

from app import create_app
from core.db import db
from core.permissions import ALLOWED_PERMISSION_KEYS
from features.kpi_management.kpi_service import recompute_plan_activity_kpis
from models import (
    User,
    Site,
    UserSite,
    Category,
    CsrPlan,
    CsrActivity,
    CsrObjective,
    CsrCompletedObjective,
    RealizedCsr,
    ExternalPartner,
    ActivityKpi,
)


def _validate_seeded_plan_after_whole_plan_drafted(plan_id: str, seed_prefix: str) -> tuple[int, int, int]:
    """
    Simulate corporate approval of the entire annual plan: once all planned lines and draft report
    rows for that plan exist, the plan is VALIDATED (with validated_at), then seeded lines and their
    reports move to VALIDATED so KPI lifecycle can resolve to PLANNED / PENDING / COMPLETED from data.
    """
    now = datetime.now(UTC)
    plans_updated = CsrPlan.query.filter(CsrPlan.id == plan_id).update(
        {
            "status": "VALIDATED",
            "validated_at": now,
            "validation_step": None,
        },
        synchronize_session=False,
    )
    activity_pattern = f"{seed_prefix}%"
    activities_updated = (
        CsrActivity.query.filter(
            CsrActivity.plan_id == plan_id,
            CsrActivity.activity_number.like(activity_pattern),
        ).update({"status": "VALIDATED"}, synchronize_session=False)
    )
    activity_ids = [
        row[0]
        for row in db.session.query(CsrActivity.id)
        .filter(
            CsrActivity.plan_id == plan_id,
            CsrActivity.activity_number.like(activity_pattern),
        )
        .all()
    ]
    reports_updated = 0
    if activity_ids:
        reports_updated = RealizedCsr.query.filter(RealizedCsr.activity_id.in_(activity_ids)).update(
            {"status": "VALIDATED"},
            synchronize_session=False,
        )
    return plans_updated, activities_updated, reports_updated


def _seed_yearly_test_plans_with_activities() -> None:
    """
    Create three annual plans on the first site (150 activities). After approval + KPI recompute,
    lifecycle follows **plan year** vs current year: past → COMPLETED, current → PENDING, future → PLANNED.

      - Past-year plan: 40 activities, each with one `realized_activity` row (CSR Reports data).
        Lifecycle COMPLETED (past year < today).
      - Current-year plan: 50 activities, no realizations → PENDING (CSR Activities).
      - Future-year plan: 60 activities, no realizations → PLANNED (CSR Activities).

    Plans are re-seeded by deleting only activities whose activity_number starts with INIT-SEED-.
    Each plan is fully drafted, then whole-plan validation runs before KPI recompute.
    """
    # Counts: CSR Activities list = PLANNED (60) + PENDING (50); CSR Reports rows = 40 (past plan).
    count_planned_bucket = 60
    count_pending_bucket = 50
    count_completed_bucket = 40

    first_site = Site.query.order_by(Site.code).first()
    first_user = User.query.order_by(User.email).first()
    first_category = Category.query.order_by(Category.name).first()
    if not (first_site and first_user and first_category):
        print("⚠ Cannot seed yearly test plans: missing site, user, or category")
        return

    current_year = datetime.now(UTC).year
    # (calendar_year, number of INIT-SEED lines, realization rule)
    # realize_after_index: None → never insert realized_activity for this plan.
    # int N → one report row per activity when line index i satisfies i > N (first N lines stay planned-only).
    year_plan_specs = [
        (current_year - 1, count_completed_bucket, 0),
        (current_year, count_pending_bucket, None),
        (current_year + 1, count_planned_bucket, None),
    ]
    seed_prefix = "INIT-SEED-"

    collaboration_variants = ["PARTNERSHIP", "SPONSORSHIP", "CHARITY_DONATION", "OTHERS"]
    periodicity_variants = ["Monthly", "Quarterly", "Annual", "One-time"]
    impact_units = ["people", "trees", "hours", "kits"]
    organizers = ["CSR Team", "HR", "Operations", "QHSE", "Logistics"]
    activity_topics = [
        "School support campaign",
        "Tree planting drive",
        "Safety awareness workshop",
        "Blood donation event",
        "Community clean-up",
        "STEM mentoring session",
    ]
    objective_templates = [
        "Engage local stakeholders",
        "Improve measurable impact",
        "Increase employee participation",
        "Deliver action within budget",
        "Improve community satisfaction",
    ]

    total_planned_budget = 0.0
    activity_lines_seeded = 0
    completed_objectives_seeded = 0
    activities_with_realization = 0
    realization_rows_seeded = 0
    plans_validated = 0
    activities_validated = 0
    reports_validated = 0

    for year, n_lines, realize_after_index in year_plan_specs:
        plan = (
            CsrPlan.query.filter_by(site_id=first_site.id, year=year)
            .order_by(CsrPlan.created_at)
            .first()
        )
        if not plan:
            plan = CsrPlan(
                site_id=first_site.id,
                year=year,
                validation_mode="101",
                status="DRAFT",
                allocated_budget=100_000,
                total_hc=800,
                created_by=first_user.id,
            )
            db.session.add(plan)
            db.session.flush()
            print(f"✓ Created test plan for site={first_site.code} year={year}")
        plan.status = "DRAFT"

        pattern = f"{seed_prefix}{year}-%"
        CsrActivity.query.filter(
            CsrActivity.plan_id == plan.id,
            CsrActivity.activity_number.like(pattern),
        ).delete(synchronize_session=False)

        for i in range(1, max(n_lines, 0) + 1):
            seed_realizations = realize_after_index is not None and i > realize_after_index
            number = f"{seed_prefix}{year}-{i:03d}"
            planned_budget = 1200 + ((i * 173) % 4200)
            total_planned_budget += float(planned_budget)
            activity_lines_seeded += 1
            employees_planned = 8 + (i % 35)
            impact_target = 20 + ((i * 7) % 140)
            partner_count = 1 + (i % 3)
            partner_names = [
                f"{['Atlas', 'Green', 'Future', 'Care', 'Impact'][((i + p) % 5)]} Partner {((i + p) % 17) + 1}"
                for p in range(partner_count)
            ]
            external_partner_name = ", ".join(partner_names)
            ext_partner = (
                ExternalPartner.query.filter(db.func.lower(ExternalPartner.name) == external_partner_name.lower()).first()
            )
            if not ext_partner:
                ext_partner = ExternalPartner(
                    name=external_partner_name,
                    type="OTHER",
                    contact_person=f"Seed Contact {i}",
                    email=f"partner.seed.{year}.{i}@example.com",
                    phone=f"+2126000{i:04d}",
                    is_active=True,
                )
                db.session.add(ext_partner)
                db.session.flush()
            activity = CsrActivity(
                plan_id=plan.id,
                category_id=first_category.id,
                external_partner_id=ext_partner.id,
                activity_number=number,
                title=f"{activity_topics[(i - 1) % len(activity_topics)]} #{i}",
                organization="Internal" if i % 2 == 0 else "External",
                contract_type="One shot" if i % 2 == 0 else "Successive performance",
                description=(
                    f"Generated diversified test activity #{i} for year {year}. "
                    + (
                        "Includes one seeded CSR report after validation."
                        if seed_realizations
                        else "Planning only (no seeded realization rows)."
                    )
                ),
                collaboration_nature=collaboration_variants[(i - 1) % len(collaboration_variants)],
                periodicity=periodicity_variants[(i - 1) % len(periodicity_variants)],
                planned_budget=planned_budget,
                action_impact_target=impact_target,
                action_impact_unit=impact_units[(i - 1) % len(impact_units)],
                action_impact_duration=("1 month" if i % 3 == 0 else ("6 months" if i % 3 == 1 else "1 year")),
                employees_planned=employees_planned,
                start_year=year,
                edition=1 + ((i - 1) % 4),
                organizer=organizers[(i - 1) % len(organizers)],
                status="DRAFT",
                created_by=first_user.id,
            )
            db.session.add(activity)
            db.session.flush()

            announced_count = 2 + (i % 3)
            objective_labels: list[str] = []
            for j in range(announced_count):
                obj_text = (
                    f"{objective_templates[(i + j - 1) % len(objective_templates)]} "
                    f"(A{number}-{j + 1})"
                )
                objective_labels.append(obj_text)
                db.session.add(CsrObjective(activity_id=activity.id, objective=obj_text))

            if seed_realizations:
                # Exactly one `realized_activity` row per completed activity (40 activities → 40 rows).
                realized_rows = 1
                activities_with_realization += 1
                realization_rows_seeded += realized_rows
                participants_total = 0
                for r in range(realized_rows):
                    participants = max(1, employees_planned + ((i + r) % 9) - 4)
                    participants_total += participants
                    budget_ratio = 0.78 + (((i + (r * 2)) % 9) * 0.06)  # ~0.78 .. 1.26
                    realized_budget = round(float(planned_budget) * budget_ratio / realized_rows, 2)
                    incidents = (i + r) % 3 if (i + r) % 7 == 0 else 0
                    month = ((i + r) % 12) + 1
                    day = ((i * 2 + r * 3) % 27) + 1
                    db.session.add(
                        RealizedCsr(
                            activity_id=activity.id,
                            participants=participants,
                            corporate_image_improved=((i + r) % 5 != 0),
                            incidents_number=incidents,
                            contact_department=organizers[(i + r) % len(organizers)],
                            realized_budget=realized_budget,
                            action_impact_actual=max(1, int(impact_target * (0.65 + (((i + r) % 8) * 0.08)))),
                            action_impact_unit=activity.action_impact_unit,
                            realization_date=date(year, month, day),
                            comment=f"Seed realization {r + 1} for {number}",
                            contact_name=f"Seed Contact {i}-{r + 1}",
                            contact_email=f"seed.{year}.{i}.{r + 1}@example.com",
                            created_by=first_user.id,
                            status="DRAFT",
                        )
                    )

                completed_count = min(announced_count, max(1, (participants_total // max(1, employees_planned)) + (i % 2)))
                completed_objectives_seeded += completed_count
                for j in range(completed_count):
                    db.session.add(
                        CsrCompletedObjective(
                            activity_id=activity.id,
                            objective=objective_labels[j],
                            achieved=True,
                        )
                    )

        pv, av, rv = _validate_seeded_plan_after_whole_plan_drafted(plan.id, seed_prefix)
        plans_validated += pv
        activities_validated += av
        reports_validated += rv

    db.session.commit()
    total_lines = count_planned_bucket + count_pending_bucket + count_completed_bucket
    print(
        f"✓ Seeded {total_lines} CSR activities: {count_completed_bucket} past + reports (COMPLETED), "
        f"{count_pending_bucket} current (PENDING), {count_planned_bucket} future (PLANNED) after KPI recompute."
    )
    print(
        "  • Workflow: each annual plan was fully drafted (DRAFT lines and report rows), then whole-plan "
        "validation set the plan to VALIDATED (validated_at), approved all seeded lines and draft reports, "
        "so KPI lifecycle recomputes as PLANNED, PENDING, or COMPLETED from planned vs realized data."
    )
    print(
        f"  • Whole-plan validation: {plans_validated} annual plan(s), {activities_validated} activity line(s), "
        f"{reports_validated} CSR report row(s) approved"
    )
    print(
        f"  • Planned budget (sum of line budgets): {total_planned_budget:,.2f} "
        f"over {activity_lines_seeded} planned CSR activity lines"
    )
    print(
        f"  • Completed objectives seeded (achieved=True): {completed_objectives_seeded} "
        f"for {activities_with_realization} activities that have report data"
    )
    print(
        f"  • CSR report rows seeded (draft insert, then validated): {realization_rows_seeded}; "
        f"{activity_lines_seeded - activities_with_realization} activity lines have no realization "
        "(PLANNED + PENDING lines only)"
    )


def _log_seeded_kpi_lifecycle_totals() -> None:
    """After KPI recompute, confirm PLANNED / PENDING / COMPLETED counts for seeded plans."""
    first_site = Site.query.order_by(Site.code).first()
    current_year = datetime.now(UTC).year
    if not first_site:
        return
    plan_ids = [
        p.id
        for p in CsrPlan.query.filter(
            CsrPlan.site_id == first_site.id,
            CsrPlan.year.in_([current_year - 1, current_year, current_year + 1]),
        ).all()
    ]
    if not plan_ids:
        return
    rows = (
        db.session.query(ActivityKpi.lifecycle_status, db.func.count(ActivityKpi.id))
        .join(CsrActivity, CsrActivity.id == ActivityKpi.activity_id)
        .filter(CsrActivity.plan_id.in_(plan_ids))
        .group_by(ActivityKpi.lifecycle_status)
        .all()
    )
    print("✓ KPI lifecycle distribution (seeded plans, first site):")
    for status, cnt in sorted(rows, key=lambda x: (x[0] is None, x[0] or "")):
        print(f"  • {status or 'NULL'}: {cnt}")


def _recompute_seeded_kpis() -> None:
    current_year = datetime.now(UTC).year
    target_years = [current_year - 1, current_year, current_year + 1]
    plan_ids = [
        row[0]
        for row in db.session.query(CsrPlan.id).filter(CsrPlan.year.in_(target_years)).all()
    ]
    for plan_id in plan_ids:
        recompute_plan_activity_kpis(plan_id)
    db.session.commit()
    print(f"✓ Recomputed activity KPIs for {len(plan_ids)} seeded plan(s)")


def init_db():
    """
    Initialize the database: drop all tables, create them, then seed with default categories, users, and sites.

    WARNING: This destroys all existing data. Use for fresh setup or reset only.
    """
    # Create the Flask app so we can use db.create_all() and db.session
    app = create_app()
    with app.app_context():
        # Drop/create with FK checks disabled (MySQL) to avoid ordering issues
        # when schema names/constraints changed across iterations.
        db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        db.session.commit()
        try:
            db.drop_all()
            print("✓ All tables dropped")
            # Create all tables defined in models (users, sites, categories, etc.)
            db.create_all()
            print("✓ Database tables created")
        finally:
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()

        # Default CSR categories
        if Category.query.count() == 0:
            for name in ["Environment", "Social", "Gouvernance", "Education", "Santé"]:
                db.session.add(Category(name=name))
            db.session.commit()
            print("✓ Categories added (Environment, Social, Gouvernance, Education, Santé)")
        else:
            print("✓ Categories already exist")

        sample_users = [
            {"email": "user@test.com", "password": "password123", "role": "SITE_USER", "first_name": "Site", "last_name": "User"},
            {"email": "admin@test.com", "password": "admin123", "role": "CORPORATE_USER", "first_name": "Corporate", "last_name": "Admin"},
            {"email": "john@example.com", "password": "john123", "role": "SITE_USER", "first_name": "John", "last_name": "Doe"},
            {"email": "user@level0.com", "password": "password123", "role": "SITE_USER", "first_name": "Level", "last_name": "Zero"},
            {"email": "user@level1.com", "password": "password123", "role": "SITE_USER", "first_name": "Level", "last_name": "One"},
            {"email": "user@level2.com", "password": "password123", "role": "SITE_USER", "first_name": "Level", "last_name": "Two"},
            {"email": "user@level3.com", "password": "password123", "role": "SITE_USER", "first_name": "Level", "last_name": "Three"},
        ]
        added = 0
        for u in sample_users:
            if User.query.filter_by(email=u["email"]).first():
                continue
            user = User(
                email=u["email"],
                password_hash=User.hash_password(u["password"]),
                role=u["role"],
                first_name=u["first_name"],
                last_name=u["last_name"],
            )
            if u["role"] == "CORPORATE_USER" and u["email"] == "admin@test.com":
                user.is_corporate_global = True
            # Seed explicit full permissions for corporate users in user_permissions table.
            if u["role"] == "CORPORATE_USER":
                user.set_permissions({"keys": sorted(ALLOWED_PERMISSION_KEYS)})
            db.session.add(user)
            added += 1
        db.session.commit()

        # Ensure existing corporate users also have explicit default permissions seeded.
        corporate_users = User.query.filter_by(role="CORPORATE_USER").all()
        updated_permissions = 0
        for cu in corporate_users:
            current = cu.get_permissions() or {}
            keys = current.get("keys") if isinstance(current, dict) else None
            if not keys:
                cu.set_permissions({"keys": sorted(ALLOWED_PERMISSION_KEYS)})
                updated_permissions += 1
        if updated_permissions:
            db.session.commit()
            print(f"✓ Seeded default permissions for {updated_permissions} corporate user(s)")

        if added:
            print(f"✓ Added {added} user(s)")
        else:
            print("✓ All sample users already exist")
        print("\nTest credentials:")
        for u in sample_users:
            print(f"  - {u['email']} / {u['password']} ({u['role']})")

        # Sample sites — aligned with "2024 CSR Consolidated Report Form (1).xlsx". Plant = site name (for Excel import matching).
        sample_sites = [
            {"name": "Tianjin", "code": "COFCN", "region": "ASIA", "country": "China", "location": "Tianjin"},
            {"name": "Durrango", "code": "COFMX", "region": "America", "country": "Mexico", "location": "Durrango"},
            {"name": "Honduras", "code": "COFHN", "region": "America", "country": "Mexico", "location": "Honduras"},
            {"name": "Juarez", "code": "COFJU", "region": "America", "country": "Mexico", "location": "Juarez"},
            {"name": "Léon", "code": "COFLN", "region": "America", "country": "Mexico", "location": "Léon"},
            {"name": "Ploeisti", "code": "COFRO", "region": "EE", "country": "Romania", "location": "Ploeisti"},
            {"name": "Romania", "code": "COFRO2", "region": "EE", "country": "Romania", "location": "Romania"},
            {"name": "Serbia", "code": "COFRS", "region": "EE", "country": "Serbia", "location": "Serbia"},
            {"name": "Kenitra", "code": "COFMA", "region": "North Africa", "country": "Morocco", "location": "Kenitra"},
            {"name": "Tangier", "code": "COFKT", "region": "North Africa", "country": "Morocco", "location": "Tangier"},
            {"name": "Mdjez el beb", "code": "COFMD", "region": "North Africa", "country": "Tunisia", "location": "Mdjez el beb"},
            {"name": "Tunis", "code": "COFTN", "region": "North Africa", "country": "Tunisia", "location": "Tunis"},
            {"name": "Guarda", "code": "COFPT", "region": "western Europe", "country": "Portugal", "location": "Guarda"},
            {"name": "Guarda 2", "code": "COFPT2", "region": "western Europe", "country": "Portugal", "location": "Guarda 2"},
        ]
        sites_added = 0
        for s in sample_sites:
            if Site.query.filter_by(code=s["code"]).first():
                continue
            site = Site(
                name=s["name"],
                code=s["code"],
                region=s["region"],
                country=s["country"],
                location=s["location"],
                is_active=True,
            )
            db.session.add(site)
            sites_added += 1
        db.session.commit()
        if sites_added:
            print(f"✓ Added {sites_added} site(s)")

        # Assign sites to site users (user@test.com, john@example.com) with level_1
        site_user_emails = ["user@test.com", "john@example.com"]
        admin_user = User.query.filter_by(email="admin@test.com").first()
        for email in site_user_emails:
            u = User.query.filter_by(email=email).first()
            if not u or u.role != "SITE_USER":
                continue
            # Assign first 2 sites to user@test.com, first 3 to john@example.com; grade = level_1
            site_limit = 2 if email == "user@test.com" else 3
            sites = Site.query.order_by(Site.code).limit(site_limit).all()
            for site in sites:
                existing = UserSite.query.filter_by(user_id=u.id, site_id=site.id).first()
                if not existing:
                    us = UserSite(
                        user_id=u.id,
                        site_id=site.id,
                        is_active=True,
                        grade="level_1",
                        granted_by=admin_user.id if admin_user else None,
                        granted_at=datetime.now(UTC),
                    )
                    db.session.add(us)
                else:
                    existing.grade = "level_1"

        # Assign admin (corporate) to first site with level_3 for validation reference
        if admin_user:
            first_site = Site.query.order_by(Site.code).first()
            if first_site:
                admin_us = UserSite.query.filter_by(user_id=admin_user.id, site_id=first_site.id).first()
                if not admin_us:
                    us = UserSite(
                        user_id=admin_user.id,
                        site_id=first_site.id,
                        is_active=True,
                        grade="level_3",
                        granted_by=admin_user.id,
                        granted_at=datetime.now(UTC),
                    )
                    db.session.add(us)
                else:
                    admin_us.grade = "level_3"

        # Assign dedicated test users to the same site with different levels
        first_site = Site.query.order_by(Site.code).first()
        if first_site:
            level_test_users = [
                ("user@level0.com", "level_0"),
                ("user@level1.com", "level_1"),
                ("user@level2.com", "level_2"),
                ("user@level3.com", "level_3"),
            ]
            for email, grade in level_test_users:
                u = User.query.filter_by(email=email).first()
                if not u:
                    continue
                existing = UserSite.query.filter_by(user_id=u.id, site_id=first_site.id).first()
                if not existing:
                    us = UserSite(
                        user_id=u.id,
                        site_id=first_site.id,
                        is_active=True,
                        grade=grade,
                        granted_by=admin_user.id if admin_user else None,
                        granted_at=datetime.now(UTC),
                    )
                    db.session.add(us)
                else:
                    existing.grade = grade

        db.session.commit()
        print("✓ Site access assigned (level_0..level_3 for test users, level_1 for site users, level_3 for admin)")

        # Seed three annual plans: 60 + 50 + 40 activities → PLANNED / PENDING / COMPLETED lifecycles
        _seed_yearly_test_plans_with_activities()

        # Ensure KPI rows are persisted for seeded plans/activities.
        _recompute_seeded_kpis()
        _log_seeded_kpi_lifecycle_totals()


if __name__ == "__main__":
    init_db()
