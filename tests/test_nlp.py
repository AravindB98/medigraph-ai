"""Tests for clinical NLP — multi-word matching, negation, code mapping."""
from __future__ import annotations

from medigraph.services import nlp


def test_extracts_conditions_and_meds():
    na = nlp.analyze_note("Type 2 diabetes and hypertension, on metformin and lisinopril.")
    problems = {p.code_key for p in na.problems}
    meds = {m.code_key for m in na.medications}
    assert "t2dm" in problems
    assert "htn" in problems
    assert "metformin" in meds
    assert "lisinopril" in meds


def test_negation_excludes_problem():
    na = nlp.analyze_note("Patient with diabetes. No chest pain. Denies stroke.")
    active = {p.code_key for p in na.problems}
    negated = {e.code_key for e in na.entities if e.negated}
    assert "t2dm" in active
    assert "stroke" in negated


def test_multiword_beats_substring():
    # "type 2 diabetes" should be a single entity, not split.
    ents = nlp.extract_entities("type 2 diabetes")
    diabetes = [e for e in ents if e.code_key == "t2dm"]
    assert len(diabetes) == 1
    assert diabetes[0].code_system == "SNOMED CT"


def test_guideline_linking():
    na = nlp.analyze_note("History of atrial fibrillation.")
    assert any(g["condition"] == "Atrial fibrillation" for g in na.linked_guidelines)
