"""
Fetches initials-avatar placeholder photos from ui-avatars.com for every
CriminalRecord and MissingPerson that doesn't have one yet. Safe to
interrupt and re-run -- only rows still missing a photo are fetched.

ui-avatars.com returns a 403 for Python's default urllib User-Agent, so
fetch_avatar_bytes sends a browser-style one instead.

Usage:
    python manage.py attach_placeholder_photos
"""
import time
import urllib.error
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from missing_persons.models import MissingPerson
from records.models import CriminalRecord

AVATAR_BASE_URL = "https://ui-avatars.com/api/"
REQUEST_TIMEOUT_SECONDS = 8
DELAY_BETWEEN_REQUESTS_SECONDS = 0.15


def fetch_avatar_bytes(name: str) -> bytes:
    query = urllib.parse.urlencode({"name": name, "size": "256", "background": "random", "bold": "true"})
    url = f"{AVATAR_BASE_URL}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


class Command(BaseCommand):
    help = "Fetches avatar-style placeholder photos for CriminalRecord/MissingPerson rows that don't have one yet."

    def handle(self, *args, **options):
        self._fill(CriminalRecord.objects.filter(photo="").order_by("pk"), "criminal record")
        self._fill(MissingPerson.objects.filter(photo="").order_by("pk"), "missing person")

    def _fill(self, queryset, label):
        total = queryset.count()
        if total == 0:
            self.stdout.write(f"No {label} rows are missing a photo -- nothing to do.")
            return

        self.stdout.write(f"Fetching photos for {total} {label} record(s) without one...")
        done, failed = 0, 0
        for obj in queryset.iterator(chunk_size=200):
            try:
                image_bytes = fetch_avatar_bytes(obj.full_name)
                obj.photo.save(f"{label.replace(' ', '_')}_{obj.pk}.png", ContentFile(image_bytes), save=True)
                done += 1
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                failed += 1
                self.stderr.write(f"  Skipped {label} #{obj.pk}: {exc}")
            if (done + failed) % 50 == 0:
                self.stdout.write(f"  ...{done + failed}/{total}")
            time.sleep(DELAY_BETWEEN_REQUESTS_SECONDS)
        self.stdout.write(self.style.SUCCESS(f"{label}: {done} photos attached, {failed} skipped."))
