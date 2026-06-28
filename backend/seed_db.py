#!/usr/bin/env python3
"""
Demo CSR seed: **every site** gets **4 annual plans** — current calendar year plus the
**previous three years** (Y, Y−1, Y−2, Y−3).

- **Current year:** only **planned** data — no ``realized_activity`` rows, no
  ``csr_completed_objectives``. About **10%** of lines use **sparse planned fields**
  (``planned_budget``, ``action_impact_target``, ``employees_planned`` set to **0**;
  no partner, etc.) but **collaboration_nature**, **edition**, and **organizer** are still
  set, like an activity **not** in the original
  budget (“hors plan initial”, déclaration à venir). There is still **no** CSR report
  row until you create one in the app (so ``is_off_plan`` stays false in the API).

- **Past three years:** each line has announced objectives, completed objectives where
  applicable, and **one validated realization**. About **10%** are true **off-plan**
  reports (``realized_activity.is_off_plan=True``) with **planned** side
  ``planned_budget``, ``action_impact_target``, ``employees_planned`` at **0** (no
  partner, etc.); **collaboration_nature**, **edition**, and **organizer** are filled;
  realization figures stay filled for KPIs.

Activity count per plan: **random 10–20** (inclusive). Activity numbers:
``DEMO10-{site_code}-{year}-{seq:03d}`` — script deletes only those lines before re-seed.

**Titles & timing:** catalogue lines are picked by a hash of ``site|year|line`` (fewer
collisions). About **one third** of lines are **multi-year programmes**: same display
title, ``start_year`` when the programme began, ``edition = plan_year - start_year + 1``
(so edition grows each annual plan). Other lines get a **unique** title suffix
(site, year, line). Categories and impact units are also hash-scattered.

Usage (from the backend directory)::

    python seed_dense_two_year_demo.py
    python seed_dense_two_year_demo.py --site-code COFMA
    python seed_dense_two_year_demo.py --seed 42

``--site-code`` limits seeding to that site (still 4 plans). Requires users, sites,
categories. Does not drop tables.
"""
from __future__ import annotations

import argparse
import random
from datetime import UTC, date, datetime

from app import create_app
from core.db import db
from features.kpi_management.kpi_service import recompute_plan_activity_kpis
from models import (
    ActivityKpi,
    Category,
    CsrActivity,
    CsrCompletedObjective,
    CsrObjective,
    CsrPlan,
    ExternalPartner,
    RealizedCsr,
    Site,
    User,
)

YEARS_BACK = 3  # current year + past 3 = 4 plans per site
ACTIVITY_COUNT_MIN = 10
ACTIVITY_COUNT_MAX = 20
OFF_PLAN_FRACTION = 0.10

