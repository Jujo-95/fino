"""Deterministic input signatures and completed-run context; no model calls."""
import hashlib
import json
from typing import Any
from ..config import ROOT, KB_DIR
from .schema import COLUMNS
from .run_audit import RunAuditStore


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def data_digest(client: Any, state: dict[str, Any]) -> str:
    fields = ','.join('"'+name+'"' for name in COLUMNS)
    checksum = hashlib.sha256()
    with client.engine.lock:
        cursor = client.engine.conn.execute(f'SELECT {fields} FROM focus_usage WHERE client_id=? '
            'AND ChargePeriodStart>=? AND ChargePeriodStart<? AND BillingCurrency=? ORDER BY row_key',
            [state['client_id'], state['period_start_utc'], state['period_end_utc'], state['billing_currency']])
        while rows := cursor.fetchmany(1000):
            for row in rows:
                checksum.update((json.dumps(row, default=str, ensure_ascii=False)+'\n').encode())
    return checksum.hexdigest()


def implementation_digest() -> str:
    paths = [*(p for p in ROOT.glob('prompts/*.md') if p.stem in {'common', 'orchestrator', 'allocation',
        'anomaly-management', 'forecasting', 'budgeting', 'rate-optimization'}), *KB_DIR.glob('*.md'),
             *(ROOT/'backend/src/finops_agent').rglob('*.py')]
    return digest([(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
                    hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(paths)])


def input_signature(container: Any, state: dict[str, Any]) -> dict[str, str]:
    client = container.client(state['client_id'])
    with client.engine.lock:
        notes = client.engine.conn.execute("SELECT d.doc_id,d.content FROM context_documents d "
            "LEFT JOIN tickets_ledger t ON d.doc_id=t.fingerprint WHERE "
            "NOT starts_with(d.doc_id,'report:') AND t.fingerprint IS NULL ORDER BY d.doc_id").fetchall()
        decisions = ticket_inputs(client)
        data = data_digest(client, state)
    provider = getattr(container.llm, 'audit_config', lambda: {'provider':type(container.llm).__name__})()
    parts = dict(data=data, context=digest(notes), decisions=digest(decisions),
        profile=digest(client.profile.model_dump()), implementation=implementation_digest(), provider=digest(provider),
        request=digest({key:state.get(key) for key in ('client_id','period_start_utc','period_end_utc',
            'billing_currency','run_mode','instruction')}))
    return {**parts, 'combined':digest(parts)}


def previous_run(client: Any, state: dict[str, Any]) -> dict[str, Any] | None:
    store = RunAuditStore(client.workspace)
    if state.get('reference_run_id'):
        explicit = store.read(state['reference_run_id'])
        return store.read(explicit['reused_run_id']) if explicit.get('reused_run_id') else explicit
    paths = sorted(store.directory.glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
    for path in paths:
        record = json.loads(path.read_text())
        if (record.get('status') == 'completed' and record.get('billing_currency') == state['billing_currency']
                and record.get('report_markdown') and not record.get('reused_run_id')):
            return dict(record)
    return None


def prior_context(record: dict[str, Any] | None, tickets: list[Any], node: str | None = None) -> dict[str, Any]:
    if not record:
        return dict(previous_run_id=None, tickets=[t.model_dump(mode='json') for t in tickets])
    traces = [event['payload'].get('trace') for event in record.get('events', [])]
    contributions = [dict(node=t['node'], output=t.get('output'), findings=t.get('findings', []))
                     for t in traces if t and (t['node'] == node if node else t['node'] != 'ingest_and_profile')]
    return dict(previous_run_id=record['run_id'], period_start_utc=record['period_start_utc'],
        period_end_utc=record['period_end_utc'], contributions=contributions,
        tickets=[t.model_dump(mode='json') for t in tickets], prior_review=record.get('incremental', {}).get('ticket_review', []))


def ticket_inputs(client: Any) -> list[dict[str, str]]:
    return [dict(ticket_id=t.ticket_id, fingerprint=t.fingerprint, status=t.status, note=t.resolution_note)
            for t in client.tickets.list()]


def finalized_signature(state: dict[str, Any], tickets: list[Any]) -> dict[str, str]:
    # Add only tickets emitted by this run. Keep starting human decisions so concurrent edits invalidate reuse.
    initial = {item['ticket_id']:item for item in state.get('ticket_inputs', [])}
    for ticket in tickets:
        initial.setdefault(ticket.ticket_id, dict(ticket_id=ticket.ticket_id, fingerprint=ticket.fingerprint,
                                                status=ticket.status, note=ticket.resolution_note))
    parts = {key:value for key,value in state.get('input_signature', {}).items() if key != 'combined'}
    parts['decisions'] = digest([initial[key] for key in sorted(initial)])
    return {**parts, 'combined':digest(parts)}
