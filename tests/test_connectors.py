"""Tests for the pluggable connector framework."""
from __future__ import annotations

import medigraph.connectors as C

HL7_ORU = (
    "MSH|^~\\&|LAB|HOSP|EHR|HOSP|20260601120000||ORU^R01|1|P|2.5\r"
    "PID|1||MRN999^^^HOSP||Roe^Jane||19550320|F|||10 Oak St^^Austin^TX^73301\r"
    "PV1|1|E\r"
    "DG1|1||I10^Essential hypertension^ICD-10\r"
    "OBX|1|NM|8480-6^Systolic blood pressure^LN||162|mmHg|||||F|||20260601"
)

CCD = (
    '<?xml version="1.0"?><ClinicalDocument xmlns="urn:hl7-org:v3"><recordTarget>'
    '<patientRole><id extension="CCD-1"/><patient><name><given>Ravi</given>'
    '<family>Kumar</family></name><administrativeGenderCode code="M"/></patient>'
    '<addr><city>Pune</city><state>MH</state></addr></patientRole></recordTarget>'
    '<component><structuredBody><component><section><code code="11450-4"/><entry>'
    '<observation><value code="44054006" displayName="Type 2 diabetes mellitus"/>'
    '</observation></entry></section></component></structuredBody></component></ClinicalDocument>'
)


def test_registry_has_core_connectors():
    keys = set(C.available_connectors())
    assert {"fhir", "hl7v2", "ccda", "csv"}.issubset(keys)


def test_catalog_covers_us_and_india():
    summary = C.catalog_summary()
    assert summary["total"] > 20
    assert summary["by_country"]["US"] > 5
    assert summary["by_country"]["IN"] > 5


def test_hl7v2_parses_oru():
    rec = C.get_connector("hl7v2").ingest(HL7_ORU)
    assert rec.patient.full_name == "Jane Roe"
    assert rec.patient.sex.value == "female"
    assert "htn" in rec.condition_keys
    assert any(o.code_key == "sbp" and o.value == 162 for o in rec.observations)
    assert rec.encounters[0].via_emergency is True


def test_ccda_parses_problems():
    rec = C.get_connector("ccda").ingest(CCD)
    assert rec.patient.full_name == "Ravi Kumar"
    assert rec.patient.city == "Pune"
    assert "t2dm" in rec.condition_keys


def test_fhir_offline_round_trip():
    fc = C.get_connector("fhir")
    assert "Offline" in fc.test_connection()
    rec = fc.fetch_all(limit=1)[0]
    bundle = fc.export(rec)
    assert bundle["resourceType"] == "Bundle"
