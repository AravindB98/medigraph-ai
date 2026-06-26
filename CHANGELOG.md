# Changelog

All notable changes to MediGraph AI are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [2.0.0] — Platform rebuild

The original prototype was a single 1,592-line Streamlit script hard-wired to a
private Snowflake + Neo4j AuraDB + OpenAI account, with secrets committed to the
repository. v2 is a ground-up rebuild into a modular, testable, **runs-anywhere**
clinical platform.

### Added
- **Offline-first architecture.** Bundled synthetic EHR data + an embedded
  NetworkX knowledge graph + a deterministic query planner mean the whole
  platform launches with **zero credentials**.
- **Pluggable backends.** Graph (embedded ↔ Neo4j) and LLM (deterministic ↔
  OpenAI) can each be swapped independently via environment variables.
- **Pluggable connector framework** for real-world systems used in the US and
  India: FHIR R4 (Epic, Cerner/Oracle Health, Athenahealth, Google/AWS/Azure
  FHIR, **ABDM/ABHA**), HL7 v2 (ADT/ORU), C-CDA, CSV/flat-file, Snowflake, Neo4j.
- **Clinical decision support**: LACE readmission risk, CHA₂DS₂-VASc stroke risk,
  eGFR/CKD staging, care-gap detection and drug–drug interaction checks.
- **Population health & cohort builder** with quality measures.
- **Clinical NLP** with dictionary NER, negation detection and code mapping.
- **FHIR R4 import/export** (Patient, Condition, MedicationStatement, Encounter,
  Observation bundles).
- **GraphRAG Q&A** grounded in the graph, with citations and a read-only query
  guardrail.
- **Security**: role-based access control, JWT auth, HIPAA-flavoured audit log,
  PHI de-identification.
- **FastAPI** REST + FHIR API sharing the same core services.
- **Tests** (pytest), **Docker** / docker-compose, **CI** and a self-explaining
  **GitHub Pages** demo site.

### Security
- Removed all committed secrets and the committed virtual environment.
- `.env` is gitignored; only `.env.example` (no secrets) is tracked.
- **Rotate any credentials that were previously committed — treat them as
  compromised.**
