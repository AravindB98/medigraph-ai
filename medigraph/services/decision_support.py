"""Clinical decision support.

Implements transparent, *citable* clinical instruments over a PatientRecord:

- **eGFR (CKD-EPI 2021, race-free)** and CKD G-staging
- **LACE index** — 30-day readmission risk
- **CHA₂DS₂-VASc** — stroke risk in atrial fibrillation
- **HAS-BLED** — bleeding risk on anticoagulation
- **Care-gap detection** — evidence-based guideline gaps
- **Drug–drug interaction** screening

Every score is rule-based and explainable (no black box), which is exactly what
clinicians and regulators expect from decision-support software. Scores are
advisory only — see the clinical-use disclaimer in LICENSE.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from medigraph.domain import terminology as T
from medigraph.domain.models import PatientRecord


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class RiskScore:
    name: str
    score: float
    risk_band: str
    interpretation: str
    components: dict = field(default_factory=dict)
    unit: str = ""


@dataclass
class CareGap:
    title: str
    severity: str           # high | moderate | low
    detail: str
    recommendation: str
    guideline: str
    condition_key: Optional[str] = None


@dataclass
class InteractionAlert:
    drug_a: str
    drug_b: str
    severity: str
    mechanism: str
    management: str


@dataclass
class PatientAssessment:
    patient_id: str
    patient_name: str
    risk_scores: List[RiskScore] = field(default_factory=list)
    care_gaps: List[CareGap] = field(default_factory=list)
    interactions: List[InteractionAlert] = field(default_factory=list)

    @property
    def priority_score(self) -> float:
        """A simple composite to rank patients for outreach (higher = more urgent)."""
        sev_weight = {"high": 3, "moderate": 2, "low": 1}
        gap = sum(sev_weight.get(g.severity, 1) for g in self.care_gaps)
        ix = sum(3 if i.severity in ("major", "contraindicated") else 1 for i in self.interactions)
        risk = sum(1 for r in self.risk_scores if r.risk_band == "high")
        return gap + ix + 2 * risk


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _latest_value(record: PatientRecord, code_key: str) -> Optional[float]:
    obs = record.latest_observation(code_key)
    return obs.value if obs else None


def _latest_dt(record: PatientRecord, code_key: str) -> Optional[datetime]:
    obs = record.latest_observation(code_key)
    return obs.effective_datetime if obs else None


def _days_since(dt: Optional[datetime], as_of: datetime) -> Optional[int]:
    if dt is None:
        return None
    return (as_of - dt).days


# ---------------------------------------------------------------------------
# eGFR / CKD
# ---------------------------------------------------------------------------
def egfr_ckd_epi_2021(creatinine: float, age: int, sex: str) -> float:
    """2021 CKD-EPI creatinine equation (race-free). Returns mL/min/1.73m²."""
    female = sex == "female"
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302
    scr_k = creatinine / kappa
    egfr = (
        142
        * (min(scr_k, 1) ** alpha)
        * (max(scr_k, 1) ** -1.200)
        * (0.9938 ** age)
        * (1.012 if female else 1.0)
    )
    return egfr


def ckd_stage(egfr: float) -> str:
    if egfr >= 90:
        return "G1 (normal)"
    if egfr >= 60:
        return "G2 (mild)"
    if egfr >= 45:
        return "G3a (mild–moderate)"
    if egfr >= 30:
        return "G3b (moderate–severe)"
    if egfr >= 15:
        return "G4 (severe)"
    return "G5 (kidney failure)"


def compute_egfr(record: PatientRecord) -> Optional[RiskScore]:
    cr = _latest_value(record, "creatinine")
    age = record.patient.age
    if cr is None or age is None:
        return None
    egfr = egfr_ckd_epi_2021(cr, age, record.patient.sex.value)
    stage = ckd_stage(egfr)
    band = "high" if egfr < 45 else ("moderate" if egfr < 60 else "low")
    return RiskScore(
        name="eGFR (CKD-EPI 2021)", score=round(egfr, 1), risk_band=band,
        interpretation=f"CKD stage {stage}", unit="mL/min/1.73m²",
        components={"serum_creatinine": cr, "age": age, "sex": record.patient.sex.value})


# ---------------------------------------------------------------------------
# LACE readmission index
# ---------------------------------------------------------------------------
def _lace_los_points(los: int) -> int:
    if los <= 0:
        return 0
    if los == 1:
        return 1
    if los == 2:
        return 2
    if los == 3:
        return 3
    if los <= 6:
        return 4
    if los <= 13:
        return 5
    return 7


def compute_lace(record: PatientRecord, as_of: datetime) -> RiskScore:
    inpatient = [e for e in record.encounters if str(getattr(e.encounter_class, "value", e.encounter_class)) == "inpatient"]
    los = max((e.length_of_stay_days for e in inpatient), default=0)
    L = _lace_los_points(los)
    A = 3 if any(e.via_emergency for e in record.encounters) else 0
    charlson = sum(T.CONDITIONS[k].charlson_weight for k in record.condition_keys if k in T.CONDITIONS)
    C = min(charlson, 5)
    E = min(record.ed_visits_last_6mo(as_of), 4)
    total = L + A + C + E
    band = "high" if total >= 10 else ("moderate" if total >= 5 else "low")
    return RiskScore(
        name="LACE readmission index", score=total, risk_band=band,
        interpretation=(
            "High 30-day readmission risk — prioritise discharge planning & follow-up"
            if band == "high" else
            "Moderate readmission risk" if band == "moderate" else "Low readmission risk"),
        components={"L_length_of_stay": L, "A_acute_admission": A,
                    "C_comorbidity": C, "E_ed_visits_6mo": E})


# ---------------------------------------------------------------------------
# CHA2DS2-VASc (only meaningful in atrial fibrillation)
# ---------------------------------------------------------------------------
def compute_cha2ds2vasc(record: PatientRecord) -> Optional[RiskScore]:
    if "afib" not in record.condition_keys:
        return None
    conds = set(record.condition_keys)
    age = record.patient.age or 0
    female = record.patient.sex.value == "female"
    comp = {
        "C_chf": 1 if "chf" in conds else 0,
        "H_hypertension": 1 if "htn" in conds else 0,
        "A2_age>=75": 2 if age >= 75 else 0,
        "D_diabetes": 1 if "t2dm" in conds else 0,
        "S2_stroke": 2 if "stroke" in conds else 0,
        "V_vascular": 1 if "cad" in conds else 0,
        "A_age65-74": 1 if 65 <= age <= 74 else 0,
        "Sc_female": 1 if female else 0,
    }
    score = sum(comp.values())
    threshold = 3 if female else 2
    high = score >= threshold
    return RiskScore(
        name="CHA₂DS₂-VASc", score=score, risk_band="high" if high else "low",
        interpretation=(
            f"Score ≥{threshold}: oral anticoagulation recommended"
            if high else "Anticoagulation may not be required"),
        components=comp)


# ---------------------------------------------------------------------------
# HAS-BLED (bleeding risk)
# ---------------------------------------------------------------------------
def compute_hasbled(record: PatientRecord, egfr: Optional[float]) -> Optional[RiskScore]:
    if "afib" not in record.condition_keys:
        return None
    conds = set(record.condition_keys)
    meds = set(record.medication_keys)
    age = record.patient.age or 0
    sbp = _latest_value(record, "sbp")
    comp = {
        "H_uncontrolled_htn": 1 if (sbp is not None and sbp > 160) else 0,
        "A_abnormal_renal": 1 if ("ckd" in conds or (egfr is not None and egfr < 30)) else 0,
        "S_stroke": 1 if "stroke" in conds else 0,
        "L_labile_inr": 1 if ("warfarin" in meds) else 0,
        "E_elderly>65": 1 if age > 65 else 0,
        "D_drugs": 1 if (meds & {"aspirin", "clopidogrel"}) else 0,
    }
    score = sum(comp.values())
    high = score >= 3
    return RiskScore(
        name="HAS-BLED", score=score, risk_band="high" if high else "low",
        interpretation=(
            "High bleeding risk — address modifiable factors, do not withhold anticoagulation reflexively"
            if high else "Acceptable bleeding risk"),
        components=comp)


# ---------------------------------------------------------------------------
# Care gaps
# ---------------------------------------------------------------------------
RECENT_DAYS = 183  # ~6 months


def detect_care_gaps(record: PatientRecord, as_of: datetime, egfr: Optional[float]) -> List[CareGap]:
    conds = set(record.condition_keys)
    meds = set(record.medication_keys)
    age = record.patient.age or 0
    gaps: List[CareGap] = []

    # Diabetes: HbA1c monitoring & control
    if "t2dm" in conds:
        a1c = _latest_value(record, "hba1c")
        a1c_age = _days_since(_latest_dt(record, "hba1c"), as_of)
        if a1c is None or a1c_age is None or a1c_age > RECENT_DAYS:
            gaps.append(CareGap(
                "HbA1c overdue", "moderate",
                "No HbA1c result in the last 6 months." if a1c_age is None or a1c_age > RECENT_DAYS
                else "No HbA1c on record.",
                "Order HbA1c; ADA recommends at least twice-yearly testing.",
                "ADA Standards of Care", "t2dm"))
        elif a1c >= 9.0:
            gaps.append(CareGap(
                "Uncontrolled diabetes", "high",
                f"Most recent HbA1c is {a1c:.1f}% (target <7%).",
                "Intensify therapy and arrange close follow-up.",
                "ADA Standards of Care", "t2dm"))
        if 40 <= age <= 75 and "atorvastatin" not in meds:
            gaps.append(CareGap(
                "Statin not prescribed (diabetes)", "moderate",
                "Adult 40–75 with diabetes is not on a statin.",
                "Consider moderate-intensity statin for ASCVD prevention.",
                "ADA / ACC", "t2dm"))

    # Hypertension control
    if "htn" in conds:
        sbp = _latest_value(record, "sbp")
        dbp = _latest_value(record, "dbp")
        if sbp is not None and (sbp >= 140 or (dbp is not None and dbp >= 90)):
            gaps.append(CareGap(
                "Uncontrolled hypertension", "high",
                f"Most recent BP {sbp:.0f}/{(dbp or 0):.0f} mmHg (target <130/80).",
                "Intensify antihypertensive therapy; reinforce lifestyle measures.",
                "ACC/AHA 2017", "htn"))

    # ASCVD / CAD secondary prevention
    if "cad" in conds:
        if "atorvastatin" not in meds:
            gaps.append(CareGap(
                "Statin not prescribed (ASCVD)", "high",
                "Patient with coronary artery disease is not on a statin.",
                "Start high-intensity statin for secondary prevention.",
                "ACC/AHA", "cad"))
        if not (meds & {"aspirin", "clopidogrel"}):
            gaps.append(CareGap(
                "Antiplatelet not prescribed (ASCVD)", "moderate",
                "No antiplatelet therapy recorded for established CAD.",
                "Consider aspirin or clopidogrel unless contraindicated.",
                "ACC/AHA", "cad"))

    # Atrial fibrillation anticoagulation
    if "afib" in conds:
        vasc = compute_cha2ds2vasc(record)
        anticoagulated = bool(meds & {"warfarin", "apixaban"})
        if vasc and vasc.risk_band == "high" and not anticoagulated:
            gaps.append(CareGap(
                "Anticoagulation gap (atrial fibrillation)", "high",
                f"CHA₂DS₂-VASc {int(vasc.score)} but no oral anticoagulant on record.",
                "Assess for oral anticoagulation to reduce stroke risk.",
                "CHEST / ESC", "afib"))

    # Heart failure GDMT
    if "chf" in conds:
        if not (meds & {"lisinopril", "losartan"}):
            gaps.append(CareGap(
                "HF therapy gap (RAAS)", "moderate",
                "Heart failure without ACE inhibitor/ARB on record.",
                "Initiate guideline-directed medical therapy if tolerated.",
                "ACC/AHA/HFSA", "chf"))

    # CKD nephroprotection & monitoring
    if "ckd" in conds:
        if not (meds & {"lisinopril", "losartan"}):
            gaps.append(CareGap(
                "Nephroprotection gap", "moderate",
                "CKD without ACE inhibitor/ARB on record.",
                "Consider ACEi/ARB for proteinuria; monitor K⁺ and eGFR.",
                "KDIGO", "ckd"))
        egfr_age = _days_since(_latest_dt(record, "egfr") or _latest_dt(record, "creatinine"), as_of)
        if egfr_age is None or egfr_age > RECENT_DAYS:
            gaps.append(CareGap(
                "Renal monitoring overdue", "low",
                "No recent creatinine/eGFR for a CKD patient.",
                "Recheck renal function and electrolytes.",
                "KDIGO", "ckd"))

    return gaps


def detect_interactions(record: PatientRecord) -> List[InteractionAlert]:
    hits = T.find_interactions(record.medication_keys)
    out = []
    for ix in hits:
        out.append(InteractionAlert(
            drug_a=T.MEDICATIONS[ix.a].name, drug_b=T.MEDICATIONS[ix.b].name,
            severity=ix.severity, mechanism=ix.mechanism, management=ix.management))
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def assess_patient(record: PatientRecord, as_of: Optional[datetime] = None) -> PatientAssessment:
    as_of = as_of or datetime.utcnow()
    egfr_score = compute_egfr(record)
    egfr_val = egfr_score.score if egfr_score else None

    scores: List[RiskScore] = [compute_lace(record, as_of)]
    if egfr_score:
        scores.append(egfr_score)
    vasc = compute_cha2ds2vasc(record)
    if vasc:
        scores.append(vasc)
    bled = compute_hasbled(record, egfr_val)
    if bled:
        scores.append(bled)

    return PatientAssessment(
        patient_id=record.patient.id,
        patient_name=record.patient.full_name,
        risk_scores=scores,
        care_gaps=detect_care_gaps(record, as_of, egfr_val),
        interactions=detect_interactions(record))
