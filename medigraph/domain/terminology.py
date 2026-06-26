"""Clinical terminology & knowledge base.

This module is the *clinical brain* of MediGraph AI. It encodes a curated subset
of standard healthcare vocabularies and clinical rules so that decision support,
care-gap detection, NLP and analytics are grounded in recognisable codes rather
than ad-hoc strings.

Code systems referenced (industry standard, used in both the US and India):
- **SNOMED CT**  — clinical conditions/findings
- **ICD-10-CM**  — diagnoses / billing
- **RxNorm**     — medications
- **LOINC**      — labs & observations
- **ATC**        — drug classes

All codes below are real, well-known identifiers included for realism and
interoperability demonstrations. They are a teaching subset, not an exhaustive
terminology service.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConditionDef:
    key: str
    name: str
    snomed: str
    icd10: str
    category: str
    # Higher = contributes more to comorbidity burden (Charlson-flavoured weight).
    charlson_weight: int = 0
    synonyms: List[str] = field(default_factory=list)


CONDITIONS: Dict[str, ConditionDef] = {
    c.key: c
    for c in [
        ConditionDef("t2dm", "Type 2 diabetes mellitus", "44054006", "E11.9",
                     "endocrine", 1, ["diabetes", "type 2 diabetes", "t2dm", "dm2", "diabetic"]),
        ConditionDef("htn", "Essential hypertension", "59621000", "I10",
                     "cardiovascular", 0, ["hypertension", "high blood pressure", "htn"]),
        ConditionDef("hld", "Hyperlipidemia", "55822004", "E78.5",
                     "cardiovascular", 0, ["hyperlipidemia", "high cholesterol", "dyslipidemia"]),
        ConditionDef("ckd", "Chronic kidney disease", "709044004", "N18.9",
                     "renal", 2, ["chronic kidney disease", "ckd", "renal insufficiency"]),
        ConditionDef("cad", "Coronary artery disease", "53741008", "I25.10",
                     "cardiovascular", 1, ["coronary artery disease", "cad", "ischemic heart disease"]),
        ConditionDef("afib", "Atrial fibrillation", "49436004", "I48.91",
                     "cardiovascular", 1, ["atrial fibrillation", "afib", "a-fib"]),
        ConditionDef("chf", "Heart failure", "84114007", "I50.9",
                     "cardiovascular", 1, ["heart failure", "chf", "congestive heart failure"]),
        ConditionDef("copd", "Chronic obstructive pulmonary disease", "13645005", "J44.9",
                     "respiratory", 1, ["copd", "chronic obstructive pulmonary disease", "emphysema"]),
        ConditionDef("asthma", "Asthma", "195967001", "J45.909",
                     "respiratory", 0, ["asthma", "reactive airway disease"]),
        ConditionDef("obesity", "Obesity", "414916001", "E66.9",
                     "endocrine", 0, ["obesity", "obese"]),
        ConditionDef("depression", "Major depressive disorder", "370143000", "F32.9",
                     "behavioral", 0, ["depression", "mdd", "major depressive disorder"]),
        ConditionDef("hypothyroid", "Hypothyroidism", "40930008", "E03.9",
                     "endocrine", 0, ["hypothyroidism", "underactive thyroid"]),
        ConditionDef("oa", "Osteoarthritis", "396275006", "M19.90",
                     "musculoskeletal", 0, ["osteoarthritis", "oa", "degenerative joint disease"]),
        ConditionDef("stroke", "History of stroke", "230690007", "I63.9",
                     "cardiovascular", 2, ["stroke", "cva", "cerebrovascular accident", "tia"]),
        ConditionDef("anemia", "Anemia", "271737000", "D64.9",
                     "hematologic", 0, ["anemia", "low hemoglobin"]),
    ]
}


# ---------------------------------------------------------------------------
# Medications
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MedicationDef:
    key: str
    name: str
    rxnorm: str
    atc_class: str
    drug_class: str
    treats: List[str] = field(default_factory=list)   # condition keys
    synonyms: List[str] = field(default_factory=list)


MEDICATIONS: Dict[str, MedicationDef] = {
    m.key: m
    for m in [
        MedicationDef("metformin", "Metformin", "6809", "A10BA02", "biguanide",
                      ["t2dm"], ["metformin", "glucophage"]),
        MedicationDef("insulin_glargine", "Insulin glargine", "274783", "A10AE04", "insulin",
                      ["t2dm"], ["insulin glargine", "lantus", "basaglar"]),
        MedicationDef("lisinopril", "Lisinopril", "29046", "C09AA03", "ACE inhibitor",
                      ["htn", "chf", "ckd"], ["lisinopril", "prinivil", "zestril"]),
        MedicationDef("losartan", "Losartan", "52175", "C09CA01", "ARB",
                      ["htn", "ckd"], ["losartan", "cozaar"]),
        MedicationDef("amlodipine", "Amlodipine", "17767", "C08CA01", "calcium channel blocker",
                      ["htn"], ["amlodipine", "norvasc"]),
        MedicationDef("hctz", "Hydrochlorothiazide", "5487", "C03AA03", "thiazide diuretic",
                      ["htn"], ["hydrochlorothiazide", "hctz", "microzide"]),
        MedicationDef("metoprolol", "Metoprolol", "6918", "C07AB02", "beta blocker",
                      ["htn", "cad", "afib", "chf"], ["metoprolol", "lopressor", "toprol"]),
        MedicationDef("atorvastatin", "Atorvastatin", "83367", "C10AA05", "statin",
                      ["hld", "cad"], ["atorvastatin", "lipitor"]),
        MedicationDef("aspirin", "Aspirin", "1191", "B01AC06", "antiplatelet",
                      ["cad", "stroke"], ["aspirin", "asa", "acetylsalicylic acid"]),
        MedicationDef("clopidogrel", "Clopidogrel", "32968", "B01AC04", "antiplatelet",
                      ["cad", "stroke"], ["clopidogrel", "plavix"]),
        MedicationDef("warfarin", "Warfarin", "11289", "B01AA03", "anticoagulant",
                      ["afib", "stroke"], ["warfarin", "coumadin"]),
        MedicationDef("apixaban", "Apixaban", "1364430", "B01AF02", "anticoagulant",
                      ["afib", "stroke"], ["apixaban", "eliquis"]),
        MedicationDef("furosemide", "Furosemide", "4603", "C03CA01", "loop diuretic",
                      ["chf"], ["furosemide", "lasix"]),
        MedicationDef("spironolactone", "Spironolactone", "9997", "C03DA01", "aldosterone antagonist",
                      ["chf"], ["spironolactone", "aldactone"]),
        MedicationDef("digoxin", "Digoxin", "3407", "C01AA05", "cardiac glycoside",
                      ["chf", "afib"], ["digoxin", "lanoxin"]),
        MedicationDef("levothyroxine", "Levothyroxine", "10582", "H03AA01", "thyroid hormone",
                      ["hypothyroid"], ["levothyroxine", "synthroid"]),
        MedicationDef("albuterol", "Albuterol", "435", "R03AC02", "SABA bronchodilator",
                      ["asthma", "copd"], ["albuterol", "salbutamol", "ventolin"]),
        MedicationDef("sertraline", "Sertraline", "36437", "N06AB06", "SSRI",
                      ["depression"], ["sertraline", "zoloft"]),
        MedicationDef("omeprazole", "Omeprazole", "7646", "A02BC01", "proton pump inhibitor",
                      [], ["omeprazole", "prilosec"]),
        MedicationDef("gabapentin", "Gabapentin", "25480", "N03AX12", "anticonvulsant",
                      ["oa"], ["gabapentin", "neurontin"]),
    ]
}


# ---------------------------------------------------------------------------
# Observations (labs & vitals) with reference ranges
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ObservationDef:
    key: str
    name: str
    loinc: str
    unit: str
    category: str            # "vital-signs" | "laboratory"
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    synonyms: List[str] = field(default_factory=list)


OBSERVATIONS: Dict[str, ObservationDef] = {
    o.key: o
    for o in [
        ObservationDef("sbp", "Systolic blood pressure", "8480-6", "mmHg", "vital-signs", 90, 120,
                       ["systolic", "sbp", "blood pressure"]),
        ObservationDef("dbp", "Diastolic blood pressure", "8462-4", "mmHg", "vital-signs", 60, 80,
                       ["diastolic", "dbp"]),
        ObservationDef("hr", "Heart rate", "8867-4", "/min", "vital-signs", 60, 100, ["heart rate", "pulse"]),
        ObservationDef("weight", "Body weight", "29463-7", "kg", "vital-signs", None, None, ["weight"]),
        ObservationDef("height", "Body height", "8302-2", "cm", "vital-signs", None, None, ["height"]),
        ObservationDef("bmi", "Body mass index", "39156-5", "kg/m2", "vital-signs", 18.5, 25, ["bmi"]),
        ObservationDef("hba1c", "Hemoglobin A1c", "4548-4", "%", "laboratory", 4.0, 5.6,
                       ["hba1c", "a1c", "glycated hemoglobin"]),
        ObservationDef("glucose", "Fasting glucose", "1558-6", "mg/dL", "laboratory", 70, 99, ["glucose", "fasting glucose"]),
        ObservationDef("ldl", "LDL cholesterol", "18262-6", "mg/dL", "laboratory", 0, 100, ["ldl", "ldl cholesterol"]),
        ObservationDef("hdl", "HDL cholesterol", "2085-9", "mg/dL", "laboratory", 40, 100, ["hdl"]),
        ObservationDef("chol", "Total cholesterol", "2093-3", "mg/dL", "laboratory", 0, 200, ["cholesterol", "total cholesterol"]),
        ObservationDef("trig", "Triglycerides", "2571-8", "mg/dL", "laboratory", 0, 150, ["triglycerides"]),
        ObservationDef("creatinine", "Serum creatinine", "2160-0", "mg/dL", "laboratory", 0.6, 1.3, ["creatinine"]),
        ObservationDef("egfr", "Estimated GFR", "33914-3", "mL/min/1.73m2", "laboratory", 90, 120, ["egfr", "gfr"]),
        ObservationDef("potassium", "Potassium", "2823-3", "mmol/L", "laboratory", 3.5, 5.1, ["potassium", "k+"]),
        ObservationDef("sodium", "Sodium", "2951-2", "mmol/L", "laboratory", 135, 145, ["sodium", "na+"]),
        ObservationDef("hgb", "Hemoglobin", "718-7", "g/dL", "laboratory", 12.0, 17.5, ["hemoglobin", "hgb", "hb"]),
        ObservationDef("tsh", "Thyroid stimulating hormone", "3016-3", "mIU/L", "laboratory", 0.4, 4.0, ["tsh"]),
        ObservationDef("inr", "INR", "6301-6", "ratio", "laboratory", 0.8, 1.2, ["inr"]),
    ]
}


# ---------------------------------------------------------------------------
# Drug–drug interactions (well-established pairs)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InteractionDef:
    a: str               # medication key
    b: str               # medication key
    severity: str        # "contraindicated" | "major" | "moderate"
    mechanism: str
    management: str


DRUG_INTERACTIONS: List[InteractionDef] = [
    InteractionDef("warfarin", "aspirin", "major",
                   "Additive antithrombotic effect", "Avoid combination unless clear indication; monitor for bleeding."),
    InteractionDef("warfarin", "clopidogrel", "major",
                   "Additive bleeding risk", "Triple therapy only if essential; minimise duration."),
    InteractionDef("apixaban", "aspirin", "major",
                   "Additive bleeding risk", "Reassess need for dual therapy; consider gastroprotection."),
    InteractionDef("apixaban", "clopidogrel", "major",
                   "Additive bleeding risk", "Use lowest effective intensity; monitor closely."),
    InteractionDef("warfarin", "sertraline", "moderate",
                   "SSRIs impair platelet aggregation; potentiate warfarin", "Monitor INR and for GI bleeding."),
    InteractionDef("lisinopril", "spironolactone", "major",
                   "Additive hyperkalemia (dual RAAS/aldosterone blockade)", "Monitor potassium and renal function."),
    InteractionDef("losartan", "spironolactone", "major",
                   "Additive hyperkalemia", "Monitor potassium; avoid in advanced CKD."),
    InteractionDef("clopidogrel", "omeprazole", "moderate",
                   "CYP2C19 inhibition reduces clopidogrel activation", "Prefer pantoprazole or an H2 blocker."),
    InteractionDef("digoxin", "furosemide", "moderate",
                   "Diuretic-induced hypokalemia increases digoxin toxicity", "Monitor potassium and digoxin level."),
    InteractionDef("digoxin", "spironolactone", "moderate",
                   "Spironolactone raises digoxin levels", "Monitor digoxin concentration."),
    InteractionDef("metformin", "furosemide", "moderate",
                   "Loop diuretics may worsen renal function and metformin accumulation", "Monitor renal function."),
    InteractionDef("levothyroxine", "omeprazole", "moderate",
                   "Reduced gastric acid lowers levothyroxine absorption", "Separate dosing; monitor TSH."),
]


def find_interactions(med_keys: List[str]) -> List[InteractionDef]:
    """Return all known interactions among the supplied medication keys."""
    present = set(med_keys)
    hits: List[InteractionDef] = []
    for ix in DRUG_INTERACTIONS:
        if ix.a in present and ix.b in present:
            hits.append(ix)
    return hits


# ---------------------------------------------------------------------------
# Clinical guidelines (used by NER linking and care-gap explanations)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GuidelineDef:
    condition_key: str
    title: str
    source: str
    recommendation: str


GUIDELINES: List[GuidelineDef] = [
    GuidelineDef("t2dm", "Glycaemic monitoring", "ADA Standards of Care",
                 "Check HbA1c at least twice yearly; target <7% for most non-pregnant adults."),
    GuidelineDef("t2dm", "Statin therapy in diabetes", "ADA / ACC",
                 "Adults 40–75 with diabetes should generally receive moderate-intensity statin."),
    GuidelineDef("htn", "Blood-pressure control", "ACC/AHA 2017",
                 "Target <130/80 mmHg for most adults with hypertension."),
    GuidelineDef("cad", "Secondary prevention", "ACC/AHA",
                 "Antiplatelet + high-intensity statin recommended after ASCVD events."),
    GuidelineDef("afib", "Stroke prophylaxis", "CHEST / ESC",
                 "Anticoagulate when CHA₂DS₂-VASc ≥2 (men) or ≥3 (women)."),
    GuidelineDef("chf", "Guideline-directed medical therapy", "ACC/AHA/HFSA",
                 "HFrEF: ACEi/ARB/ARNI + beta-blocker + MRA + SGLT2 inhibitor."),
    GuidelineDef("ckd", "Nephroprotection", "KDIGO",
                 "ACEi/ARB for albuminuria; monitor eGFR and potassium."),
    GuidelineDef("copd", "Maintenance bronchodilation", "GOLD",
                 "Long-acting bronchodilators for symptomatic COPD; rescue SABA."),
]


def guidelines_for(condition_key: str) -> List[GuidelineDef]:
    return [g for g in GUIDELINES if g.condition_key == condition_key]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------
def condition_by_name(text: str) -> Optional[ConditionDef]:
    t = text.strip().lower()
    for c in CONDITIONS.values():
        if t == c.name.lower() or t in [s.lower() for s in c.synonyms]:
            return c
    return None


def all_condition_synonyms() -> Dict[str, str]:
    """Map every synonym/name -> condition key (for NER)."""
    out: Dict[str, str] = {}
    for c in CONDITIONS.values():
        out[c.name.lower()] = c.key
        for s in c.synonyms:
            out[s.lower()] = c.key
    return out


def all_medication_synonyms() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in MEDICATIONS.values():
        out[m.name.lower()] = m.key
        for s in m.synonyms:
            out[s.lower()] = m.key
    return out
