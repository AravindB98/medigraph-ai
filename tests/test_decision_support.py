"""Tests for clinical decision support — deterministic, known-answer cases."""
from __future__ import annotations

from medigraph.services import decision_support as ds
from tests.conftest import AS_OF


def test_egfr_ckd_epi_known_value():
    # 70y female, Scr 1.1 -> ~50s mL/min/1.73m2 (CKD-EPI 2021)
    egfr = ds.egfr_ckd_epi_2021(creatinine=1.1, age=70, sex="female")
    assert 45 < egfr < 65
    assert ds.ckd_stage(50).startswith("G3a")
    assert ds.ckd_stage(95).startswith("G1")
    assert ds.ckd_stage(10).startswith("G5")


def test_cha2ds2vasc_high(high_risk_af_patient):
    score = ds.compute_cha2ds2vasc(high_risk_af_patient)
    # CHF(1)+HTN(1)+age>=75(2)+DM(1)+female(1) = 6
    assert score is not None
    assert score.score == 6
    assert score.risk_band == "high"


def test_cha2ds2vasc_none_without_afib(interaction_patient):
    interaction_patient.conditions = [c for c in interaction_patient.conditions if c.code_key != "afib"]
    assert ds.compute_cha2ds2vasc(interaction_patient) is None


def test_lace_high_for_long_emergent_stay(high_risk_af_patient):
    lace = ds.compute_lace(high_risk_af_patient, as_of=AS_OF)
    # LOS 8 -> 5, emergent -> 3, comorbidity capped, ED visit recent
    assert lace.score >= 10
    assert lace.risk_band == "high"


def test_anticoagulation_care_gap(high_risk_af_patient):
    a = ds.assess_patient(high_risk_af_patient, as_of=AS_OF)
    titles = [g.title for g in a.care_gaps]
    assert any("Anticoagulation gap" in t for t in titles)
    assert any("Uncontrolled diabetes" in t for t in titles)
    assert any("Uncontrolled hypertension" in t for t in titles)


def test_drug_interaction_detected(interaction_patient):
    alerts = ds.detect_interactions(interaction_patient)
    pairs = {(a.drug_a, a.drug_b) for a in alerts}
    assert ("Warfarin", "Aspirin") in pairs
    assert alerts[0].severity in ("major", "contraindicated", "moderate")


def test_priority_score_positive(high_risk_af_patient):
    a = ds.assess_patient(high_risk_af_patient, as_of=AS_OF)
    assert a.priority_score > 0
