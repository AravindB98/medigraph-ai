# Security & compliance

Healthcare software lives and dies on access control and accountability.
MediGraph AI ships these as first-class concerns, designed against **HIPAA** (US)
and **DPDP / ABDM** (India) expectations. It is a reference implementation, not a
compliance certification.

## Role-based access control (`security/rbac.py`)

| Role | View PHI | Decision support | Cohorts | Analytics | Import/Export | Audit | Manage users |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **clinician** | ✅ | ✅ | ✅ | ✅ | ✅ | – | – |
| **nurse** | ✅ | ✅ | – | ✅ | – | – | – |
| **analyst** | de-identified | – | ✅ | ✅ | – | – | – |
| **auditor** | de-identified | – | – | – | – | ✅ | – |

Every API route declares the permission it needs via a `require(Permission.…)`
dependency; the UI hides or gates actions by the signed-in role.

## Authentication (`security/auth.py`)

Implemented with the **standard library only** (no extra crypto dependency):
passwords are hashed with PBKDF2-HMAC-SHA256 (120k rounds, per-password salt), and
sessions are spec-correct **HS256 JWTs** with `iat`/`exp`. Tampered or expired
tokens are rejected. In production, point `UserStore` at your IdP / LDAP /
SMART-on-FHIR authorization server instead of the bundled demo users.

## Audit trail (`security/audit.py`)

Every patient access, decision-support run, query, export and denied request is
appended as a JSON line: *who (actor + role), what (action), which record
(resource/patient), outcome, and when (UTC)*. The log is append-only and trivial
to ship to a SIEM. The `auditor` role can review it in the UI and via `GET /audit`.

```json
{"actor":"dr.house","role":"clinician","action":"view_patient",
 "resource":"Patient/pat-0001","patient_id":"pat-0001","outcome":"success",
 "timestamp":"2026-06-27T12:00:00+00:00"}
```

## De-identification (`security/deidentify.py`)

A HIPAA Safe-Harbor-flavoured transform for the analyst pathway: direct
identifiers (name, MRN, ABHA, dates) are removed, ids are pseudonymised with a
keyed hash, ages > 89 are capped, and locations are generalised to state/country.
Analysts therefore work on real distributions without ever touching identifiable
PHI — the same separation real analytics teams operate under.

## Secrets hygiene

- `.env` is gitignored; only `.env.example` (no secrets) is tracked.
- No credentials, tokens or virtualenvs are committed.
- `MEDIGRAPH_SECRET_KEY` signs JWTs and seeds the de-identification hash — set a
  strong value in production (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).

> ⚠️ **Migration note.** The original prototype committed live Snowflake, Neo4j and
> OpenAI credentials to git. Treat any previously committed secret as compromised
> and **rotate it**.

## Hardening checklist for production

1. Replace demo `UserStore` with your enterprise IdP (OIDC/SAML/SMART-on-FHIR).
2. Terminate TLS at the edge; never expose the API over plain HTTP.
3. Set a strong `MEDIGRAPH_SECRET_KEY` and rotate periodically.
4. Ship the audit log to immutable storage / SIEM; alert on `denied` spikes.
5. Run least-privilege DB credentials; the LLM path is already read-only-guarded.
6. Sign a BAA (US) / follow ABDM data-fiduciary obligations (India) with each data source.