# Realistic CSR activity titles (plant / community context); cycled as needed.
ACTIVITY_TITLES: list[str] = [

"Energy audit and LED retrofit — production hall A",
"Local blood drive with regional hospital partnership",
"STEM workshop for secondary schools near the plant",
"Riverbank clean-up with municipal environment office",
"Noise reduction project — community consultation round",
"Scholarships for apprentices in industrial maintenance",
"First-aid refresher for volunteer responders on site",
"Donation of IT equipment to vocational training centre",
"Tree planting with regional forestry association",
"Women in manufacturing mentoring day",
"Road safety awareness session for logistics teams",
"Sponsorship of junior robotics competition",
"Water consumption optimisation — cooling towers",
"Hearing conservation campaign and free screenings",
"Food bank collection during Ramadan",
"Solar panels feasibility study on warehouse roof",
"English skills course for shop-floor team leaders",
"Recycling bins and awareness campaign — offices",
"Support to local fire brigade — protective equipment",
"Open day for families — plant tour and QHSE demos",
"Charity run benefiting children’s oncology ward",
"Waste sorting training and new colour-coded stations",
"Partnership with NGO for inclusive hiring outreach",
"Donation of cables and materials to technical school",
"Mental health first-aiders certification programme",
"Groundwater monitoring wells — community reporting",
"Anti-harassment refresher and anonymous hotline comms",
"Renovation of village kindergarten playground",
"Carpooling pilot and CO₂ savings dashboard",
"Diabetes screening for employees and contractors",
"Local supplier diversity workshop",
"Biodiversity baseline survey — site perimeter",
"Winter coats collection for nearby mountain villages",
"Digital literacy afternoon for retirees’ association",
"Sponsorship of municipal youth sports league",
"Compressed air leak detection and repair blitz",
"Ergonomic assessments for repetitive assembly stations",
"Coastal litter pick (employee volunteering day)",
"Grant to university lab — materials science research",
"Community newsletter on plant environmental performance",
"Defibrillator donation to neighbouring industrial park",
"Sign language basics course for customer-facing staff",
"Habitat restoration with fishing cooperative",
"Paperless shop-floor dashboards pilot",
"Support fund for employees affected by flooding",
"Chemistry show for primary schools — safety themed",
"Night-shift shuttle safety upgrade with local council",
"Reusable bottle initiative and refill stations",
"Annual ethics & compliance town hall with Q&A",
"ISO 14001 awareness session and environmental self-assessment",
"Community solar lighting installation near school zone",
"Free dental check-up week for employees",
"Partnership with recycling startup for plastic recovery",
"Scholarship programme for women in engineering",
"Industrial waste reduction challenge — production teams",
"School supplies donation campaign before academic year",
"Green commuting awareness week",
"Fire evacuation drill with local authorities",
"Employee volunteering at regional orphanage",
"Rainwater harvesting pilot project — cafeteria building",
"Cybersecurity awareness month for office staff",
"Clothing donation drive for refugee families",
"Tree maintenance and irrigation volunteer programme",
"Workshop on responsible water usage at home",
"Community health caravan in rural areas",
"Industrial internship opportunities for university students",
"Roadside tree protection initiative near factory entrance",
"Supplier sustainability assessment campaign",
"Accessible workstation improvements for disabled employees",
"Partnership with local artists for mural painting",
"Beach protection awareness campaign with schools",
"Energy-saving competition between departments",
"Donation of laboratory equipment to science faculty",
"Women leadership panel in industrial careers",
"Green roofs pilot project — administrative building",
"Career orientation sessions in underserved schools",
"Air quality monitoring awareness event",
"CSR innovation hackathon for employees",
"Employee bicycle subsidy programme",
"Community library renovation and book donation",
"Plastic-free cafeteria awareness campaign",
"Support to local animal shelter — food and medicine",
"Zero-paper procurement workflow implementation",
"Occupational stress prevention workshops",
"Installation of EV charging stations on site",
"Financial literacy course for employees",
"Volunteer mentoring for startup entrepreneurs",
"Clean drinking water project for rural school",
"Inclusive recruitment awareness with disability NGO",
"Waste oil recycling partnership initiative",
"Energy-efficient HVAC upgrade — headquarters",
"Traditional crafts support fair for local artisans",
"Women health awareness and screening day",
"Flood prevention clean-up around industrial zone",
"Community football tournament sponsorship",
"Environmental reporting transparency workshop",
"Sustainable agriculture support with local farmers",
"Plant nursery creation for biodiversity support",
"School science fair sponsorship",
"Reusable lunchbox campaign for employees",
"Community dialogue meeting on traffic concerns",
"Electrical safety awareness training",
"Support programme for low-income students",
"Food waste reduction campaign in cafeteria",
"Public speaking workshop for young volunteers",
"Digital transformation awareness for suppliers",
"Battery recycling collection campaign",
"Plant biodiversity garden for employee wellbeing",
"Scholarship for data science students",
"Workshop on climate change adaptation",
"Volunteer painting day at community centre",
"Free vision screening for employees",
"Community Wi-Fi hotspot sponsorship",
"Employee savings and budgeting seminar",
"Donation of emergency kits to local clinic",
"Sustainable packaging pilot with suppliers",
"Green manufacturing awareness day",
"Community recycling awareness caravan",
"School transportation safety programme",
"Employee-led blood pressure awareness campaign",
"Workshop on anti-corruption and business ethics",
"Environmental documentary screening evening",
"Youth coding bootcamp partnership",
"CSR ambassador training for team leaders",
"Clean energy awareness for nearby communities",
"Occupational ergonomics improvement project",
"Public park clean-up and bench renovation",
"Solar-powered streetlights near industrial road",
"Technical training scholarships for unemployed youth",
"Digital wellness seminar for employees",
"Volunteer tutoring for mathematics students",
"Community composting awareness workshop",
"Supplier code of conduct awareness programme",
"Emergency response coordination exercise",
"Support for women entrepreneurship cooperative",
"Energy efficiency audit — compressed air systems",
"Rainwater reuse awareness campaign",
"Healthy nutrition week in cafeteria",
"Waste minimisation awareness posters installation",
"School computer lab maintenance campaign",
"Local history preservation partnership",
"Employee volunteer beach safety awareness day",
"Mental wellbeing webinar series",
"Tree adoption campaign for employees",
"Public transport awareness incentive programme",
"Workshop on sustainable procurement practices",
"Medical check-up caravan for nearby villages",
"Environmental risk mapping consultation",
"Support for children with special needs centre",
"Employee volunteering for literacy programme",
"Bicycle parking expansion initiative",
"Reforestation awareness event with scouts",
"Water leak detection awareness campaign",
"Local clean cooking initiative sponsorship",
"Plastic bottle collection competition",
"Employee emergency preparedness training",
"Free hearing test campaign for contractors",
"Workshop on workplace inclusion and diversity",
"Climate resilience awareness workshop",
"Green office certification preparation project",
"Partnership for renewable energy awareness",
"Industrial emissions reduction brainstorming workshop",
"Food donation partnership with local charities",
"Women engineers networking breakfast",
"Tree census and biodiversity mapping activity",
"Community open forum on environmental initiatives",
"Sustainable mobility challenge for employees",
"First responder coordination with municipal services",
"Awareness campaign on reducing single-use plastics",
"School recycling club sponsorship",
"Local entrepreneurship incubation mentoring",
"Volunteer day for elderly assistance centre",
"Air compressor optimisation awareness session",
"Public awareness campaign on water conservation",
"Employee wellness yoga and fitness week",
"Industrial heritage exhibition sponsorship",
"Donation of books to rural libraries",
"Sustainable landscaping around facility perimeter",
"Women in STEM scholarship ceremony",
"Community-driven urban gardening project",
"Health and hygiene kits distribution campaign",
"Renewable energy awareness booth at local fair",
"Ethical sourcing awareness for procurement teams",
"School safety equipment donation",
"Employee volunteer programme for beach cleaning",
"Water-saving faucet installation project",
"CSR photography competition — community impact",
"Industrial waste segregation training",
"Workshop on emotional intelligence at work",
"Support to local marathon charity event",
"Community dialogue on environmental concerns",
"Tree protection barriers installation campaign",
"Public bicycle repair station sponsorship",
"Digital inclusion training for seniors",
"Employee volunteering in local food kitchen",
"Hazardous waste awareness workshop",
"School environmental awareness mural project",
"Volunteer reading sessions for children",
"Green procurement supplier engagement meeting",
"Wellness challenge — steps and fitness tracking",
"Factory neighbourhood beautification initiative",
"Community compost bins installation",
"Women safety and empowerment seminar",
"Renewable energy innovation contest",
"Employee mentoring for vocational students",
"Accessible pathways improvement near site",
"Donation of PPE to local emergency teams",
"Industrial ecology awareness conference",
"Support to local cultural heritage festival",
"Electricity consumption reduction challenge",
"Community career fair sponsorship",
"Reusable tote bag awareness campaign",
"Workshop on sustainable manufacturing principles",
"Employee volunteer tree nursery management",
"Digital skills mentoring for teenagers",
"Local biodiversity awareness exhibition",
"Health awareness campaign during summer heatwave",
"Public environmental awareness radio campaign",
"Water stewardship training for employees",
"Employee volunteer blood donation marathon",
"Plant cafeteria sustainable menu initiative",
"Climate action brainstorming workshop",
"School eco-club support programme",
"Support for local disability sports association",
"Industrial equipment donation for technical training",
"Volunteer clean-up around historical sites",
"CSR innovation awards ceremony",
"Workshop on responsible consumption habits",
"Public awareness campaign on recycling electronics",
"Women mentoring network in operations",
"Factory energy dashboard awareness campaign",
"Community first-aid awareness training",
"School gardening and sustainability programme",
"Supplier engagement on carbon reduction",
"Employee volunteer programme for hospital visits",
"Air pollution awareness with local NGOs",
"Digital entrepreneurship mentoring sessions",
"Support to local disaster preparedness programme",
"Reusable cup initiative in vending areas",
"Industrial process water optimisation project",
"School attendance support for disadvantaged children",
"Volunteer literacy support for adults",
"Public awareness workshop on circular economy",
"Employee recognition day for community volunteers",
"Green transportation awareness for suppliers",
"Workplace conflict resolution seminar",
"Community playground refurbishment initiative",
"Sponsorship of youth innovation challenge",
"Employee volunteer tree irrigation campaign",
"Plastic recycling machine donation project",
"Workshop on sustainable household practices",
"Community women empowerment networking event",
"Safety awareness sessions for subcontractors",
"School meal support programme partnership",
"Environmental storytelling competition for students",
"Support to local flood relief operations",
"Volunteer painting of community sports hall",
"Recycling awareness stickers installation campaign",
"Employee wellness nutrition counselling sessions",
"Community science education outreach",
"Green innovation training for engineers",
"Donation of reusable school supplies",
"Industrial sustainability benchmarking workshop",
"Volunteer support for animal vaccination campaign",
"Public seminar on renewable energy adoption",
"Wastewater treatment awareness tour",
"School transportation bicycles donation initiative",
"Employee-led awareness on responsible driving",
"Community resilience workshop with municipalities",
"Tree planting around river restoration area",
"Women entrepreneurship grant support programme",
"Volunteer support for disability inclusion events",
"Environmental cleanup around coastal wetlands",
"Public awareness event on energy conservation",
"Industrial safety awareness for interns",
"Employee volunteer cooking for charity shelters",
"Green corridor landscaping near plant entrance",
"Support for local youth leadership camp",
"Workshop on workplace wellbeing and resilience",
"Employee-led charity clothing market",
"Rain garden installation pilot project",
"Community awareness on industrial recycling",
"School coding competition sponsorship",
"Public clean water access awareness campaign",
"Volunteer support for local marathon logistics",
"Energy management awareness month",
"Women empowerment storytelling conference",
"Local organic farming partnership support",
"Factory waste heat recovery awareness session",
"Employee volunteer language tutoring initiative",
"Community awareness on road traffic safety",
"Solar-powered charging station installation",
"Public discussion forum on environmental responsibility",
"School STEM laboratory renovation project",
"Industrial sustainability best practices seminar",
"Employee-led campaign for eco-friendly commuting",
"Donation of hygiene products to shelters",
"Volunteer support at children rehabilitation centre",
"Green workplace challenge across departments",
"Community recycling centre awareness day",
"Workshop on ethical leadership in business",
"Support for youth environmental ambassadors",
"Tree planting along industrial access roads",
"Employee volunteer coaching for sports clubs",
"Water footprint reduction awareness campaign",
"School anti-bullying awareness programme",
"Public seminar on sustainable urban mobility",
"Industrial environmental monitoring awareness event",
"Women technical careers promotion workshop",
"Volunteer-led clean-up of hiking trails",
"Community awareness on household recycling",
"Green innovation idea competition",
"Donation of sports equipment to schools",
"Employee volunteer support for food distribution",
"Workshop on sustainable event management",
"Community awareness on biodiversity conservation",
"Renewable energy awareness training for students",
"Industrial social responsibility reporting workshop",
"Volunteer support for literacy campaign",
"Plant environmental transparency open house",
"Employee volunteering at local blood bank",
"School eco-awareness theatre programme",
"Community support for winter heating assistance",
"Energy-saving tips campaign in offices",
"Public awareness on reducing food waste",
"Volunteer restoration of community gardens",
"Industrial water stewardship roundtable",
"Women empowerment entrepreneurship bootcamp",
"Support for local climate action projects",
"Employee-led charity fundraising concert",
"Community awareness campaign on fire prevention",
"Green office supplies transition programme",
"Workshop on workplace communication skills",
"Volunteer support for elderly meal delivery",
"School environmental quiz sponsorship",
"Industrial biodiversity enhancement initiative",
"Employee volunteer tutoring in science subjects",
"Public awareness on sustainable shopping habits",
"Community support for accessible education",
"Renewable energy career orientation day",
"Factory environmental compliance awareness session",
"Volunteer support for orphanage renovation",
"Employee-led campaign for reusable containers",
"Workshop on sustainable innovation culture",
"Community clean-up near industrial waterways",
"Women mentorship for technical apprentices",
"Public awareness on responsible energy use",
"School environmental poster competition",
"Industrial resource efficiency awareness programme",
"Volunteer support for refugee assistance centre",
"Employee health awareness fitness challenge",
"Community awareness on preserving green spaces",
"Donation of emergency lighting to clinics",
"Workshop on digital responsibility and ethics",
"Support to local youth coding association",
"Volunteer support for environmental education fair",
"Factory green maintenance awareness campaign",
"Employee-led donation campaign for schools",
"Public seminar on environmental citizenship",
"Community awareness on reducing water pollution",
"Women leadership mentoring in operations",
"Industrial sustainable logistics workshop",
"Volunteer support for local clean water project",
"School awareness sessions on climate action",
"Employee volunteer mentorship for startups",
"Green procurement awareness for vendors",
"Community partnership for urban tree planting",
"Workshop on stress management and wellbeing",
"Volunteer support at local health campaign",
"Industrial circular economy awareness initiative",
"Employee-led office energy reduction challenge",
"School awareness on renewable technologies",
"Community support for emergency preparedness",
"Public awareness campaign on air pollution",
"Women engineering inspiration conference",
"Volunteer support for food security programme",
"Industrial sustainability innovation showcase",
"Employee volunteering at community recycling centre",
"Workshop on sustainable leadership development",
"Community awareness on responsible waste disposal",
"Support to local educational scholarship fund",
"Volunteer support for disability awareness campaign",
"Green transportation incentive programme",
"Employee-led awareness on safe internet use",
"School environmental awareness field trip",
"Industrial carbon footprint reduction workshop",
"Volunteer support for neighbourhood renovation",
"Public awareness on sustainable water management",
"Women career development networking forum",
"Employee volunteer gardening for schools",
"Community biodiversity restoration campaign",
"Workshop on inclusive workplace culture",
"Volunteer support for local art therapy programme",
"Factory energy optimisation awareness week",
"School awareness campaign on ocean protection",
"Industrial sustainability supplier collaboration day",
"Employee-led eco-driving awareness sessions",
"Community awareness on plastic waste reduction",
"Workshop on workplace adaptability and innovation",
"Volunteer support for children education charity",
"Public awareness campaign on renewable resources",
"Women empowerment training for entrepreneurs",
"Employee volunteer support for literacy classes",
"Green manufacturing continuous improvement initiative",
"Community support for rural health outreach",
"Workshop on sustainable teamwork practices",
"Volunteer support for environmental cleanup marathon",
"School awareness on biodiversity protection",
"Industrial waste reduction innovation challenge",
"Employee-led campaign on healthy lifestyles",
"Community awareness on eco-friendly transportation",
"Workshop on resilience and crisis preparedness",
"Volunteer support for local environmental NGO",
"Public awareness on sustainable food practices",
"Women mentorship programme in engineering",
"Employee volunteer support for youth mentorship",
"Green innovation forum for local businesses",
"Community awareness on preserving water resources",
"Workshop on ethical workplace behaviour",
"Volunteer support for educational technology donation",
"Industrial environmental sustainability awareness day",
"Employee-led tree planting in urban areas",
"School awareness sessions on environmental health",
"Community support for social inclusion programmes",
"Workshop on sustainable procurement and sourcing",
"Volunteer support for community clean energy fair",
"Public awareness on reducing industrial waste",
"Women career mentoring for students",
"Employee volunteer support for cultural festival",
"Green workplace sustainability training",
"Community awareness on reducing carbon emissions",
"Workshop on collaborative problem-solving",
"Volunteer support for local youth shelters",
"Industrial sustainability reporting awareness session",
"Employee-led environmental volunteering initiative",
"School awareness on responsible recycling",
"Community support for local environmental education",
"Workshop on workplace diversity and inclusion",
"Volunteer support for public health awareness drive",
"Public awareness on eco-conscious living",
"Women empowerment networking and leadership day",
"Employee volunteer support for science education",
"Green office waste reduction campaign",
"Community awareness on renewable energy benefits",
"Workshop on communication and teamwork excellence",
"Volunteer support for local environmental restoration",
"Industrial resource conservation awareness programme",
"Employee-led initiative for sustainable commuting",
"School awareness on responsible energy consumption",
"Community support for climate resilience planning",
"Workshop on positive workplace culture",
"Volunteer support for community literacy outreach",
"Public awareness on environmental stewardship",
"Women leadership development workshop",
"Employee volunteer support for local charities",
"Green innovation awareness and training programme",
"Community awareness on preserving biodiversity",
"Workshop on sustainability in industrial operations",
"Volunteer support for educational mentoring programme",
"Industrial environmental responsibility awareness event",
"Employee-led sustainability ambassador initiative",
"School awareness on reducing environmental impact",
"Community support for eco-friendly urban projects",
"Workshop on employee wellbeing and engagement",
"Volunteer support for public environmental campaign",
"Public awareness on sustainable industrial practices",
"Women mentorship and empowerment conference",
"Employee volunteer support for environmental projects",
"Green culture awareness campaign in workplace",
"Community awareness on sustainable resource management",
"Workshop on innovation and continuous improvement",
"Volunteer support for youth empowerment activities",
"Industrial sustainability and ethics awareness session",
"Employee-led community volunteering programme",
"School awareness on sustainable development goals",
"Community support for renewable energy awareness",
"Workshop on leadership and social responsibility",
"Volunteer support for local green initiatives",
"Public awareness on responsible environmental behaviour",
"Women empowerment through technical education",
"Employee volunteer support for local education programmes",
"Green operations continuous awareness campaign",
"Community awareness on protecting natural habitats",
"Workshop on environmental and social governance",
"Volunteer support for local sustainability projects",
"Industrial environmental innovation awareness event",
"Employee-led social responsibility engagement week",
"School awareness on environmental citizenship",
"Community support for sustainable community development",
"Workshop on teamwork and ethical practices",
"Volunteer support for local environmental sustainability",
"Public awareness on sustainable community living",
]

