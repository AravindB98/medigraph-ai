"""Population-health & quality-measure analytics.

Aggregate views over the whole graph: disease prevalence, medication usage,
utilisation, HEDIS-flavoured quality measures and risk stratification. These are
the analytics a clinic/ACO needs for value-based-care reporting and panel
management.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import pandas as pd

from medigraph.domain import terminology as T
from medigraph.domain.models import PatientRecord
from medigraph.services import decision_support as ds


def population_summary(records: List[PatientRecord]) -> dict:
    ages = [r.patient.age for r in records if r.patient.age is not None]
    countries: dict[str, int] = {}
    sexes: dict[str, int] = {}
    for r in records:
        countries[r.patient.country] = countries.get(r.patient.country, 0) + 1
        sexes[r.patient.sex.value] = sexes.get(r.patient.sex.value, 0) + 1
    return {
        "patients": len(records),
        "mean_age": round(sum(ages) / len(ages), 1) if ages else None,
        "median_age": int(sorted(ages)[len(ages) // 2]) if ages else None,
        "country_split": countries,
        "sex_split": sexes,
        "avg_conditions": round(sum(len(r.conditions) for r in records) / max(1, len(records)), 2),
        "avg_medications": round(sum(len(r.medications) for r in records) / max(1, len(records)), 2),
    }


def condition_prevalence(records: List[PatientRecord]) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for r in records:
        for k in set(r.condition_keys):
            counts[k] = counts.get(k, 0) + 1
    n = max(1, len(records))
    rows = [
        {"condition": T.CONDITIONS[k].name if k in T.CONDITIONS else k,
         "icd10": T.CONDITIONS[k].icd10 if k in T.CONDITIONS else "",
         "patients": v, "prevalence_pct": round(100 * v / n, 1)}
        for k, v in counts.items()
    ]
    return pd.DataFrame(rows).sort_values("patients", ascending=False).reset_index(drop=True)


def medication_usage(records: List[PatientRecord]) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for r in records:
        for k in set(r.medication_keys):
            counts[k] = counts.get(k, 0) + 1
    rows = [
        {"medication": T.MEDICATIONS[k].name if k in T.MEDICATIONS else k,
         "drug_class": T.MEDICATIONS[k].drug_class if k in T.MEDICATIONS else "",
         "patients": v}
        for k, v in counts.items()
    ]
    return pd.DataFrame(rows).sort_values("patients", ascending=False).reset_index(drop=True)


def utilization(records: List[PatientRecord]) -> dict:
    classes: dict[str, int] = {}
    ed_visits = 0
    inpatient = 0
    for r in records:
        for e in r.encounters:
            cls = str(getattr(e.encounter_class, "value", e.encounter_class))
            classes[cls] = classes.get(cls, 0) + 1
            if e.via_emergency:
                ed_visits += 1
            if cls == "inpatient":
                inpatient += 1
    return {
        "total_encounters": sum(classes.values()),
        "encounter_classes": classes,
        "ed_visits": ed_visits,
        "inpatient_admissions": inpatient,
    }


@dataclass
class QualityMeasure:
    name: str
    numerator: int
    denominator: int
    description: str

    @property
    def rate(self) -> float:
        return round(100 * self.numerator / self.denominator, 1) if self.denominator else 0.0


def quality_measures(records: List[PatientRecord], as_of: Optional[datetime] = None) -> List[QualityMeasure]:
    as_of = as_of or datetime.utcnow()
    measures: List[QualityMeasure] = []

    # Diabetes HbA1c testing (any result within ~6 months)
    diabetics = [r for r in records if "t2dm" in r.condition_keys]
    a1c_tested = 0
    a1c_controlled = 0
    statin_in_dm = 0
    statin_eligible = 0
    for r in diabetics:
        obs = r.latest_observation("hba1c")
        if obs and obs.effective_datetime and (as_of - obs.effective_datetime).days <= ds.RECENT_DAYS:
            a1c_tested += 1
        if obs and obs.value is not None and obs.value < 8.0:
            a1c_controlled += 1
        age = r.patient.age or 0
        if 40 <= age <= 75:
            statin_eligible += 1
            if "atorvastatin" in r.medication_keys:
                statin_in_dm += 1
    if diabetics:
        measures.append(QualityMeasure("Diabetes: HbA1c tested (6 mo)", a1c_tested, len(diabetics),
                                       "Diabetic patients with a recent HbA1c result."))
        measures.append(QualityMeasure("Diabetes: HbA1c < 8% (control)", a1c_controlled, len(diabetics),
                                       "Diabetic patients with adequate glycaemic control."))
    if statin_eligible:
        measures.append(QualityMeasure("Diabetes: statin use (age 40–75)", statin_in_dm, statin_eligible,
                                       "Statin therapy in age-eligible diabetics."))

    # Hypertension control (<140/90)
    htn = [r for r in records if "htn" in r.condition_keys]
    bp_controlled = 0
    for r in htn:
        sbp = r.latest_observation("sbp")
        dbp = r.latest_observation("dbp")
        if sbp and sbp.value is not None and sbp.value < 140 and (dbp is None or (dbp.value or 0) < 90):
            bp_controlled += 1
    if htn:
        measures.append(QualityMeasure("Hypertension: BP < 140/90", bp_controlled, len(htn),
                                       "Hypertensive patients at goal blood pressure."))

    # CAD statin use
    cad = [r for r in records if "cad" in r.condition_keys]
    cad_statin = sum(1 for r in cad if "atorvastatin" in r.medication_keys)
    if cad:
        measures.append(QualityMeasure("ASCVD: statin therapy", cad_statin, len(cad),
                                       "Coronary-disease patients on a statin."))

    # AF anticoagulation when indicated
    af = [r for r in records if "afib" in r.condition_keys]
    af_indicated = 0
    af_treated = 0
    for r in af:
        vasc = ds.compute_cha2ds2vasc(r)
        if vasc and vasc.risk_band == "high":
            af_indicated += 1
            if set(r.medication_keys) & {"warfarin", "apixaban"}:
                af_treated += 1
    if af_indicated:
        measures.append(QualityMeasure("AF: anticoagulated when indicated", af_treated, af_indicated,
                                       "High-CHA₂DS₂-VASc AF patients on anticoagulation."))

    return measures


def risk_stratification(records: List[PatientRecord], as_of: Optional[datetime] = None) -> dict:
    as_of = as_of or datetime.utcnow()
    bands = {"high": 0, "moderate": 0, "low": 0}
    total_gaps = 0
    total_interactions = 0
    for r in records:
        a = ds.assess_patient(r, as_of=as_of)
        lace = next((s for s in a.risk_scores if s.name.startswith("LACE")), None)
        if lace:
            bands[lace.risk_band] = bands.get(lace.risk_band, 0) + 1
        total_gaps += len(a.care_gaps)
        total_interactions += len(a.interactions)
    return {
        "lace_bands": bands,
        "total_care_gaps": total_gaps,
        "total_interactions": total_interactions,
        "patients": len(records),
    }


def top_priority_patients(records: List[PatientRecord], as_of: Optional[datetime] = None,
                          limit: int = 15) -> pd.DataFrame:
    as_of = as_of or datetime.utcnow()
    rows = []
    for r in records:
        a = ds.assess_patient(r, as_of=as_of)
        if a.priority_score <= 0:
            continue
        rows.append({
            "patient_id": r.patient.id,
            "name": r.patient.full_name,
            "age": r.patient.age,
            "country": r.patient.country,
            "priority": round(a.priority_score, 1),
            "care_gaps": len(a.care_gaps),
            "interactions": len(a.interactions),
            "top_gap": a.care_gaps[0].title if a.care_gaps else "",
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("priority", ascending=False).head(limit).reset_index(drop=True)
