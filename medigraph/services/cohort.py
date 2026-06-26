"""Cohort builder.

Turns a set of inclusion/exclusion criteria into a concrete patient cohort —
the basic building block for population health, quality reporting, registries and
clinical-trial pre-screening. Criteria compose graph facts (conditions,
medications, demographics) with the latest lab/vital values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from medigraph.domain.models import PatientRecord


@dataclass
class CohortCriteria:
    any_conditions: List[str] = field(default_factory=list)      # match if ANY present
    all_conditions: List[str] = field(default_factory=list)      # match if ALL present
    exclude_conditions: List[str] = field(default_factory=list)
    any_medications: List[str] = field(default_factory=list)
    without_medications: List[str] = field(default_factory=list)
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    sex: Optional[str] = None
    country: Optional[str] = None
    # Lab/vital filters: (code_key, operator, threshold), operator in {">=","<=",">","<"}
    lab_filters: List[tuple] = field(default_factory=list)
    label: str = "Custom cohort"


@dataclass
class CohortResult:
    label: str
    patient_ids: List[str]
    records: List[PatientRecord]
    size: int

    def summary(self) -> dict:
        ages = [r.patient.age for r in self.records if r.patient.age is not None]
        female = sum(1 for r in self.records if r.patient.sex.value == "female")
        return {
            "size": self.size,
            "mean_age": round(sum(ages) / len(ages), 1) if ages else None,
            "female_pct": round(100 * female / self.size, 1) if self.size else 0,
        }


_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
}


def _matches(record: PatientRecord, c: CohortCriteria) -> bool:
    conds = set(record.condition_keys)
    meds = set(record.medication_keys)
    p = record.patient

    if c.all_conditions and not set(c.all_conditions).issubset(conds):
        return False
    if c.any_conditions and not (set(c.any_conditions) & conds):
        return False
    if c.exclude_conditions and (set(c.exclude_conditions) & conds):
        return False
    if c.any_medications and not (set(c.any_medications) & meds):
        return False
    if c.without_medications and (set(c.without_medications) & meds):
        return False
    if c.min_age is not None and (p.age is None or p.age < c.min_age):
        return False
    if c.max_age is not None and (p.age is None or p.age > c.max_age):
        return False
    if c.sex and p.sex.value != c.sex:
        return False
    if c.country and p.country != c.country:
        return False
    for code_key, op, threshold in c.lab_filters:
        obs = record.latest_observation(code_key)
        if obs is None or obs.value is None:
            return False
        if not _OPS.get(op, lambda a, b: False)(obs.value, threshold):
            return False
    return True


def build_cohort(records: List[PatientRecord], criteria: CohortCriteria) -> CohortResult:
    matched = [r for r in records if _matches(r, criteria)]
    return CohortResult(
        label=criteria.label,
        patient_ids=[r.patient.id for r in matched],
        records=matched,
        size=len(matched))


# A few ready-made registries for the demo / common workflows.
def preset_registries() -> dict[str, CohortCriteria]:
    return {
        "Diabetes registry": CohortCriteria(any_conditions=["t2dm"], label="Diabetes registry"),
        "Uncontrolled diabetes (HbA1c ≥ 9)": CohortCriteria(
            any_conditions=["t2dm"], lab_filters=[("hba1c", ">=", 9.0)],
            label="Uncontrolled diabetes (HbA1c ≥ 9)"),
        "Hypertension, uncontrolled (SBP ≥ 140)": CohortCriteria(
            any_conditions=["htn"], lab_filters=[("sbp", ">=", 140.0)],
            label="Hypertension, uncontrolled (SBP ≥ 140)"),
        "Atrial fibrillation, no anticoagulant": CohortCriteria(
            any_conditions=["afib"], without_medications=["warfarin", "apixaban"],
            label="Atrial fibrillation, no anticoagulant"),
        "ASCVD without statin": CohortCriteria(
            any_conditions=["cad"], without_medications=["atorvastatin"],
            label="ASCVD without statin"),
        "CKD stage 3+ (eGFR < 60)": CohortCriteria(
            any_conditions=["ckd"], lab_filters=[("egfr", "<", 60.0)],
            label="CKD stage 3+ (eGFR < 60)"),
    }
