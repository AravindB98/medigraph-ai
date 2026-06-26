"""Shared pytest fixtures."""
from __future__ import annotations

from datetime import datetime

import pytest

from medigraph.domain.models import (
    ConditionInstance,
    Encounter,
    EncounterClass,
    MedicationInstance,
    ObservationInstance,
    Patient,
    PatientRecord,
    Provider,
    Sex,
)

AS_OF = datetime(2026, 6, 27, 9, 0)


def make_observation(code_key, name, loinc, value, unit, days_ago, category="laboratory"):
    return ObservationInstance(
        code_key=code_key, name=name, loinc=loinc, value=value, unit=unit,
        category=category, effective_datetime=datetime(2026, 6, 27) - __import__("datetime").timedelta(days=days_ago))


@pytest.fixture
def high_risk_af_patient() -> PatientRecord:
    """A 78-year-old with AF + multiple comorbidities, NOT anticoagulated:
    designed to trigger high CHA2DS2-VASc, an anticoagulation care gap and an
    interaction (aspirin + ... none here) deterministically."""
    patient = Patient(id="t-001", full_name="Test AFib", sex=Sex.female, age=78,
                      country="US", mrn="MRN-T001")
    conditions = [
        ConditionInstance(code_key="afib", name="Atrial fibrillation", snomed="49436004", icd10="I48.91"),
        ConditionInstance(code_key="htn", name="Essential hypertension", snomed="59621000", icd10="I10"),
        ConditionInstance(code_key="t2dm", name="Type 2 diabetes mellitus", snomed="44054006", icd10="E11.9"),
        ConditionInstance(code_key="chf", name="Heart failure", snomed="84114007", icd10="I50.9"),
    ]
    medications = [
        MedicationInstance(code_key="metformin", name="Metformin", rxnorm="6809"),
        MedicationInstance(code_key="furosemide", name="Furosemide", rxnorm="4603"),
    ]
    observations = [
        make_observation("hba1c", "Hemoglobin A1c", "4548-4", 9.4, "%", 30),
        make_observation("creatinine", "Serum creatinine", "2160-0", 1.1, "mg/dL", 30),
        make_observation("sbp", "Systolic blood pressure", "8480-6", 158, "mmHg", 10, "vital-signs"),
        make_observation("dbp", "Diastolic blood pressure", "8462-4", 94, "mmHg", 10, "vital-signs"),
    ]
    encounters = [
        Encounter(id="e1", encounter_class=EncounterClass.inpatient, length_of_stay_days=8,
                  via_emergency=True, start=datetime(2026, 5, 1)),
    ]
    return PatientRecord(patient=patient, conditions=conditions, medications=medications,
                         observations=observations, encounters=encounters,
                         providers=[Provider(id="p1", name="Dr. Test", specialty="Cardiology")])


@pytest.fixture
def interaction_patient() -> PatientRecord:
    patient = Patient(id="t-002", full_name="Test Interaction", sex=Sex.male, age=70, country="US")
    conditions = [ConditionInstance(code_key="afib", name="Atrial fibrillation", snomed="49436004", icd10="I48.91")]
    medications = [
        MedicationInstance(code_key="warfarin", name="Warfarin", rxnorm="11289"),
        MedicationInstance(code_key="aspirin", name="Aspirin", rxnorm="1191"),
    ]
    return PatientRecord(patient=patient, conditions=conditions, medications=medications)
