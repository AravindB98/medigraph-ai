"""Tests for the FastAPI surface, including RBAC enforcement."""
from __future__ import annotations

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")
from fastapi.testclient import TestClient  # noqa: E402

from medigraph.api.main import app  # noqa: E402

client = TestClient(app)


def _token(username, password):
    return client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]


def _auth(username, password):
    return {"Authorization": f"Bearer {_token(username, password)}"}


def test_health_and_meta():
    assert client.get("/health").json()["status"] == "ok"
    assert "mode" in client.get("/meta").json()


def test_login_required():
    assert client.get("/patients").status_code == 401


def test_clinician_sees_phi():
    h = _auth("dr.house", "clinician123")
    patients = client.get("/patients?limit=3", headers=h).json()
    assert "full_name" in patients[0]


def test_analyst_denied_decision_support_and_phi():
    h = _auth("analyst.sam", "analyst123")
    pid = client.get("/patients?limit=1", headers=_auth("dr.house", "clinician123")).json()[0]["id"]
    assert client.get(f"/patients/{pid}/assessment", headers=h).status_code == 403
    body = client.get(f"/patients/{pid}", headers=h).json()
    assert body["patient"]["mrn"] is None  # de-identified


def test_cohort_and_qa():
    h = _auth("dr.house", "clinician123")
    cohort = client.post("/cohort", json={"any_conditions": ["t2dm"], "label": "DM"}, headers=h).json()
    assert cohort["size"] >= 0
    qa = client.post("/qa", json={"question": "most common conditions"}, headers=h).json()
    assert qa["grounded"] is True


def test_auditor_can_read_audit_clinician_cannot():
    assert client.get("/audit", headers=_auth("auditor.lee", "auditor123")).status_code == 200
    assert client.get("/audit", headers=_auth("dr.house", "clinician123")).status_code == 403
