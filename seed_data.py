"""
Seed Harbor with realistic demo data.

Run with:  python manage.py shell < seed_data.py

Creates a rich mid-stream demo environment where every role has
realistic in-progress activity visible on their dashboard.
"""
import os
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'harbor.settings')
django.setup()

from django.utils import timezone

from allauth.account.models import EmailAddress
from core.models import Agency, AuditLog, Notification, Organization, User
from grants.models import (
    FederalOpportunity,
    FundingSource,
    GrantProgram,
    OpportunityCollaborator,
    TrackedOpportunity,
)
from applications.models import (
    Application,
    ApplicationComment,
    ApplicationComplianceItem,
    ApplicationSection,
    ApplicationStatusHistory,
)
from reviews.models import (
    ReviewAssignment,
    ReviewRubric,
    ReviewScore,
    ReviewSummary,
    RubricCriterion,
)
from awards.models import Award, AwardAmendment, PerformanceMetric, SubRecipient
from financial.models import (
    Budget,
    BudgetLineItem,
    CoreCTAccountString,
    DrawdownRequest,
    Transaction,
)
from reporting.models import Report, ReportTemplate, SF425Report
from closeout.models import Closeout, CloseoutChecklist, FundReturn

now = timezone.now()

# ── Clean up stale data from prior runs ──────────────────────
print("Cleaning stale data from prior seed runs...")
# Remove duplicate ReviewAssignments (old script created without rubric filter)
from django.db.models import Count
dupes = (
    ReviewAssignment.objects.values('application', 'reviewer')
    .annotate(cnt=Count('id'))
    .filter(cnt__gt=1)
)
for d in dupes:
    extras = ReviewAssignment.objects.filter(
        application_id=d['application'], reviewer_id=d['reviewer'],
    ).order_by('assigned_at')[1:]  # keep the first, delete the rest
    for extra in extras:
        extra.scores.all().delete()
        extra.delete()
print(f"  Cleaned {len(dupes)} duplicate review assignment groups.")

# ── Agencies ─────────────────────────────────────────────────
print("Creating agencies...")
agencies_data = [
    ("Department of Commerce and Development", "DCD",
     "Fosters economic growth through business development, tourism, arts, and community investment.",
     "10500", "12060", "11000"),
    ("Office of Budget and Management", "OBM",
     "Provides budget, policy, and planning services to the Governor and state agencies.",
     "10100", "12001", "11001"),
    ("Department of Housing", "DOH",
     "Provides leadership and policy direction for affordable housing in the state.",
     "13500", "12070", "11003"),
    ("Department of Energy and Environmental Protection", "DEEP",
     "Protects and improves the state's environment and natural resources.",
     "22000", "12090", "11004"),
    ("State Office of the Arts", "SOA",
     "Supports arts organizations and individual artists through grants and services.",
     "10500", "12060", "11005"),
]

agencies = {}
for name, abbr, desc, dept, fund, prog in agencies_data:
    a, _ = Agency.objects.get_or_create(
        abbreviation=abbr,
        defaults=dict(
            name=name, description=desc,
            department_code=dept, fund_code=fund, program_code=prog,
            contact_name=f"{abbr} Grants Office",
            contact_email=f"grants@{abbr.lower()}.dok.gov",
            contact_phone="(860) 500-2300",
            is_active=True, onboarded_at=now,
        ),
    )
    agencies[abbr] = a

# ── Organizations (applicants) ───────────────────────────────
print("Creating organizations...")
orgs_data = [
    ("City of Capital", "municipality", "06103"),
    ("Town of Greenwich", "municipality", "06830"),
    ("Town of Stamford", "municipality", "06901"),
    ("State Children's Museum", "nonprofit", "06106"),
    ("Riverside Arts Council", "nonprofit", "06510"),
    ("Capital Stage Company", "nonprofit", "06103"),
    ("Bridgeport Neighborhood Trust", "nonprofit", "06604"),
    ("Innovation Labs LLC", "business", "06851"),
    ("Eastern Manufacturing Alliance", "business", "06320"),
    ("Mashantucket Pequot Tribal Nation", "tribal", "06338"),
    ("State University Foundation", "educational", "06269"),
    ("Goodwin University", "educational", "06118"),
]

orgs = {}
for name, otype, zipcode in orgs_data:
    o, _ = Organization.objects.get_or_create(
        name=name,
        defaults=dict(
            org_type=otype, state='CT', zip_code=zipcode,
            city=name.split(" of ")[-1].split(" ")[0] if " of " in name else "Capital City",
            sam_registered=True,
            sam_expiration=date.today() + timedelta(days=365),
            is_active=True,
        ),
    )
    orgs[name] = o

# ── Users (one per role, password: demo2026) ─────────────────
print("Creating users...")

def make_user(username, first, last, role, email, agency=None, org=None, is_staff=False):
    u, created = User.objects.get_or_create(
        username=username,
        defaults=dict(
            first_name=first, last_name=last, role=role,
            email=email, agency=agency, organization=org,
            is_staff=is_staff, is_state_user=agency is not None,
            accepted_terms=True, accepted_terms_at=now,
        ),
    )
    if created:
        u.set_password('demo2026')
        u.save()
    # Ensure allauth EmailAddress record exists
    if email:
        EmailAddress.objects.get_or_create(
            user=u, email=email,
            defaults={'verified': True, 'primary': True},
        )
    return u

# System Admin (also the Django superuser)
admin_user = User.objects.filter(username='admin').first()
if admin_user:
    admin_user.agency = agencies['DCD']
    admin_user.role = 'system_admin'
    admin_user.first_name = 'System'
    admin_user.last_name = 'Administrator'
    admin_user.save()
    if admin_user.email:
        EmailAddress.objects.get_or_create(
            user=admin_user, email=admin_user.email,
            defaults={'verified': True, 'primary': True},
        )

# Agency staff — one per role
sarah = make_user('agency.admin', 'Agency', 'Administrator', 'agency_admin', 'agency.admin@dok.gov', agencies['DCD'])
mike = make_user('program.officer', 'Program', 'Officer', 'program_officer', 'program.officer@dok.gov', agencies['DCD'])
lisa = make_user('fiscal.officer', 'Fiscal', 'Officer', 'fiscal_officer', 'fiscal.officer@dok.gov', agencies['DCD'])

# Reviewer
rev1 = make_user('reviewer', 'Grant', 'Reviewer', 'reviewer', 'reviewer@dok.gov')

# Primary Applicant (City of Capital)
app1 = make_user('applicant', 'Grant', 'Applicant', 'applicant', 'applicant@capitalcity.gov', org=orgs['City of Capital'])

# Auditor
auditor = make_user('auditor', 'System', 'Auditor', 'auditor', 'auditor@dok.gov', agencies['OBM'])

# Federal Fund Coordinator (manages the state's federal funding pipeline)
fed_coord = make_user(
    'fed.coordinator', 'Federal', 'Coordinator', 'federal_coordinator',
    'fed.coordinator@dok.gov', agencies['OBM'],
)

# ── Additional applicant users (for multi-org variety) ────────
print("Creating additional applicant users...")
app_greenwich = make_user(
    'maria.santos', 'Maria', 'Santos', 'applicant',
    'maria.santos@greenwich.gov', org=orgs['Town of Greenwich'],
)
app_arts = make_user(
    'james.chen', 'James', 'Chen', 'applicant',
    'james.chen@riversidearts.org', org=orgs['Riverside Arts Council'],
)
app_uconn = make_user(
    'priya.patel', 'Priya', 'Patel', 'applicant',
    'priya.patel@stateuniv.edu', org=orgs['State University Foundation'],
)
app_bridgeport = make_user(
    'derek.williams', 'Derek', 'Williams', 'applicant',
    'derek.williams@bpt-trust.org', org=orgs['Bridgeport Neighborhood Trust'],
)
app_ctinno = make_user(
    'rachel.kim', 'Rachel', 'Kim', 'applicant',
    'rachel.kim@innovation.com', org=orgs['Innovation Labs LLC'],
)

# ── Funding Sources ──────────────────────────────────────────
print("Creating funding sources...")
fs_data = [
    ("Community Development Block Grant (CDBG)", "federal", "14.218", "HUD"),
    ("State Bond Fund - Economic Development", "state", "", ""),
    ("National Endowment for the Arts", "federal", "45.024", "NEA"),
    ("State General Fund Appropriation", "state", "", ""),
    ("EPA Brownfields Program", "federal", "66.818", "EPA"),
]

fund_sources = {}
for name, stype, cfda, agency_name in fs_data:
    fs, _ = FundingSource.objects.get_or_create(
        name=name,
        defaults=dict(
            source_type=stype, cfda_number=cfda,
            federal_agency=agency_name,
            description=f"{name} funding for state programs.",
        ),
    )
    fund_sources[name] = fs

