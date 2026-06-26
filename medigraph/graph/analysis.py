"""Shared graph algorithms over canonical PatientRecords.

Centralised here so both the embedded and Neo4j backends (and the analytics
services) get *identical* graph projections, visual subgraphs and centrality
results regardless of where the data physically lives.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import networkx as nx
import pandas as pd

from medigraph.domain.models import PatientRecord

# Colour palette for node labels (used by the visual subgraph).
NODE_COLOURS = {
    "Patient": "#38bdf8",
    "Encounter": "#a78bfa",
    "Condition": "#f87171",
    "Medication": "#34d399",
    "Provider": "#fbbf24",
    "Observation": "#94a3b8",
}


def _pagerank(g: nx.Graph, damping: float = 0.85, iterations: int = 60) -> Dict[str, float]:
    """Pure-Python PageRank (power iteration) — avoids a hard scipy dependency.

    Works on an undirected graph by treating each edge as bidirectional.
    """
    nodes = list(g.nodes())
    n = len(nodes)
    if n == 0:
        return {}
    pr = {node: 1.0 / n for node in nodes}
    degrees = {node: g.degree(node) for node in nodes}
    for _ in range(iterations):
        new_pr = {}
        dangling = sum(pr[node] for node in nodes if degrees[node] == 0)
        for node in nodes:
            rank = (1.0 - damping) / n + damping * dangling / n
            for nbr in g.neighbors(node):
                deg = degrees[nbr]
                if deg > 0:
                    rank += damping * pr[nbr] / deg
            new_pr[node] = rank
        norm = sum(new_pr.values()) or 1.0
        pr = {node: val / norm for node, val in new_pr.items()}
    return pr


def build_networkx(records: List[PatientRecord]) -> nx.MultiDiGraph:
    """Project canonical records into a labelled property graph."""
    g = nx.MultiDiGraph()
    for rec in records:
        p = rec.patient
        g.add_node(p.id, label="Patient", title=p.full_name, name=p.full_name)
        for prov in rec.providers:
            g.add_node(prov.id, label="Provider", title=prov.name, name=prov.name)
            g.add_edge(p.id, prov.id, type="HAS_PROVIDER")
        if p.primary_provider_id:
            g.add_edge(p.id, p.primary_provider_id, type="HAS_PROVIDER")
        for c in rec.conditions:
            nid = f"cond:{c.code_key}"
            g.add_node(nid, label="Condition", title=c.name, name=c.name)
            g.add_edge(p.id, nid, type="HAS_CONDITION")
        for m in rec.medications:
            nid = f"med:{m.code_key}"
            g.add_node(nid, label="Medication", title=m.name, name=m.name)
            g.add_edge(p.id, nid, type="TAKES_MEDICATION")
        for e in rec.encounters:
            g.add_node(e.id, label="Encounter", title=e.reason or "Encounter",
                       name=(e.encounter_class.value if hasattr(e.encounter_class, "value") else str(e.encounter_class)))
            g.add_edge(p.id, e.id, type="HAS_ENCOUNTER")
            if e.provider_id:
                g.add_edge(e.id, e.provider_id, type="HAS_PROVIDER")
    return g


def subgraph_elements(
    records: List[PatientRecord], limit: int = 75
) -> Tuple[List[dict], List[dict]]:
    """Build a bounded (nodes, edges) payload for visualisation."""
    nodes: Dict[str, dict] = {}
    edges: List[dict] = []
    triples = 0
    for rec in records:
        if triples >= limit:
            break
        p = rec.patient
        nodes[p.id] = {"id": p.id, "label": p.full_name, "group": "Patient",
                       "color": NODE_COLOURS["Patient"]}
        for c in rec.conditions[:4]:
            nid = f"cond:{c.code_key}"
            nodes[nid] = {"id": nid, "label": c.name, "group": "Condition",
                          "color": NODE_COLOURS["Condition"]}
            edges.append({"from": p.id, "to": nid, "label": "HAS_CONDITION"})
            triples += 1
        for m in rec.medications[:4]:
            nid = f"med:{m.code_key}"
            nodes[nid] = {"id": nid, "label": m.name, "group": "Medication",
                          "color": NODE_COLOURS["Medication"]}
            edges.append({"from": p.id, "to": nid, "label": "TAKES_MEDICATION"})
            triples += 1
        for prov in rec.providers[:1]:
            nodes[prov.id] = {"id": prov.id, "label": prov.name, "group": "Provider",
                              "color": NODE_COLOURS["Provider"]}
            edges.append({"from": p.id, "to": prov.id, "label": "HAS_PROVIDER"})
            triples += 1
    return list(nodes.values()), edges


def provider_centrality(records: List[PatientRecord]) -> pd.DataFrame:
    """Rank providers by PageRank centrality in the patient–provider network,
    with a community label from greedy modularity. Mirrors a Neo4j GDS workflow.
    """
    g = nx.Graph()
    prov_names: Dict[str, str] = {}
    prov_specialty: Dict[str, str] = {}
    for rec in records:
        for prov in rec.providers:
            prov_names[prov.id] = prov.name
            prov_specialty[prov.id] = prov.specialty
        pid = rec.patient.id
        targets = {prov.id for prov in rec.providers}
        if rec.patient.primary_provider_id:
            targets.add(rec.patient.primary_provider_id)
        for e in rec.encounters:
            if e.provider_id:
                targets.add(e.provider_id)
        for prov_id in targets:
            g.add_edge(pid, prov_id)

    if g.number_of_edges() == 0:
        return pd.DataFrame(columns=["provider_id", "name", "specialty", "pr_score",
                                     "patient_panel", "community"])

    pr = _pagerank(g)
    try:
        from networkx.algorithms.community import greedy_modularity_communities

        communities = greedy_modularity_communities(g)
        node_community = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                node_community[node] = idx
    except Exception:  # pragma: no cover
        node_community = {}

    rows = []
    for prov_id, name in prov_names.items():
        if prov_id not in g:
            continue
        panel = g.degree(prov_id)
        rows.append({
            "provider_id": prov_id,
            "name": name,
            "specialty": prov_specialty.get(prov_id, ""),
            "pr_score": round(pr.get(prov_id, 0.0), 5),
            "patient_panel": panel,
            "community": node_community.get(prov_id, 0),
        })
    df = pd.DataFrame(rows).sort_values("pr_score", ascending=False).reset_index(drop=True)
    return df


def latest_observation_datetime(records: List[PatientRecord]):
    """Most recent observation timestamp across the dataset (anchor for 'recent')."""
    latest = None
    for rec in records:
        for o in rec.observations:
            if o.effective_datetime and (latest is None or o.effective_datetime > latest):
                latest = o.effective_datetime
    return latest
