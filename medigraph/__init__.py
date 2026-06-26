"""MediGraph AI — LLM-enabled healthcare knowledge-graph platform.

A clinical knowledge-graph platform that models patients, encounters, conditions,
medications, providers and observations as an interconnected graph and layers
clinical decision support, population-health analytics, clinical NLP, FHIR
interoperability and grounded GraphRAG Q&A on top of it.

The platform runs **offline by default** (bundled synthetic data + an embedded
in-memory graph + a deterministic query planner) so it can be launched with zero
credentials, and **optionally connects to live infrastructure** (Neo4j AuraDB,
Snowflake, OpenAI) for production deployments.
"""

__version__ = "2.0.0"
__author__ = "Aravind Balaji"

from medigraph.config import get_settings  # noqa: E402,F401

__all__ = ["get_settings", "__version__", "__author__"]