# ── Grant Programs ───────────────────────────────────────────
print("Creating grant programs...")
programs_data = [
    {
        "title": "Small Business Innovation Grant Program",
        "desc": "Provides funding to small businesses for innovative projects that drive economic growth, create jobs, and foster technological advancement. Eligible projects include product development, process innovation, and technology commercialization.",
        "agency": "DCD", "type": "competitive",
        "funding": 2500000, "min": 25000, "max": 250000,
        "fy": "2025-2026", "months": 12,
        "deadline_days": 45, "status": "accepting_applications",
        "fs": "State Bond Fund - Economic Development",
        "match": True, "match_pct": 25,
    },
    {
        "title": "Community Arts & Culture Grants",
        "desc": "Supports arts organizations in delivering programming that engages communities, advances arts education, and celebrates cultural diversity across the state.",
        "agency": "SOA", "type": "competitive",
        "funding": 1000000, "min": 5000, "max": 75000,
        "fy": "2025-2026", "months": 12,
        "deadline_days": 30, "status": "accepting_applications",
        "fs": "National Endowment for the Arts",
        "match": True, "match_pct": 50,
    },
    {
        "title": "Municipal Infrastructure Resilience Program",
        "desc": "Assists municipalities in upgrading critical infrastructure to withstand climate-related impacts including flooding, extreme heat, and severe weather events.",
        "agency": "DEEP", "type": "formula",
        "funding": 10000000, "min": 100000, "max": 2000000,
        "fy": "2025-2026", "months": 24,
        "deadline_days": 60, "status": "accepting_applications",
        "fs": "EPA Brownfields Program",
        "match": True, "match_pct": 20,
    },
    {
        "title": "Affordable Housing Development Fund",
        "desc": "Supports the development and preservation of affordable housing units across the state through construction, rehabilitation, and adaptive reuse projects.",
        "agency": "DOH", "type": "competitive",
        "funding": 15000000, "min": 500000, "max": 3000000,
        "fy": "2025-2026", "months": 36,
        "deadline_days": 90, "status": "posted",
        "fs": "Community Development Block Grant (CDBG)",
        "match": True, "match_pct": 10,
    },
    {
        "title": "Workforce Development Initiative",
        "desc": "Funds innovative job training programs that prepare state residents for in-demand careers in advanced manufacturing, healthcare, technology, and clean energy sectors.",
        "agency": "DCD", "type": "competitive",
        "funding": 5000000, "min": 50000, "max": 500000,
        "fy": "2024-2025", "months": 18,
        "deadline_days": -30, "status": "under_review",
        "fs": "State General Fund Appropriation",
        "match": False, "match_pct": 0,
    },
    {
        "title": "Neighborhood Revitalization Grant",
        "desc": "Provides catalytic funding for neighborhood-level projects that improve quality of life, strengthen community bonds, and address blight in urban centers.",
        "agency": "DCD", "type": "competitive",
        "funding": 3000000, "min": 25000, "max": 300000,
        "fy": "2024-2025", "months": 12,
        "deadline_days": -90, "status": "awards_pending",
        "fs": "State Bond Fund - Economic Development",
        "match": True, "match_pct": 15,
    },
]

programs = {}
for p in programs_data:
    deadline = now + timedelta(days=p["deadline_days"])
    posting = deadline - timedelta(days=60)
    gp, _ = GrantProgram.objects.get_or_create(
        title=p["title"],
        defaults=dict(
            description=p["desc"],
            agency=agencies[p["agency"]],
            funding_source=fund_sources[p["fs"]],
            created_by=sarah,
            grant_type=p["type"],
            total_funding=Decimal(str(p["funding"])),
            min_award=Decimal(str(p["min"])),
            max_award=Decimal(str(p["max"])),
            fiscal_year=p["fy"],
            duration_months=p["months"],
            application_deadline=deadline,
            posting_date=posting,
            status=p["status"],
            match_required=p["match"],
            match_percentage=Decimal(str(p["match_pct"])) if p["match"] else None,
            is_published=True,
            published_at=posting,
            eligibility_criteria="Open to eligible state entities including municipalities, nonprofits, businesses, and educational institutions.",
            contact_name="DCD Grants Office",
            contact_email="grants@dcd.dok.gov",
            contact_phone="(860) 500-2300",
        ),
    )
    programs[p["title"]] = gp

# ── Applications ─────────────────────────────────────────────
print("Creating applications...")
apps_data = [
    # ── Workforce Development Initiative (under review) ──
    # Capital City applicant apps
    {
        "program": "Workforce Development Initiative",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Capital City Advanced Manufacturing Pipeline",
        "desc": "Training 200 Capital City residents in CNC machining, robotics, and quality control to fill critical manufacturing workforce gaps in the greater Capital City region.",
        "amount": 450000, "status": "submitted",
        "start": 60, "end": 60 + 540,
    },
    {
        "program": "Workforce Development Initiative",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Tech Talent Accelerator",
        "desc": "Intensive 16-week coding bootcamp and placement program targeting underemployed adults in Norwalk and Stamford, focusing on cloud computing and cybersecurity skills.",
        "amount": 275000, "status": "under_review",
        "start": 60, "end": 60 + 540,
    },
    {
        "program": "Workforce Development Initiative",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Bridgeport Green Jobs Corps",
        "desc": "Training 150 Bridgeport residents in solar installation, energy auditing, and weatherization to support the state's clean energy transition.",
        "amount": 380000, "status": "submitted",
        "start": 60, "end": 60 + 540,
    },
    # State University applicant app for Workforce
    {
        "program": "Workforce Development Initiative",
        "user": app_uconn, "org": orgs["State University Foundation"],
        "title": "Healthcare Workforce Expansion Program",
        "desc": "Accelerated nursing and allied health certification program to address critical staffing shortages in state hospitals and long-term care facilities.",
        "amount": 420000, "status": "submitted",
        "start": 60, "end": 60 + 540,
    },
    # Bridgeport Trust app for Workforce
    {
        "program": "Workforce Development Initiative",
        "user": app_bridgeport, "org": orgs["Bridgeport Neighborhood Trust"],
        "title": "Bridgeport Youth Trades Academy",
        "desc": "Pre-apprenticeship program for 100 young adults ages 18-24 in electrical, plumbing, and HVAC trades, with direct pathways to union apprenticeships.",
        "amount": 350000, "status": "submitted",
        "start": 60, "end": 60 + 540,
    },

    # ── Neighborhood Revitalization Grant (awards pending) ──
    {
        "program": "Neighborhood Revitalization Grant",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Frog Hollow Neighborhood Transformation",
        "desc": "Comprehensive neighborhood improvement including streetscape upgrades, community garden installation, facade improvements, and small business incubator space.",
        "amount": 275000, "status": "approved",
        "start": 30, "end": 30 + 365,
    },
    {
        "program": "Neighborhood Revitalization Grant",
        "user": app1, "org": orgs["City of Capital"],
        "title": "East End Community Hub",
        "desc": "Conversion of vacant school building into mixed-use community center with youth programming, workforce training, and community health services.",
        "amount": 300000, "status": "approved",
        "start": 30, "end": 30 + 365,
    },
    {
        "program": "Neighborhood Revitalization Grant",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Westville Creative District",
        "desc": "Arts-driven neighborhood revitalization creating public murals, artist workspaces, and a monthly cultural market in the Westville neighborhood.",
        "amount": 125000, "status": "denied",
        "start": 30, "end": 30 + 365,
    },
    # Bridgeport Trust Neighborhood app
    {
        "program": "Neighborhood Revitalization Grant",
        "user": app_bridgeport, "org": orgs["Bridgeport Neighborhood Trust"],
        "title": "East Bridgeport Greenway Corridor",
        "desc": "Converting abandoned rail corridor into a 2.5-mile linear park with community gardens, fitness stations, and pedestrian/cycling paths connecting neighborhoods.",
        "amount": 285000, "status": "approved",
        "start": 30, "end": 30 + 365,
    },

    # ── Small Business Innovation (accepting applications) ──
    {
        "program": "Small Business Innovation Grant Program",
        "user": app1, "org": orgs["City of Capital"],
        "title": "AI-Powered Quality Inspection System",
        "desc": "Development of computer vision platform for automated quality inspection in aerospace manufacturing, reducing defect rates and inspection costs.",
        "amount": 200000, "status": "submitted",
        "start": 90, "end": 90 + 365,
    },
    {
        "program": "Small Business Innovation Grant Program",
        "user": app_ctinno, "org": orgs["Innovation Labs LLC"],
        "title": "IoT-Enabled Smart Grid Monitor",
        "desc": "Developing low-cost IoT sensor network for real-time monitoring of municipal power grid infrastructure, enabling predictive maintenance and reducing outages.",
        "amount": 175000, "status": "submitted",
        "start": 90, "end": 90 + 365,
    },
    {
        "program": "Small Business Innovation Grant Program",
        "user": app_ctinno, "org": orgs["Innovation Labs LLC"],
        "title": "Biotech Cold Chain Tracking Platform",
        "desc": "Cloud-based temperature monitoring and compliance platform for pharmaceutical and biotech supply chains using blockchain-verified sensor data.",
        "amount": 225000, "status": "draft",
        "start": 90, "end": 90 + 365,
    },

    # ── Community Arts & Culture ──
    {
        "program": "Community Arts & Culture Grants",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Community Theater Outreach Program",
        "desc": "Expanding access to professional theater through free student matinees, community workshops, and a new outdoor summer series in Bushnell Park.",
        "amount": 65000, "status": "draft",
        "start": 90, "end": 90 + 365,
    },
    {
        "program": "Community Arts & Culture Grants",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Riverside Mural Festival 2026",
        "desc": "Commissioning 15 large-scale murals by local and regional artists celebrating Riverside's diverse cultural heritage and community stories.",
        "amount": 50000, "status": "submitted",
        "start": 90, "end": 90 + 365,
    },
    {
        "program": "Community Arts & Culture Grants",
        "user": app_arts, "org": orgs["Riverside Arts Council"],
        "title": "Elm City Jazz & Heritage Festival",
        "desc": "Three-day outdoor jazz festival featuring local musicians, youth workshops, and cultural exhibits celebrating the city's rich musical heritage.",
        "amount": 45000, "status": "submitted",
        "start": 90, "end": 90 + 365,
    },
    {
        "program": "Community Arts & Culture Grants",
        "user": app_arts, "org": orgs["Riverside Arts Council"],
        "title": "Digital Arts Youth Academy",
        "desc": "After-school program teaching digital art, animation, and graphic design to underserved youth in Riverside public schools.",
        "amount": 35000, "status": "draft",
        "start": 90, "end": 90 + 365,
    },

    # ── Municipal Infrastructure ──
    {
        "program": "Municipal Infrastructure Resilience Program",
        "user": app1, "org": orgs["City of Capital"],
        "title": "Park River Flood Mitigation Phase II",
        "desc": "Green infrastructure installation along Park River corridor including bioswales, permeable pavements, and expanded detention basins.",
        "amount": 1500000, "status": "draft",
        "start": 120, "end": 120 + 730,
    },
    {
        "program": "Municipal Infrastructure Resilience Program",
        "user": app_greenwich, "org": orgs["Town of Greenwich"],
        "title": "Coastal Storm Surge Barrier System",
        "desc": "Installation of deployable flood barriers and upgraded stormwater systems protecting Greenwich Harbor commercial district from increasing coastal flooding events.",
        "amount": 1800000, "status": "submitted",
        "start": 120, "end": 120 + 730,
    },
]

