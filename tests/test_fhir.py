"""Tests for FHIR R4 import/export round-tripping."""
from __future__ import annotations

from medigraph.services import fhir
from medigraph.services import get_engine


def test_record_to_bundle_shape():
    rec = get_engine().all_records()[0]
    bundle = fhir.record_to_bundle(rec)
    assert bundle["resourceType"] == "Bundle"
    types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "Patient" in types


def test_round_trip_preserves_core_facts():
    eng = get_engine()
    rec = next(r for r in eng.all_records() if r.conditions and r.medications)
    bundle = fhir.record_to_bundle(rec)
    back = fhir.bundle_to_record(bundle)
    assert back.patient.full_name == rec.patient.full_name
    assert set(back.condition_keys) == set(rec.condition_keys)
    assert set(back.medication_keys) == set(rec.medication_keys)


def test_bundle_without_patient_raises():
    import pytest
    with pytest.raises(ValueError):
        fhir.bundle_to_record({"resourceType": "Bundle", "entry": []})
