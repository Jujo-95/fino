"""Compatibility module for persisted documents; no graph, embeddings or HippoRAG."""
import re
from pathlib import Path
from typing import Any
from .duckdb_engine import DuckDBFocusEngine


def entities(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", text)}


class ClientContextStore:
    def __init__(self, kb_dir: Path) -> None:
        self.kb = {p.stem: p.read_text() for p in sorted(kb_dir.glob("*.md"))}
        self.clients: dict[str, dict[str, str]] = {}

    def restore(self, client_id: str, engine: DuckDBFocusEngine) -> None:
        with engine.lock:
            self.clients[client_id] = dict(engine.conn.execute("SELECT doc_id,content FROM context_documents").fetchall())

    def prepared_graph(self, client_id: str, doc_id: str, text: str) -> dict[str, str]:
        # Legacy method name retained for atomic ticket projection compatibility.
        return {**self.clients.get(client_id, {}), doc_id: text}

    def documents(self, client_id: str) -> list[dict[str, Any]]:
        return [dict(doc_id=key, text=text) for key, text in self.clients.get(client_id, {}).items()]

    def retrieve(self, query: str, client_id: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        docs = self.clients.get(client_id, {}) if client_id else self.kb
        tokens = entities(query)
        ranked = [(key, text, len(tokens & entities(text))) for key, text in docs.items()]
        return [dict(doc_id=key, text=text, score=score) for key, text, score in
                sorted(ranked, key=lambda item: (-item[2], item[0]))[:limit] if score]



