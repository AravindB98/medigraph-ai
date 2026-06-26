"""Read-only Cypher guardrail.

When the LLM proposes Cypher to run against a live Neo4j database, we must never
let it mutate or exfiltrate the graph. This module statically validates a query
and rejects anything that is not a pure read. It is intentionally conservative:
when in doubt, block.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

# Clauses / procedures that can write, delete, or escape the sandbox.
_FORBIDDEN_KEYWORDS = [
    "create", "merge", "delete", "detach", "set ", "remove", "drop",
    "foreach", "load csv", "call db.", "call dbms.", "call apoc.",
    "call gds.", "periodic", "use ", "grant", "deny", "revoke",
    "terminate", "show ", "alter",
]
# Multi-statement attempts.
_SEMICOLON = re.compile(r";\s*\S")


@dataclass
class GuardResult:
    allowed: bool
    reason: str = ""
    normalized: str = ""


def _strip(cypher: str) -> str:
    # Remove /* */ and // comments and string literals before keyword scan.
    no_block = re.sub(r"/\*.*?\*/", " ", cypher, flags=re.S)
    no_line = re.sub(r"//[^\n]*", " ", no_block)
    no_strings = re.sub(r"'(?:[^'\\]|\\.)*'", "''", no_line)
    no_strings = re.sub(r'"(?:[^"\\]|\\.)*"', '""', no_strings)
    return no_strings


def validate(cypher: str) -> GuardResult:
    if not cypher or not cypher.strip():
        return GuardResult(False, "Empty query.")

    raw = cypher.strip().rstrip(";").strip()
    scan = _strip(raw).lower()

    if _SEMICOLON.search(_strip(raw)):
        return GuardResult(False, "Multiple statements are not allowed.")

    for kw in _FORBIDDEN_KEYWORDS:
        if kw in scan:
            return GuardResult(False, f"Write/admin keyword detected: '{kw.strip()}'.")

    # Must be a read query — start with MATCH / WITH / UNWIND / RETURN / OPTIONAL.
    if not re.match(r"^(match|with|unwind|optional match|return|profile|explain)\b", scan):
        return GuardResult(False, "Query must begin with a read clause (MATCH/WITH/UNWIND/RETURN).")

    if "return" not in scan:
        return GuardResult(False, "Read query must contain a RETURN clause.")

    # Enforce a result ceiling for safety if no LIMIT present.
    normalized = raw
    if not re.search(r"\blimit\b", scan):
        normalized = f"{raw}\nLIMIT 200"

    return GuardResult(True, "ok", normalized)


def is_read_only(cypher: str) -> bool:
    return validate(cypher).allowed
