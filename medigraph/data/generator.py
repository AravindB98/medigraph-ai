"""Deterministic synthetic-EHR generator.

Produces a clinically *coherent* dataset (not just random noise) so that the
decision-support, care-gap and population-health features have something
meaningful to work on out of the box. Patients are a realistic mix of US and
India locales, with correlated conditions, medications and labs — and a few
**intentional care gaps** (e.g. a diabetic overdue for HbA1c, an AF patient not
anticoagulated) so the alerts demonstrably fire.

All output is written as CSV to ``medigraph/data/synthetic/``. Re-running with the
same seed reproduces byte-identical files.
"""
from __future__ import annotations

import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List

from medigraph.config import DATA_DIR, get_settings
from medigraph.domain import terminology as T

REFERENCE_DATE = date(2026, 6, 27)

US_FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
            "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Karen",
            "Thomas", "Nancy", "Carlos", "Maria", "Aisha", "Wei", "Sofia", "Marcus"]
US_LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
           "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Lee", "Nguyen"]
US_CITIES = [("Boston", "MA"), ("Austin", "TX"), ("Seattle", "WA"), ("Denver", "CO"),
             ("Chicago", "IL"), ("Atlanta", "GA"), ("Phoenix", "AZ"), ("Columbus", "OH")]

IN_FIRST = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Reyansh", "Ananya", "Diya",
            "Saanvi", "Aadhya", "Priya", "Ishaan", "Kabir", "Anaya", "Rohan", "Meera",
            "Lakshmi", "Rahul", "Sneha", "Karthik", "Divya", "Aravind", "Nisha", "Vikram"]
IN_LAST = ["Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Singh", "Gupta",
           "Rao", "Menon", "Das", "Khan", "Bose", "Mehta", "Pillai", "Balaji"]
IN_CITIES = [("Bengaluru", "KA"), ("Chennai", "TN"), ("Mumbai", "MH"), ("Delhi", "DL"),
             ("Hyderabad", "TG"), ("Pune", "MH"), ("Kolkata", "WB"), ("Kochi", "KL")]

SPECIALTIES = ["Internal Medicine", "Family Medicine", "Cardiology", "Endocrinology",
               "Nephrology", "Pulmonology", "General Practice"]


def _age_to_birthdate(age: int, rnd: random.Random) -> date:
    days = age * 365 + rnd.randint(0, 364)
    return REFERENCE_DATE - timedelta(days=days)


def _prevalence_by_age(age: int) -> Dict[str, float]:
    """Rough age-scaled prevalence for condition assignment."""
    f = min(1.0, max(0.1, (age - 20) / 60.0))  # 0.1 at 20y -> 1.0 at 80y
    return {
        "htn": 0.55 * f,
        "t2dm": 0.42 * f,
        "hld": 0.50 * f,
        "obesity": 0.30,
        "cad": 0.30 * f,
        "afib": 0.22 * f,
        "chf": 0.18 * f,
        "ckd": 0.22 * f,
        "copd": 0.16 * f,
        "asthma": 0.10,
        "depression": 0.15,
        "hypothyroid": 0.12,
        "oa": 0.35 * f,
        "stroke": 0.10 * f,
        "anemia": 0.14,
    }


def _gen_providers(rnd: random.Random, n: int) -> List[dict]:
    providers = []
    for i in range(n):
        india = rnd.random() < 0.35
        if india:
            name = f"Dr. {rnd.choice(IN_FIRST)} {rnd.choice(IN_LAST)}"
            city, state = rnd.choice(IN_CITIES)
            providers.append(dict(
                id=f"prov-{i:04d}", name=name, specialty=rnd.choice(SPECIALTIES),
                npi="", hpr_id=f"HPR-{rnd.randint(10**9, 10**10 - 1)}",
                organization=f"{city} Multispeciality Hospital", state=state, country="IN"))
        else:
            name = f"Dr. {rnd.choice(US_FIRST)} {rnd.choice(US_LAST)}"
            city, state = rnd.choice(US_CITIES)
            providers.append(dict(
                id=f"prov-{i:04d}", name=name, specialty=rnd.choice(SPECIALTIES),
                npi=str(rnd.randint(10**9, 10**10 - 1)), hpr_id="",
                organization=f"{city} Health System", state=state, country="US"))
    return providers


