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
"""
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy import text

from app import create_app
from core.db import db
from core.permissions import ALLOWED_PERMISSION_KEYS
from models import User, Site, UserSite, Category, CsrPlan, CsrActivity


def _run_seed_activities_sql() -> None:
    """
    Run the re-runnable SQL seed script that creates a dedicated test plan
    with 50 planned activities and 100 realized rows (year 2099).

    This is optional and safe to call multiple times: the script cleans up
    only its own generated rows (activity_number starting with SEED-PA-).
    """
    backend_root = Path(__file__).resolve().parent
    sql_path = backend_root / "migrations" / "seed_test_activities.sql"
    if not sql_path.is_file():
        print("⚠ seed_test_activities.sql not found; skipping activity seeding")
        return

    raw = sql_path.read_text(encoding="utf-8")
    statements = []
    buf: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        # Skip SQL comments
        if stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt:
                # Remove trailing semicolon for SQLAlchemy text() execution
                if stmt.endswith(";"):
                    stmt = stmt[:-1].strip()
                statements.append(stmt)
            buf = []
    if buf:
        stmt = "\n".join(buf).strip()
        if stmt:
            statements.append(stmt)

    conn = db.session.connection()
    for stmt in statements:
        conn.execute(text(stmt))
    db.session.commit()


def _seed_yearly_test_plans_with_activities() -> None:
    """
    Create 1 plan with 50 planned activities for each of:
      - past year (current_year - 1)
      - current year
      - future year (current_year + 1)

    The plans are attached to the first site and first user and are
    re-seeded safely on each run by deleting only activities whose
    activity_number starts with an INIT-SEED prefix.
    """
    first_site = Site.query.order_by(Site.code).first()
    first_user = User.query.order_by(User.email).first()
    first_category = Category.query.order_by(Category.name).first()
    if not (first_site and first_user and first_category):
        print("⚠ Cannot seed yearly test plans: missing site, user, or category")
        return

    current_year = datetime.now(UTC).year
    years = [current_year - 1, current_year, current_year + 1]
    seed_prefix = "INIT-SEED-"

    for year in years:
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

        pattern = f"{seed_prefix}{year}-%"
        CsrActivity.query.filter(
            CsrActivity.plan_id == plan.id,
            CsrActivity.activity_number.like(pattern),
        ).delete(synchronize_session=False)

        for i in range(1, 51):
            number = f"{seed_prefix}{year}-{i:03d}"
            activity = CsrActivity(
                plan_id=plan.id,
                category_id=first_category.id,
                activity_number=number,
                title=f"Seed activity {i} for {year}",
                organization="Internal" if i % 2 == 0 else "External",
                contract_type="One shot" if i % 2 == 0 else "Successive performance",
                description=f"Generated test activity #{i} for year {year}.",
                collaboration_nature="PARTNERSHIP",
                periodicity="Annual",
                planned_budget=500 + i * 50,
                action_impact_target=10 + i,
                action_impact_unit="people",
                action_impact_duration="1 year",
                employees_planned=5 + (i % 20),
                start_year=year,
                edition=1,
                organizer="CSR Team",
                status="DRAFT",
                created_by=first_user.id,
            )
            db.session.add(activity)

    db.session.commit()
    print("✓ Seeded yearly test plans with 50 planned activities each (past/current/future)")


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

        # Seed per-year test plans (past, current, future) with 50 planned activities each
        _seed_yearly_test_plans_with_activities()

        # Seed dedicated test plan (year 2099) with 50 planned + 100 realized activities
        _run_seed_activities_sql()


if __name__ == "__main__":
    init_db()
