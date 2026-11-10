"""Scoped historical context for the remaining legacy specialist runner."""
from typing import Any


def history_for_node(state: dict[str, Any], capability: str) -> dict[str, Any]:
    history = state.get('historical_context') or {}
    return dict(
        tickets=[item for item in history.get('tickets', []) if item.get('capability') == capability],
        contributions=[item for item in history.get('contributions', []) if item.get('capability') == capability],
    )
