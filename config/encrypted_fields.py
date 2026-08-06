"""
Application-layer field encryption for sensitive PII.

CJIS Security Policy Area 5 (Access Control) and Area 4 (Audit and
Accountability) both assume that criminal justice information is
protected even from someone with raw database access -- a DBA, a
stolen backup file, a misconfigured read replica. Row-Level Security
and Postgres's pgcrypto extension cover this at the database layer in
production; this Fernet-based field wraps the same idea at the model
layer so the demo works identically on SQLite in development and
Postgres in production.

Do not treat this as a replacement for encryption at rest and in
transit -- it is one additional layer, not the only one.
"""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def get_fernet() -> Fernet:
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
            "and set it as an environment variable -- never commit it."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """A TextField that is encrypted at rest at the application layer."""

    description = "Encrypted text (Fernet / AES-128-CBC + HMAC)"

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        token = get_fernet().encrypt(str(value).encode("utf-8"))
        return token.decode("utf-8")

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Value was written before encryption was enabled, or the key rotated.
            return "[unreadable -- encryption key mismatch]"

    def to_python(self, value):
        return value