applications = {}
for ad in apps_data:
    start = date.today() + timedelta(days=ad["start"])
    end = date.today() + timedelta(days=ad["end"])
    submitted_at = now - timedelta(days=abs(ad["start"])) if ad["status"] != "draft" else None

    a, created = Application.objects.get_or_create(
        project_title=ad["title"],
        defaults=dict(
            grant_program=programs[ad["program"]],
            applicant=ad["user"],
            organization=ad["org"],
            project_description=ad["desc"],
            requested_amount=Decimal(str(ad["amount"])),
            proposed_start_date=start,
            proposed_end_date=end,
            status=ad["status"],
            submitted_at=submitted_at,
        ),
    )
    applications[ad["title"]] = a

    # Add sections
    if created:
        for i, (sec_name, content) in enumerate([
            ("Project Narrative", {"summary": ad["desc"], "goals": "Detailed goals and objectives for this project."}),
            ("Budget Justification", {"narrative": "Detailed budget breakdown and justification for the proposed project expenses."}),
            ("Organizational Capacity", {"history": "Organization background, relevant experience, and demonstrated capacity to execute this project."}),
        ]):
            ApplicationSection.objects.create(
                application=a, section_name=sec_name, section_order=i,
                content=content, is_complete=ad["status"] != "draft",
            )

# ── Compliance Items for submitted apps ──────────────────────
print("Creating compliance items...")
for app_title, app_obj in applications.items():
    if app_obj.status in ('submitted', 'under_review', 'approved'):
        for item_type, label, verified in [
            ('sam_registration', 'SAM Registration Verified', True),
            ('eligibility_confirmed', 'Eligibility Requirements Met', True),
            ('budget_review', 'Budget Review Complete', app_obj.status in ('under_review', 'approved')),
            ('narrative_review', 'Narrative Review Complete', app_obj.status in ('under_review', 'approved')),
            ('conflict_of_interest', 'Conflict of Interest Check', app_obj.status == 'approved'),
        ]:
            ApplicationComplianceItem.objects.get_or_create(
                application=app_obj, item_type=item_type,
                defaults=dict(
                    label=label,
                    is_verified=verified,
                    verified_by=mike if verified else None,
                    verified_at=now - timedelta(days=10) if verified else None,
                    is_required=True,
                ),
            )

# ── Review Rubrics & Assignments ─────────────────────────────
print("Creating review rubrics and scores...")

# Rubric for Workforce Development
rubric_wf, _ = ReviewRubric.objects.get_or_create(
    name="Standard Competitive Review",
    grant_program=programs["Workforce Development Initiative"],
    defaults=dict(created_by=sarah, is_active=True),
)

criteria_data = [
    ("Project Design & Methodology", "Quality and feasibility of the proposed approach.", 25, 1),
    ("Organizational Capacity", "Demonstrated ability to successfully execute the project.", 20, 2),
    ("Budget Reasonableness", "Appropriateness and justification of the proposed budget.", 20, 3),
    ("Impact & Outcomes", "Expected measurable outcomes and community impact.", 25, 4),
    ("Sustainability", "Plan for sustaining project outcomes beyond the grant period.", 10, 5),
]

criteria = {}
for cname, cdesc, max_score, order in criteria_data:
    c, _ = RubricCriterion.objects.get_or_create(
        rubric=rubric_wf, name=cname,
        defaults=dict(description=cdesc, max_score=max_score, weight=Decimal('1.0'), order=order),
    )
    criteria[cname] = c

# Rubric for Small Business Innovation
rubric_sbi, _ = ReviewRubric.objects.get_or_create(
    name="Innovation & Impact Review",
    grant_program=programs["Small Business Innovation Grant Program"],
    defaults=dict(created_by=sarah, is_active=True),
)
sbi_criteria_data = [
    ("Innovation & Novelty", "Degree of innovation and technological advancement.", 30, 1),
    ("Market Viability", "Market analysis, commercialization plan, and economic impact.", 25, 2),
    ("Technical Feasibility", "Technical approach, timeline, and resource plan.", 20, 3),
    ("Job Creation & Economic Impact", "Projected job creation and economic multiplier effect.", 15, 4),
    ("Management Team", "Qualifications and track record of the project team.", 10, 5),
]
sbi_criteria = {}
for cname, cdesc, max_score, order in sbi_criteria_data:
    c, _ = RubricCriterion.objects.get_or_create(
        rubric=rubric_sbi, name=cname,
        defaults=dict(description=cdesc, max_score=max_score, weight=Decimal('1.0'), order=order),
    )
    sbi_criteria[cname] = c

# ── Completed reviews for Capital City Workforce apps ──
for app_title, scores_list, avg, rec, risk in [
    ("Capital City Advanced Manufacturing Pipeline", [22, 18, 17, 23, 8], '86.5', 'fund', 'low'),
    ("Tech Talent Accelerator", [20, 16, 18, 21, 7], '81.2', 'fund_with_conditions', 'medium'),
    ("Bridgeport Green Jobs Corps", [21, 17, 19, 22, 9], '84.0', 'fund', 'low'),
]:
    app_obj = applications[app_title]
    ra, created = ReviewAssignment.objects.get_or_create(
        application=app_obj, reviewer=rev1, rubric=rubric_wf,
        defaults=dict(status='completed', completed_at=now - timedelta(days=5)),
    )
    if created:
        for (cname, _cdesc, _ms, _o), score in zip(criteria_data, scores_list):
            ReviewScore.objects.create(
                assignment=ra, criterion=criteria[cname], score=score,
                comment=f"Strong showing in {cname.lower()}. Score: {score}/{_ms}.",
            )

    ReviewSummary.objects.get_or_create(
        application=app_obj,
        defaults=dict(
            average_score=Decimal(avg),
            total_reviews=1,
            recommendation=rec,
            risk_level=risk,
        ),
    )

# ── PENDING reviews for reviewer (new apps needing scoring) ──
print("Creating pending review assignments for reviewer...")
# Healthcare Workforce — assigned but not started
ra_healthcare, created = ReviewAssignment.objects.get_or_create(
    application=applications["Healthcare Workforce Expansion Program"],
    reviewer=rev1, rubric=rubric_wf,
    defaults=dict(status='assigned'),
)

# Bridgeport Youth Trades — in progress (partially scored)
ra_trades, created = ReviewAssignment.objects.get_or_create(
    application=applications["Bridgeport Youth Trades Academy"],
    reviewer=rev1, rubric=rubric_wf,
    defaults=dict(status='in_progress'),
)
if created:
    # Score only the first 2 criteria (reviewer is mid-stream)
    for (cname, _cdesc, _ms, _o), score in zip(criteria_data[:2], [23, 19]):
        ReviewScore.objects.create(
            assignment=ra_trades, criterion=criteria[cname], score=score,
            comment=f"Excellent community partnerships. Score: {score}/{_ms}.",
        )

# AI Quality Inspection — assigned for SBI rubric
ra_ai, created = ReviewAssignment.objects.get_or_create(
    application=applications["AI-Powered Quality Inspection System"],
    reviewer=rev1, rubric=rubric_sbi,
    defaults=dict(status='assigned'),
)

# IoT Smart Grid — assigned for SBI rubric
ra_iot, created = ReviewAssignment.objects.get_or_create(
    application=applications["IoT-Enabled Smart Grid Monitor"],
    reviewer=rev1, rubric=rubric_sbi,
    defaults=dict(status='assigned'),
)

# ── Awards ───────────────────────────────────────────────────
print("Creating awards...")
awards_data = [
    {
        "app": "Frog Hollow Neighborhood Transformation",
        "number": "DCD-NR-2025-001",
        "amount": 250000,
        "status": "active",
        "start_days": -180, "end_days": 185,
    },
    {
        "app": "East End Community Hub",
        "number": "DCD-NR-2025-002",
        "amount": 280000,
        "status": "active",
        "start_days": -150, "end_days": 215,
    },
    {
        "app": "East Bridgeport Greenway Corridor",
        "number": "DCD-NR-2025-003",
        "amount": 260000,
        "status": "active",
        "start_days": -120, "end_days": 245,
    },
]

