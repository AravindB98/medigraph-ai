"""FHIR R4 interoperability.

Converts between MediGraph's canonical ``PatientRecord`` and HL7 **FHIR R4**
bundles (Patient, Condition, MedicationStatement, Encounter, Observation). FHIR
is the lingua franca of modern interoperability in both the US (US Core, TEFCA)
and India (ABDM), so this module is the foundation every external connector
maps through.

The mappings are deliberately lossless for the fields MediGraph models and use
real code systems (SNOMED CT, RxNorm, LOINC, ICD-10).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from medigraph.domain import terminology as T
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

SYS_SNOMED = "http://snomed.info/sct"
SYS_ICD10 = "http://hl7.org/fhir/sid/icd-10-cm"
SYS_RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
SYS_LOINC = "http://loinc.org"
SYS_MRN = "urn:oid:2.16.840.1.113883.4.1"            # example MRN system
SYS_ABHA = "https://healthid.ndhm.gov.in"            # India ABHA


# ---------------------------------------------------------------------------
# Export: PatientRecord -> FHIR Bundle
# ---------------------------------------------------------------------------
def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def patient_to_fhir(p: Patient) -> dict:
    identifiers = []
    if p.mrn:
        identifiers.append({"system": SYS_MRN, "value": p.mrn})
    if p.abha_id:
        identifiers.append({"system": SYS_ABHA, "value": p.abha_id})
    parts = p.full_name.split(" ", 1)
    given = [parts[0]]
    family = parts[1] if len(parts) > 1 else ""
    return {
        "resourceType": "Patient",
        "id": p.id,
        "identifier": identifiers,
        "name": [{"use": "official", "family": family, "given": given}],
        "gender": p.sex.value,
        "birthDate": _iso(p.birth_date),
        "address": [{"city": p.city, "state": p.state, "country": p.country}],
    }


def condition_to_fhir(c: ConditionInstance, patient_id: str) -> dict:
    coding = []
    if c.snomed:
        coding.append({"system": SYS_SNOMED, "code": c.snomed, "display": c.name})
    if c.icd10:
        coding.append({"system": SYS_ICD10, "code": c.icd10, "display": c.name})
    return {
        "resourceType": "Condition",
        "clinicalStatus": {"coding": [{"code": c.clinical_status}]},
        "code": {"coding": coding, "text": c.name},
        "subject": {"reference": f"Patient/{patient_id}"},
        "onsetDateTime": _iso(c.onset_date),
    }


def medication_to_fhir(m: MedicationInstance, patient_id: str) -> dict:
    return {
        "resourceType": "MedicationStatement",
        "status": "active" if m.status == "active" else "stopped",
        "medicationCodeableConcept": {
            "coding": [{"system": SYS_RXNORM, "code": m.rxnorm, "display": m.name}],
            "text": m.name},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": _iso(m.start_date),
    }


def observation_to_fhir(o: ObservationInstance, patient_id: str) -> dict:
    res = {
        "resourceType": "Observation",
        "status": "final",
        "category": [{"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": o.category}]}],
        "code": {"coding": [{"system": SYS_LOINC, "code": o.loinc, "display": o.name}], "text": o.name},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": _iso(o.effective_datetime),
    }
    if o.value is not None:
        res["valueQuantity"] = {"value": o.value, "unit": o.unit, "system": "http://unitsofmeasure.org"}
    else:
        res["valueString"] = o.value_text
    if o.interpretation:
        res["interpretation"] = [{"text": o.interpretation}]
    return res


def encounter_to_fhir(e: Encounter, patient_id: str) -> dict:
    return {
        "resourceType": "Encounter",
        "id": e.id,
        "status": "finished",
        "class": {"code": str(getattr(e.encounter_class, "value", e.encounter_class))},
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": _iso(e.start), "end": _iso(e.end)},
        "reasonCode": [{"text": e.reason}] if e.reason else [],
    }


def record_to_bundle(record: PatientRecord) -> dict:
    pid = record.patient.id
    entries = [{"resource": patient_to_fhir(record.patient)}]
    entries += [{"resource": condition_to_fhir(c, pid)} for c in record.conditions]
    entries += [{"resource": medication_to_fhir(m, pid)} for m in record.medications]
    entries += [{"resource": encounter_to_fhir(e, pid)} for e in record.encounters]
    entries += [{"resource": observation_to_fhir(o, pid)} for o in record.observations]
    return {"resourceType": "Bundle", "type": "collection",
            "timestamp": datetime.utcnow().isoformat(), "entry": entries}


# ---------------------------------------------------------------------------
# Import: FHIR Bundle -> PatientRecord
# ---------------------------------------------------------------------------
def _match_condition(coding: list, text: str) -> Optional[str]:
    for c in coding:
        for cdef in T.CONDITIONS.values():
            if c.get("code") in (cdef.snomed, cdef.icd10):
                return cdef.key
    cdef = T.condition_by_name(text or "")
    return cdef.key if cdef else None


def _match_medication(coding: list, text: str) -> Optional[str]:
    for c in coding:
        for mdef in T.MEDICATIONS.values():
            if c.get("code") == mdef.rxnorm:
                return mdef.key
    key = T.all_medication_synonyms().get((text or "").lower())
    return key


def _match_observation(coding: list, text: str) -> Optional[str]:
    for c in coding:
        for odef in T.OBSERVATIONS.values():
            if c.get("code") == odef.loinc:
                return odef.key
    return None


def bundle_to_record(bundle: dict) -> PatientRecord:
    patient: Optional[Patient] = None
    conditions: List[ConditionInstance] = []
    medications: List[MedicationInstance] = []
    observations: List[ObservationInstance] = []
    encounters: List[Encounter] = []

    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        rtype = res.get("resourceType")

        if rtype == "Patient":
            name = (res.get("name") or [{}])[0]
            given = " ".join(name.get("given", []))
            full = f"{given} {name.get('family', '')}".strip() or res.get("id", "unknown")
            addr = (res.get("address") or [{}])[0]
            mrn = abha = None
            for ident in res.get("identifier", []):
                if ident.get("system") == SYS_ABHA:
                    abha = ident.get("value")
                else:
                    mrn = ident.get("value")
            gender = res.get("gender", "unknown")
            patient = Patient(
                id=res.get("id", "imported"), full_name=full,
                sex=Sex(gender) if gender in Sex._value2member_map_ else Sex.unknown,
                birth_date=_parse_date(res.get("birthDate")),
                city=addr.get("city"), state=addr.get("state"),
                country=addr.get("country", "US"), mrn=mrn, abha_id=abha)

        elif rtype == "Condition":
            code = res.get("code", {})
            coding = code.get("coding", [])
            text = code.get("text", "")
            key = _match_condition(coding, text)
            cdef = T.CONDITIONS.get(key) if key else None
            conditions.append(ConditionInstance(
                code_key=key or "unknown", name=cdef.name if cdef else text,
                snomed=cdef.snomed if cdef else None, icd10=cdef.icd10 if cdef else None,
                clinical_status=(res.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "active")),
                onset_date=_parse_date(res.get("onsetDateTime"))))

        elif rtype in ("MedicationStatement", "MedicationRequest"):
            cc = res.get("medicationCodeableConcept", {})
            coding = cc.get("coding", [])
            text = cc.get("text", "")
            key = _match_medication(coding, text)
            mdef = T.MEDICATIONS.get(key) if key else None
            medications.append(MedicationInstance(
                code_key=key or "unknown", name=mdef.name if mdef else text,
                rxnorm=mdef.rxnorm if mdef else None,
                drug_class=mdef.drug_class if mdef else None,
                status="active" if res.get("status") == "active" else "stopped"))

        elif rtype == "Observation":
            code = res.get("code", {})
            coding = code.get("coding", [])
            text = code.get("text", "")
            key = _match_observation(coding, text)
            odef = T.OBSERVATIONS.get(key) if key else None
            vq = res.get("valueQuantity", {})
            observations.append(ObservationInstance(
                code_key=key or "unknown", name=odef.name if odef else text,
                loinc=odef.loinc if odef else None,
                value=vq.get("value"), unit=vq.get("unit") or (odef.unit if odef else None),
                value_text=res.get("valueString"),
                category=odef.category if odef else "laboratory",
                effective_datetime=_parse_dt(res.get("effectiveDateTime")),
                interpretation=(res.get("interpretation", [{}])[0].get("text") if res.get("interpretation") else None)))

        elif rtype == "Encounter":
            period = res.get("period", {})
            cls = res.get("class", {}).get("code", "ambulatory")
            encounters.append(Encounter(
                id=res.get("id", "enc-imported"),
                encounter_class=EncounterClass(cls) if cls in EncounterClass._value2member_map_ else EncounterClass.ambulatory,
                start=_parse_dt(period.get("start")), end=_parse_dt(period.get("end")),
                reason=(res.get("reasonCode", [{}])[0].get("text") if res.get("reasonCode") else None),
                via_emergency=(cls == "emergency")))

    if patient is None:
        raise ValueError("Bundle contains no Patient resource.")
    return PatientRecord(patient=patient, conditions=conditions, medications=medications,
                         observations=observations, encounters=encounters, providers=[])


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
