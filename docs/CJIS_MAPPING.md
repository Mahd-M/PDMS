# Mapping this repo to the CJIS Security Policy

This is a technical reference for anyone evaluating the project against
the FBI CJIS Security Policy (the framework current as of 2026 is v6.0,
released December 27 2024, with the modernized v6.1 released June 25
2026 and audits continuing against v5.9.5 through March 2027). It's
written to be read honestly: some policy areas are fully addressed in
code, some are partially addressed, and several are organizational by
nature and cannot be satisfied by any codebase. Claiming otherwise
would be the opposite of the point of this document.

## Fully addressed in code

**Identification and Authentication.** CJIS has required Advanced
Authentication (a second factor beyond a password) for all access to
criminal justice information since October 1, 2024, at Authenticator
Assurance Level 2. This repo enforces TOTP-based MFA at
`accounts/models.py::User.verify_totp` and the two-step login flow in
`accounts/views.py` -- a password alone never completes a session; a
second step (`mfa_verify_view` or, on first login, `mfa_setup_view`)
must also succeed. Password policy (`config/settings.py:
AUTH_PASSWORD_VALIDATORS`) enforces a 12-character minimum plus
Django's common-password and similarity checks. Account lockout after
repeated failures lives in `accounts/models.py::register_failed_login`.

**Access Control.** Role-based access is modeled explicitly
(`accounts/models.py::Role`: Admin, Station House Officer,
Investigator, Records Clerk, Auditor) and enforced per-view rather than
only in the UI -- see the role checks in `cases/views.py::fir_create`
and `case_update_status`. Row-level visibility (sealed FIRs excluded
from clerk queries) is enforced in `cases/views.py::visible_firs_for`
and, in the production Postgres deployment, mirrored as an actual
database-level Row-Level Security policy (`docs/DATABASE.md`) so the
restriction holds even for a client that bypasses this application
entirely. Session idle timeout is enforced in
`config/security_middleware.py::SessionIdleTimeoutMiddleware`
independently of Django's absolute session expiry.

**Audit and Accountability.** Every state-changing request is logged
by `config/security_middleware.py::AuditLogMiddleware` into
`audit/models.py::AuditLog`, which is hash-chained
(`audit/hashchain.py`) and refuses both updates and deletes at the
model layer -- tampering with a past entry breaks the stored hash of
every entry after it, which is checkable with `verify_chain`. Evidence
handling gets its own parallel trail
(`evidence/models.py::ChainOfCustodyEntry`) scoped per exhibit, which
is what a chain-of-custody argument in court actually needs: an
unbroken record for *that specific item*, not just a global log.

**System and Communications Protection.** The Content-Security-Policy
header (`script-src 'none'`) in
`config/security_middleware.py::SecurityHeadersMiddleware` makes "no
client-side script execution" a browser-enforced property rather than
a coding convention. `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`,
and `CSRF_COOKIE_SECURE` are environment-gated (`DJANGO_USE_TLS`) so
the same settings file is correct in local development over plain HTTP
and in production behind TLS.

## Partially addressed -- code helps, but this is only half the control

**Information Exchange / encryption of CJI.** CJIS requires FIPS
140-2/140-3 validated cryptography for CJI in transit and at rest.
`config/encrypted_fields.py` encrypts specific PII columns
(complainant details) at the application layer using Fernet
(AES-128-CBC + HMAC-SHA256) so the demo's SQLite database never holds
that data as plaintext -- this is verified in practice, not just
asserted (a raw sqlite3 read of the stored bytes returns ciphertext).
That said: (a) Fernet's AES-128 is not itself a FIPS-140-validated
*module* -- a real deployment needs a FIPS-validated cryptographic
library behind this interface, and (b) field-level encryption is one
layer, not the whole story -- production also needs TLS in transit and
encryption at rest for the whole database (Postgres TDE or
filesystem-level encryption via LUKS), covered in `docs/DATABASE.md`.

**Configuration Management.** The settings file separates
environment-specific values from code (`os.environ.get(...)` throughout
`config/settings.py`), which is necessary but not sufficient --
CJIS's configuration-management area also expects a documented baseline,
change-control process, and vulnerability-scanning cadence, none of
which live in a codebase.

## Explicitly out of scope for any codebase

These are real CJIS policy areas, and skipping them here isn't an
oversight -- they're organizational and procedural by nature:

- **Physical Protection** -- controlling physical access to the room,
  rack, or facility where the server and backups live.
- **Personnel Security** -- background checks and vetting for anyone
  with access to CJI, including IT staff and contractors.
- **Security Awareness Training** -- mandated periodic training for
  everyone who touches the system.
- **Incident Response** -- a written, rehearsed plan for what the
  agency does when something goes wrong. Software can generate the
  alerts; it can't be the plan.
- **Formal Audits** -- CJIS compliance is reviewed on a cycle by the
  state's CJIS Systems Agency, not self-certified.
- **Supply Chain Risk Management** (new in the v6.x modernization) --
  vetting cloud providers and vendors before deployment, and requiring
  breach notification from them.

A real pitch to a department should present this document as "here's
what the software does, and here's the list of things the agency
still has to do" -- that split is itself a credible, accurate thing to
say in the room, and it's a more defensible claim than "CJIS
compliant" plastered on a slide.
