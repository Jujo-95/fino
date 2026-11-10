import logging
from datetime import date
from typing import Any
import yaml


def recalled_suppressions(memory: Any, client_id: str, keys: list[str], start: str, end: str, evidence: list[dict[str, Any]] | None = None) -> set[str]:
    suppressed: set[str] = set()
    for key in keys:
        passages = memory.documents(client_id)
        # Match exact structured identity/date/status across every persisted document.
        if evidence is not None:
            evidence.extend({**passage, "source": "client_memory", "query": key,
                "usage": "anomaly_suppression_check"} for passage in passages)
        documents = [frontmatter(passage['text']) for passage in passages]
        if any(matches_decision(doc, key, start) or matches_plan(doc, key, start, end) for doc in documents):
            suppressed.add(key)
    return suppressed


def frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith('---\n'):
        return {}
    pieces = text.split('---', 2)
    try:
        parsed = yaml.safe_load(pieces[1]) if len(pieces) > 2 else {}
    except yaml.YAMLError:
        logging.getLogger(__name__).warning("Ignoring malformed context metadata")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def matches_decision(doc: dict[str, Any], key: str, start: str) -> bool:
    identity = str(doc.get('sub_account_id')) + ':' + str(doc.get('service_name'))
    if doc.get('capability') != 'anomaly-management' or identity != key or doc.get('period_bucket') != start[:7]:
        return False
    status = doc.get('status')
    approved_plan = status == 'APPROVED' and any(token in str(doc.get('resolution_note', '')).lower()
                                                for token in ('planned', 'planificado', 'approved training'))
    return status in ('FALSE_POSITIVE', 'SNOOZED', 'REJECTED', 'IMPLEMENTED', 'RESOLVED') or approved_plan


def matches_plan(doc: dict[str, Any], key: str, start: str, end: str) -> bool:
    events = doc.get('planned_events', [])
    if not isinstance(events, list):
        return False
    return any(isinstance(event, dict) and active_plan(event, key, start, end) for event in events)


def active_plan(event: dict[str, Any], key: str, start: str, end: str) -> bool:
    identity = str(event.get('sub_account_id')) + ':' + str(event.get('service_name'))
    if identity != key or event.get('approved') is not True:
        return False
    try:
        first = date.fromisoformat(str(event['start_utc'])[:10])
        last = date.fromisoformat(str(event['end_utc'])[:10])
        selected_end = date.fromisoformat(end[:10])
    except (KeyError, ValueError):
        return False
    return first < selected_end <= last
