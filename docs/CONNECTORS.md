# Connectors & interoperability

MediGraph AI is **vendor-neutral**. Every external system is wrapped in a
`BaseConnector` that maps the source into the canonical `PatientRecord`, so the
clinical features never know whether a patient came from Epic in Ohio or an
ABDM-linked hospital in Bengaluru.

The strategic insight: real-world interoperability in both the US and India
converges on a handful of standards — **HL7 FHIR R4**, **HL7 v2**, **C-CDA** and
**X12** — plus national networks (**TEFCA/Carequality/CommonWell** in the US,
**ABDM/ABHA** in India). So one well-built FHIR adapter plus HL7 v2 and C-CDA
adapters genuinely covers the long tail of vendors; each vendor is "point the
standard adapter at this endpoint with this auth."

## Built-in adapters

| Connector | Standard | Direction | Status | Tested offline |
|---|---|---|---|---|
| `fhir` | HL7 FHIR R4 | read/write | ✅ supported | Yes (round-trips bundles) |
| `hl7v2` | HL7 v2.x (ADT/ORU) | read | ✅ supported | Yes (parses messages) |
| `ccda` | C-CDA / CCD | read | ✅ supported | Yes (parses documents) |
| `csv` | CSV / flat file | read | ✅ supported | Yes (default source) |
| `neo4j` | Property graph | read/write | ✅ supported | Live |
| `snowflake` | SQL warehouse | read | ⚙️ config | Needs credentials |

## Vendor profiles (FHIR R4)

The one `fhir` connector, configured with a base URL + token, covers all of these.
`FHIRConnector.from_vendor(...)` presets the auth style and notes.

| Vendor | Region | Auth |
|---|---|---|
| Epic (Epic on FHIR / App Orchard) | US | SMART-on-FHIR OAuth2 |
| Oracle Health (Cerner Millennium) | US | SMART-on-FHIR |
| athenahealth | US | OAuth2 client credentials |
| Google Cloud Healthcare API | US | OAuth bearer |
| AWS HealthLake | US | AWS SigV4 |
| Azure Health Data Services | US | Entra ID bearer |
| **ABDM / ABHA** | India | ABDM consent + FHIR (India IG) |
| SMART Health IT sandbox | US | Open (testing) |

## Supported-systems catalog (35 entries)

The full catalog is data-driven in `medigraph/connectors/catalog.py` and exposed
at `GET /connectors/catalog` and in the UI (Interoperability page). Highlights:

**🇺🇸 United States** — Epic · Oracle Health (Cerner) · athenahealth · Veradigm
(Allscripts) · eClinicalWorks · NextGen · MEDITECH · Greenway · Google/AWS/Azure
FHIR · Redox/Health Gorilla/1upHealth · TEFCA/Carequality/CommonWell · LabCorp/Quest
· Surescripts · Change Healthcare/Availity.

**🇮🇳 India** — ABDM/ABHA national stack · Health Facility Registry (HFR) ·
Healthcare Professionals Registry (HPR) · eSanjeevani · Insta by Practo · KareXpert
· Napier Healthcare · Birlamedisoft · MocDoc · Medixcel · CoWIN.

**🌐 Global standards** — any FHIR R4 server · HL7 v2 feeds · C-CDA documents · CSV
· Snowflake · Neo4j · OMOP CDM (roadmap) · DICOMweb (roadmap).

> Status legend — **supported**: works today incl. an offline/sample path;
> **config**: implemented, needs the customer's endpoint + credentials;
> **roadmap**: documented integration path.

## Usage

```python
from medigraph.connectors import get_connector

# HL7 v2 ORU lab result → canonical record
rec = get_connector("hl7v2").ingest(oru_message_text)

# C-CDA document → canonical record
rec = get_connector("ccda").ingest(ccd_xml_text)

# FHIR — offline (serves the bundled graph as FHIR) …
fc = get_connector("fhir")
bundle = fc.export(fc.fetch_record("pat-0001"))

# … or live against a real server
from medigraph.connectors.fhir_connector import FHIRConnector
epic = FHIRConnector.from_vendor("epic", base_url="https://fhir.epic.example/api/FHIR/R4",
                                 token="<smart-access-token>")
rec = epic.fetch_record("<patient-id>")
```

## Adding a connector

```python
from medigraph.connectors.base import BaseConnector, ConnectorInfo, Standard, Direction, Status, register

@register("my_his")
class MyHISConnector(BaseConnector):
    info = ConnectorInfo(key="my_his", name="My Hospital HIS", standard=Standard.FHIR_R4,
                         direction=Direction.READ, status=Status.CONFIG, countries=["IN"])
    def test_connection(self): ...
    def fetch_record(self, patient_id): ...   # return a PatientRecord
```

It is now discoverable via `available_connectors()`, the `/connectors` API and the UI.