COLLABORATION = ["PARTNERSHIP", "SPONSORSHIP", "CHARITY_DONATION", "OTHERS"]
PERIODICITY = ["Monthly", "Quarterly", "Annual", "One-time"]
IMPACT_UNITS = ["people", "trees", "hours", "kits", "m²", "t CO₂e avoided"]
ORGANIZERS = ["CSR Team", "HR", "Operations", "QHSE", "Logistics", "Maintenance"]


def _site_year_pairs(sites: list[Site], single_site: Site | None) -> list[tuple[Site, int]]:
    """For each site: (site, Y), (site, Y-1), (site, Y-2), (site, Y-3)."""
    cy = date.today().year
    years = [cy - k for k in range(YEARS_BACK + 1)]
    if single_site:
        return [(single_site, y) for y in years]
    pairs: list[tuple[Site, int]] = []
    for site in sites:
        for y in years:
            pairs.append((site, y))
    return pairs


def _approve_demo_lines(plan_id: str, demo_pattern: str) -> None:
    """VALIDATE demo lines and their realization rows (if any). Validate whole plan only if demo-only."""
    now = datetime.now(UTC)
    plan = CsrPlan.query.filter_by(id=plan_id).first()
    if not plan:
        return

    CsrActivity.query.filter(
        CsrActivity.plan_id == plan_id,
        CsrActivity.activity_number.like(demo_pattern),
    ).update({"status": "VALIDATED"}, synchronize_session=False)
    ids = [
        r[0]
        for r in db.session.query(CsrActivity.id)
        .filter(
            CsrActivity.plan_id == plan_id,
            CsrActivity.activity_number.like(demo_pattern),
        )
        .all()
    ]
    if ids:
        RealizedCsr.query.filter(RealizedCsr.activity_id.in_(ids)).update(
            {"status": "VALIDATED"},
            synchronize_session=False,
        )

    total_lines = CsrActivity.query.filter(CsrActivity.plan_id == plan_id).count()
    demo_lines = CsrActivity.query.filter(
        CsrActivity.plan_id == plan_id,
        CsrActivity.activity_number.like(demo_pattern),
    ).count()
    other_lines = total_lines - demo_lines
    if other_lines == 0:
        plan.status = "VALIDATED"
        plan.validated_at = now
        plan.validation_step = None


