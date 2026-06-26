# Architecture

MediGraph AI is layered so that **clinical logic never depends on where the data
lives or which LLM is configured**. Each layer talks only to the abstraction
below it, and the two infrastructure choices that usually lock a healthcare app
to one vendor — the graph store and the LLM — are pluggable behind interfaces.

## Layers

```
Surfaces        Streamlit clinical app  ·  FastAPI REST/FHIR API
                        │ both call the same facade
Facade          ClinicalEngine  (services/__init__.py)
                        │
Services        decision_support · cohort · analytics · nlp · fhir · qa
                        │ operate on canonical PatientRecords
Graph           GraphBackend  ── EmbeddedGraph (NetworkX)  ↔  Neo4jGraph
                        │
Domain          PatientRecord / Patient / Condition / … + terminology
                        ▲ mapped into by every connector
Connectors      FHIR R4 · HL7 v2 · C-CDA · CSV · Snowflake · Neo4j
Cross-cutting   security (RBAC · JWT · audit · de-identify) · llm (mock ↔ openai) · config
```

## Key design decisions

**Canonical model as the contract.** Every connector maps its source format into
one `PatientRecord` (FHIR-aligned). Services and backends only ever see that
model, so adding Epic, an HL7 feed, or an India ABDM source is additive and never
touches clinical code.

**Data-centric backend interface.** Rather than re-implementing analytics once in
Python (offline) and once in Cypher (Neo4j), backends only *hydrate*
`PatientRecord` objects; the clinical services compute on those uniformly. This
keeps a single source of truth for every score and care-gap rule.

**Offline-first.** With no configuration, `get_settings()` selects the embedded
NetworkX graph over bundled synthetic CSVs and the deterministic planner. Supplying
`NEO4J_*` (and choosing `MEDIGRAPH_GRAPH_BACKEND=neo4j`) or `OPENAI_API_KEY`
switches each subsystem independently, with graceful fallback if a live connection
fails.

**Stable "as-of" clock.** Time-relative logic (overdue labs, recent vitals) is
anchored to the dataset's most recent observation, not wall-clock time, so demos
and tests are reproducible.

**Safety around the LLM.** The LLM is confined to two narrow roles: proposing
read-only Cypher and summarising already-retrieved facts. Any generated Cypher is
passed through a static `cypher_guard` that rejects writes, admin clauses, multiple
statements and APOC/GDS calls, and injects a `LIMIT`. The structured GraphRAG
planner is fully deterministic and grounded.

## Request lifecycle (example: patient assessment)

1. UI/API authenticates the caller (JWT) and checks the `RUN_DECISION_SUPPORT`
   permission (RBAC).
2. `ClinicalEngine.assess(pid)` fetches the `PatientRecord` from the active
   `GraphBackend`.
3. `decision_support.assess_patient` computes eGFR, LACE, CHA₂DS₂-VASc, HAS-BLED,
   care gaps and interactions against the terminology knowledge base.
4. The access is written to the append-only audit log.
5. The result is rendered (Streamlit cards) or serialised (JSON).

## Extending

| To add… | Do this |
|---|---|
| A new data source | Subclass `connectors.BaseConnector`, map to `PatientRecord`, `@register("key")` |
| A new graph store | Implement `graph.base.GraphBackend`, wire it in `graph/__init__.py` |
| A new risk score | Add a function in `services/decision_support.py` and include it in `assess_patient` |
| A new API route | Add to `medigraph/api/main.py` with a `require(Permission.…)` dependency |
| A new LLM provider | Implement `llm.base.Planner`, select it in `llm/__init__.py` |
