"""
Wipes and reseeds a large synthetic demo dataset for local development.

Separate from `seed_demo`, the lightweight bootstrap used against the
live deploy (5 role accounts + one sample FIR). Never touches the five
core demo accounts (admin_demo / sho_demo / investigator_demo /
clerk_demo / auditor_demo) or their MFA enrollment.

Names, CNICs, phone numbers, and narratives are generated combinatorially
from the Pakistani name/locality lists below -- no real dataset or person.

Usage:
    python manage.py seed_bulk_demo
    python manage.py seed_bulk_demo --noinput
    python manage.py seed_bulk_demo --scale 1500
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role
from cases.models import FIR, Case
from evidence.models import ChainOfCustodyEntry, Evidence
from missing_persons.models import MissingPerson
from personnel.models import Assignment, Officer, OfficerAttendance
from records.models import CourtDate, CriminalRecord
from vehicles.models import Vehicle

User = get_user_model()

CORE_USERNAMES = {"admin_demo", "sho_demo", "investigator_demo", "clerk_demo", "auditor_demo"}

# Combined combinatorially (first name x last name); no real dataset or person.

MALE_FIRST_NAMES = [
    "Muhammad", "Ahmed", "Ali", "Hassan", "Hussain", "Bilal", "Usman", "Hamza",
    "Zeeshan", "Faisal", "Imran", "Kashif", "Waqas", "Adnan", "Shahzad", "Tariq",
    "Naveed", "Rizwan", "Asif", "Saad", "Umar", "Junaid", "Aamir", "Farhan",
    "Kamran", "Shoaib", "Yasir", "Zubair", "Danish", "Arslan", "Haris", "Salman",
    "Sajjad", "Nasir", "Fahad", "Talha", "Ibrahim", "Awais", "Noman", "Sheraz",
]
FEMALE_FIRST_NAMES = [
    "Ayesha", "Fatima", "Sana", "Amina", "Hina", "Sadia", "Mehwish", "Rabia",
    "Nadia", "Saima", "Farah", "Zainab", "Maryam", "Iqra", "Bushra", "Sobia",
    "Uzma", "Shazia", "Naila", "Rukhsana", "Anum", "Sidra", "Komal", "Warda",
    "Mahnoor", "Alishba", "Hafsa", "Amber", "Tahira", "Nida", "Sundas", "Aqsa",
]
LAST_NAMES = [
    "Khan", "Malik", "Sheikh", "Chaudhry", "Butt", "Awan", "Qureshi", "Siddiqui",
    "Baig", "Iqbal", "Javed", "Akhtar", "Farooq", "Nawaz", "Hussain", "Raza",
    "Abbasi", "Gondal", "Rana", "Bhatti", "Warraich", "Cheema", "Tarar", "Dogar",
    "Mughal", "Ansari", "Zaidi", "Rizvi", "Bajwa", "Minhas", "Sandhu", "Chandio",
]

LAHORE_STATIONS = [
    "Model Town", "Gulberg", "Iqbal Town", "Township", "Faisal Town",
    "Johar Town", "Garden Town", "Shadman", "Cantt", "Data Ganj Bakhsh",
    "Ravi Road", "Samanabad", "Green Town", "Nishtar Colony", "Baghbanpura",
    "Shalimar", "Mughalpura", "Factory Area", "Sabzazar", "Wahdat Colony",
]
LAHORE_LOCALITIES = [
    "Liberty Market", "Anarkali Bazaar", "Mall Road", "DHA Phase 5",
    "Wapda Town", "Bahria Town", "Askari X", "Ichhra", "Barkat Market",
    "Allama Iqbal Town", "Gawalmandi", "Chauburji", "Thokar Niaz Baig",
    "Kalma Chowk", "Firdous Market", "Cavalry Ground", "Model Colony",
]

PPC_SECTION_COMBOS = [
    "PPC 379", "PPC 379, 411", "PPC 392", "PPC 392, 397", "PPC 302",
    "PPC 302, 34", "PPC 324", "PPC 324, 337", "PPC 420", "PPC 420, 468, 471",
    "PPC 489-F", "PPC 337-A", "PPC 148, 149", "PPC 380", "PPC 401",
    "PPC 411", "PPC 34", "PPC 109", "PPC 506", "PPC 452",
]

VEHICLE_MAKES_MODELS = [
    ("Suzuki", "Mehran"), ("Suzuki", "Cultus"), ("Suzuki", "Alto"),
    ("Suzuki", "Bolan"), ("Suzuki", "Swift"), ("Suzuki", "WagonR"),
    ("Toyota", "Corolla"), ("Toyota", "Vitz"), ("Toyota", "Hilux"),
    ("Toyota", "Fortuner"), ("Honda", "City"), ("Honda", "Civic"),
    ("Honda", "BR-V"), ("Daihatsu", "Coure"), ("Daihatsu", "Move"),
    ("Hyundai", "Tucson"), ("Hyundai", "Elantra"), ("KIA", "Sportage"),
    ("KIA", "Picanto"), ("Changan", "Alsvin"),
]

OFFICER_RANKS_WEIGHTED = (
    ["Constable"] * 12 + ["Head Constable"] * 8 + ["Assistant Sub-Inspector"] * 5
    + ["Sub-Inspector"] * 4 + ["Inspector"] * 2 + ["DSP"] * 1
)
OFFICER_DEPARTMENTS = ["Investigation", "Patrol", "Traffic", "Crime Branch", "Special Branch"]
ASSIGNMENT_DESCRIPTIONS = [
    "Beat patrol", "Traffic duty", "VIP security detail", "Crime scene response unit",
    "Investigation support", "Court liaison duty", "Community policing", "Night patrol",
]

EVIDENCE_DESCRIPTIONS = [
    "Mobile phone recovered at scene", "Bloodstained clothing", "CCTV footage (USB drive)",
    "Fingerprint lift card", "Forged bank cheque", "Recovered firearm",
    "Suspect's laptop", "Vehicle registration documents", "Torn clothing fragment",
    "Ransom note", "Broken window glass sample", "Blood sample vial",
    "Recovered stolen jewelry", "Suspect's SIM card", "Photograph printouts",
    "Hair sample", "Knife recovered from scene", "Cash recovered (marked notes)",
    "Handwritten threat letter", "Drug sample (sealed)",
]

FIR_NARRATIVE_TEMPLATES = [
    "Complainant reported that unknown persons broke into the premises and removed valuables during the night of {date}.",
    "On {date}, complainant's vehicle was reported stolen from outside their residence near {locality}.",
    "A physical altercation was reported between two parties near {locality}, resulting in injuries.",
    "Complainant alleges being defrauded of a sum of money through a fraudulent investment scheme.",
    "An armed robbery was reported at a shop in {locality} on {date}.",
    "Complainant reported the disappearance of a family member last seen near {locality}.",
    "A case of forged cheques being used at a local bank branch was reported by the branch manager.",
    "Complainant reported receiving repeated threats via phone calls demanding money.",
    "Two vehicles collided near {locality}, with one driver fleeing the scene.",
    "Complainant reported the recovery of a stolen motorcycle matching a previous complaint.",
]

MISSING_PERSON_DESCRIPTIONS = [
    "Last seen wearing a blue shalwar kameez.", "Has a mole on the left cheek.",
    "Was wearing a school uniform at the time of disappearance.",
    "Known to frequent the area near {locality}.", "Has a distinctive scar on the right hand.",
    "Was last seen carrying a black backpack.", "No distinguishing marks reported.",
]

COURT_NAMES = [
    "District Court Lahore", "Sessions Court Lahore", "Lahore High Court",
    "Anti-Terrorism Court", "Magistrate Court Model Town",
]
COURT_OUTCOMES = ["", "", "Adjourned", "Hearing pending", "Bail granted", "Case dismissed", "Remanded"]

ALIASES_POOL = ["Chotu", "Kaala", "Lambi", "Sheeda", "Bobby", "Guddu", "Shera", "Pappu"]


def random_date_within(days_back_max, days_back_min=0):
    days = random.randint(days_back_min, days_back_max)
    return timezone.now() - timedelta(days=days, hours=random.randint(0, 23), minutes=random.randint(0, 59))


def random_cnic():
    return f"{random.randint(10000, 99999)}-{random.randint(1000000, 9999999)}-{random.randint(0, 9)}"


def random_phone():
    return f"03{random.randint(0, 49):02d}-{random.randint(1000000, 9999999)}"


def random_name():
    sex = random.choice(["m", "f"])
    first = random.choice(MALE_FIRST_NAMES if sex == "m" else FEMALE_FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}"


class Command(BaseCommand):
    help = "Wipes and reseeds a large, realistic-looking synthetic demo dataset. Does not touch the 5 core demo accounts or their MFA enrollment."

    def add_arguments(self, parser):
        parser.add_argument("--noinput", action="store_true", help="Skip the confirmation prompt.")
        parser.add_argument("--scale", type=int, default=1200, help="Approximate row count for the largest tables (default 1200).")

    def handle(self, *args, **options):
        scale = options["scale"]
        if not options["noinput"]:
            self.stdout.write(self.style.WARNING(
                "This will DELETE all FIRs, cases, criminal records, missing persons, "
                "vehicles, evidence, and every officer/user account EXCEPT admin_demo / "
                "sho_demo / investigator_demo / clerk_demo / auditor_demo (their MFA "
                "enrollment is left untouched), then regenerate a large synthetic dataset."
            ))
            if input("Type 'yes' to continue: ").strip().lower() != "yes":
                self.stdout.write("Aborted.")
                return

        with transaction.atomic():
            self._wipe()
            officers = self._seed_officers(count=scale)
            self._seed_attendance(officers, days=14)
            self._seed_assignments(officers)
            cases = self._seed_firs_and_cases(count=scale)
            self._seed_evidence(cases)
            self._seed_criminal_records(count=scale)
            self._seed_missing_persons(count=int(scale * 0.9))
            self._seed_vehicles(count=scale, cases=cases)

        self.stdout.write(self.style.SUCCESS(
            "Done. Run `python manage.py attach_placeholder_photos` next to fetch "
            "avatar-style photos for criminal records and missing persons -- that's a "
            "separate, slower, network-bound step on purpose."
        ))

    # ---- wipe --------------------------------------------------------
    def _wipe(self):
        self.stdout.write("Wiping existing bulk data...")
        # QuerySet.delete() is a bulk SQL DELETE; it bypasses each instance's
        # overridden .delete() (the immutability guards on
        # ChainOfCustodyEntry/AuditLog only block obj.delete() calls).
        ChainOfCustodyEntry.objects.all().delete()
        Evidence.objects.all().delete()
        Vehicle.objects.all().delete()
        Case.objects.all().delete()
        FIR.objects.all().delete()
        CriminalRecord.objects.all().delete()  # cascades CourtDate
        MissingPerson.objects.all().delete()
        # Officer.user is a CASCADE FK, so deleting these users cascades
        # down through Officer -> OfficerAttendance/Assignment too.
        User.objects.exclude(username__in=CORE_USERNAMES).delete()

    # ---- officers ------------------------------------------------------
    def _seed_officers(self, count):
        self.stdout.write(f"Creating {count} officers...")
        users = []
        for i in range(count):
            sex = random.choice(["m", "f"])
            first = random.choice(MALE_FIRST_NAMES if sex == "m" else FEMALE_FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            role = random.choices([Role.INVESTIGATOR, Role.SHO, Role.CLERK], weights=[75, 15, 10])[0]
            user = User(
                username=f"ofc_{i:05d}",
                first_name=first,
                last_name=last,
                role=role,
                badge_number=f"PB-{random.randint(10000, 99999)}",
                is_staff=False,
                is_superuser=False,
                mfa_enabled=False,
            )
            # Roster entries only; nobody logs in as these.
            user.set_unusable_password()
            users.append(user)
        User.objects.bulk_create(users, batch_size=500)

        bulk_users = list(User.objects.filter(username__startswith="ofc_"))
        officers = []
        for user in bulk_users:
            officers.append(Officer(
                user=user,
                rank=random.choice(OFFICER_RANKS_WEIGHTED),
                station=random.choice(LAHORE_STATIONS),
                department=random.choice(OFFICER_DEPARTMENTS),
                shift=random.choice(["morning", "evening", "night"]),
                contact_number=random_phone(),
                date_joined_force=(timezone.now() - timedelta(days=random.randint(200, 9000))).date(),
                active=random.random() > 0.05,  # ~95% active
            ))
        Officer.objects.bulk_create(officers, batch_size=500)
        return list(Officer.objects.select_related("user").filter(user__username__startswith="ofc_"))

    def _seed_attendance(self, officers, days=14):
        self.stdout.write(f"Creating attendance for the last {days} days across {len(officers)} officers...")
        marker = User.objects.get(username="sho_demo")
        today = timezone.localdate()
        rows = []
        for officer in officers:
            for d in range(days):
                status = random.choices(
                    [OfficerAttendance.Status.PRESENT, OfficerAttendance.Status.ABSENT, OfficerAttendance.Status.LEAVE],
                    weights=[85, 8, 7],
                )[0]
                rows.append(OfficerAttendance(officer=officer, date=today - timedelta(days=d), status=status, marked_by=marker))
        OfficerAttendance.objects.bulk_create(rows, batch_size=1000, ignore_conflicts=True)

    def _seed_assignments(self, officers):
        self.stdout.write("Creating assignments...")
        rows = []
        for officer in officers:
            for _ in range(random.randint(1, 2)):
                start = timezone.now() - timedelta(days=random.randint(30, 1500))
                ongoing = random.random() > 0.4
                end_date = None if ongoing else (start + timedelta(days=random.randint(10, 400))).date()
                rows.append(Assignment(
                    officer=officer,
                    description=random.choice(ASSIGNMENT_DESCRIPTIONS),
                    station=officer.station,
                    start_date=start.date(),
                    end_date=end_date,
                ))
        Assignment.objects.bulk_create(rows, batch_size=1000)

    # ---- FIRs / cases ----------------------------------------------------
    def _seed_firs_and_cases(self, count):
        self.stdout.write(f"Creating {count} FIRs and cases...")
        clerks = list(User.objects.filter(role=Role.CLERK))
        investigators = list(User.objects.filter(role=Role.INVESTIGATOR))

        # date_filed is auto_now_add=True, which forces timezone.now() on
        # every insert (bulk_create included) unless disabled first.
        date_field = FIR._meta.get_field("date_filed")
        date_field.auto_now_add = False
        firs = []
        try:
            for i in range(count):
                locality = random.choice(LAHORE_LOCALITIES)
                filed_at = random_date_within(days_back_max=900)
                narrative = random.choice(FIR_NARRATIVE_TEMPLATES).format(
                    date=filed_at.strftime("%d %B %Y"), locality=locality,
                )
                firs.append(FIR(
                    fir_number=f"FIR-{filed_at.year}-{i + 1:06d}",
                    station=random.choice(LAHORE_STATIONS),
                    date_filed=filed_at,
                    sections_of_law=random.choice(PPC_SECTION_COMBOS),
                    complainant_name=random_name(),
                    complainant_contact=random_phone(),
                    narrative=narrative,
                    is_sealed=random.random() < 0.08,
                    filed_by=random.choice(clerks),
                ))
            FIR.objects.bulk_create(firs, batch_size=500)
        finally:
            date_field.auto_now_add = True

        created_firs = list(FIR.objects.filter(fir_number__startswith="FIR-"))
        cases = []
        for fir in created_firs:
            status = random.choices(
                [Case.Status.OPEN, Case.Status.UNDER_INVESTIGATION, Case.Status.CHALLAN_FILED,
                 Case.Status.IN_COURT, Case.Status.CLOSED],
                weights=[15, 25, 15, 10, 35],
            )[0]
            cases.append(Case(
                fir=fir,
                status=status,
                assigned_officer=random.choice(investigators) if random.random() > 0.1 else None,
                court_reference=f"CR-{random.randint(1000, 9999)}/{fir.date_filed.year}" if status in (Case.Status.IN_COURT, Case.Status.CHALLAN_FILED) else "",
                next_hearing_date=(timezone.now() + timedelta(days=random.randint(1, 120))).date() if status == Case.Status.IN_COURT else None,
            ))
        Case.objects.bulk_create(cases, batch_size=500)
        return list(Case.objects.select_related("fir").filter(fir__in=created_firs))

    # ---- evidence ----------------------------------------------------------
    def _seed_evidence(self, cases):
        # Evidence.save() computes sha256_hash and the first custody entry;
        # bulk_create() would bypass save() entirely, so this loops with
        # real saves instead.
        investigators = list(User.objects.filter(role=Role.INVESTIGATOR))
        self.stdout.write(f"Creating evidence for {len(cases)} cases (uses real per-item SHA-256 + custody entries, so this is the slower step)...")
        created = 0
        for case in cases:
            for _ in range(random.choices([0, 1, 2, 3], weights=[15, 45, 30, 10])[0]):
                description = random.choice(EVIDENCE_DESCRIPTIONS)
                placeholder_text = (
                    f"Placeholder evidence file for: {description}\n"
                    f"Case: {case.fir.fir_number}\n"
                    "Generated by seed_bulk_demo -- replace with a real file if needed.\n"
                )
                item = Evidence(
                    case=case,
                    description=description,
                    evidence_type=random.choice(Evidence.EvidenceType.values),
                    storage_location=f"Evidence Locker {random.choice('ABCD')}, Shelf {random.randint(1, 12)}",
                    uploaded_by=random.choice(investigators),
                )
                item.file.save(f"placeholder_{case.pk}_{created}.txt", ContentFile(placeholder_text.encode()), save=False)
                item.save()  # computes sha256_hash + creates the RECEIVED custody entry
                if random.random() < 0.3:
                    ChainOfCustodyEntry.record(
                        item, action=ChainOfCustodyEntry.Action.ACCESSED,
                        actor=random.choice(investigators), note="Reviewed during investigation",
                    )
                created += 1
        self.stdout.write(f"  ...{created} evidence items created.")

    # ---- criminal records -------------------------------------------------
    def _seed_criminal_records(self, count):
        self.stdout.write(f"Creating {count} criminal records...")
        records = []
        for _ in range(count):
            status = random.choices(
                [CriminalRecord.Status.WANTED, CriminalRecord.Status.IN_CUSTODY,
                 CriminalRecord.Status.RELEASED, CriminalRecord.Status.DECEASED],
                weights=[15, 25, 50, 10],
            )[0]
            records.append(CriminalRecord(
                full_name=random_name(),
                cnic=random_cnic(),
                aliases=", ".join(random.sample(ALIASES_POOL, k=random.choice([0, 1, 2]))),
                fingerprint_id=f"FP-{random.randint(100000, 999999)}",
                status=status,
                charges=random.choice(PPC_SECTION_COMBOS),
            ))
        CriminalRecord.objects.bulk_create(records, batch_size=500)

        # Court dates for anyone still wanted or in custody.
        active_statuses = (CriminalRecord.Status.WANTED, CriminalRecord.Status.IN_CUSTODY)
        active_records = [r for r in records if r.status in active_statuses]
        court_dates = []
        for record in active_records:
            for _ in range(random.randint(1, 3)):
                court_dates.append(CourtDate(
                    criminal_record=record,
                    date=(timezone.now() + timedelta(days=random.randint(-200, 180))).date(),
                    court_name=random.choice(COURT_NAMES),
                    outcome=random.choice(COURT_OUTCOMES),
                ))
        CourtDate.objects.bulk_create(court_dates, batch_size=1000)

    # ---- missing persons ----------------------------------------------------
    def _seed_missing_persons(self, count):
        self.stdout.write(f"Creating {count} missing person reports...")
        records = []
        for _ in range(count):
            status = random.choices(
                [MissingPerson.Status.MISSING, MissingPerson.Status.FOUND, MissingPerson.Status.DECEASED],
                weights=[35, 55, 10],
            )[0]
            locality = random.choice(LAHORE_LOCALITIES)
            records.append(MissingPerson(
                full_name=random_name(),
                last_seen_date=(timezone.now() - timedelta(days=random.randint(1, 900))).date(),
                last_seen_location=locality,
                reporting_relative_name=random_name(),
                reporting_relative_contact=random_phone(),
                description=random.choice(MISSING_PERSON_DESCRIPTIONS).format(locality=locality),
                status=status,
            ))
        MissingPerson.objects.bulk_create(records, batch_size=500)

    # ---- vehicles ------------------------------------------------------------
    def _seed_vehicles(self, count, cases):
        self.stdout.write(f"Creating {count} vehicles...")
        used_plates = set()

        def unique_plate():
            while True:
                plate = f"LE{random.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}-{random.randint(1000, 9999)}"
                if plate not in used_plates:
                    used_plates.add(plate)
                    return plate

        # ~1 in 5 vehicles is tied to a case; most are unlinked lookup entries.
        linked_cases = random.sample(cases, k=min(int(count * 0.2), len(cases)))
        vehicles = []
        for i in range(count):
            make, model = random.choice(VEHICLE_MAKES_MODELS)
            status = random.choices(
                [Vehicle.Status.NORMAL, Vehicle.Status.RECOVERED, Vehicle.Status.WANTED],
                weights=[78, 12, 10],
            )[0]
            vehicles.append(Vehicle(
                registration_number=unique_plate(),
                make=make,
                model=model,
                owner_name=random_name(),
                owner_contact=random_phone(),
                status=status,
                case=linked_cases[i] if i < len(linked_cases) else None,
            ))
        Vehicle.objects.bulk_create(vehicles, batch_size=500)
