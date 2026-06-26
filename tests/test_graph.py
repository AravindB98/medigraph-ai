"""Tests for the embedded graph backend and graph analysis."""
from __future__ import annotations

from medigraph.graph import get_graph
from medigraph.graph.analysis import provider_centrality, subgraph_elements


def test_embedded_graph_loads():
    g = get_graph(force_reload=True)
    stats = g.stats()
    assert stats.node_counts.get("Patient", 0) > 50
    assert stats.total_relationships > 0
    assert g.name == "embedded"


def test_patient_records_hydrate():
    g = get_graph()
    recs = g.all_patient_records()
    assert len(recs) > 50
    r = recs[0]
    assert r.patient.id
    assert isinstance(r.condition_keys, list)


def test_subgraph_bounded():
    g = get_graph()
    nodes, edges = g.subgraph_elements(limit=30)
    assert len(nodes) > 0
    assert len(edges) > 0
    assert len(edges) <= 60  # roughly bounded by the triple limit


def test_provider_centrality_ranks():
    g = get_graph()
    df = provider_centrality(g.all_patient_records())
    assert not df.empty
    assert df.iloc[0]["pr_score"] >= df.iloc[-1]["pr_score"]
    assert {"provider_id", "pr_score", "community"}.issubset(df.columns)