awards = {}
for aw in awards_data:
    app_obj = applications[aw["app"]]
    a, _ = Award.objects.get_or_create(
        award_number=aw["number"],
        defaults=dict(
            title=app_obj.project_title,
            application=app_obj,
            grant_program=app_obj.grant_program,
            agency=app_obj.grant_program.agency,
            recipient=app_obj.applicant,
            organization=app_obj.organization,
            award_amount=Decimal(str(aw["amount"])),
            status=aw["status"],
            award_date=date.today() + timedelta(days=aw["start_days"]),
            start_date=date.today() + timedelta(days=aw["start_days"]),
            end_date=date.today() + timedelta(days=aw["end_days"]),
            approved_by=sarah,
            approved_at=now + timedelta(days=aw["start_days"]),
            executed_at=now + timedelta(days=aw["start_days"] + 7),
            terms_and_conditions="Standard state grant terms and conditions apply. Grantee must comply with all applicable state and federal regulations.",
            special_conditions="Quarterly progress reports required. Match documentation due with each drawdown request.",
            requires_match=True,
            match_amount=Decimal(str(int(aw["amount"] * 0.15))),
        ),
    )
    awards[aw["number"]] = a

# ── Performance Metrics (for active awards) ──────────────────
print("Creating performance metrics...")
# Frog Hollow metrics
award1 = awards["DCD-NR-2025-001"]
for name, desc, mtype, target, actual, unit, period in [
    ("Storefronts Improved", "Number of commercial facades renovated", "output", 12, 7, "storefronts", "Q1-Q2 2025"),
    ("Jobs Created", "New permanent jobs from incubator tenants", "outcome", 25, 11, "jobs", "Q1-Q2 2025"),
    ("Community Garden Plots", "Raised bed garden plots installed", "output", 40, 40, "plots", "Q1 2025"),
    ("Resident Engagement", "Unique residents participating in programs", "outcome", 500, 285, "people", "Q1-Q2 2025"),
    ("Cost per Storefront", "Average renovation cost per storefront", "efficiency", 18000, 17200, "dollars", "Q1-Q2 2025"),
]:
    PerformanceMetric.objects.get_or_create(
        award=award1, name=name,
        defaults=dict(
            description=desc, metric_type=mtype,
            target_value=Decimal(str(target)),
            actual_value=Decimal(str(actual)) if actual else None,
            unit_of_measure=unit, reporting_period=period,
        ),
    )

# East End Community Hub metrics
award2 = awards["DCD-NR-2025-002"]
for name, desc, mtype, target, actual, unit, period in [
    ("Building Square Footage Renovated", "Total sq ft of school building converted", "output", 15000, 8500, "sq ft", "Q1-Q2 2025"),
    ("Youth Program Enrollment", "Youth enrolled in after-school programs", "outcome", 150, 62, "youth", "Q1 2025"),
    ("Workforce Training Completions", "Adults completing workforce training modules", "outcome", 100, 28, "adults", "Q1 2025"),
    ("Community Events Hosted", "Events held in the new community space", "output", 24, 8, "events", "Q1-Q2 2025"),
]:
    PerformanceMetric.objects.get_or_create(
        award=award2, name=name,
        defaults=dict(
            description=desc, metric_type=mtype,
            target_value=Decimal(str(target)),
            actual_value=Decimal(str(actual)) if actual else None,
            unit_of_measure=unit, reporting_period=period,
        ),
    )

# Bridgeport Greenway metrics
award3 = awards["DCD-NR-2025-003"]
for name, desc, mtype, target, actual, unit, period in [
    ("Trail Miles Completed", "Linear miles of greenway trail constructed", "output", Decimal('2.5'), Decimal('0.8'), "miles", "Q1 2025"),
    ("Garden Plots Installed", "Community garden plots along corridor", "output", 30, 10, "plots", "Q1 2025"),
    ("Weekly Trail Users", "Average weekly pedestrian and cyclist count", "outcome", 500, None, "users", ""),
]:
    PerformanceMetric.objects.get_or_create(
        award=award3, name=name,
        defaults=dict(
            description=desc, metric_type=mtype,
            target_value=Decimal(str(target)),
            actual_value=Decimal(str(actual)) if actual else None,
            unit_of_measure=unit, reporting_period=period,
        ),
    )

# ── Sub-Recipients ───────────────────────────────────────────
print("Creating sub-recipients...")
SubRecipient.objects.get_or_create(
    award=award1, organization=orgs["Capital Stage Company"],
    defaults=dict(
        contact_name="Patricia Morrison",
        contact_email="p.morrison@capitalstage.org",
        contact_phone="(860) 525-5601",
        sub_award_amount=Decimal('35000'),
        start_date=award1.start_date,
        end_date=award1.end_date,
        scope_of_work="Manage cultural programming for the Frog Hollow community space including monthly events, youth workshops, and seasonal performances.",
        status='active', risk_level='low',
        monitoring_notes="On track. Q1 report received and satisfactory.",
    ),
)
SubRecipient.objects.get_or_create(
    award=award2, organization=orgs["Goodwin University"],
    defaults=dict(
        contact_name="Dr. Robert Tan",
        contact_email="r.tan@goodwin.edu",
        contact_phone="(860) 727-6900",
        sub_award_amount=Decimal('45000'),
        start_date=award2.start_date,
        end_date=award2.end_date,
        scope_of_work="Deliver workforce training modules in healthcare, IT, and advanced manufacturing at the East End Community Hub.",
        status='active', risk_level='low',
    ),
)

# ── State ERP Account Strings ──────────────────────────────────
print("Creating State ERP account strings...")
CoreCTAccountString.objects.get_or_create(
    award=award1,
    defaults=dict(
        fund='12060', department='10500', sid='11000',
        program='11000', account='52591',
        budget_ref_year='2025', project='DCD-NR-001',
    ),
)
CoreCTAccountString.objects.get_or_create(
    award=award2,
    defaults=dict(
        fund='12060', department='10500', sid='11000',
        program='11000', account='52592',
        budget_ref_year='2025', project='DCD-NR-002',
    ),
)

# ── Budgets & Line Items ─────────────────────────────────────
print("Creating budgets...")
for award_num, award_obj in awards.items():
    budget, created = Budget.objects.get_or_create(
        award=award_obj, fiscal_year=2025,
        defaults=dict(
            total_amount=award_obj.award_amount,
            status='approved',
            approved_by=lisa,
            approved_at=now - timedelta(days=160),
            submitted_at=now - timedelta(days=170),
        ),
    )
    if created:
        line_items = [
            ("personnel", "Project Manager (1 FTE)", Decimal('85000')),
            ("personnel", "Program Coordinator (0.5 FTE)", Decimal('32500')),
            ("fringe", "Benefits @ 30%", Decimal('35250')),
            ("supplies", "Program materials and supplies", Decimal('15000')),
            ("contractual", "Evaluation consultant", Decimal('25000')),
            ("travel", "Local travel and site visits", Decimal('5000')),
            ("other", "Community outreach and events", Decimal('12250')),
            ("indirect", "Indirect costs @ 10%", Decimal(str(award_obj.award_amount - Decimal('210000')))),
        ]
        for cat, desc, amt in line_items:
            if amt > 0:
                BudgetLineItem.objects.create(
                    budget=budget, category=cat,
                    description=desc, amount=amt,
                )

# ── Drawdown Requests ────────────────────────────────────────
print("Creating drawdown requests...")

# Award 1 (Frog Hollow) — well into draw cycle
award1_drawdowns = [
    ("DR-DCD-NR-2025-001-0001", 62500, "paid", -120, -110),
    ("DR-DCD-NR-2025-001-0002", 62500, "paid", -60, -50),
    ("DR-DCD-NR-2025-001-0003", 62500, "approved", -10, -5),
    ("DR-DCD-NR-2025-001-0004", 62500, "submitted", 0, None),  # Pending fiscal review!
]
for req_num, amount, status, sub_days, rev_days in award1_drawdowns:
    period_start = date.today() + timedelta(days=sub_days - 90)
    period_end = date.today() + timedelta(days=sub_days)
    DrawdownRequest.objects.get_or_create(
        request_number=req_num,
        defaults=dict(
            award=award1,
            amount=Decimal(str(amount)),
            period_start=period_start,
            period_end=period_end,
            status=status,
            description=f"Quarterly drawdown for period {period_start} to {period_end}",
            submitted_by=app1,
            submitted_at=now + timedelta(days=sub_days) if status != 'draft' else None,
            reviewed_by=lisa if status in ('paid', 'approved') else None,
            reviewed_at=now + timedelta(days=rev_days) if rev_days else None,
            paid_at=now + timedelta(days=rev_days + 5) if status == 'paid' and rev_days else None,
        ),
    )

