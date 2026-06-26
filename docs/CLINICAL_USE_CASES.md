# Clinical use cases

MediGraph AI is built for concrete clinic and hospital workflows. Each below is
implemented and demonstrable today.

## 1. Discharge readmission targeting (hospital)
Compute the **LACE index** for inpatients and flag the high-risk cohort for
intensive discharge planning and early follow-up. Surfaced per-patient (Patient
360) and as a population band (Population Health → risk stratification).

> LACE = Length-of-stay points + Acute/emergent admission (3) + Charlson
> comorbidity (capped 5) + ED visits in prior 6 months (capped 4). Score ≥10 = high.

## 2. Atrial-fibrillation stroke prevention (cardiology / primary care)
For every AF patient, compute **CHA₂DS₂-VASc** (stroke risk) and **HAS-BLED**
(bleeding risk), and raise an **anticoagulation care gap** when CHA₂DS₂-VASc is at
or above the sex-specific threshold but no oral anticoagulant is on record. The
"AF, no anticoagulant" registry is one click in the Cohort Builder.

## 3. Diabetes panel management (primary care / ACO)
Detect diabetics **overdue for HbA1c** (no result in 6 months), **uncontrolled**
diabetes (HbA1c ≥ 9%), and statin under-treatment in age-eligible patients. The
diabetes registry and "uncontrolled (HbA1c ≥ 9)" cohort are presets, and the
"Diabetes: HbA1c tested / controlled / statin use" quality measures track the
panel over time.

## 4. Hypertension control (primary care)
Flag hypertensives whose most recent BP is ≥140/90 and report the population
"BP < 140/90" control rate as a HEDIS-style measure.

## 5. CKD nephroprotection & monitoring (nephrology)
Stage chronic kidney disease from **eGFR (CKD-EPI 2021, race-free)**, flag CKD
patients without an ACEi/ARB, and surface overdue renal monitoring.

## 6. Medication safety (pharmacy / all settings)
Screen each patient's active medications for well-established **drug–drug
interactions** (e.g. warfarin + aspirin, ACEi + spironolactone) with mechanism and
management guidance.

## 7. Cohort & registry building (quality / research)
Compose any combination of conditions, medications, demographics and lab
thresholds into a cohort for outreach, quality reporting, or trial pre-screening —
then export to CSV. Six preset registries ship out of the box.

## 8. Clinical-note understanding (documentation / intake)
Extract problems, medications and labs from free-text notes with **negation
detection** (so "no chest pain" and "denies stroke" are excluded), map them to
SNOMED/RxNorm/LOINC, and surface the linked guidelines for detected problems.

## 9. Ask-the-graph (any role)
Pose natural-language questions ("patients with atrial fibrillation not on
anticoagulant", "most common conditions") and get answers grounded in the graph
**with citations** to the contributing nodes.

## 10. Outreach prioritisation (care management)
A composite **priority score** (care gaps + interactions + high-risk scores) ranks
the panel so care managers work the highest-impact patients first.

---

### Validity note
All instruments are implemented transparently and reference real clinical sources
(ADA Standards of Care, ACC/AHA, KDIGO, CHEST/ESC, CKD-EPI 2021, the LACE index).
They are decision-support aids, not certified diagnostics — see the disclaimer in
[`LICENSE`](../LICENSE).