def _remove_demo_lines_for_pair(site_id: str, year: int, site_code: str) -> None:
    pattern = f"DEMO10-{site_code}-{year}-%"
    plan = CsrPlan.query.filter_by(site_id=site_id, year=year).first()
    if not plan:
        return
    CsrActivity.query.filter(
        CsrActivity.plan_id == plan.id,
        CsrActivity.activity_number.like(pattern),
    ).delete(synchronize_session=False)


def _ensure_plan(site_id: str, year: int, user_id: str) -> CsrPlan:
    plan = CsrPlan.query.filter_by(site_id=site_id, year=year).first()
    if plan:
        plan.validation_mode = "101"
        plan.allocated_budget = max(float(plan.allocated_budget or 0), 280_000.0)
        plan.total_hc = plan.total_hc or 950
        return plan
    plan = CsrPlan(
        site_id=site_id,
        year=year,
        validation_mode="101",
        status="DRAFT",
        allocated_budget=320_000.0 + (year % 7) * 12_000.0,
        total_hc=880 + (year % 5) * 40,
        created_by=user_id,
    )
    db.session.add(plan)
    db.session.flush()
    return plan


def _partner_for_line(site_code: str, year: int, i: int) -> ExternalPartner:
    name = (
        f"Alliance {site_code} {year}-{i:03d} — "
        f"{['ONG Verte', 'École technique', 'Association locale', 'Fondation Avenir', 'Collectif Quartier'][(i - 1) % 5]}"
    )
    existing = ExternalPartner.query.filter(db.func.lower(ExternalPartner.name) == name.lower()).first()
    if existing:
        return existing
    ep = ExternalPartner(
        name=name,
        type="NGO" if i % 2 == 0 else "ASSOCIATION",
        contact_person=f"Contact partenaire {site_code}-{i}",
        email=f"contact.demo.{site_code}.{year}.{i:03d}@partenaire-demo.org",
        phone=f"+212 5 00 {1000 + i:04d}",
        is_active=True,
    )
    db.session.add(ep)
    db.session.flush()
    return ep