# Award 2 (East End) — fewer draws, one submitted awaiting review
award2_drawdowns = [
    ("DR-DCD-NR-2025-002-0001", 70000, "paid", -100, -90),
    ("DR-DCD-NR-2025-002-0002", 70000, "submitted", -5, None),  # Pending fiscal review!
    ("DR-DCD-NR-2025-002-0003", 70000, "draft", 0, None),
]
for req_num, amount, status, sub_days, rev_days in award2_drawdowns:
    period_start = date.today() + timedelta(days=sub_days - 90)
    period_end = date.today() + timedelta(days=sub_days)
    DrawdownRequest.objects.get_or_create(
        request_number=req_num,
        defaults=dict(
            award=award2,
            amount=Decimal(str(amount)),
            period_start=period_start,
            period_end=period_end,
            status=status,
            description=f"Quarterly drawdown for period {period_start} to {period_end}",
            submitted_by=app1,
            submitted_at=now + timedelta(days=sub_days) if status != 'draft' else None,
            reviewed_by=lisa if status == 'paid' else None,
            reviewed_at=now + timedelta(days=rev_days) if rev_days else None,
            paid_at=now + timedelta(days=rev_days + 5) if status == 'paid' and rev_days else None,
        ),
    )

# Award 3 (Bridgeport Greenway) — early stage, first draw submitted
award3_drawdowns = [
    ("DR-DCD-NR-2025-003-0001", 65000, "submitted", -3, None),  # Pending fiscal review!
]
for req_num, amount, status, sub_days, rev_days in award3_drawdowns:
    period_start = date.today() + timedelta(days=sub_days - 90)
    period_end = date.today() + timedelta(days=sub_days)
    DrawdownRequest.objects.get_or_create(
        request_number=req_num,
        defaults=dict(
            award=award3,
            amount=Decimal(str(amount)),
            period_start=period_start,
            period_end=period_end,
            status=status,
            description=f"Initial quarterly drawdown for {period_start} to {period_end}",
            submitted_by=app_bridgeport,
            submitted_at=now + timedelta(days=sub_days),
        ),
    )

# ── Transactions ─────────────────────────────────────────────
print("Creating transactions...")
# Award 1 transactions
Transaction.objects.get_or_create(
    reference_number="OBL-2025-001",
    defaults=dict(
        award=award1, transaction_type='obligation',
        amount=Decimal('250000'),
        description="Initial obligation for Frog Hollow Neighborhood Transformation",
        transaction_date=date.today() - timedelta(days=180),
        created_by=lisa,
    ),
)
for i, (amt, days_ago) in enumerate([(62500, 115), (62500, 55)]):
    Transaction.objects.get_or_create(
        reference_number=f"PMT-2025-{i+1:03d}",
        defaults=dict(
            award=award1, transaction_type='payment',
            amount=Decimal(str(amt)),
            description=f"Drawdown payment #{i+1}",
            transaction_date=date.today() - timedelta(days=days_ago),
            created_by=lisa,
        ),
    )

# Award 2 transactions
Transaction.objects.get_or_create(
    reference_number="OBL-2025-002",
    defaults=dict(
        award=award2, transaction_type='obligation',
        amount=Decimal('280000'),
        description="Initial obligation for East End Community Hub",
        transaction_date=date.today() - timedelta(days=150),
        created_by=lisa,
    ),
)
Transaction.objects.get_or_create(
    reference_number="PMT-2025-010",
    defaults=dict(
        award=award2, transaction_type='payment',
        amount=Decimal('70000'),
        description="Drawdown payment #1 - East End",
        transaction_date=date.today() - timedelta(days=85),
        created_by=lisa,
    ),
)

# Award 3 transactions
Transaction.objects.get_or_create(
    reference_number="OBL-2025-003",
    defaults=dict(
        award=award3, transaction_type='obligation',
        amount=Decimal('260000'),
        description="Initial obligation for East Bridgeport Greenway Corridor",
        transaction_date=date.today() - timedelta(days=120),
        created_by=lisa,
    ),
)

# ── Report Templates ─────────────────────────────────────────
print("Creating report templates...")
templates = {}
for name, rtype, freq in [
    ("Quarterly Progress Report", "progress", "quarterly"),
    ("Quarterly Fiscal Report", "fiscal", "quarterly"),
    ("Final Progress Report", "final_progress", "one_time"),
    ("Final Fiscal Report", "final_fiscal", "one_time"),
]:
    rt, _ = ReportTemplate.objects.get_or_create(
        name=name, agency=agencies["DCD"],
        defaults=dict(
            report_type=rtype, frequency=freq,
            created_by=sarah, is_active=True,
            sections={"fields": ["narrative", "outcomes", "challenges"]},
        ),
    )
    templates[name] = rt

# ── Reports ──────────────────────────────────────────────────
print("Creating reports...")
reports_data = [
    # Award 1 reports
    {"award": award1, "type": "progress", "template": "Quarterly Progress Report",
     "start": -180, "end": -90, "due": -80, "status": "approved", "submitter": app1},
    {"award": award1, "type": "fiscal", "template": "Quarterly Fiscal Report",
     "start": -180, "end": -90, "due": -80, "status": "approved", "submitter": app1},
    {"award": award1, "type": "progress", "template": "Quarterly Progress Report",
     "start": -90, "end": 0, "due": 10, "status": "submitted", "submitter": app1},
    {"award": award1, "type": "fiscal", "template": "Quarterly Fiscal Report",
     "start": -90, "end": 0, "due": 10, "status": "draft", "submitter": app1},
    # Award 2 reports
    {"award": award2, "type": "progress", "template": "Quarterly Progress Report",
     "start": -150, "end": -60, "due": -50, "status": "approved", "submitter": app1},
    {"award": award2, "type": "fiscal", "template": "Quarterly Fiscal Report",
     "start": -150, "end": -60, "due": -50, "status": "approved", "submitter": app1},
    {"award": award2, "type": "progress", "template": "Quarterly Progress Report",
     "start": -60, "end": 30, "due": 40, "status": "draft", "submitter": app1},
    # Award 3 reports (early stage — first report due soon)
    {"award": award3, "type": "progress", "template": "Quarterly Progress Report",
     "start": -120, "end": -30, "due": 15, "status": "draft", "submitter": app_bridgeport},
]

for rd in reports_data:
    Report.objects.get_or_create(
        award=rd["award"],
        report_type=rd["type"],
        reporting_period_start=date.today() + timedelta(days=rd["start"]),
        reporting_period_end=date.today() + timedelta(days=rd["end"]),
        defaults=dict(
            template=templates[rd["template"]],
            status=rd["status"],
            due_date=date.today() + timedelta(days=rd["due"]),
            submitted_by=rd["submitter"] if rd["status"] not in ("draft",) else None,
            submitted_at=now + timedelta(days=rd["due"] - 5) if rd["status"] not in ("draft",) else None,
            reviewed_by=mike if rd["status"] == "approved" else None,
            reviewed_at=now + timedelta(days=rd["due"]) if rd["status"] == "approved" else None,
            reviewer_comments="All deliverables on track. Approved." if rd["status"] == "approved" else "",
            data={"narrative": "Project is progressing on schedule.", "outcomes": "Key milestones met.", "challenges": "Minor supply chain delays mitigated."},
        ),
    )

# ── SF-425 Report ────────────────────────────────────────────
print("Creating SF-425 report...")
SF425Report.objects.get_or_create(
    award=award1,
    reporting_period_start=date.today() - timedelta(days=180),
    reporting_period_end=date.today() - timedelta(days=90),
    defaults=dict(
        federal_cash_receipts=Decimal('125000'),
        federal_expenditures=Decimal('118750'),
        federal_unliquidated_obligations=Decimal('6250'),
        recipient_share_expenditures=Decimal('18750'),
        remaining_federal_funds=Decimal('125000'),
        status='approved',
        generated_by=lisa,
        approved_by=sarah,
        submitted_at=now - timedelta(days=75),
        approved_at=now - timedelta(days=70),
    ),
)

# ── Award Amendment ──────────────────────────────────────────
print("Creating award amendments...")
AwardAmendment.objects.get_or_create(
    award=award1, amendment_number=1,
    defaults=dict(
        amendment_type='budget_modification',
        description="Reallocation of $5,000 from travel to supplies to accommodate increased material costs.",
        old_value={"travel": 5000, "supplies": 15000},
        new_value={"travel": 0, "supplies": 20000},
        status='approved',
        requested_by=app1,
        approved_by=sarah,
        submitted_at=now - timedelta(days=60),
        approved_at=now - timedelta(days=55),
    ),
)
# Pending amendment on Award 2 (for agency admin to review)
AwardAmendment.objects.get_or_create(
    award=award2, amendment_number=1,
    defaults=dict(
        amendment_type='time_extension',
        description="Requesting 3-month extension due to construction permit delays. Building renovation timeline shifted from original schedule.",
        old_value={"end_date": str(award2.end_date)},
        new_value={"end_date": str(award2.end_date + timedelta(days=90))},
        status='submitted',
        requested_by=app1,
        submitted_at=now - timedelta(days=3),
    ),
)

# ── Closeout (completed award scenario) ──────────────────────
# We'll create a completed-style award for closeout demo
print("Creating closeout data...")
# First create a completed application + award for closeout
co_app, co_created = Application.objects.get_or_create(
    project_title="Downtown Capital Streetscape Phase I",
    defaults=dict(
        grant_program=programs["Neighborhood Revitalization Grant"],
        applicant=app1, organization=orgs["City of Capital"],
        project_description="Phase I streetscape improvements on Pratt Street including decorative lighting, planters, benches, and wayfinding signage.",
        requested_amount=Decimal('150000'),
        proposed_start_date=date.today() - timedelta(days=400),
        proposed_end_date=date.today() - timedelta(days=35),
        status='approved',
        submitted_at=now - timedelta(days=420),
    ),
)
applications["Downtown Capital Streetscape Phase I"] = co_app

