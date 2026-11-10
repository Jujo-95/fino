"""Committed lifecycle events, with conservative recovery from command receipts."""
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Any
from ..engine.incremental_inputs import digest
from .ticket_lifecycle import task_state


def record_transition(tx: Any, ticket: Any) -> None:
    tx.execute('CREATE TABLE IF NOT EXISTS task_progress_events (id VARCHAR PRIMARY KEY, document JSON)')
    row = tx.execute('SELECT document FROM tickets_ledger WHERE client_id=? AND ticket_id=?',
                     [ticket.client_id,ticket.ticket_id]).fetchone()
    if not row:
        return
    before, after = json.loads(row[0]), ticket.model_dump(mode='json')
    if before['status']==after['status']:
        return
    identity = digest([ticket.client_id,ticket.ticket_id,before['updated_at_utc'],after['updated_at_utc'],after['status']])
    event = dict(id=identity,client_id=ticket.client_id,ticket_id=ticket.ticket_id,title=ticket.title,
        before=before['status'],after=ticket.status,state=task_state(after),at=ticket.updated_at_utc,
        summary=ticket.note_history[-1].get('text',ticket.resolution_note) if ticket.note_history else ticket.resolution_note,
        actor=ticket.note_history[-1].get('actor','not_recorded') if ticket.note_history else 'not_recorded',
        evidence=dict(run_id=ticket.last_evaluated_run_id,criterion=ticket.followup.closure_criterion if ticket.followup else ticket.action_details.completion_criterion))
    tx.execute('INSERT OR IGNORE INTO task_progress_events VALUES (?,?)',[identity,json.dumps(event)])


def read_events(client: Any) -> list[dict[str, Any]]:
    with client.engine.lock:
        tables = {r[0] for r in client.engine.conn.execute('SHOW TABLES').fetchall()}
        events = [json.loads(r[0]) for r in client.engine.conn.execute('SELECT document FROM task_progress_events').fetchall()] if 'task_progress_events' in tables else []
        receipts = client.engine.conn.execute('SELECT document FROM ticket_commands').fetchall() if 'ticket_commands' in tables else []
        keys = {(e['ticket_id'],e['at'],e['after']) for e in events}
        for row in receipts:
            receipt = json.loads(row[0])
            before = {t['ticket_id']:t for t in receipt.get('before',[]) if t.get('ticket_id')}
            for ticket in receipt.get('result',{}).get('tickets',[]):
                old = before.get(ticket['ticket_id'])
                key = (ticket['ticket_id'],ticket['updated_at_utc'],ticket['status'])
                if old and old['status']!=ticket['status'] and key not in keys:
                    events.append(dict(id=digest(key),client_id=client.profile.client_id,ticket_id=ticket['ticket_id'],
                        title=ticket['title'],before=old['status'],after=ticket['status'],state=task_state(ticket),
                        at=ticket['updated_at_utc'],summary=ticket.get('resolution_note',''),evidence=dict(command_id=receipt['command_id'])))
                    keys.add(key)
    return sorted((e for e in events if e['client_id']==client.profile.client_id),key=lambda e:e['at'],reverse=True)


def history_summary(client: Any, tickets: list[dict[str, Any]]) -> dict[str, Any]:
    events = read_events(client)
    current = {t['ticket_id']:t for t in tickets}
    now = datetime.now(timezone.utc).astimezone(ZoneInfo('America/Bogota'))
    monday = (now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
    closures = [e for e in events if e['state']=='resolved' and e['ticket_id'] in current
                and task_state(current[e['ticket_id']])=='resolved']
    week = {e['ticket_id'] for e in closures if datetime.fromisoformat(e['at'].replace('Z','+00:00'))>=monday}
    return dict(resolved_total=sum(task_state(t)=='resolved' for t in tickets),resolved_this_week=len(week),
        observing=sum(task_state(t)=='monitoring' for t in tickets),recent=events[:30],
        timezone='America/Bogota',week_start=monday.isoformat())
