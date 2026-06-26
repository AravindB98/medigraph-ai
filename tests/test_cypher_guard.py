"""Tests for the read-only Cypher guardrail."""
from __future__ import annotations

import pytest

from medigraph.graph.cypher_guard import validate


@pytest.mark.parametrize("query", [
    "MATCH (p:Patient) RETURN p LIMIT 5",
    "match (p:Patient)-[:HAS_CONDITION]->(c) where toLower(c.name) contains 'diabetes' return p",
])
def test_read_queries_allowed(query):
    assert validate(query).allowed


@pytest.mark.parametrize("query", [
    "MATCH (p) DELETE p",
    "CREATE (p:Patient {id:'x'}) RETURN p",
    "MATCH (p:Patient) SET p.name='x' RETURN p",
    "MERGE (p:Patient {id:'x'})",
    "MATCH (p) DETACH DELETE p",
    "CALL apoc.export.csv.all('x', {}) YIELD file RETURN file",
    "MATCH (p) RETURN p; MATCH (q) RETURN q",
    "DROP INDEX ON :Patient(id)",
])
def test_write_queries_blocked(query):
    result = validate(query)
    assert not result.allowed
    assert result.reason


def test_limit_injected_when_missing():
    result = validate("MATCH (p:Patient) RETURN p")
    assert result.allowed
    assert "LIMIT" in result.normalized.upper()


def test_string_literals_do_not_falsely_trip_guard():
    # "create" inside a string literal must not block a legitimate read.
    q = "MATCH (c:Condition) WHERE c.name = 'procreate study' RETURN c"
    assert validate(q).allowed
