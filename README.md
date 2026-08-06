# PDMS -- Police Department Management System

A station-level records management system (FIRs, case tracking, evidence
chain-of-custody, personnel roster) built as a **zero-client-JavaScript
web application**, with its security controls designed against the
**FBI CJIS Security Policy** as the reference benchmark rather than an
ad-hoc checklist.

> **On the CJIS claim, precisely:** no codebase can be "CJIS certified"
> on its own -- certification is an audited property of the operating
> agency (background-checked personnel, physical facility controls,
> incident-response process, a signed CJIS Security Addendum, etc.),
> not of software. What this repo _can_ honestly claim is that its
> technical controls -- access control, authentication, audit logging,
> encryption, session management -- are built to the same bar CJIS's
> technical policy areas require. See
> [`docs/CJIS_MAPPING.md`](docs/CJIS_MAPPING.md) for exactly which
> areas that covers and which are explicitly out of scope for code.

## Why no client-side JavaScript

Every page is fully server-rendered. Every state change is a plain
HTML `<form>` POST or a link click -- there is no `fetch`, no client
router, no client state. The `Content-Security-Policy: script-src
'none'` header (see `config/security_middleware.py`) makes this a
property the browser enforces, not just a coding convention: even a
successful injection attack has no script engine to run in.

The tradeoff, stated plainly: every interaction is a full page
round-trip. There's no live/async UI. That's an intentional trade of
snappiness for a smaller client attack surface, appropriate for an
internal records system rather than a consumer app.

```
Browser (JS disabled)
        |  TLS 1.3
        v
Reverse proxy + WAF  (Nginx, CSP: script-src 'none')
        |
        v
App server  (Django, server-rendered HTML, RBAC, CSRF)
        |
        +------------------+------------------+
        v                  v                  v
   Database           Audit log         Evidence store
 (Postgres, RLS        (immutable        (encrypted,
  + pgcrypto)          hash chain)         hashed)
        |
        v
   Backups (encrypted, offsite, point-in-time)
```

## Features

- **Accounts** -- role-based users (Admin / Station House Officer /
  Investigator / Records Clerk / Auditor), mandatory TOTP MFA enrolled
  on first login, account lockout after repeated failed attempts.
- **Cases** -- FIR registration (Pakistani Cr.P.C. terminology),
  case status workflow, sealed-FIR row-level visibility.
- **Evidence** -- file upload with a SHA-256 hash computed once at
  intake, and a hash-chained, tamper-evident chain-of-custody log.
- **Audit** -- every state-changing request is logged in an append-only,
  hash-chained audit trail that refuses updates or deletes at the model
  layer.
- **Personnel** -- officer roster linked to login accounts.
- **Dashboard** -- server-rendered summary stats and a pure-CSS/HTML
  bar chart -- no charting library, no client script.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in DJANGO_SECRET_KEY and FIELD_ENCRYPTION_KEY in .env, then:
export $(grep -v '^#' .env | xargs)

python manage.py migrate
python manage.py seed_demo   # creates one demo user per role + a sample FIR
python manage.py runserver
```

Sign in at `/accounts/login/` as `admin_demo` / `sho_demo` /
`investigator_demo` / `clerk_demo` / `auditor_demo`, password
`Demo-Pass-2026!`. Every account enrolls its own authenticator (TOTP)
on first login -- MFA is mandatory, including in the demo, because
making it skippable "just for the demo" would be exactly the kind of
shortcut this project is arguing against.

## Security controls at a glance

| Concern                                 | Where it lives                                                                                |
| --------------------------------------- | --------------------------------------------------------------------------------------------- |
| No script execution, even if injected   | `config/security_middleware.py` (CSP `script-src 'none'`)                                     |
| Role-based access control               | `accounts/models.py` (`Role`), enforced per-view                                              |
| Row-level data visibility (sealed FIRs) | `cases/views.py::visible_firs_for` (mirrored as Postgres RLS in prod, see `docs/DATABASE.md`) |
| Mandatory MFA (TOTP)                    | `accounts/models.py`, `accounts/views.py`                                                     |
| Account lockout                         | `accounts/models.py::register_failed_login`                                                   |
| Idle session timeout                    | `config/security_middleware.py::SessionIdleTimeoutMiddleware`                                 |
| CSRF protection                         | Django built-in, on every form                                                                |
| Field-level PII encryption              | `config/encrypted_fields.py`                                                                  |
| Evidence integrity                      | `evidence/models.py` (SHA-256 at intake)                                                      |
| Tamper-evident audit trail              | `audit/models.py`, `evidence/models.py::ChainOfCustodyEntry`                                  |

Full control-by-control mapping to CJIS Security Policy areas:
[`docs/CJIS_MAPPING.md`](docs/CJIS_MAPPING.md). Production database
hardening (Postgres RLS, pgcrypto, pgAudit): [`docs/DATABASE.md`](docs/DATABASE.md).

## Project structure

```
pdms/
  config/          settings, URL root, security middleware, encrypted field type
  accounts/        custom User, roles, MFA, lockout
  cases/           FIR + Case models, RBAC-filtered views
  evidence/        Evidence + hash-chained chain of custody
  audit/           append-only, hash-chained audit log
  personnel/       officer roster
  dashboard/       server-rendered summary stats
  templates/, static/   HTML + CSS only -- no JS anywhere
  docs/            CJIS mapping, production database notes
```

## Deploying for real

This ships on SQLite so it runs immediately after cloning. Production
should move to PostgreSQL (`docs/DATABASE.md`), sit behind Nginx or
Caddy terminating TLS with the demo's `DJANGO_USE_TLS=true`, and add a
WAF (e.g. ModSecurity + the OWASP Core Rule Set) in front of that.

## License

Academic Use Only License -- see `LICENSE`.
