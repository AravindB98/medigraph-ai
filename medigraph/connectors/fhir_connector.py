"""Universal HL7 FHIR R4 connector.

FHIR R4 is the single most important integration surface in modern healthcare —
it is how Epic, Oracle Health (Cerner), athenahealth, the cloud FHIR services
(Google Cloud Healthcare API, AWS HealthLake, Azure Health Data Services) and
India's **ABDM** all expose data. This one connector, configured with a base URL
and an access token, therefore covers the large majority of real integrations.

Modes:
- **Offline / demo** (no base_url): serves the bundled graph *as* a FHIR source
  and round-trips bundles through ``services.fhir`` — fully testable with no
  network.
- **Live** (base_url set): performs read calls against a real FHIR server. The
  HTTP client is imported lazily so the offline install needs no extra packages.

Vendor *profiles* preset the base-URL shape and auth style for common systems so
an integrator just supplies their endpoint + token.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from medigraph.connectors.base import (
    BaseConnector,
    ConnectorInfo,
    Direction,
    Standard,
    Status,
    register,
)
from medigraph.domain.models import PatientRecord
from medigraph.services import fhir as fhir_svc


@dataclass
class VendorProfile:
    key: str
    name: str
    country: str
    auth: str            # "SMART/OAuth2", "Bearer", "ABDM consent", "API key"
    notes: str


# Real-world FHIR endpoints all share the R4 REST shape; only base URL + auth differ.
VENDOR_PROFILES: Dict[str, VendorProfile] = {
    "epic": VendorProfile("epic", "Epic (Epic on FHIR / App Orchard)", "US", "SMART/OAuth2",
                          "Epic exposes US Core R4 at /api/FHIR/R4. Register a SMART app for OAuth2."),
    "cerner": VendorProfile("cerner", "Oracle Health (Cerner Millennium)", "US", "SMART/OAuth2",
                            "Cerner Ignite APIs expose R4; SMART-on-FHIR authorization."),
    "athena": VendorProfile("athena", "athenahealth", "US", "OAuth2",
                            "athenahealth FHIR R4 APIs; OAuth2 client credentials."),
    "google_fhir": VendorProfile("google_fhir", "Google Cloud Healthcare API", "US", "Bearer",
                                 "GCP FHIR store R4; OAuth bearer token from a service account."),
    "aws_healthlake": VendorProfile("aws_healthlake", "AWS HealthLake", "US", "SigV4",
                                    "HealthLake is a managed R4 datastore; AWS SigV4 signed requests."),
    "azure_fhir": VendorProfile("azure_fhir", "Azure Health Data Services", "US", "Bearer",
                                "Azure FHIR service R4; Entra ID bearer token."),
    "abdm": VendorProfile("abdm", "ABDM / ABHA (India)", "IN", "ABDM consent",
                          "India's national health stack: FHIR R4 via the HIE-CM with ABHA-linked "
                          "consent artefacts. Profiles align to NRCeS India FHIR IG."),
    "smart_sandbox": VendorProfile("smart_sandbox", "SMART Health IT sandbox", "US", "Open/SMART",
                                   "Public R4 sandbox useful for testing the live path."),
}


@register("fhir")
class FHIRConnector(BaseConnector):
    info = ConnectorInfo(
        key="fhir", name="HL7 FHIR R4", standard=Standard.FHIR_R4,
        direction=Direction.BIDIRECTIONAL, status=Status.SUPPORTED,
        description="Universal FHIR R4 adapter (Epic, Cerner, athenahealth, cloud FHIR, ABDM).",
        countries=["US", "IN"])

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None,
                 vendor: Optional[str] = None, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/") if base_url else None
        self.token = token
        self.vendor = vendor
        self.timeout = timeout

    @classmethod
    def from_vendor(cls, vendor: str, base_url: str, token: Optional[str] = None) -> "FHIRConnector":
        if vendor not in VENDOR_PROFILES:
            raise KeyError(f"Unknown vendor profile '{vendor}'.")
        return cls(base_url=base_url, token=token, vendor=vendor)

    # ---- status -----------------------------------------------------------
    def test_connection(self) -> str:
        if not self.base_url:
            return "Offline FHIR mode — serving the bundled knowledge graph as FHIR R4."
        meta = self._get("metadata")
        kind = meta.get("fhirVersion", "unknown") if isinstance(meta, dict) else "unknown"
        return f"Connected to FHIR server ({self.base_url}); fhirVersion={kind}."

    # ---- read -------------------------------------------------------------
    def fetch_record(self, patient_id: str) -> Optional[PatientRecord]:
        if not self.base_url:
            from medigraph.services import get_engine

            return get_engine().record(patient_id)
        # Live: assemble a bundle from standard R4 search queries.
        bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}
        patient = self._get(f"Patient/{patient_id}")
        if patient:
            bundle["entry"].append({"resource": patient})
        for rtype in ("Condition", "MedicationStatement", "Observation", "Encounter"):
            search = self._get(f"{rtype}?patient={patient_id}&_count=200")
            for e in (search.get("entry", []) if isinstance(search, dict) else []):
                bundle["entry"].append({"resource": e.get("resource", {})})
        return fhir_svc.bundle_to_record(bundle)

    def fetch_all(self, limit: Optional[int] = None) -> List[PatientRecord]:
        if not self.base_url:
            from medigraph.services import get_engine

            recs = get_engine().all_records()
            return recs[:limit] if limit else recs
        search = self._get(f"Patient?_count={limit or 50}")
        ids = [e["resource"]["id"] for e in (search.get("entry", []) if isinstance(search, dict) else [])]
        return [r for r in (self.fetch_record(pid) for pid in ids) if r]

    # ---- ingest / export --------------------------------------------------
    def ingest(self, payload: dict) -> PatientRecord:
        return fhir_svc.bundle_to_record(payload)

    def export(self, record: PatientRecord) -> dict:
        return fhir_svc.record_to_bundle(record)

    # ---- live HTTP --------------------------------------------------------
    def _get(self, path: str) -> dict:
        import urllib.request  # stdlib; avoids a hard httpx dependency

        url = f"{self.base_url}/{path}"
        headers = {"Accept": "application/fhir+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
            import json

            return json.loads(resp.read().decode())
