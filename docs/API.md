# REST + FHIR API

A FastAPI surface that exposes the same clinical core as the UI. Every endpoint is
authenticated with a JWT and authorised by role (RBAC); patient access and queries
are audited. Interactive OpenAPI docs are served at **`/docs`**.

```bash
uvicorn medigraph.api.main:app --reload   # http://localhost:8000/docs
```

## Authentication

```bash
# 1) get a token (demo users: clinician/nurse/analyst/admin/auditor; pwd = role+123)
curl -s -X POST localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"dr.house","password":"clinician123"}'
# → {"access_token":"<jwt>","token_type":"bearer"}

# 2) call protected endpoints
curl localhost:8000/patients -H "Authorization: Bearer <jwt>"
```

## Endpoints

| Method & path | Permission | Description |
|---|---|---|
| `GET /health` | public | Liveness + version |
| `GET /meta` | public | Mode summary (offline/live) |
| `POST /auth/login` | public | Exchange credentials for a JWT |
| `GET /patients?limit=` | any auth | List patients (de-identified if no PHI permission) |
| `GET /patients/{id}` | any auth | Patient record (de-identified without `view_phi`) |
| `GET /patients/{id}/assessment` | `run_decision_support` | Risk scores, care gaps, interactions |
| `GET /patients/{id}/fhir` | `import_export` | Export FHIR R4 Bundle |
| `POST /fhir/import` | `import_export` | Ingest a FHIR Bundle |
| `POST /cohort` | `build_cohort` | Build a cohort from criteria |
| `GET /analytics/population` | `view_analytics` | Demographics & averages |
| `GET /analytics/prevalence` | `view_analytics` | Condition prevalence |
| `GET /analytics/quality` | `view_analytics` | HEDIS-style quality measures |
| `GET /analytics/risk` | `view_analytics` | LACE risk stratification |
| `POST /qa` | `run_query` | Grounded GraphRAG answer (+ citations) |
| `POST /nlp/analyze` | `run_query` | Note → entities, negation, guidelines |
| `GET /connectors` | any auth | Registered connectors |
| `GET /connectors/catalog?country=` | any auth | Supported systems (US/IN/Global) |
| `GET /graph/stats` | any auth | Node/relationship counts |
| `GET /audit?limit=` | `view_audit` | Audit trail |

## Examples

```bash
# Decision support
curl localhost:8000/patients/pat-0001/assessment -H "Authorization: Bearer $T"

# Cohort: AF patients not on an anticoagulant
curl -X POST localhost:8000/cohort -H "Authorization: Bearer $T" \
  -H 'content-type: application/json' \
  -d '{"any_conditions":["afib"],"without_medications":["warfarin","apixaban"],"label":"AF no AC"}'

# Grounded Q&A
curl -X POST localhost:8000/qa -H "Authorization: Bearer $T" \
  -H 'content-type: application/json' \
  -d '{"question":"most common conditions"}'

# FHIR export
curl localhost:8000/patients/pat-0001/fhir -H "Authorization: Bearer $T"
```

## RBAC behaviour

The same endpoint adapts to the caller's role. For `GET /patients/{id}`:
a **clinician** receives full PHI; an **analyst** receives a de-identified record
(no MRN/ABHA, generalised location, pseudonymous id). Calling
`/patients/{id}/assessment` as an analyst returns **403** (lacks
`run_decision_support`); calling `/audit` as a clinician returns **403** (lacks
`view_audit`). See [SECURITY.md](SECURITY.md).
