# Roadmap

MediGraph AI is built on open standards and a pluggable core, so the roadmap is
about depth and reach rather than rewrites. Future-proofing themes:

## Interoperability
- **SMART-on-FHIR app launch** — run inside the EHR with EHR-issued OAuth context.
- **TEFCA / QHIN query** — national record retrieval (Carequality/CommonWell).
- **ABDM end-to-end** — ABHA linking, consent artefacts via HIE-CM, India FHIR IG profiles.
- **FHIR Subscriptions / HL7 v2 MLLP listener** — real-time feeds instead of pull.
- **Bulk FHIR ($export)** for population loads; **X12** 837/835/270-271 for claims & eligibility.

## Data & modelling
- **OMOP CDM** import/export for research interoperability (OHDSI tools).
- **DICOMweb** linkage for imaging metadata.
- Full terminology service (SNOMED/LOINC/RxNorm) replacing the bundled subset.

## Intelligence
- **Vector / semantic retrieval** layer for GraphRAG (embeddings over notes + nodes)
  combined with the existing structured planner.
- **Transformer clinical NER** (medspaCy/scispaCy or a hosted clinical LLM) behind
  the current `extract_entities` interface, with the dictionary NER as fallback.
- **Calibrated ML risk models** (e.g. readmission, deterioration) alongside the
  transparent rule-based scores, with explainability.
- **Agentic care-coordination** workflows (draft referrals, prep visit summaries,
  close care gaps) with human-in-the-loop approval.

## Platform
- Persistent stores for users/audit (Postgres) and an admin console.
- Write-back of computed flags to the EHR via FHIR (where permitted).
- Multi-tenant deployment, per-tenant audit and data isolation.
- FHIR-conformance and security test suites in CI.

## Governance
- Model cards / measure definitions for every score.
- Bias & drift monitoring for any ML components.
- Configurable data-residency (US vs India) and retention policies.

> Contributions welcome — the connector registry and service layer are designed so
> most of the above is additive.
