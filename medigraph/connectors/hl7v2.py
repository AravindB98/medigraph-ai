"""HL7 v2.x connector.

HL7 v2 remains the workhorse messaging standard inside hospitals worldwide
(admissions, lab results, orders). This connector parses the common message
types into canonical records:

- **ADT** (A01/A04/A08 …) — patient demographics & visits (PID, PV1, DG1)
- **ORU^R01** — observation/lab results (OBX)

It is a pragmatic, dependency-free parser (pipe/hat delimited) covering the
segments MediGraph models; a full HL7 engine (e.g. Mirth/NextGen Connect, hl7apy)
can be substituted behind the same interface for production routing.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from medigraph.connectors.base import (
    BaseConnector,
    ConnectorInfo,
    Direction,
    Standard,
    Status,
    register,
)
from medigraph.domain import terminology as T
from medigraph.domain.models import (
    ConditionInstance,
    Encounter,
    EncounterClass,
    ObservationInstance,
    Patient,
    PatientRecord,
    Sex,
)

_SEX_MAP = {"M": Sex.male, "F": Sex.female, "O": Sex.other, "U": Sex.unknown}


def _parse_hl7_dt(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(value[:len(fmt.replace("%", "")) + 4], fmt)
        except (ValueError, TypeError):
            continue
    try:
        return datetime.strptime(value[:8], "%Y%m%d")
    except (ValueError, TypeError):
        return None


@register("hl7v2")
class HL7v2Connector(BaseConnector):
    info = ConnectorInfo(
        key="hl7v2", name="HL7 v2.x (ADT / ORU)", standard=Standard.HL7_V2,
        direction=Direction.READ, status=Status.SUPPORTED,
        description="Parses HL7 v2 ADT and ORU messages into canonical records.",
        countries=["US", "IN"])

    def test_connection(self) -> str:
        return "HL7 v2 parser ready (offline). Point an MLLP/TCP feed here in production."

    def ingest(self, payload: str) -> PatientRecord:
        return self.parse_message(payload)

    # ---- parser -----------------------------------------------------------
    def parse_message(self, message: str) -> PatientRecord:
        segments = [s for s in message.replace("\n", "\r").split("\r") if s.strip()]
        patient: Optional[Patient] = None
        conditions: List[ConditionInstance] = []
        observations: List[ObservationInstance] = []
        encounters: List[Encounter] = []

        for seg in segments:
            fields = seg.split("|")
            seg_id = fields[0]

            if seg_id == "PID":
                patient = self._parse_pid(fields)
            elif seg_id == "PV1":
                enc = self._parse_pv1(fields)
                if enc:
                    encounters.append(enc)
            elif seg_id == "DG1":
                cond = self._parse_dg1(fields)
                if cond:
                    conditions.append(cond)
            elif seg_id == "OBX":
                obs = self._parse_obx(fields)
                if obs:
                    observations.append(obs)

        if patient is None:
            raise ValueError("HL7 message has no PID segment.")
        return PatientRecord(patient=patient, conditions=conditions,
                             observations=observations, encounters=encounters)

    @staticmethod
    def _comp(field: str, idx: int) -> str:
        parts = field.split("^")
        return parts[idx] if idx < len(parts) else ""

    def _parse_pid(self, f: List[str]) -> Patient:
        pid_id = self._comp(f[3], 0) if len(f) > 3 else "hl7-unknown"
        name_field = f[5] if len(f) > 5 else ""
        family = self._comp(name_field, 0)
        given = self._comp(name_field, 1)
        dob = _parse_hl7_dt(f[7]) if len(f) > 7 else None
        sex = _SEX_MAP.get((f[8].strip() if len(f) > 8 else "").upper(), Sex.unknown)
        city = self._comp(f[11], 2) if len(f) > 11 else None
        state = self._comp(f[11], 3) if len(f) > 11 else None
        age = None
        if dob:
            age = int((datetime.utcnow() - dob).days // 365)
        return Patient(
            id=pid_id or "hl7-unknown", full_name=f"{given} {family}".strip() or pid_id,
            sex=sex, birth_date=dob.date() if dob else None, age=age,
            city=city or None, state=state or None, mrn=pid_id)

    def _parse_pv1(self, f: List[str]) -> Optional[Encounter]:
        if len(f) < 2:
            return None
        cls_code = (f[2].strip() if len(f) > 2 else "").upper()
        mapping = {"E": EncounterClass.emergency, "I": EncounterClass.inpatient,
                   "O": EncounterClass.ambulatory, "P": EncounterClass.ambulatory}
        eclass = mapping.get(cls_code, EncounterClass.ambulatory)
        return Encounter(id=f"hl7-enc-{datetime.utcnow().timestamp():.0f}",
                         encounter_class=eclass, via_emergency=(eclass == EncounterClass.emergency))

    def _parse_dg1(self, f: List[str]) -> Optional[ConditionInstance]:
        if len(f) < 4:
            return None
        code = self._comp(f[3], 0)
        desc = self._comp(f[3], 1)
        key = None
        for cdef in T.CONDITIONS.values():
            if code in (cdef.icd10, cdef.snomed) or desc.lower() == cdef.name.lower():
                key = cdef.key
                break
        if key is None:
            from medigraph.domain.terminology import condition_by_name

            cdef = condition_by_name(desc)
            key = cdef.key if cdef else None
        cdef = T.CONDITIONS.get(key) if key else None
        return ConditionInstance(
            code_key=key or "unknown", name=cdef.name if cdef else (desc or code),
            snomed=cdef.snomed if cdef else None,
            icd10=cdef.icd10 if cdef else (code or None))

    def _parse_obx(self, f: List[str]) -> Optional[ObservationInstance]:
        if len(f) < 6:
            return None
        code = self._comp(f[3], 0)
        name = self._comp(f[3], 1)
        value_raw = f[5].strip()
        unit = self._comp(f[6], 0) if len(f) > 6 else ""
        key = None
        for odef in T.OBSERVATIONS.values():
            if code == odef.loinc or name.lower() == odef.name.lower():
                key = odef.key
                break
        odef = T.OBSERVATIONS.get(key) if key else None
        try:
            value = float(value_raw)
            value_text = None
        except ValueError:
            value = None
            value_text = value_raw
        eff = _parse_hl7_dt(f[14]) if len(f) > 14 else None
        return ObservationInstance(
            code_key=key or "unknown", name=odef.name if odef else (name or code),
            loinc=odef.loinc if odef else (code or None),
            value=value, value_text=value_text, unit=unit or (odef.unit if odef else None),
            category=odef.category if odef else "laboratory", effective_datetime=eff)
