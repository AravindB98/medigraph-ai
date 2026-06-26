"""Supported-systems catalog (US + India).

A declarative map of the real-world systems clinics and hospitals use, the
interoperability standard each speaks, and which MediGraph connector handles it.
Because integration converges on a handful of standards (FHIR R4, HL7 v2, C-CDA,
X12) plus national networks (TEFCA in the US, ABDM in India), one set of
standard adapters covers the long tail of vendors — each row below is "pick the
standard adapter, point it at the endpoint."

Status legend:
- supported : works today (incl. an offline/sample path)
- config    : implemented; needs the customer's endpoint + credentials
- roadmap   : documented integration path on the roadmap
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class CatalogEntry:
    name: str
    country: str            # "US" | "IN" | "Global"
    category: str           # EHR | HIS | Cloud FHIR | HIE/Network | Lab | Pharmacy | Claims | National | Standard | Warehouse/Graph
    standard: str
    connector: str          # connector key
    status: str             # supported | config | roadmap
    notes: str = ""


CATALOG: List[CatalogEntry] = [
    # ---- Open standards (work today) ----
    CatalogEntry("Any HL7 FHIR R4 server", "Global", "Standard", "HL7 FHIR R4", "fhir", "supported",
                 "Universal adapter — the basis for most modern integrations."),
    CatalogEntry("HL7 v2.x feed (ADT/ORU)", "Global", "Standard", "HL7 v2.x", "hl7v2", "supported",
                 "In-hospital messaging for admissions and lab results."),
    CatalogEntry("C-CDA / CCD documents", "US", "Standard", "C-CDA", "ccda", "supported",
                 "Document exchange mandated by US certification programs."),
    CatalogEntry("CSV / flat-file export", "Global", "Standard", "CSV", "csv", "supported",
                 "For small clinics, registries and legacy exports."),
    CatalogEntry("Neo4j knowledge graph", "Global", "Warehouse/Graph", "Property graph", "neo4j", "supported",
                 "Native graph backend (live mode)."),
    CatalogEntry("Snowflake warehouse", "Global", "Warehouse/Graph", "SQL views", "snowflake", "config",
                 "Cloud warehouse source (MEDIGRAPH views)."),

    # ---- US EHR / EMR vendors (via FHIR R4) ----
    CatalogEntry("Epic", "US", "EHR", "HL7 FHIR R4 (US Core)", "fhir", "config",
                 "Epic on FHIR / App Orchard; SMART-on-FHIR OAuth2."),
    CatalogEntry("Oracle Health (Cerner)", "US", "EHR", "HL7 FHIR R4", "fhir", "config",
                 "Cerner Ignite APIs; SMART-on-FHIR."),
    CatalogEntry("athenahealth", "US", "EHR", "HL7 FHIR R4", "fhir", "config",
                 "athenahealth FHIR APIs; OAuth2 client credentials."),
    CatalogEntry("Veradigm (Allscripts)", "US", "EHR", "HL7 FHIR R4", "fhir", "config", "Unity/FHIR APIs."),
    CatalogEntry("eClinicalWorks", "US", "EHR", "HL7 FHIR R4", "fhir", "config", "FHIR R4 endpoints."),
    CatalogEntry("NextGen Healthcare", "US", "EHR", "HL7 FHIR R4", "fhir", "config", "FHIR R4 endpoints."),
    CatalogEntry("MEDITECH", "US", "EHR", "HL7 FHIR R4", "fhir", "config", "Greenfield FHIR APIs."),
    CatalogEntry("Greenway Health", "US", "EHR", "HL7 FHIR R4", "fhir", "config", "FHIR R4 endpoints."),

    # ---- US cloud FHIR & integrators ----
    CatalogEntry("Google Cloud Healthcare API", "US", "Cloud FHIR", "HL7 FHIR R4", "fhir", "config",
                 "Managed R4 store; OAuth bearer."),
    CatalogEntry("AWS HealthLake", "US", "Cloud FHIR", "HL7 FHIR R4", "fhir", "config",
                 "Managed R4 datastore; SigV4."),
    CatalogEntry("Azure Health Data Services", "US", "Cloud FHIR", "HL7 FHIR R4", "fhir", "config",
                 "Azure FHIR service; Entra ID bearer."),
    CatalogEntry("Redox / Health Gorilla / 1upHealth", "US", "HIE/Network", "HL7 FHIR R4", "fhir", "config",
                 "Aggregator platforms exposing normalized FHIR."),
    CatalogEntry("TEFCA / Carequality / CommonWell", "US", "HIE/Network", "FHIR + IHE", "fhir", "roadmap",
                 "National query networks for record retrieval."),
    CatalogEntry("LabCorp / Quest Diagnostics", "US", "Lab", "HL7 v2 / FHIR", "hl7v2", "config",
                 "Lab result feeds via HL7 v2 ORU or FHIR."),
    CatalogEntry("Surescripts (e-prescribing)", "US", "Pharmacy", "NCPDP SCRIPT", "fhir", "roadmap",
                 "Medication history & e-prescribing network."),
    CatalogEntry("Change Healthcare / Availity", "US", "Claims", "X12 EDI", "csv", "roadmap",
                 "Claims/eligibility clearinghouses (837/835/270/271)."),

    # ---- India national stack & HIS vendors ----
    CatalogEntry("ABDM / ABHA (national stack)", "IN", "National", "HL7 FHIR R4 (India IG)", "fhir", "config",
                 "Ayushman Bharat Digital Mission; ABHA-linked consented FHIR via HIE-CM."),
    CatalogEntry("Health Facility Registry (HFR)", "IN", "National", "REST", "fhir", "roadmap",
                 "National registry of facilities."),
    CatalogEntry("Healthcare Professionals Registry (HPR)", "IN", "National", "REST", "fhir", "roadmap",
                 "National registry of clinicians."),
    CatalogEntry("eSanjeevani (telemedicine)", "IN", "National", "FHIR / REST", "fhir", "roadmap",
                 "Government national telemedicine service."),
    CatalogEntry("Insta by Practo", "IN", "HIS", "HL7 / FHIR", "fhir", "config", "Hospital information system."),
    CatalogEntry("KareXpert", "IN", "HIS", "HL7 FHIR R4", "fhir", "config", "Cloud HIS; ABDM-ready."),
    CatalogEntry("Napier Healthcare", "IN", "HIS", "HL7 v2 / FHIR", "hl7v2", "config", "Hospital information system."),
    CatalogEntry("Birlamedisoft", "IN", "HIS", "HL7 v2 / CSV", "hl7v2", "config", "Widely used clinic/hospital HMS."),
    CatalogEntry("MocDoc HMS", "IN", "HIS", "FHIR / CSV", "csv", "config", "Clinic & hospital management."),
    CatalogEntry("Medixcel EMR", "IN", "EHR", "FHIR / CSV", "csv", "config", "Clinic chain EMR."),
    CatalogEntry("CoWIN (immunization)", "IN", "National", "REST API", "fhir", "roadmap", "Vaccination records API."),

    # ---- Cross-cutting roadmap ----
    CatalogEntry("OMOP Common Data Model", "Global", "Standard", "OMOP CDM", "csv", "roadmap",
                 "Research/analytics CDM (OHDSI)."),
    CatalogEntry("DICOMweb imaging", "Global", "Standard", "DICOM / DICOMweb", "fhir", "roadmap",
                 "Imaging metadata linkage."),
]


def catalog_by_country(country: str) -> List[CatalogEntry]:
    return [e for e in CATALOG if e.country in (country, "Global")]


def catalog_summary() -> dict:
    by_status: dict = {}
    by_country: dict = {}
    for e in CATALOG:
        by_status[e.status] = by_status.get(e.status, 0) + 1
        by_country[e.country] = by_country.get(e.country, 0) + 1
    return {"total": len(CATALOG), "by_status": by_status, "by_country": by_country}
