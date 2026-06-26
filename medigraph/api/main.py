"""MediGraph AI REST + FHIR API.

A documented FastAPI surface that exposes the same clinical core as the UI, so a
hospital can integrate MediGraph programmatically: pull a patient as FHIR, run
decision support, build cohorts, query analytics, ingest external bundles. Every
endpoint is authenticated (JWT), authorised by role (RBAC) and audited.

Run locally:
    uvicorn medigraph.api.main:app --reload
    # interactive docs at http://localhost:8000/docs
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from medigraph import __version__
from medigraph.config import get_settings
from medigraph.security import audit, decode_jwt, deidentify_record, login as do_login
from medigraph.security.rbac import Permission, Role, has_permission
from medigraph.services import get_engine
from medigraph.services.cohort import CohortCriteria

app = FastAPI(
    title="MediGraph AI API",
    version=__version__,
    description="Clinical knowledge-graph, decision-support, FHIR and analytics API.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
class CurrentUser(BaseModel):
    username: str
    role: Role
    name: str


def current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        claims = decode_jwt(creds.credentials)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc))
    return CurrentUser(username=claims["sub"], role=Role(claims["role"]), name=claims.get("name", ""))


def require(permission: Permission):
    def _dep(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not has_permission(user.role, permission):
            audit.record(user.username, user.role.value, "access_denied",
                         detail=permission.value, outcome="denied")
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Role '{user.role.value}' lacks permission '{permission.value}'")
        return user
    return _dep


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class QARequest(BaseModel):
    question: str


class NoteRequest(BaseModel):
    text: str


class CohortRequest(BaseModel):
    label: str = "API cohort"
    any_conditions: List[str] = []
    all_conditions: List[str] = []
    exclude_conditions: List[str] = []
    any_medications: List[str] = []
    without_medications: List[str] = []
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    sex: Optional[str] = None
    country: Optional[str] = None
    lab_filters: List[list] = []   # [["hba1c", ">=", 9.0], ...]


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": __version__}


@app.get("/meta", tags=["meta"])
def meta():
    s = get_settings()
    return {
        "app": s.app_name, "version": __version__, "organization": s.organization,
        "mode": s.mode_summary, "graph_live": s.graph_is_live, "llm_live": s.llm_is_live,
    }


@app.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(body: LoginRequest):
    token = do_login(body.username, body.password)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    audit.record(body.username, "?", "login", outcome="success")
    return TokenResponse(access_token=token)


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------
@app.get("/patients", tags=["patients"])
def list_patients(limit: int = 50, user: CurrentUser = Depends(current_user)):
    eng = get_engine()
    patients = eng.list_patients(limit=limit)
    can_phi = has_permission(user.role, Permission.VIEW_PHI)
    audit.record(user.username, user.role.value, "list_patients", detail=f"limit={limit}")
    if can_phi:
        return [p.model_dump() for p in patients]
    # de-identified summary for analyst/auditor
    out = []
    for p in patients:
        out.append({"id": "deid", "age": p.age, "sex": p.sex.value, "country": p.country})
    return out


@app.get("/patients/{patient_id}", tags=["patients"])
def get_patient(patient_id: str, user: CurrentUser = Depends(current_user)):
    eng = get_engine()
    rec = eng.record(patient_id)
    if not rec:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    if not has_permission(user.role, Permission.VIEW_PHI):
        rec = deidentify_record(rec)
        audit.record(user.username, user.role.value, "view_patient_deidentified",
                     resource=f"Patient/{patient_id}", patient_id=patient_id)
    else:
        audit.record(user.username, user.role.value, "view_patient",
                     resource=f"Patient/{patient_id}", patient_id=patient_id)
    return rec.model_dump()


@app.get("/patients/{patient_id}/assessment", tags=["decision-support"])
def assessment(patient_id: str, user: CurrentUser = Depends(require(Permission.RUN_DECISION_SUPPORT))):
    eng = get_engine()
    a = eng.assess(patient_id)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    audit.record(user.username, user.role.value, "run_decision_support",
                 resource=f"Patient/{patient_id}", patient_id=patient_id)
    return {
        "patient_id": a.patient_id, "patient_name": a.patient_name,
        "priority_score": a.priority_score,
        "risk_scores": [vars(s) for s in a.risk_scores],
        "care_gaps": [vars(g) for g in a.care_gaps],
        "interactions": [vars(i) for i in a.interactions],
    }


@app.get("/patients/{patient_id}/fhir", tags=["fhir"])
def patient_fhir(patient_id: str, user: CurrentUser = Depends(require(Permission.IMPORT_EXPORT))):
    eng = get_engine()
    bundle = eng.to_fhir(patient_id)
    if not bundle:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    audit.record(user.username, user.role.value, "export_fhir",
                 resource=f"Patient/{patient_id}", patient_id=patient_id)
    return bundle


@app.post("/fhir/import", tags=["fhir"])
def fhir_import(bundle: dict, user: CurrentUser = Depends(require(Permission.IMPORT_EXPORT))):
    eng = get_engine()
    try:
        rec = eng.import_fhir(bundle)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    audit.record(user.username, user.role.value, "import_fhir", resource=f"Patient/{rec.patient.id}")
    return {"imported_patient": rec.patient.full_name,
            "conditions": rec.condition_keys, "medications": rec.medication_keys}


# ---------------------------------------------------------------------------
# Analytics & cohorts
# ---------------------------------------------------------------------------
@app.get("/analytics/population", tags=["analytics"])
def analytics_population(user: CurrentUser = Depends(require(Permission.VIEW_ANALYTICS))):
    return get_engine().population_summary()


@app.get("/analytics/prevalence", tags=["analytics"])
def analytics_prevalence(user: CurrentUser = Depends(require(Permission.VIEW_ANALYTICS))):
    return get_engine().condition_prevalence().to_dict(orient="records")


@app.get("/analytics/quality", tags=["analytics"])
def analytics_quality(user: CurrentUser = Depends(require(Permission.VIEW_ANALYTICS))):
    return [{"name": m.name, "numerator": m.numerator, "denominator": m.denominator,
             "rate": m.rate, "description": m.description} for m in get_engine().quality_measures()]


@app.get("/analytics/risk", tags=["analytics"])
def analytics_risk(user: CurrentUser = Depends(require(Permission.VIEW_ANALYTICS))):
    return get_engine().risk_stratification()


@app.post("/cohort", tags=["analytics"])
def build_cohort(body: CohortRequest, user: CurrentUser = Depends(require(Permission.BUILD_COHORT))):
    criteria = CohortCriteria(
        any_conditions=body.any_conditions, all_conditions=body.all_conditions,
        exclude_conditions=body.exclude_conditions, any_medications=body.any_medications,
        without_medications=body.without_medications, min_age=body.min_age,
        max_age=body.max_age, sex=body.sex, country=body.country,
        lab_filters=[tuple(f) for f in body.lab_filters], label=body.label)
    res = get_engine().build_cohort(criteria)
    audit.record(user.username, user.role.value, "build_cohort", detail=body.label)
    return {"label": res.label, "size": res.size, "summary": res.summary(),
            "patient_ids": res.patient_ids[:200]}


# ---------------------------------------------------------------------------
# Q&A & NLP
# ---------------------------------------------------------------------------
@app.post("/qa", tags=["qa"])
def qa(body: QARequest, user: CurrentUser = Depends(require(Permission.RUN_QUERY))):
    res = get_engine().ask(body.question)
    audit.record(user.username, user.role.value, "run_query", detail=body.question[:120])
    return {"answer": res.answer, "intent": res.intent, "grounded": res.grounded,
            "citations": res.citations, "cypher": res.cypher,
            "data": res.data.to_dict(orient="records") if res.data is not None else None}


@app.post("/nlp/analyze", tags=["qa"])
def nlp_analyze(body: NoteRequest, user: CurrentUser = Depends(require(Permission.RUN_QUERY))):
    na = get_engine().analyze_note(body.text)
    return {
        "problems": [{"text": e.text, "code_system": e.code_system, "code": e.code} for e in na.problems],
        "medications": [{"text": e.text, "code": e.code} for e in na.medications],
        "negated": [{"text": e.text, "type": e.entity_type} for e in na.entities if e.negated],
        "linked_guidelines": na.linked_guidelines,
    }


# ---------------------------------------------------------------------------
# Connectors & graph
# ---------------------------------------------------------------------------
@app.get("/connectors", tags=["connectors"])
def connectors(user: CurrentUser = Depends(current_user)):
    from medigraph.connectors import connector_directory

    return connector_directory()


@app.get("/connectors/catalog", tags=["connectors"])
def connectors_catalog(country: Optional[str] = None, user: CurrentUser = Depends(current_user)):
    from medigraph.connectors import CATALOG, catalog_by_country

    entries = catalog_by_country(country) if country else CATALOG
    return [vars(e) for e in entries]


@app.get("/graph/stats", tags=["graph"])
def graph_stats(user: CurrentUser = Depends(current_user)):
    s = get_engine().stats()
    return {"node_counts": s.node_counts, "relationship_counts": s.relationship_counts,
            "total_nodes": s.total_nodes, "total_relationships": s.total_relationships}


@app.get("/audit", tags=["security"])
def audit_log(limit: int = 100, user: CurrentUser = Depends(require(Permission.VIEW_AUDIT))):
    return audit.read_events(limit=limit)


def run():  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run("medigraph.api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":  # pragma: no cover
    run()