co_award, co_aw_created = Award.objects.get_or_create(
    award_number="DCD-NR-2024-010",
    defaults=dict(
        title="Downtown Capital Streetscape Phase I",
        application=co_app,
        grant_program=programs["Neighborhood Revitalization Grant"],
        agency=agencies["DCD"],
        recipient=app1, organization=orgs["City of Capital"],
        award_amount=Decimal('150000'),
        status='completed',
        award_date=date.today() - timedelta(days=400),
        start_date=date.today() - timedelta(days=400),
        end_date=date.today() - timedelta(days=35),
        approved_by=sarah, approved_at=now - timedelta(days=400),
        executed_at=now - timedelta(days=393),
        terms_and_conditions="Standard state grant terms apply.",
        requires_match=True, match_amount=Decimal('22500'),
    ),
)
awards["DCD-NR-2024-010"] = co_award

if co_aw_created:
    # Budget for closeout award
    co_budget = Budget.objects.create(
        award=co_award, fiscal_year=2024,
        total_amount=Decimal('150000'), status='approved',
        approved_by=lisa, approved_at=now - timedelta(days=390),
        submitted_at=now - timedelta(days=395),
    )
    for cat, desc, amt in [
        ("personnel", "Project Manager", Decimal('45000')),
        ("contractual", "Construction contractor", Decimal('80000')),
        ("supplies", "Street furniture and materials", Decimal('20000')),
        ("indirect", "Indirect costs", Decimal('5000')),
    ]:
        BudgetLineItem.objects.create(budget=co_budget, category=cat, description=desc, amount=amt)

    # Closeout record
    closeout, _ = Closeout.objects.get_or_create(
        award=co_award,
        defaults=dict(
            status='in_progress',
            initiated_by=mike,
        ),
    )

    # Checklist items (some complete, some pending)
    checklist_items = [
        ("Final Progress Report Submitted", "Submit the final narrative report covering all project activities.", True),
        ("Final Fiscal Report Submitted", "Submit the final fiscal report with all expenditure details.", True),
        ("Equipment Inventory Verified", "Verify and document disposition of any equipment purchased.", True),
        ("Audit Clearance", "Confirm single audit requirements met or waived.", False),
        ("Unexpended Funds Returned", "Calculate and return any unexpended grant funds.", False),
        ("Record Retention Confirmed", "Confirm grantee understands 7-year record retention requirement.", False),
        ("Final Site Visit Completed", "Program officer completes final on-site verification.", True),
    ]
    for item_name, item_desc, completed in checklist_items:
        CloseoutChecklist.objects.create(
            closeout=closeout, item_name=item_name,
            item_description=item_desc, is_required=True,
            is_completed=completed,
            completed_by=mike if completed else None,
            completed_at=now - timedelta(days=10) if completed else None,
        )

    # Fund return (small balance)
    FundReturn.objects.create(
        closeout=closeout,
        amount=Decimal('2847.50'),
        reason="Unexpended balance remaining after all project activities completed. Savings from favorable contractor bid.",
        status='pending',
    )

# ── Federal Opportunities (demo data for Grants.gov integration) ──
print("Creating demo federal opportunities...")
federal_opps_data = [
    {
        "opp_id": "350994", "opp_num": "HHS-2026-ACF-OCC-YD-0042",
        "title": "Youth Development Community Partnerships",
        "desc": "Grants to support the development of community partnerships that promote positive youth development outcomes for underserved youth ages 12-24 through evidence-based programming.",
        "agency_name": "Administration for Children and Families",
        "agency_code": "HHS-ACF", "category": "Discretionary",
        "instrument": "grant", "cfda": ["93.590"],
        "floor": 100000, "ceiling": 500000, "total": 15000000,
        "expected": 30, "post_days": -30, "close_days": 45,
        "status": "posted", "applicants": ["State governments", "County governments", "Nonprofits"],
    },
    {
        "opp_id": "351127", "opp_num": "EPA-OLEM-OBLR-26-03",
        "title": "Brownfields Assessment and Cleanup Cooperative Agreements",
        "desc": "EPA is soliciting applications for Brownfields Assessment and Cleanup cooperative agreements for communities, states, and tribes to assess and clean up contaminated brownfield properties.",
        "agency_name": "Environmental Protection Agency",
        "agency_code": "EPA", "category": "Discretionary",
        "instrument": "cooperative_agreement", "cfda": ["66.818"],
        "floor": 200000, "ceiling": 2000000, "total": 60000000,
        "expected": 80, "post_days": -20, "close_days": 60,
        "status": "posted", "applicants": ["State governments", "County governments", "City or township governments", "Nonprofits"],
    },
    {
        "opp_id": "351455", "opp_num": "DOT-FHWA-2026-RAISE",
        "title": "RAISE Transportation Discretionary Grants",
        "desc": "The RAISE program provides competitive grants for surface transportation infrastructure projects that will have a significant local or regional impact on safety, environmental sustainability, and economic competitiveness.",
        "agency_name": "Department of Transportation",
        "agency_code": "DOT", "category": "Discretionary",
        "instrument": "grant", "cfda": ["20.933"],
        "floor": 5000000, "ceiling": 25000000, "total": 2200000000,
        "expected": 200, "post_days": -45, "close_days": 30,
        "status": "posted", "applicants": ["State governments", "County governments", "City or township governments"],
    },
    {
        "opp_id": "351002", "opp_num": "ED-GRANTS-2026-STEMGROW",
        "title": "STEM Education Growth Initiative",
        "desc": "Supports innovative approaches to improving STEM education outcomes, with emphasis on expanding access for underrepresented populations in science, technology, engineering, and mathematics fields.",
        "agency_name": "Department of Education",
        "agency_code": "ED", "category": "Discretionary",
        "instrument": "grant", "cfda": ["84.305A"],
        "floor": 250000, "ceiling": 1500000, "total": 45000000,
        "expected": 50, "post_days": -60, "close_days": -15,
        "status": "closed", "applicants": ["State governments", "Educational institutions", "Nonprofits"],
    },
    {
        "opp_id": "350888", "opp_num": "HUD-2026-CPD-CDBG-DR",
        "title": "Community Development Block Grant - Disaster Recovery",
        "desc": "Provides flexible grants to help cities, counties, and states recover from presidentially declared disasters, with focus on housing, infrastructure, and economic revitalization in affected areas.",
        "agency_name": "Department of Housing and Urban Development",
        "agency_code": "HUD", "category": "Discretionary",
        "instrument": "grant", "cfda": ["14.218", "14.228"],
        "floor": 1000000, "ceiling": 50000000, "total": 500000000,
        "expected": 25, "post_days": -90, "close_days": 90,
        "status": "posted", "applicants": ["State governments", "County governments", "City or township governments"],
    },
]

federal_opps = {}
for fd in federal_opps_data:
    post_d = date.today() + timedelta(days=fd["post_days"])
    close_d = date.today() + timedelta(days=fd["close_days"])
    fopp, _ = FederalOpportunity.objects.get_or_create(
        opportunity_id=fd["opp_id"],
        defaults=dict(
            opportunity_number=fd["opp_num"],
            title=fd["title"],
            description=fd["desc"],
            agency_name=fd["agency_name"],
            agency_code=fd["agency_code"],
            category=fd["category"],
            funding_instrument=fd["instrument"],
            cfda_numbers=fd["cfda"],
            award_floor=Decimal(str(fd["floor"])),
            award_ceiling=Decimal(str(fd["ceiling"])),
            total_funding=Decimal(str(fd["total"])),
            expected_awards=fd["expected"],
            post_date=post_d,
            close_date=close_d,
            opportunity_status=fd["status"],
            applicant_types=fd["applicants"],
            eligible_applicants="See full opportunity listing on Grants.gov for complete eligibility details.",
            grants_gov_url=f"https://simpler.grants.gov/opportunity/{fd['opp_id']}",
        ),
    )
    federal_opps[fd["opp_id"]] = fopp

# ── Tracked Opportunities (Federal Coordinator's pipeline) ───
print("Creating tracked federal opportunities...")
tracked_data = [
    {
        "opp": "351127", "status": "preparing", "priority": "high",
        "notes": "EPA Brownfields — aligns with DEEP priorities. Meeting scheduled with DEEP Commissioner's office next week to discuss state match strategy.",
    },
    {
        "opp": "351455", "status": "watching", "priority": "high",
        "notes": "RAISE grants — DOT is interested. Need to coordinate with state DOT on which projects to put forward. Capital City busway expansion is leading candidate.",
    },
    {
        "opp": "350994", "status": "watching", "priority": "medium",
        "notes": "Youth Development — DCF may be interested. Reached out to Deputy Commissioner's office.",
    },
    {
        "opp": "351002", "status": "declined", "priority": "low",
        "notes": "Deadline passed. We did not have a strong enough multi-agency consortium ready in time. Consider for next funding cycle.",
    },
    {
        "opp": "350888", "status": "preparing", "priority": "high",
        "notes": "CDBG-DR — Critical for post-storm recovery in coastal towns. DOH is taking the lead; coordinating with DCD on economic revitalization component.",
    },
]

tracked_records = {}
for td in tracked_data:
    tr, _ = TrackedOpportunity.objects.get_or_create(
        federal_opportunity=federal_opps[td["opp"]],
        tracked_by=fed_coord,
        defaults=dict(
            status=td["status"],
            priority=td["priority"],
            notes=td["notes"],
        ),
    )
    tracked_records[td["opp"]] = tr

