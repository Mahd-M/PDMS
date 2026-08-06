# Production database: PostgreSQL hardening

This repo ships on SQLite so it runs immediately after cloning. This
document is the migration path to what an actual deployment should
run: PostgreSQL with Row-Level Security, pgcrypto, and pgAudit enabled.
None of this DDL is applied automatically -- it's a reference for
whoever stands up the production instance.

## 1. Switch the Django database backend

```python
# config/settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DB_NAME"],
        "USER": os.environ["DB_USER"],
        "PASSWORD": os.environ["DB_PASSWORD"],
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {"sslmode": "verify-full"},
    }
}
```

Add `psycopg2-binary` from the commented line in `requirements.txt`.

## 2. Row-Level Security -- enforce sealed-FIR visibility at the database itself

`cases/views.py::visible_firs_for` already enforces this in the
application. RLS makes the same rule hold even for a raw `psql`
session or a misconfigured read replica -- true defense in depth, not
just "the UI hides it":

```sql
ALTER TABLE cases_fir ENABLE ROW LEVEL SECURITY;

-- Records clerks and the general "app" role never see sealed FIRs
CREATE POLICY clerk_hides_sealed ON cases_fir
    FOR SELECT
    TO app_clerk_role
    USING (is_sealed = false);

-- Admins, station house officers, and auditors see everything
CREATE POLICY full_visibility ON cases_fir
    FOR SELECT
    TO app_admin_role, app_sho_role, app_auditor_role
    USING (true);
```

Map Django's DB connection to the right Postgres role per request (via
`SET ROLE` in a connection-pool hook, or per-request connections keyed
to the user's CJIS role) so RLS actually discriminates by role rather
than every request running as one superuser.

## 3. pgcrypto -- database-level encryption alongside the application-level field

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Example: an additional, database-level encrypted column
-- (the app already encrypts this at the Django field level --
-- pgcrypto is a second, independent layer, not a replacement)
ALTER TABLE cases_fir
    ADD COLUMN complainant_cnic_enc bytea;

UPDATE cases_fir
    SET complainant_cnic_enc = pgp_sym_encrypt(complainant_cnic, current_setting('app.encryption_key'));

-- Read back with:
SELECT pgp_sym_decrypt(complainant_cnic_enc, current_setting('app.encryption_key'));
```

## 4. pgAudit -- database-level audit logging alongside the application's audit trail

```sql
-- postgresql.conf
shared_preload_libraries = 'pgaudit'

-- Per-database
CREATE EXTENSION IF NOT EXISTS pgaudit;
ALTER SYSTEM SET pgaudit.log = 'read, write, role, ddl';
```

This logs every `SELECT`/`INSERT`/`UPDATE`/`DELETE` at the database
layer, independent of `audit/models.py::AuditLog`. The two overlap
deliberately: the application's hash-chained log is what gets shown to
a court or an oversight officer; pgAudit's log is what a DBA or a
security team reviews to confirm the application isn't lying about
what it did.

## 5. Encryption in transit and at rest

- **In transit**: `sslmode=verify-full` above forces the app-to-database
  connection over TLS; also terminate client-facing TLS 1.3 at the
  reverse proxy (see the main README's architecture diagram).
- **At rest**: enable Postgres's Transparent Data Encryption if your
  distribution supports it, or encrypt the underlying volume with LUKS.
  This is what protects a stolen disk or an unencrypted backup file --
  neither pgcrypto nor the Django field encryption helps if someone
  copies the raw data directory.

## 6. Backups

Point-in-time recovery via WAL archiving, with the WAL archive itself
encrypted and stored offsite. Test the restore procedure on a schedule
-- an untested backup is a hope, not a control.
