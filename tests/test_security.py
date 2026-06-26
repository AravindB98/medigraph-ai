"""Tests for auth, RBAC, audit and de-identification."""
from __future__ import annotations

import pytest

from medigraph.security import (
    Permission,
    Role,
    decode_jwt,
    deidentify_record,
    encode_jwt,
    has_permission,
    hash_password,
    login,
    verify_password,
)
from medigraph.services import get_engine


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)


def test_jwt_encode_decode():
    tok = encode_jwt({"sub": "u", "role": "clinician", "name": "U"})
    claims = decode_jwt(tok)
    assert claims["sub"] == "u"


def test_jwt_tampered_rejected():
    tok = encode_jwt({"sub": "u", "role": "admin", "name": "U"})
    tampered = tok[:-2] + ("aa" if not tok.endswith("aa") else "bb")
    with pytest.raises(ValueError):
        decode_jwt(tampered)


def test_login_and_rbac():
    assert login("dr.house", "clinician123") is not None
    assert login("dr.house", "nope") is None
    assert has_permission(Role.clinician, Permission.VIEW_PHI)
    assert not has_permission(Role.analyst, Permission.VIEW_PHI)
    assert has_permission(Role.auditor, Permission.VIEW_AUDIT)


def test_deidentification_strips_phi():
    rec = get_engine().all_records()[0]
    d = deidentify_record(rec)
    assert d.patient.mrn is None
    assert d.patient.abha_id is None
    assert d.patient.id != rec.patient.id
    assert d.patient.full_name != rec.patient.full_name