def _title_index(site_code: str, plan_year: int, line_index: int, modulo: int) -> int:
    """Spread catalogue indices across site, plan year, and line (avoids same title every line)."""
    return abs(hash(f"{site_code}|{plan_year}|{line_index}")) % modulo


def _timing_series(
    site_code: str, plan_year: int, line_index: int, window_min_year: int
) -> tuple[str, int, int, str]:
    """Catalogue base title, ``start_year``, ``edition``, and display title.

    ~34% of lines model a **multi-year programme**: same catalogue title
    (``display_title == base``), ``start_year`` when it began, and
    ``edition = plan_year - start_year + 1`` (e.g. start 2024 → edition 2 in 2025,
    edition 3 in 2026).

    Other lines get a **unique display title** (suffix with site, year, line) while
    ``start_year`` / ``edition`` still vary for testing.
    """
    n = len(ACTIVITY_TITLES)
    idx = _title_index(site_code, plan_year, line_index, n)
    base = ACTIVITY_TITLES[idx]
    if abs(hash(f"REC|{site_code}|{line_index}")) % 100 < 34:
        d = 1 + (abs(hash(f"{site_code}|{line_index}|span")) % 3)
        start_year = max(window_min_year, plan_year - d)
        edition = plan_year - start_year + 1
        return base, start_year, edition, base
    flavours = ("", ", phase site", ", volet communauté", ", module QHSE", ", extension")
    fv = flavours[_title_index(site_code, plan_year, line_index, len(flavours))]
    display = f"{base}{fv} — {site_code} {plan_year}-{line_index:02d}"
    start_year = plan_year - (1 if (line_index % 5 == 0) else 0)
    if start_year < window_min_year:
        start_year = window_min_year
    edition = 1 + ((line_index + plan_year * 2) % 4)
    return base, start_year, edition, display


