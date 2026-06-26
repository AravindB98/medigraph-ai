"""C-CDA (Consolidated CDA) connector.

C-CDA documents (CCD, Discharge Summary, etc.) are the document-based exchange
format mandated for US Meaningful Use and widely produced by every certified EHR.
This connector parses the demographics and the Problems / Medications / Results
sections of a CCD into a canonical record.

It is namespace-aware and dependency-free (stdlib ElementTree). It targets the
common HL7 CCD section LOINC codes; a production deployment can layer a full
C-CDA validator/transform on top.
"""
from __future__ import annotations

from typing import List, Optional
from xml.etree import ElementTree as ET

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
    MedicationInstance,
    Patient,
    PatientRecord,
    Sex,
)

_NS = {"h": "urn:hl7-org:v3"}
SECTION_PROBLEMS = "11450-4"
SECTION_MEDICATIONS = "10160-0"

_SEX_MAP = {"M": Sex.male, "F": Sex.female, "UN": Sex.unknown}


@register("ccda")
class CCDAConnector(BaseConnector):
    info = ConnectorInfo(
        key="ccda", name="C-CDA (CCD documents)", standard=Standard.CCDA,
        direction=Direction.READ, status=Status.SUPPORTED,
        description="Parses C-CDA / CCD demographics, problems and medications.",
        countries=["US"])

    def test_connection(self) -> str:
        return "C-CDA parser ready (offline). Feed exported CCD documents here."

    def ingest(self, payload: str) -> PatientRecord:
        return self.parse_document(payload)

    def parse_document(self, xml_text: str) -> PatientRecord:
        root = ET.fromstring(xml_text)
        patient = self._parse_patient(root)
        conditions = self._parse_problems(root)
        medications = self._parse_medications(root)
        return PatientRecord(patient=patient, conditions=conditions, medications=medications)

    # ---- demographics -----------------------------------------------------
    def _parse_patient(self, root: ET.Element) -> Patient:
        pr = root.find(".//h:recordTarget/h:patientRole", _NS)
        pid = "ccda-unknown"
        full_name = "Unknown"
        sex = Sex.unknown
        city = state = None
        if pr is not None:
            id_el = pr.find("h:id", _NS)
            if id_el is not None:
                pid = id_el.get("extension") or id_el.get("root") or pid
            pat = pr.find("h:patient", _NS)
            if pat is not None:
                name = pat.find("h:name", _NS)
                if name is not None:
                    given = name.findtext("h:given", default="", namespaces=_NS)
                    family = name.findtext("h:family", default="", namespaces=_NS)
                    full_name = f"{given} {family}".strip() or full_name
                gender = pat.find("h:administrativeGenderCode", _NS)
                if gender is not None:
                    sex = _SEX_MAP.get((gender.get("code") or "").upper(), Sex.unknown)
            addr = pr.find("h:addr", _NS)
            if addr is not None:
                city = addr.findtext("h:city", default=None, namespaces=_NS)
                state = addr.findtext("h:state", default=None, namespaces=_NS)
        return Patient(id=pid, full_name=full_name, sex=sex, city=city, state=state, mrn=pid)

    # ---- sections ---------------------------------------------------------
    def _find_section(self, root: ET.Element, loinc: str) -> Optional[ET.Element]:
        for section in root.findall(".//h:section", _NS):
            code = section.find("h:code", _NS)
            if code is not None and code.get("code") == loinc:
                return section
        return None

    def _parse_problems(self, root: ET.Element) -> List[ConditionInstance]:
        section = self._find_section(root, SECTION_PROBLEMS)
        out: List[ConditionInstance] = []
        if section is None:
            return out
        for value in section.findall(".//h:value", _NS):
            code = value.get("code")
            display = value.get("displayName") or ""
            key = self._match_condition(code, display)
            cdef = T.CONDITIONS.get(key) if key else None
            if cdef or display:
                out.append(ConditionInstance(
                    code_key=key or "unknown", name=cdef.name if cdef else display,
                    snomed=cdef.snomed if cdef else code, icd10=cdef.icd10 if cdef else None))
        return out

    def _parse_medications(self, root: ET.Element) -> List[MedicationInstance]:
        section = self._find_section(root, SECTION_MEDICATIONS)
        out: List[MedicationInstance] = []
        if section is None:
            return out
        for mat in section.findall(".//h:manufacturedMaterial", _NS):
            code_el = mat.find("h:code", _NS)
            if code_el is None:
                continue
            code = code_el.get("code")
            display = code_el.get("displayName") or ""
            key = self._match_medication(code, display)
            mdef = T.MEDICATIONS.get(key) if key else None
            out.append(MedicationInstance(
                code_key=key or "unknown", name=mdef.name if mdef else display,
                rxnorm=mdef.rxnorm if mdef else code,
                drug_class=mdef.drug_class if mdef else None))
        return out

    @staticmethod
    def _match_condition(code, display) -> Optional[str]:
        for cdef in T.CONDITIONS.values():
            if code in (cdef.snomed, cdef.icd10):
                return cdef.key
        from medigraph.domain.terminology import condition_by_name

        cdef = condition_by_name(display or "")
        return cdef.key if cdef else None

    @staticmethod
    def _match_medication(code, display) -> Optional[str]:
        for mdef in T.MEDICATIONS.values():
            if code == mdef.rxnorm:
                return mdef.key
        return T.all_medication_synonyms().get((display or "").lower())