# ── Collaborators on tracked opportunities ───────────────────
print("Creating opportunity collaborators...")
# EPA Brownfields — DEEP staff + external EPA liaison
epa_tracked = tracked_records["351127"]
OpportunityCollaborator.objects.get_or_create(
    tracked_opportunity=epa_tracked, user=mike,
    defaults=dict(role='contributor', invited_by=fed_coord),
)
OpportunityCollaborator.objects.get_or_create(
    tracked_opportunity=epa_tracked, email='j.martinez@epa.gov',
    defaults=dict(
        name='Jorge Martinez', role='observer',
        invited_by=fed_coord,
    ),
)

# RAISE — DOT staff internal
raise_tracked = tracked_records["351455"]
OpportunityCollaborator.objects.get_or_create(
    tracked_opportunity=raise_tracked, user=sarah,
    defaults=dict(role='reviewer', invited_by=fed_coord),
)

# CDBG-DR — DOH staff + external HUD contact
cdbg_tracked = tracked_records["350888"]
OpportunityCollaborator.objects.get_or_create(
    tracked_opportunity=cdbg_tracked, user=lisa,
    defaults=dict(role='contributor', invited_by=fed_coord),
)
OpportunityCollaborator.objects.get_or_create(
    tracked_opportunity=cdbg_tracked, email='r.thompson@hud.gov',
    defaults=dict(
        name='Regina Thompson', role='observer',
        invited_by=fed_coord,
    ),
)

# ── Notifications (comprehensive, per role) ──────────────────
print("Creating notifications...")

# Clear old notifications first for clean state
Notification.objects.all().delete()

notifs = [
    # ── Agency Admin notifications ──
    (sarah, "New Application Submitted", "A new application 'Coastal Storm Surge Barrier System' has been submitted by Town of Greenwich for the Municipal Infrastructure Resilience Program.", "high", False, ""),
    (sarah, "Amendment Request Pending", "Award amendment request for DCD-NR-2025-002 (East End Community Hub) is awaiting your approval. Type: Time Extension.", "high", False, ""),
    (sarah, "Drawdown Request Pending", "Drawdown request DR-DCD-NR-2025-001-0004 for $62,500 is awaiting fiscal review.", "medium", False, ""),
    (sarah, "Report Due Soon", "Quarterly Progress Report for DCD-NR-2025-001 is due in 10 days.", "medium", False, ""),
    (sarah, "Closeout In Progress", "Closeout for DCD-NR-2024-010 (Downtown Capital Streetscape Phase I) is in progress. 4 of 7 checklist items completed.", "medium", False, ""),
    (sarah, "Review Scoring Complete", "All reviewers have completed scoring for 3 of 5 Workforce Development Initiative applications.", "medium", True, ""),

    # ── Program Officer notifications ──
    (mike, "Review Assignments Complete", "Reviewer has completed scoring for the Capital City Advanced Manufacturing Pipeline, Tech Talent Accelerator, and Bridgeport Green Jobs Corps.", "high", False, ""),
    (mike, "New Applications to Assign", "2 new applications for the Small Business Innovation Grant Program are awaiting reviewer assignment.", "high", False, ""),
    (mike, "Quarterly Report Submitted", "Grant Applicant submitted Quarterly Progress Report for Frog Hollow Neighborhood Transformation (DCD-NR-2025-001).", "medium", False, ""),
    (mike, "Closeout Checklist Update", "4 of 7 closeout checklist items completed for Downtown Capital Streetscape Phase I.", "medium", False, ""),
    (mike, "Application Volume Update", "19 applications received across all active programs. 7 are awaiting initial review.", "low", True, ""),

    # ── Fiscal Officer notifications ──
    (lisa, "Drawdown Awaiting Review", "Drawdown request DR-DCD-NR-2025-001-0004 for $62,500 submitted by Grant Applicant requires your review and approval.", "high", False, ""),
    (lisa, "Drawdown Awaiting Review", "Drawdown request DR-DCD-NR-2025-002-0002 for $70,000 submitted by Grant Applicant requires your review and approval.", "high", False, ""),
    (lisa, "Drawdown Awaiting Review", "Drawdown request DR-DCD-NR-2025-003-0001 for $65,000 submitted by Derek Williams requires your review and approval.", "high", False, ""),
    (lisa, "SF-425 Report Due", "Federal SF-425 Financial Status Report for DCD-NR-2025-001 is due next quarter.", "medium", False, ""),
    (lisa, "Fund Return Pending", "Unexpended balance of $2,847.50 from DCD-NR-2024-010 closeout awaiting processing.", "medium", False, ""),
    (lisa, "Budget Amendment Processed", "Budget modification for DCD-NR-2025-001 (travel → supplies reallocation) was approved.", "low", True, ""),

    # ── Reviewer notifications ──
    (rev1, "New Review Assignment", "You have been assigned to review 'Healthcare Workforce Expansion Program' for the Workforce Development Initiative.", "high", False, ""),
    (rev1, "New Review Assignment", "You have been assigned to review 'AI-Powered Quality Inspection System' for the Small Business Innovation Grant Program.", "high", False, ""),
    (rev1, "New Review Assignment", "You have been assigned to review 'IoT-Enabled Smart Grid Monitor' for the Small Business Innovation Grant Program.", "medium", False, ""),
    (rev1, "Review In Progress", "You have partially scored 'Bridgeport Youth Trades Academy' (2 of 5 criteria completed). Please complete your review.", "medium", False, ""),
    (rev1, "Scoring Deadline Reminder", "Review scoring for Workforce Development Initiative applications is due within 14 days.", "medium", False, ""),
    (rev1, "Review Completed", "Your review of 'Capital City Advanced Manufacturing Pipeline' has been recorded. Score: 86.5/100.", "low", True, ""),

    # ── Applicant (app1) notifications ──
    (app1, "Drawdown Approved", "Your drawdown request DR-DCD-NR-2025-001-0003 has been approved for $62,500.", "high", False, ""),
    (app1, "Report Due Soon", "Your Quarterly Fiscal Report for Frog Hollow project (DCD-NR-2025-001) is due in 10 days.", "medium", False, ""),
    (app1, "Report Due Soon", "Your Quarterly Progress Report for East End Community Hub (DCD-NR-2025-002) is due in 40 days.", "medium", False, ""),
    (app1, "Application Received", "Your application 'AI-Powered Quality Inspection System' has been received and is under review.", "medium", True, ""),
    (app1, "Application Received", "Your application 'Riverside Mural Festival 2026' has been received.", "medium", True, ""),
    (app1, "Award Amendment Submitted", "Your time extension request for East End Community Hub has been submitted and is pending review.", "medium", False, ""),
    (app1, "Application Denied", "Your application 'Westville Creative District' was not selected for funding. Contact the program office for feedback.", "low", True, ""),

    # ── Other applicant notifications ──
    (app_bridgeport, "Award Executed", "Your award DCD-NR-2025-003 for East Bridgeport Greenway Corridor ($260,000) has been executed.", "high", True, ""),
    (app_bridgeport, "Report Due Soon", "Your first Quarterly Progress Report for DCD-NR-2025-003 is due in 15 days.", "medium", False, ""),
    (app_bridgeport, "Drawdown Submitted", "Your drawdown request DR-DCD-NR-2025-003-0001 for $65,000 has been submitted for review.", "medium", True, ""),

    (app_greenwich, "Application Received", "Your application 'Coastal Storm Surge Barrier System' has been received and is under review.", "medium", True, ""),

    (app_arts, "Application Received", "Your application 'Elm City Jazz & Heritage Festival' has been received.", "medium", True, ""),
    (app_arts, "Draft Reminder", "You have an incomplete draft application 'Digital Arts Youth Academy'. The deadline is approaching.", "low", False, ""),

    (app_ctinno, "Application Received", "Your application 'IoT-Enabled Smart Grid Monitor' has been received.", "medium", True, ""),
    (app_ctinno, "Draft Reminder", "You have an incomplete draft application 'Biotech Cold Chain Tracking Platform'. Complete and submit before the deadline.", "low", False, ""),

    # ── Auditor notifications ──
    (auditor, "Monthly Audit Summary", "February 2026 audit summary: 325 system actions logged. 3 awards active, 1 in closeout. No anomalies detected.", "medium", False, ""),
    (auditor, "Closeout Audit Required", "Award DCD-NR-2024-010 is in closeout status. Audit review of final reports and fund return is required.", "high", False, ""),
    (auditor, "High-Value Transaction Alert", "Obligation transaction OBL-2025-003 for $260,000 recorded for new award DCD-NR-2025-003.", "medium", True, ""),

    # ── Federal Coordinator notifications ──
    (fed_coord, "New Federal Opportunities Synced", "5 new federal opportunities have been synced from Grants.gov. Review the latest postings.", "medium", False, ""),
    (fed_coord, "Deadline Approaching", "EPA Brownfields Assessment and Cleanup Cooperative Agreements closes in 60 days. Status: Preparing Application.", "high", False, ""),
    (fed_coord, "Deadline Approaching", "RAISE Transportation Discretionary Grants closes in 30 days. Status: Watching.", "high", False, ""),
    (fed_coord, "Collaborator Update", "Program Officer joined as contributor on EPA Brownfields tracked opportunity.", "medium", True, ""),
    (fed_coord, "CDBG-DR Coordination", "DOH confirmed participation in CDBG-DR application. Meeting with HUD regional office scheduled for next Tuesday.", "medium", False, ""),

    # ── System Admin (admin user) notifications ──
]
if admin_user:
    notifs.extend([
        (admin_user, "System Health Check", "All services operational. Database: 19 applications, 4 awards, 3 active grant programs. Last backup: 2 hours ago.", "low", True, ""),
        (admin_user, "New User Registrations", "5 new applicant accounts created this week. All terms accepted and verified.", "medium", True, ""),
        (admin_user, "Pending Closeout", "Award DCD-NR-2024-010 closeout in progress. 3 checklist items remaining before completion.", "medium", False, ""),
        (admin_user, "Drawdown Queue", "3 drawdown requests awaiting fiscal officer review totaling $197,500.", "high", False, ""),
        (admin_user, "Review Progress", "Workforce Development Initiative: 3 of 5 applications fully reviewed. 2 pending reviewer action.", "medium", False, ""),
    ])

