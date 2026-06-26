"""Clinical NLP — dictionary NER with negation & code mapping.

A lightweight, explainable clinical entity extractor that improves on simple
keyword matching by adding:

- multi-word term matching against curated condition/medication/lab vocabularies,
- **negation detection** (a compact NegEx-style window), so "no chest pain" is not
  recorded as an active problem,
- **code mapping** to SNOMED CT / RxNorm / LOINC, and
- linkage of detected problems to clinical **guidelines** in the knowledge graph.

This is intentionally dependency-free (no model download) so it runs anywhere.
For production, a transformer NER (e.g. medspaCy/scispaCy or a hosted clinical
LLM) can be dropped in behind the same ``extract_entities`` interface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from medigraph.domain import terminology as T

_NEGATION_TRIGGERS = [
    "no", "not", "denies", "denied", "without", "negative for", "absence of",
    "ruled out", "r/o", "no evidence of", "free of", "resolved",
]
_NEGATION_WINDOW = 4  # tokens before the entity


@dataclass
class ClinicalEntity:
    text: str
    entity_type: str          # condition | medication | observation
    code_key: str
    code_system: str
    code: str
    negated: bool = False
    start: int = 0
    end: int = 0


@dataclass
class NoteAnalysis:
    entities: List[ClinicalEntity]
    problems: List[ClinicalEntity] = field(default_factory=list)
    medications: List[ClinicalEntity] = field(default_factory=list)
    observations: List[ClinicalEntity] = field(default_factory=list)
    linked_guidelines: List[dict] = field(default_factory=list)


def _build_lexicon() -> List[tuple]:
    """Return (phrase, type, code_key) sorted by length desc for greedy matching."""
    lex: List[tuple] = []
    for key, syns in _condition_terms().items():
        for s in syns:
            lex.append((s, "condition", key))
    for key, syns in _medication_terms().items():
        for s in syns:
            lex.append((s, "medication", key))
    for key, obs in T.OBSERVATIONS.items():
        for s in [obs.name.lower()] + obs.synonyms:
            lex.append((s, "observation", key))
    # Longer phrases first so "type 2 diabetes" beats "diabetes".
    lex.sort(key=lambda t: len(t[0]), reverse=True)
    return lex


def _condition_terms() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for c in T.CONDITIONS.values():
        out[c.key] = [c.name.lower()] + [s.lower() for s in c.synonyms]
    return out


def _medication_terms() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for m in T.MEDICATIONS.values():
        out[m.key] = [m.name.lower()] + [s.lower() for s in m.synonyms]
    return out


_LEXICON = _build_lexicon()


def _is_negated(text_lower: str, start: int) -> bool:
    """Look back a few tokens for a negation trigger."""
    prefix = text_lower[:start]
    tokens = re.findall(r"[a-z/]+", prefix)
    window = tokens[-_NEGATION_WINDOW:]
    window_str = " ".join(window)
    for trig in _NEGATION_TRIGGERS:
        if trig in window_str:
            # Avoid spanning across sentence boundaries.
            seg = prefix[prefix.rfind(".") + 1:]
            if trig in seg.lower():
                return True
    return False


def extract_entities(text: str) -> List[ClinicalEntity]:
    if not text or not text.strip():
        return []
    lower = text.lower()
    occupied = [False] * len(lower)
    entities: List[ClinicalEntity] = []

    for phrase, etype, key in _LEXICON:
        for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", lower):
            s, e = m.start(), m.end()
            if any(occupied[s:e]):
                continue
            for i in range(s, e):
                occupied[i] = True
            if etype == "condition":
                cdef = T.CONDITIONS[key]
                csys, code = "SNOMED CT", cdef.snomed
            elif etype == "medication":
                mdef = T.MEDICATIONS[key]
                csys, code = "RxNorm", mdef.rxnorm
            else:
                odef = T.OBSERVATIONS[key]
                csys, code = "LOINC", odef.loinc
            entities.append(ClinicalEntity(
                text=text[s:e], entity_type=etype, code_key=key,
                code_system=csys, code=code, negated=_is_negated(lower, s),
                start=s, end=e))
    entities.sort(key=lambda x: x.start)
    return entities


def analyze_note(text: str) -> NoteAnalysis:
    ents = extract_entities(text)
    problems = [e for e in ents if e.entity_type == "condition" and not e.negated]
    meds = [e for e in ents if e.entity_type == "medication" and not e.negated]
    obs = [e for e in ents if e.entity_type == "observation"]

    linked = []
    seen = set()
    for p in problems:
        if p.code_key in seen:
            continue
        seen.add(p.code_key)
        for g in T.guidelines_for(p.code_key):
            linked.append({
                "condition": T.CONDITIONS[p.code_key].name,
                "title": g.title, "source": g.source, "recommendation": g.recommendation})
    return NoteAnalysis(entities=ents, problems=problems, medications=meds,
                        observations=obs, linked_guidelines=linked)
