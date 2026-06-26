"""Live OpenAI planner.

Translates natural language to read-only Cypher using the shared schema hint.
The output is always passed through ``cypher_guard.validate`` by the caller
before any execution — this module never touches the database itself.
"""
from __future__ import annotations

from medigraph.config import get_settings
from medigraph.llm.base import SCHEMA_HINT, Planner


class OpenAIPlanner(Planner):
    name = "openai"
    is_live = True

    def __init__(self):
        from openai import OpenAI  # imported lazily

        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def generate_cypher(self, question: str) -> str:
        if not question or not question.strip():
            raise ValueError("Question is empty.")
        prompt = (
            f"{SCHEMA_HINT}\n\nUser question:\n\"\"\"{question.strip()}\"\"\"\n\n"
            "Respond with a SINGLE valid read-only Cypher query. No markdown, no comments."
        )
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are an expert Neo4j Cypher generator. "
                                              "You only ever produce read-only queries."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        cypher = resp.choices[0].message.content.strip()
        if cypher.startswith("```"):
            cypher = cypher.strip("`")
            if cypher.lower().startswith("cypher"):
                cypher = cypher[6:].strip()
        return cypher

    def summarize(self, question: str, facts: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "Summarise the clinical facts factually and "
                                              "concisely. Do not add anything not in the facts."},
                {"role": "user", "content": f"Question: {question}\n\nFacts:\n{facts}"},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