for item in notifs:
    recipient, title, message, priority, is_read = item[0], item[1], item[2], item[3], item[4]
    Notification.objects.get_or_create(
        recipient=recipient, title=title,
        defaults=dict(
            message=message, priority=priority,
            is_read=is_read,
            read_at=now if is_read else None,
        ),
    )

# ── Comments on applications ─────────────────────────────────
print("Creating comments...")
app_capital = applications["Capital City Advanced Manufacturing Pipeline"]
ApplicationComment.objects.get_or_create(
    application=app_capital, content="Strong proposal with clear workforce outcomes. Budget is well-justified.",
    defaults=dict(author=mike, is_internal=True),
)
ApplicationComment.objects.get_or_create(
    application=app_capital, content="We've updated the timeline per the program officer's suggestion.",
    defaults=dict(author=app1, is_internal=False),
)

# Comments on other applications
app_tech = applications["Tech Talent Accelerator"]
ApplicationComment.objects.get_or_create(
    application=app_tech, content="Recommend adding more detail on employer partnerships. Which companies have committed to hiring graduates?",
    defaults=dict(author=mike, is_internal=True),
)
ApplicationComment.objects.get_or_create(
    application=app_tech, content="Cybersecurity curriculum looks solid but market analysis could be stronger for the Stamford corridor.",
    defaults=dict(author=rev1, is_internal=True),
)

app_ai = applications["AI-Powered Quality Inspection System"]
ApplicationComment.objects.get_or_create(
    application=app_ai, content="Innovative use of computer vision in manufacturing QC. Confirm IP ownership terms.",
    defaults=dict(author=mike, is_internal=True),
)

app_greenwich_obj = applications["Coastal Storm Surge Barrier System"]
ApplicationComment.objects.get_or_create(
    application=app_greenwich_obj, content="Large infrastructure request. Recommend site visit before review assignment.",
    defaults=dict(author=sarah, is_internal=True),
)

# ── Status History ───────────────────────────────────────────
print("Creating status history...")
for app_obj in applications.values():
    if app_obj.status != 'draft':
        ApplicationStatusHistory.objects.get_or_create(
            application=app_obj, old_status='draft', new_status='submitted',
            defaults=dict(changed_by=app_obj.applicant, comment="Application submitted."),
        )
    if app_obj.status in ('under_review', 'approved', 'denied'):
        ApplicationStatusHistory.objects.get_or_create(
            application=app_obj, old_status='submitted', new_status=app_obj.status,
            defaults=dict(changed_by=sarah, comment=f"Status changed to {app_obj.get_status_display()}."),
        )

# ── Audit Log entries ────────────────────────────────────────
print("Creating audit log entries...")
audit_entries = [
    (admin_user or sarah, 'login', 'User', 'admin', 'System Administrator logged in.'),
    (sarah, 'login', 'User', 'agency.admin', 'Agency Administrator logged in.'),
    (sarah, 'create', 'GrantProgram', str(programs["Small Business Innovation Grant Program"].pk), 'Created grant program: Small Business Innovation Grant Program.'),
    (sarah, 'approve', 'Award', str(award1.pk), 'Approved award DCD-NR-2025-001 for Frog Hollow Neighborhood Transformation.'),
    (sarah, 'approve', 'Award', str(award2.pk), 'Approved award DCD-NR-2025-002 for East End Community Hub.'),
    (sarah, 'approve', 'Award', str(award3.pk), 'Approved award DCD-NR-2025-003 for East Bridgeport Greenway Corridor.'),
    (mike, 'login', 'User', 'program.officer', 'Program Officer logged in.'),
    (mike, 'update', 'Application', str(applications["Tech Talent Accelerator"].pk), 'Moved application to Under Review status.'),
    (mike, 'approve', 'Report', 'progress-001', 'Approved Q1 Progress Report for DCD-NR-2025-001.'),
    (lisa, 'login', 'User', 'fiscal.officer', 'Fiscal Officer logged in.'),
    (lisa, 'approve', 'DrawdownRequest', 'DR-DCD-NR-2025-001-0003', 'Approved drawdown request for $62,500.'),
    (lisa, 'approve', 'Budget', str(award1.pk), 'Approved FY2025 budget for DCD-NR-2025-001.'),
    (rev1, 'login', 'User', 'reviewer', 'Grant Reviewer logged in.'),
    (rev1, 'submit', 'ReviewAssignment', 'review-capital', 'Completed review for Capital City Advanced Manufacturing Pipeline. Score: 86.5.'),
    (rev1, 'submit', 'ReviewAssignment', 'review-tech', 'Completed review for Tech Talent Accelerator. Score: 81.2.'),
    (app1, 'login', 'User', 'applicant', 'Grant Applicant logged in.'),
    (app1, 'submit', 'Application', str(applications["AI-Powered Quality Inspection System"].pk), 'Submitted application: AI-Powered Quality Inspection System.'),
    (app1, 'submit', 'DrawdownRequest', 'DR-DCD-NR-2025-001-0004', 'Submitted drawdown request for $62,500.'),
    (app_bridgeport, 'login', 'User', 'derek.williams', 'Derek Williams logged in.'),
    (app_bridgeport, 'submit', 'DrawdownRequest', 'DR-DCD-NR-2025-003-0001', 'Submitted first drawdown request for $65,000.'),
    (auditor, 'login', 'User', 'auditor', 'System Auditor logged in.'),
    (auditor, 'view', 'AuditLog', 'export-feb', 'Exported audit log for February 2026.'),
    (auditor, 'export', 'Report', 'sf425-001', 'Exported SF-425 Federal Financial Report.'),
]

for user, action, etype, eid, desc in audit_entries:
    if user:
        AuditLog.objects.get_or_create(
            user=user, action=action, entity_type=etype, entity_id=eid,
            defaults=dict(description=desc, ip_address='10.0.1.100'),
        )

# ── Final Summary ────────────────────────────────────────────
print("\n✓ Seed data created successfully!")
print(f"  Agencies:           {Agency.objects.count()}")
print(f"  Organizations:      {Organization.objects.count()}")
print(f"  Users:              {User.objects.count()}")
print(f"  Grant Programs:     {GrantProgram.objects.count()}")
print(f"  Applications:       {Application.objects.count()}")
print(f"  Review Rubrics:     {ReviewRubric.objects.count()}")
print(f"  Review Assign.:     {ReviewAssignment.objects.count()}")
print(f"  Awards:             {Award.objects.count()}")
print(f"  Perf. Metrics:      {PerformanceMetric.objects.count()}")
print(f"  Sub-Recipients:     {SubRecipient.objects.count()}")
print(f"  Budgets:            {Budget.objects.count()}")
print(f"  Drawdowns:          {DrawdownRequest.objects.count()}")
print(f"  Transactions:       {Transaction.objects.count()}")
print(f"  Reports:            {Report.objects.count()}")
print(f"  Closeouts:          {Closeout.objects.count()}")
print(f"  Federal Opps:       {FederalOpportunity.objects.count()}")
print(f"  Tracked Opps:       {TrackedOpportunity.objects.count()}")
print(f"  Collaborators:      {OpportunityCollaborator.objects.count()}")
print(f"  Notifications:      {Notification.objects.count()}")
print(f"  Audit Logs:         {AuditLog.objects.count()}")

print("\n── Demo User Summary ──")
print("  applicant       / demo2026  → 13 apps (2 draft, 6 submitted, 1 under review, 3 approved, 1 denied)")
print("  reviewer        / demo2026  → 7 review assignments (3 completed, 1 in-progress, 3 assigned)")
print("  program.officer / demo2026  → Applications pipeline, report reviews, closeout management")
print("  fiscal.officer  / demo2026  → 3 pending drawdowns to review ($197,500), fund returns")
print("  agency.admin    / demo2026  → Agency overview, pending amendment, closeout oversight")
print("  auditor         / demo2026  → Audit trail, closeout audit, transaction monitoring")
print("  fed.coordinator / demo2026  → Federal Fund Coordinator (OBM), 5 tracked opps, collaborators")
print("  admin           / demo2026  → Full system admin, analytics, all data")
print("  maria.santos    / demo2026  → Greenwich infrastructure applicant")
print("  james.chen      / demo2026  → Riverside arts applicant (1 submitted, 1 draft)")
print("  priya.patel     / demo2026  → State University healthcare workforce applicant")
print("  derek.williams  / demo2026  → Bridgeport Trust (1 award active, drawdown pending)")
print("  rachel.kim      / demo2026  → Innovation Labs (1 submitted, 1 draft)")
