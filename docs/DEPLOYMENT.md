# Deployment

## Local (offline demo)

```bash
pip install -r requirements.txt
streamlit run ui/streamlit_app.py          # UI  → :8501
uvicorn medigraph.api.main:app --reload    # API → :8000/docs
```

## Docker

```bash
docker build -t medigraph-ai .
docker run -p 8501:8501 medigraph-ai                 # UI
docker run -p 8000:8000 medigraph-ai \
  uvicorn medigraph.api.main:app --host 0.0.0.0      # API
```

## Docker Compose (UI + API together)

```bash
docker compose up        # UI :8501, API :8000
```

Uncomment the `neo4j` service and the `NEO4J_*` env vars in `docker-compose.yml`
to run against a live knowledge graph with Graph Data Science enabled.

## Going live

Each subsystem is enabled independently via environment variables (see
`.env.example`). With none set, everything stays offline.

| Capability | Variables |
|---|---|
| Live graph (Neo4j AuraDB) | `MEDIGRAPH_GRAPH_BACKEND=neo4j`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` |
| Live LLM (OpenAI) | `MEDIGRAPH_LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Warehouse source | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, … |
| Security | `MEDIGRAPH_SECRET_KEY`, `MEDIGRAPH_TOKEN_TTL_MIN` |
| Dataset size | `MEDIGRAPH_SYNTH_PATIENTS`, `MEDIGRAPH_SYNTH_SEED` |

If a live connection fails at startup, the platform logs a warning and falls back
to the embedded backend, so a bad credential never causes a hard outage.

## Loading real data into Neo4j

Point a connector at your source and write the canonical records to Neo4j using the
schema in [DATA_MODEL.md](DATA_MODEL.md). A minimal ingest loop:

```python
from medigraph.connectors import get_connector
records = get_connector("fhir").fetch_all(limit=1000)   # or hl7v2/ccda/csv
# upsert each record into Neo4j using the documented node/relationship schema
```

## GitHub Pages (demo website)

`/.github/workflows/pages.yml` regenerates the demo data and publishes `website/`
on every push to `main`. Enable it in **Settings → Pages → Source: GitHub Actions**.

## Scaling notes

- The embedded graph is in-memory and ideal for demos, small clinics and a few
  thousand patients. For hospital-scale data, use the Neo4j backend.
- The API is stateless behind the JWT, so it scales horizontally; put it behind a
  load balancer and terminate TLS at the edge.
- Heavy population analytics iterate every record; cache results or precompute on a
  schedule for very large panels.
