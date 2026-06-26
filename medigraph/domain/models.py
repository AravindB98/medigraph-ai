"""Canonical domain models (FHIR-aligned).

These Pydantic models are the *internal lingua franca* of MediGraph AI. Every
connector (FHIR, HL7 v2, C-CDA, CSV, Snowflake …) maps its source format into
these models, and every backend (embedded graph, Neo4j) stores them. Keeping a
single canonical model is what makes the platform vendor-neutral and pluggable.

The field names intentionally echo FHIR R4 resources so that import/export is a
thin, lossless mapping rather than a translation.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Sex(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"


class EncounterClass(str, Enum):
    ambulatory = "ambulatory"
    emergency = "emergency"
    inpatient = "inpatient"
    virtual = "virtual"
    wellness = "wellness"


class Provider(BaseModel):
    id: str
    name: str
    specialty: str = "General Practice"
    npi: Optional[str] = None          # US National Provider Identifier
    hpr_id: Optional[str] = None       # India Healthcare Professionals Registry
    organization: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"


class ConditionInstance(BaseModel):
    code_key: str                      # terminology key, e.g. "t2dm"
    name: str
    snomed: Optional[str] = None
    icd10: Optional[str] = None
    clinical_status: str = "active"    # active | resolved | inactive
    onset_date: Optional[date] = None


class MedicationInstance(BaseModel):
    code_key: str
    name: str
    rxnorm: Optional[str] = None
    drug_class: Optional[str] = None
    status: str = "active"             # active | stopped | completed
    start_date: Optional[date] = None


class ObservationInstance(BaseModel):
    code_key: str
    name: str
    loinc: Optional[str] = None
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    category: str = "laboratory"
    effective_datetime: Optional[datetime] = None
    encounter_id: Optional[str] = None
    interpretation: Optional[str] = None   # normal | high | low | critical


class Encounter(BaseModel):
    id: str
    encounter_class: EncounterClass = EncounterClass.ambulatory
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    provider_id: Optional[str] = None
    reason: Optional[str] = None
    length_of_stay_days: int = 0
    via_emergency: bool = False


class Patient(BaseModel):
    id: str
    full_name: str
    sex: Sex = Sex.unknown
    birth_date: Optional[date] = None
    age: Optional[int] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "US"
    # Standard health identifiers (kept separate so they can be de-identified).
    mrn: Optional[str] = None          # local medical record number
    abha_id: Optional[str] = None      # India — Ayushman Bharat Health Account
    primary_provider_id: Optional[str] = None


class PatientRecord(BaseModel):
    """Everything known about one patient — the unit connectors exchange."""

    patient: Patient
    conditions: List[ConditionInstance] = Field(default_factory=list)
    medications: List[MedicationInstance] = Field(default_factory=list)
    encounters: List[Encounter] = Field(default_factory=list)
    observations: List[ObservationInstance] = Field(default_factory=list)
    providers: List[Provider] = Field(default_factory=list)

    # Convenience accessors -------------------------------------------------
    @property
    def condition_keys(self) -> List[str]:
        return [c.code_key for c in self.conditions if c.clinical_status == "active"]

    @property
    def medication_keys(self) -> List[str]:
        return [m.code_key for m in self.medications if m.status == "active"]

    def latest_observation(self, code_key: str) -> Optional[ObservationInstance]:
        obs = [o for o in self.observations if o.code_key == code_key and o.value is not None]
        if not obs:
            return None
        return sorted(
            obs,
            key=lambda o: o.effective_datetime or datetime.min,
        )[-1]

    def ed_visits_last_6mo(self, as_of: Optional[datetime] = None) -> int:
        as_of = as_of or datetime.utcnow()
        count = 0
        for e in self.encounters:
            if e.via_emergency and e.start:
                delta_days = (as_of - e.start).days
                if 0 <= delta_days <= 183:
                    count += 1
        return count