def _obs(pid, eid, key, value, when, rnd):
    d = T.OBSERVATIONS[key]
    interp = "normal"
    if d.ref_high is not None and value > d.ref_high:
        interp = "high"
    elif d.ref_low is not None and value < d.ref_low:
        interp = "low"
    return dict(
        id=f"obs-{pid}-{key}-{when:%Y%m%d}-{rnd.randint(100, 999)}",
        patient_id=pid, encounter_id=eid, code_key=key, name=d.name, loinc=d.loinc,
        value=round(value, 1), unit=d.unit, category=d.category,
        effective_datetime=datetime(when.year, when.month, when.day, 9, 0).isoformat(),
        interpretation=interp)


def generate(num_patients: int | None = None, seed: int | None = None) -> Dict[str, int]:
    """Generate the full synthetic dataset and write CSVs. Returns row counts."""
    settings = get_settings()
    num_patients = num_patients or settings.synthetic_patients
    seed = settings.synthetic_seed if seed is None else seed
    rnd = random.Random(seed)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    providers = _gen_providers(rnd, max(8, num_patients // 8))
    patients, conditions, medications, encounters, observations = [], [], [], [], []

    for i in range(num_patients):
        pid = f"pat-{i:04d}"
        india = rnd.random() < 0.32
        sex = rnd.choice(["male", "female"])
        age = int(min(95, max(18, rnd.gauss(58, 17))))
        bdate = _age_to_birthdate(age, rnd)
        prov = rnd.choice(providers)

        if india:
            first = rnd.choice(IN_FIRST)
            last = rnd.choice(IN_LAST)
            city, state = rnd.choice(IN_CITIES)
            country = "IN"
            abha = f"{rnd.randint(10,99)}-{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}-{rnd.randint(1000,9999)}"
            mrn = f"IN-MRN-{rnd.randint(100000, 999999)}"
        else:
            first = rnd.choice(US_FIRST)
            last = rnd.choice(US_LAST)
            city, state = rnd.choice(US_CITIES)
            country = "US"
            abha = ""
            mrn = f"MRN-{rnd.randint(100000, 999999)}"

        patients.append(dict(
            id=pid, full_name=f"{first} {last}", sex=sex, birth_date=bdate.isoformat(),
            age=age, city=city, state=state, country=country, mrn=mrn, abha_id=abha,
            primary_provider_id=prov["id"]))

        # ---- Conditions ----
        prev = _prevalence_by_age(age)
        pt_conditions: List[str] = []
        for ckey, p in prev.items():
            if rnd.random() < p:
                cdef = T.CONDITIONS[ckey]
                onset = REFERENCE_DATE - timedelta(days=rnd.randint(180, 3650))
                conditions.append(dict(
                    patient_id=pid, code_key=ckey, name=cdef.name, snomed=cdef.snomed,
                    icd10=cdef.icd10, clinical_status="active", onset_date=onset.isoformat()))
                pt_conditions.append(ckey)

        # ---- Medications (derived from conditions, with intentional gaps) ----
        pt_meds: List[str] = []

        def add_med(mkey: str):
            if mkey in pt_meds:
                return
            mdef = T.MEDICATIONS[mkey]
            start = REFERENCE_DATE - timedelta(days=rnd.randint(60, 1800))
            medications.append(dict(
                patient_id=pid, code_key=mkey, name=mdef.name, rxnorm=mdef.rxnorm,
                drug_class=mdef.drug_class, status="active", start_date=start.isoformat()))
            pt_meds.append(mkey)

        if "t2dm" in pt_conditions:
            add_med("metformin")
            if rnd.random() < 0.35:
                add_med("insulin_glargine")
        if "htn" in pt_conditions:
            add_med(rnd.choice(["lisinopril", "amlodipine", "losartan", "hctz"]))
            if rnd.random() < 0.4:
                add_med("metoprolol")
        # Statin gap: only ~65% of HLD/CAD/diabetics get a statin
        if ("hld" in pt_conditions or "cad" in pt_conditions or "t2dm" in pt_conditions) and rnd.random() < 0.65:
            add_med("atorvastatin")
        if "cad" in pt_conditions and rnd.random() < 0.7:
            add_med(rnd.choice(["aspirin", "clopidogrel"]))
        # Anticoagulation gap: only ~60% of AF patients anticoagulated
        if "afib" in pt_conditions and rnd.random() < 0.6:
            add_med(rnd.choice(["warfarin", "apixaban"]))
        if "chf" in pt_conditions:
            add_med("furosemide")
            if rnd.random() < 0.5:
                add_med("spironolactone")
            if rnd.random() < 0.3:
                add_med("digoxin")
        if "hypothyroid" in pt_conditions:
            add_med("levothyroxine")
        if "asthma" in pt_conditions or "copd" in pt_conditions:
            add_med("albuterol")
        if "depression" in pt_conditions:
            add_med("sertraline")
        if "oa" in pt_conditions and rnd.random() < 0.4:
            add_med("gabapentin")
        if rnd.random() < 0.3:
            add_med("omeprazole")

        # ---- Encounters ----
        # Decide chronic-control phenotype once per patient so the *latest*
        # readings are internally consistent (≈60% of hypertensives at goal).
        htn = "htn" in pt_conditions
        htn_controlled = rnd.random() < 0.60
        n_enc = rnd.randint(1, 8)
        last_enc_id = None
        for _ in range(n_enc):
            when = REFERENCE_DATE - timedelta(days=rnd.randint(0, 1000))
            eclass = rnd.choices(
                ["ambulatory", "wellness", "emergency", "inpatient", "virtual"],
                weights=[40, 25, 12, 8, 15])[0]
            via_ed = eclass == "emergency"
            los = rnd.randint(2, 12) if eclass == "inpatient" else 0
            eid = f"enc-{pid}-{rnd.randint(10000, 99999)}"
            last_enc_id = eid
            encounters.append(dict(
                id=eid, patient_id=pid, encounter_class=eclass,
                start=datetime(when.year, when.month, when.day, 10, 0).isoformat(),
                end=datetime(when.year, when.month, when.day, 11, 0).isoformat(),
                provider_id=rnd.choice(providers)["id"],
                reason="Follow-up" if not via_ed else "Acute presentation",
                length_of_stay_days=los, via_emergency=via_ed))

            # Vitals at most encounters
            if rnd.random() < 0.9:
                if htn and not htn_controlled:
                    sbp = rnd.gauss(150, 8)
                    dbp = rnd.gauss(92, 6)
                elif htn:
                    sbp = rnd.gauss(128, 7)
                    dbp = rnd.gauss(80, 5)
                else:
                    sbp = rnd.gauss(119, 9)
                    dbp = rnd.gauss(76, 6)
                observations.append(_obs(pid, eid, "sbp", sbp, when, rnd))
                observations.append(_obs(pid, eid, "dbp", dbp, when, rnd))
                observations.append(_obs(pid, eid, "hr", rnd.gauss(76, 8), when, rnd))
                wt = rnd.gauss(92 if "obesity" in pt_conditions else 74, 12)
                ht = rnd.gauss(170, 9)
                bmi = wt / ((ht / 100) ** 2)
                observations.append(_obs(pid, eid, "weight", wt, when, rnd))
                observations.append(_obs(pid, eid, "height", ht, when, rnd))
                observations.append(_obs(pid, eid, "bmi", bmi, when, rnd))

        # ---- Condition-specific labs (timed to create some care gaps) ----
        def lab(key, value, days_ago):
            when = REFERENCE_DATE - timedelta(days=days_ago)
            observations.append(_obs(pid, last_enc_id, key, value, when, rnd))

        if "t2dm" in pt_conditions:
            controlled = rnd.random() < 0.55
            a1c = rnd.gauss(6.6 if controlled else 8.9, 0.6)
            # ~30% are overdue (last HbA1c > 6 months) -> monitoring gap
            days_ago = rnd.randint(20, 170) if rnd.random() < 0.7 else rnd.randint(200, 420)
            lab("hba1c", max(5.0, a1c), days_ago)
            lab("glucose", rnd.gauss(120 if controlled else 165, 20), days_ago)
        if "hld" in pt_conditions or "cad" in pt_conditions:
            on_statin = "atorvastatin" in pt_meds
            lab("ldl", rnd.gauss(95 if on_statin else 145, 25), rnd.randint(30, 300))
            lab("hdl", rnd.gauss(48, 10), rnd.randint(30, 300))
            lab("chol", rnd.gauss(185 if on_statin else 225, 25), rnd.randint(30, 300))
            lab("trig", rnd.gauss(160, 40), rnd.randint(30, 300))
        if "ckd" in pt_conditions:
            cr = rnd.gauss(1.8, 0.5)
            lab("creatinine", max(0.7, cr), rnd.randint(20, 200))
            # crude eGFR proxy; real value computed in decision_support
            lab("egfr", max(8, rnd.gauss(48, 18)), rnd.randint(20, 200))
            lab("potassium", rnd.gauss(4.7, 0.5), rnd.randint(20, 200))
        else:
            lab("creatinine", rnd.gauss(0.95, 0.18), rnd.randint(20, 300))
        if "afib" in pt_conditions and "warfarin" in pt_meds:
            lab("inr", rnd.gauss(2.4, 0.6), rnd.randint(10, 60))
        if "hypothyroid" in pt_conditions:
            lab("tsh", rnd.gauss(3.5, 1.5), rnd.randint(30, 300))
        if "anemia" in pt_conditions:
            lab("hgb", rnd.gauss(10.5, 1.0), rnd.randint(20, 200))

    counts = _write_all(providers, patients, conditions, medications, encounters, observations)
    return counts


def _write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> int:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def _write_all(providers, patients, conditions, medications, encounters, observations) -> Dict[str, int]:
    counts = {}
    counts["providers"] = _write_csv(DATA_DIR / "providers.csv", providers,
        ["id", "name", "specialty", "npi", "hpr_id", "organization", "state", "country"])
    counts["patients"] = _write_csv(DATA_DIR / "patients.csv", patients,
        ["id", "full_name", "sex", "birth_date", "age", "city", "state", "country",
         "mrn", "abha_id", "primary_provider_id"])
    counts["conditions"] = _write_csv(DATA_DIR / "conditions.csv", conditions,
        ["patient_id", "code_key", "name", "snomed", "icd10", "clinical_status", "onset_date"])
    counts["medications"] = _write_csv(DATA_DIR / "medications.csv", medications,
        ["patient_id", "code_key", "name", "rxnorm", "drug_class", "status", "start_date"])
    counts["encounters"] = _write_csv(DATA_DIR / "encounters.csv", encounters,
        ["id", "patient_id", "encounter_class", "start", "end", "provider_id",
         "reason", "length_of_stay_days", "via_emergency"])
    counts["observations"] = _write_csv(DATA_DIR / "observations.csv", observations,
        ["id", "patient_id", "encounter_id", "code_key", "name", "loinc", "value",
         "unit", "category", "effective_datetime", "interpretation"])
    return counts


def main() -> None:
    counts = generate()
    print("Synthetic dataset written to", DATA_DIR)
    for k, v in counts.items():
        print(f"  {k:12s}: {v:,}")


if __name__ == "__main__":
    main()