def _objective_texts(i: int, title: str) -> list[str]:
    return [
        (
            f"Réaliser l’action « {title[:52]} » avec validation du responsable site "
            f"et indicateurs de suivi documentés (ligne #{i:03d})."
        ),
        (
            f"Mobiliser au moins {8 + (i % 20)} collaborateurs et mesurer la satisfaction "
            f"à chaud (questionnaire interne)."
        ),
        (
            f"Publier une fiche retour d’expérience et les chiffres d’impact "
            f"(budget, participants, indicateur clé) dans le rapport annuel CSR."
        ),
    ]


def seed_demo_plans(site_code: str | None, rng: random.Random) -> None:
    sites = Site.query.order_by(Site.code).all()
    if not sites:
        raise SystemExit("No site in database")

    single_site: Site | None = None
    if site_code:
        single_site = Site.query.filter_by(code=site_code.strip()).first()
        if not single_site:
            raise SystemExit(f"No site with code {site_code!r}")

    user = User.query.order_by(User.email).first()
    if not user:
        raise SystemExit("No user in database")

    categories = Category.query.order_by(Category.name).all()
    if not categories:
        raise SystemExit("No categories in database")

    cy = date.today().year
    pairs = _site_year_pairs(sites, single_site)

    for site, year in pairs:
        _remove_demo_lines_for_pair(site.id, year, site.code)
    db.session.commit()

    total_plans = 0
    for site, year in pairs:
        total_plans += 1
        is_current_year = year == cy
        n_act = rng.randint(ACTIVITY_COUNT_MIN, ACTIVITY_COUNT_MAX)
        plan = _ensure_plan(site.id, year, user.id)
        demo_pattern = f"DEMO10-{site.code}-{year}-%"
        prefix = f"DEMO10-{site.code}-{year}-"

        off_plan_count = 0
        sparse_planned_count = 0
        window_min_year = cy - YEARS_BACK

        for i in range(1, n_act + 1):
            title_base, start_year, edition, display_title = _timing_series(
                site.code, year, i, window_min_year
            )
            is_multi_year_same_title = display_title == title_base
            site_label = site.name or site.code

            if is_current_year:
                sparse_planned = rng.random() < OFF_PLAN_FRACTION
                if sparse_planned:
                    sparse_planned_count += 1
                title = (
                    f"{display_title} — hors plan initial (déclaration {year})"
                    if sparse_planned
                    else display_title
                )
                number = f"{prefix}{i:03d}"
                cat = categories[_title_index(site.code, year, i, len(categories))]
                planned_budget = 2500.0 + ((i * 317 + year) % 14_000)
                employees_planned = 8 + (i % 18)
                impact_target = 20.0 + ((i * 11 + year % 5) % 160)
                impact_unit = IMPACT_UNITS[_title_index(site.code, year, i, len(IMPACT_UNITS))]
                partner = _partner_for_line(site.code, year, i)
                series_note = (
                    f" Programme pluriannuel (lancement {start_year}, édition {edition} dans le plan {year})."
                    if is_multi_year_same_title and edition > 1
                    else (
                        f" Lancement {start_year}, édition {edition}."
                        if is_multi_year_same_title
                        else ""
                    )
                )

                if sparse_planned:
                    activity = CsrActivity(
                        plan_id=plan.id,
                        category_id=cat.id,
                        external_partner_id=None,
                        nb_of_external_partner=0,
                        activity_number=number,
                        title=title,
                        organization="INTERNAL" if i % 2 == 0 else "EXTERNAL",
                        contract_type="ONE_SHOT" if i % 2 == 0 else "SUCCESSIVE_PERFORMANCE",
                        description=(
                            f"Ligne ajoutée hors enveloppe initiale {year} — site {site_label} ({site.code}). "
                            f"À budgétiser ou déclarer en fin d’exercice ; pas de partenaire figé en amont.{series_note}"
                        ),
                        collaboration_nature=COLLABORATION[(i - 1) % len(COLLABORATION)],
                        periodicity=None,
                        planned_budget=0,
                        action_impact_target=0,
                        action_impact_unit=None,
                        action_impact_duration=None,
                        employees_planned=0,
                        start_year=start_year,
                        edition=edition,
                        organizer=ORGANIZERS[(i - 1) % len(ORGANIZERS)],
                        status="DRAFT",
                        created_by=user.id,
                    )
                else:
                    activity = CsrActivity(
                        plan_id=plan.id,
                        category_id=cat.id,
                        external_partner_id=partner.id,
                        nb_of_external_partner=1,
                        activity_number=number,
                        title=title,
                        organization="INTERNAL" if i % 2 == 0 else "EXTERNAL",
                        contract_type="ONE_SHOT" if i % 2 == 0 else "SUCCESSIVE_PERFORMANCE",
                        description=(
                            f"Ligne plan CSR {year} — {site_label} ({site.code}). "
                            f"Budget indicatif {planned_budget:.0f} €, cible {impact_target:g} {impact_unit}. "
                            f"Pilote: {ORGANIZERS[(i - 1) % len(ORGANIZERS)]}. "
                            f"Aucune réalisation saisie (année en cours).{series_note}"
                        ),
                        collaboration_nature=COLLABORATION[(i - 1) % len(COLLABORATION)],
                        periodicity=PERIODICITY[(i - 1) % len(PERIODICITY)],
                        planned_budget=planned_budget,
                        action_impact_target=impact_target,
                        action_impact_unit=impact_unit,
                        action_impact_duration="6 months" if i % 2 == 0 else "12 months",
                        employees_planned=employees_planned,
                        start_year=start_year,
                        edition=edition,
                        organizer=ORGANIZERS[(i - 1) % len(ORGANIZERS)],
                        status="DRAFT",
                        created_by=user.id,
                    )
                db.session.add(activity)
                db.session.flush()

                obj_texts = _objective_texts(i, title)
                for t in obj_texts:
                    db.session.add(CsrObjective(activity_id=activity.id, objective=t))
                continue

            # Past years: full cycle with realizations (same _timing_series as current year for coherence)
            is_off_plan = rng.random() < OFF_PLAN_FRACTION
            title = f"{display_title} (hors plan)" if is_off_plan else display_title
            number = f"{prefix}{i:03d}"
            cat = categories[_title_index(site.code, year, i, len(categories))]
            planned_budget = 2500.0 + ((i * 317 + year) % 14_000)
            employees_planned = 8 + (i % 18)
            impact_target = 20.0 + ((i * 11 + year % 5) % 160)
            impact_unit = IMPACT_UNITS[_title_index(site.code, year, i, len(IMPACT_UNITS))]
            partner = None if is_off_plan else _partner_for_line(site.code, year, i)
            series_note = (
                f" Programme depuis {start_year}, édition {edition} (plan {year})."
                if is_multi_year_same_title
                else f" Lancement {start_year}, édition {edition}."
            )

            if is_off_plan:
                off_plan_count += 1
                activity = CsrActivity(
                    plan_id=plan.id,
                    category_id=cat.id,
                    external_partner_id=None,
                    nb_of_external_partner=0,
                    activity_number=number,
                    title=title,
                    organization="INTERNAL" if i % 2 == 0 else "EXTERNAL",
                    contract_type="ONE_SHOT" if i % 2 == 0 else "SUCCESSIVE_PERFORMANCE",
                    description=(
                        f"Activité CSR hors plan validée — {site_label} ({site.code}), exercice {year}. "
                        f"Non inscrite au budget annuel initial ; reporting consolidé après coup.{series_note}"
                    ),
                    collaboration_nature=COLLABORATION[(i - 1) % len(COLLABORATION)],
                    periodicity=None,
                    planned_budget=0,
                    action_impact_target=0,
                    action_impact_unit=None,
                    action_impact_duration=None,
                    employees_planned=0,
                    start_year=start_year,
                    edition=edition,
                    organizer=ORGANIZERS[(i - 1) % len(ORGANIZERS)],
                    status="DRAFT",
                    created_by=user.id,
                )
            else:
                activity = CsrActivity(
                    plan_id=plan.id,
                    category_id=cat.id,
                    external_partner_id=partner.id,
                    nb_of_external_partner=1,
                    activity_number=number,
                    title=title,
                    organization="INTERNAL" if i % 2 == 0 else "EXTERNAL",
                    contract_type="ONE_SHOT" if i % 2 == 0 else "SUCCESSIVE_PERFORMANCE",
                    description=(
                        f"Action CSR réalisée {year} — {site_label} ({site.code}). "
                        f"Budget planifié {planned_budget:.0f} €, cible {impact_target:g} {impact_unit}.{series_note}"
                    ),
                    collaboration_nature=COLLABORATION[(i - 1) % len(COLLABORATION)],
                    periodicity=PERIODICITY[(i - 1) % len(PERIODICITY)],
                    planned_budget=planned_budget,
                    action_impact_target=impact_target,
                    action_impact_unit=impact_unit,
                    action_impact_duration="6 months" if i % 2 == 0 else "12 months",
                    employees_planned=employees_planned,
                    start_year=start_year,
                    edition=edition,
                    organizer=ORGANIZERS[(i - 1) % len(ORGANIZERS)],
                    status="DRAFT",
                    created_by=user.id,
                )
            db.session.add(activity)
            db.session.flush()

            if is_off_plan:
                obj_one = (
                    "Objectif annoncé après coup (activité hors plan) — suivi impact et retour parties prenantes."
                )
                db.session.add(CsrObjective(activity_id=activity.id, objective=obj_one))
                db.session.add(
                    CsrCompletedObjective(
                        activity_id=activity.id,
                        objective=obj_one,
                        achieved=True,
                    )
                )
            else:
                obj_texts = _objective_texts(i, title)
                for t in obj_texts:
                    db.session.add(CsrObjective(activity_id=activity.id, objective=t))

                db.session.add(
                    CsrCompletedObjective(
                        activity_id=activity.id,
                        objective=obj_texts[0],
                        achieved=True,
                    )
                )
                db.session.add(
                    CsrCompletedObjective(
                        activity_id=activity.id,
                        objective=obj_texts[1],
                        achieved=True,
                    )
                )
                if i % 4 == 0:
                    db.session.add(
                        CsrCompletedObjective(
                            activity_id=activity.id,
                            objective=obj_texts[2],
                            achieved=False,
                        )
                    )
                else:
                    db.session.add(
                        CsrCompletedObjective(
                            activity_id=activity.id,
                            objective=obj_texts[2],
                            achieved=True,
                        )
                    )

            budget_ratio = 0.82 + ((i % 10) * 0.04)
            if is_off_plan:
                realized_budget = round(3200.0 + ((i * 419 + year) % 18_000), 2)
                participants = max(6, min(16 + (i % 20), 72))
                impact_actual = max(1.0, round(12.0 + ((i * 13) % 150), 2))
            else:
                realized_budget = round(planned_budget * budget_ratio, 2)
                participants = max(4, min(employees_planned + 5 + (i % 7), 78))
                impact_actual = max(1.0, round(float(impact_target) * (0.72 + (i % 7) * 0.035), 2))
            month = ((i + year) % 12) + 1
            day = min(28, ((i * 3) % 25) + 1)
            dept = ORGANIZERS[(i + 2) % len(ORGANIZERS)]

            db.session.add(
                RealizedCsr(
                    activity_id=activity.id,
                    participants=participants,
                    corporate_image_improved=(i % 6 != 0),
                    incidents_number=1 if i % 17 == 0 else 0,
                    contact_department=dept,
                    realized_budget=realized_budget,
                    action_impact_actual=impact_actual,
                    action_impact_unit=impact_unit,
                    is_off_plan=is_off_plan,
                    off_plan_validation_mode=None,
                    off_plan_validation_step=None,
                    realization_date=date(year, month, day),
                    comment=(
                        f"Rapport CSR consolidé {year} ({site.code}){' — hors plan' if is_off_plan else ''}. "
                        f"Participants: {participants}. Budget réalisé: {realized_budget} €."
                    ),
                    contact_name=f"Responsable reporting — {dept}",
                    contact_email=f"reporting.{site.code}.{year}.{i:03d}@demo-plant.example.com",
                    created_by=user.id,
                    status="DRAFT",
                )
            )

        db.session.flush()
        _approve_demo_lines(plan.id, demo_pattern)
        db.session.commit()
        recompute_plan_activity_kpis(plan.id)
        db.session.commit()

        n_rows = (
            CsrActivity.query.filter(
                CsrActivity.plan_id == plan.id,
                CsrActivity.activity_number.like(demo_pattern),
            ).count()
        )
        n_kpi = (
            db.session.query(ActivityKpi.id)
            .join(CsrActivity, CsrActivity.id == ActivityKpi.activity_id)
            .filter(CsrActivity.plan_id == plan.id, CsrActivity.activity_number.like(demo_pattern))
            .count()
        )
        n_real = (
            db.session.query(RealizedCsr.id)
            .join(CsrActivity, CsrActivity.id == RealizedCsr.activity_id)
            .filter(CsrActivity.plan_id == plan.id, CsrActivity.activity_number.like(demo_pattern))
            .count()
        )

        if is_current_year:
            print(
                f"✓ {site.code} / {year} [CURRENT planned-only]: plan_id={plan.id} — {n_rows} activities "
                f"(target {n_act}), sparse planned ~{sparse_planned_count}, "
                f"realizations={n_real}, KPI rows={n_kpi}"
            )
        else:
            print(
                f"✓ {site.code} / {year}: plan_id={plan.id} — {n_rows} activities (target {n_act}), "
                f"off-plan reports={off_plan_count}, realizations={n_real}, KPI rows={n_kpi}"
            )

    print(f"— Seeded {total_plans} plan(s) ({len(pairs) // max(1, YEARS_BACK + 1)} site(s) × {YEARS_BACK + 1} years).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed 4 plans per site (current + 3 past years): current=planned only; past=reports + ~10% off-plan."
    )
    parser.add_argument(
        "--site-code",
        default=None,
        help="Only this site (still 4 plans: Y..Y-3).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed (activity counts 10–20, off-plan / sparse picks).",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)

    app = create_app()
    with app.app_context():
        seed_demo_plans(args.site_code, rng)
    print("Done.")


if __name__ == "__main__":
    main()
