from django.core.management.base import BaseCommand

from accounts.models import Role, User
from cases.models import FIR, Case
from personnel.models import Officer


class Command(BaseCommand):
    help = "Creates one demo user per role plus a sample FIR, for a quick first run."

    def handle(self, *args, **options):
        demo_users = [
            ("admin_demo", Role.ADMIN, True, True),
            ("sho_demo", Role.SHO, False, False),
            ("investigator_demo", Role.INVESTIGATOR, False, False),
            ("clerk_demo", Role.CLERK, False, False),
            ("auditor_demo", Role.AUDITOR, False, False),
        ]
        created_users = {}
        for username, role, is_staff, is_superuser in demo_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"role": role, "is_staff": is_staff, "is_superuser": is_superuser},
            )
            if created:
                user.set_password("Demo-Pass-2026!")
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created {username} ({role}) / password: Demo-Pass-2026!"))
            created_users[role] = user

        if not FIR.objects.filter(fir_number="FIR-2026-000001").exists():
            fir = FIR.objects.create(
                fir_number="FIR-2026-000001",
                station="Model Town",
                sections_of_law="PPC 379, PPC 411",
                complainant_name="Sample Complainant",
                complainant_contact="0300-0000000",
                narrative="Demo FIR seeded for a first run -- replace with real data.",
                filed_by=created_users[Role.CLERK],
            )
            Case.objects.create(fir=fir, assigned_officer=created_users[Role.INVESTIGATOR])
            self.stdout.write(self.style.SUCCESS("Seeded sample FIR-2026-000001"))

        Officer.objects.get_or_create(
            user=created_users[Role.INVESTIGATOR],
            defaults={"rank": "Sub-Inspector", "station": "Model Town"},
        )

        self.stdout.write(self.style.WARNING(
            "\nEvery demo account still needs authenticator (TOTP) enrollment on first login -- "
            "that's expected: MFA is mandatory, not optional, even for a demo."
        ))
