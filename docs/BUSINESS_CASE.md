# Business case

A concise commercial framing for MediGraph AI — useful for pitches, stakeholder
conversations and interviews.

## The problem (and why now)
Care teams are accountable for outcomes and quality measures, but the data needed
to act lives in disconnected tables across the EHR, lab and pharmacy systems.
Care gaps (an un-anticoagulated AF patient, a diabetic overdue for HbA1c) go
unseen until they become admissions. Meanwhile, regulation in both markets is
forcing data to open up — **US: ONC info-blocking rules, USCDI, TEFCA**; **India:
ABDM/ABHA** — which finally makes a vendor-neutral, FHIR-native layer practical.

## The product
A clinical knowledge-graph layer that sits on top of existing systems (it does not
replace the EHR) and turns connected data into **prioritised, explainable action**:
risk scores, care-gap worklists, population quality measures, and grounded Q&A —
with the interoperability to ingest from any FHIR/HL7/C-CDA source.

## Who buys it
| Segment | Primary value | Buyer |
|---|---|---|
| Hospitals / health systems | Reduce 30-day readmissions; close GDMT/anticoagulation gaps | CMIO, Quality, Population Health |
| Small & mid clinics | Turn-key diabetes/HTN registries with minimal IT lift | Practice owner / lead physician |
| ACOs & value-based groups | HEDIS-style measurement + risk stratification across panels | VBC / quality leadership |
| Payers & digital-health | De-identified population analytics; API integration | Analytics / product |

## Value drivers
- **Readmission reduction.** LACE-based targeting concentrates discharge resources
  where they change outcomes; even small reductions move large penalty dollars
  (US HRRP) and bed-day costs.
- **Quality-measure performance.** Directly tracks and surfaces the gaps behind
  HEDIS/MIPS-style measures, tied to value-based revenue.
- **Clinician time saved.** One-click cohorts and grounded Q&A replace manual
  chart review and brittle SQL.
- **Faster integration.** Standards-first connectors shorten the usual EHR
  integration timeline and de-risk multi-vendor environments.

## Why it can win
- **Explainable by construction** — every score is rule-based and citable, which
  clinicians trust and regulators expect (vs. opaque ML).
- **Vendor-neutral** — one FHIR/HL7/C-CDA core spans Epic, Cerner, athenahealth and
  the Indian HIS/ABDM ecosystem.
- **Low adoption friction** — runs offline with synthetic data for evaluation; no
  credentials needed to trial the full feature set.
- **Dual-market** — purpose-built for both US and India interoperability stacks.

## Deployment & commercial model (illustrative)
SaaS per-provider or per-bed subscription, with a self-hosted/on-prem option for
data-residency-sensitive customers. Land with a single high-value workflow
(readmissions or a diabetes registry), expand to population health and Q&A.

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| Regulatory (clinical claims) | Position as decision support, not a diagnostic device; keep scores transparent |
| Data access / integration | Standards-first connectors; partner with HIE aggregators (Redox, Health Gorilla) |
| Privacy & trust | RBAC, audit, de-identification built in; BAA/ABDM compliance posture |
| Incumbent EHR modules | Complement, don't replace; integrate via FHIR and write-back where allowed |

> Figures and segments here are illustrative framing, not financial projections.
