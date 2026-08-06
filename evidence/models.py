import hashlib

from django.conf import settings
from django.db import models

from audit.hashchain import GENESIS_HASH, compute_row_hash
from cases.models import Case


def evidence_upload_path(instance, filename):
    return f"evidence/case_{instance.case_id}/{filename}"


class Evidence(models.Model):
    """
    A piece of physical or digital evidence attached to a case.
    The SHA-256 hash is computed once, at upload time, and never
    recomputed -- if the stored file's hash ever stops matching this
    value, the file has been altered or corrupted, which is exactly
    what a chain-of-custody check needs to catch.
    """
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="evidence_items")
    description = models.CharField(max_length=255)
    file = models.FileField(upload_to=evidence_upload_path)
    sha256_hash = models.CharField(max_length=64, editable=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.file:
            hasher = hashlib.sha256()
            for chunk in self.file.chunks():
                hasher.update(chunk)
            self.sha256_hash = hasher.hexdigest()
            super().save(update_fields=["sha256_hash"])
            ChainOfCustodyEntry.record(self, action=ChainOfCustodyEntry.Action.RECEIVED, actor=self.uploaded_by)

    def __str__(self):
        return f"{self.description} ({self.case})"


class ChainOfCustodyEntry(models.Model):
    """
    Append-only, hash-chained custody log for a single piece of
    evidence -- who received it, transferred it, or accessed it, and
    when. Chained per evidence item so a court can be shown an
    unbroken, tamper-evident trail for that specific exhibit.
    """

    class Action(models.TextChoices):
        RECEIVED = "received", "Received into evidence"
        TRANSFERRED = "transferred", "Transferred custody"
        ACCESSED = "accessed", "Accessed / reviewed"
        RELEASED = "released", "Released"

    evidence = models.ForeignKey(Evidence, on_delete=models.PROTECT, related_name="custody_log")
    timestamp = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=20, choices=Action.choices)
    note = models.CharField(max_length=255, blank=True)

    prev_hash = models.CharField(max_length=64)
    row_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["timestamp"]
        verbose_name_plural = "Chain of custody entries"

    @classmethod
    def record(cls, evidence: Evidence, action: str, actor, note: str = ""):
        last = cls.objects.filter(evidence=evidence).order_by("-id").first()
        prev_hash = last.row_hash if last else GENESIS_HASH
        row_hash = compute_row_hash(prev_hash, str(evidence.pk), action, str(actor.pk), note)
        return cls.objects.create(
            evidence=evidence, actor=actor, action=action, note=note,
            prev_hash=prev_hash, row_hash=row_hash,
        )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Chain-of-custody entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Chain-of-custody entries cannot be deleted.")
