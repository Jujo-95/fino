import json
from datetime import datetime, timedelta, timezone
from typing import Any
from ..engine.incremental_inputs import digest
from ..engine.ticket_batch import commit_batch
from .models import PlanRequest
from .operation_batch import before_changes, prepare_batch


def revision(ticket: Any) -> str:
    return digest(ticket.model_dump(mode='json',exclude={'is_new','reviewed_at_utc','needs_attention','attention_reason','last_evaluated_run_id'}))


class TicketOperations:
    def __init__(self, client: Any) -> None:
        self.client = client
        with client.engine.atomic_tx() as tx:
            tx.execute('CREATE TABLE IF NOT EXISTS ticket_change_plans '
                '(plan_id VARCHAR PRIMARY KEY, thread_id VARCHAR, status VARCHAR, document JSON)')
            tx.execute('CREATE TABLE IF NOT EXISTS ticket_commands '
                '(command_id VARCHAR PRIMARY KEY, plan_id VARCHAR UNIQUE, thread_id VARCHAR, document JSON)')

    def tickets(self, ids: list[str]) -> list[dict[str, Any]]:
        records = {t.ticket_id:t for t in self.client.tickets.list()}
        if not ids or len(ids)>50 or any(key not in records for key in ids):
            raise ValueError('Los tickets deben existir en este cliente (máximo 50).')
        return [{**records[key].model_dump(mode='json'), 'revision':revision(records[key])} for key in ids]

    def plan(self, request: PlanRequest, thread_id: str, turn_id: str, *, contributors: list[dict[str,str]] | None = None, report_run_id: str | None = None) -> dict[str, Any]:
        plan_id = digest([thread_id, turn_id, request.model_dump(mode='json',exclude_unset=True),report_run_id])
        with self.client.engine.lock:
            existing = self.client.engine.conn.execute('SELECT document FROM ticket_change_plans WHERE plan_id=?', [plan_id]).fetchone()
            if existing:
                return dict(json.loads(existing[0]))
            completed = self.completed_equivalent(request,thread_id,turn_id)
            if completed:
                return completed
            before = before_changes(self,request)
            now = datetime.now(timezone.utc)
            plan = dict(plan_id=plan_id, thread_id=thread_id, turn_id=turn_id, status='pending',
                expires_at=(now+timedelta(hours=24)).isoformat(), changes=request.model_dump(mode='json',exclude_unset=True)['changes'], before=before,
                contributors=contributors or [],report_run_id=report_run_id)
            with self.client.engine.atomic_tx() as tx:
                tx.execute('INSERT INTO ticket_change_plans VALUES (?,?,?,?)', [plan_id, thread_id, 'pending', json.dumps(plan)])
            return plan

    def completed_equivalent(self, request: PlanRequest, thread_id: str, turn_id: str) -> dict[str, Any] | None:
        rows = self.client.engine.conn.execute("SELECT document FROM ticket_change_plans WHERE thread_id=? AND status='applied'",
                                              [thread_id]).fetchall()
        def shape(changes: list[dict[str, Any]]) -> str:
            return digest([{k:v.strip() if k=='append_note' else v for k,v in c.items()
                if k not in ('expected_revision','reason','evidence_refs')} for c in changes])
        expected = shape(request.model_dump(mode='json',exclude_unset=True)['changes'])
        return next((dict(p) for row in rows for p in [json.loads(row[0])]
                     if p['turn_id']==turn_id and shape(p['changes'])==expected), None)

    def read(self, plan_id: str, thread_id: str) -> dict[str, Any]:
        with self.client.engine.lock:
            row = self.client.engine.conn.execute('SELECT document,status FROM ticket_change_plans '
                'WHERE plan_id=? AND thread_id=?', [plan_id,thread_id]).fetchone()
        if not row:
            raise KeyError('Propuesta no encontrada en esta conversación.')
        return {**json.loads(row[0]), 'status':row[1]}

    def apply(self, plan_id: str, thread_id: str, command_id: str, authorization: dict[str, str]) -> dict[str, Any]:
        if not authorization.get('message_id') or authorization.get('actor') != 'local-user':
            raise ValueError('Falta autorización del usuario para esta propuesta.')
        with self.client.engine.lock:
            receipt = self.client.engine.conn.execute('SELECT document FROM ticket_commands '
                'WHERE command_id=? OR plan_id=?', [command_id,plan_id]).fetchone()
            if receipt:
                previous = json.loads(receipt[0])
                if previous['plan_id'] != plan_id or previous['thread_id'] != thread_id:
                    raise ValueError('El comando ya pertenece a otra operación.')
                return dict(previous['result'])
            plan = self.read(plan_id, thread_id)
            if plan['status'] != 'pending' or datetime.fromisoformat(plan['expires_at']) < datetime.now(timezone.utc):
                raise ValueError('La propuesta caducó o ya no está pendiente.')
            try:
                tickets,current = prepare_batch(self,plan,authorization)
            except ValueError as error:
                raise ValueError('Cambió un ticket del lote o apareció un duplicado. No se aplicó ningún cambio; '+str(error)) from error
            result = commit_batch(self.client.tickets, tickets, dict(command_id=command_id, plan_id=plan_id,
                thread_id=thread_id, authorization=authorization, before=current, changes=plan['changes'],report_run_id=plan.get('report_run_id')))
            if any(ticket.status == 'IMPLEMENTED' for ticket in tickets):
                from ..consulting.workflow import sync_tasks
                sync_tasks(self.client)
            return result

    def receipt(self, plan_id: str, thread_id: str) -> dict[str, Any] | None:
        with self.client.engine.lock:
            row = self.client.engine.conn.execute('SELECT document FROM ticket_commands WHERE plan_id=? AND thread_id=?',
                                                  [plan_id,thread_id]).fetchone()
        return dict(json.loads(row[0])['result']) if row else None

    def invalidate(self, plan_id: str) -> None:
        with self.client.engine.atomic_tx() as tx:
            tx.execute("UPDATE ticket_change_plans SET status='stale' WHERE plan_id=? AND status='pending'", [plan_id])

    def reject(self, plan_id: str, thread_id: str) -> None:
        self.read(plan_id, thread_id)
        with self.client.engine.atomic_tx() as tx:
            tx.execute("UPDATE ticket_change_plans SET status='rejected' WHERE plan_id=? AND status='pending'", [plan_id])


def updated_ticket(document: dict[str, Any], change: Any, thread_id: str, authorization: dict[str, str]) -> Any:
    from ..models import FinOpsTicket
    old = FinOpsTicket.model_validate(document)
    now = datetime.now(timezone.utc).isoformat()
    text = change.append_note.strip() or change.reason.strip()
    history = list(old.note_history)
    if old.resolution_note and not history:
        history.append(dict(text=old.resolution_note, at=old.updated_at_utc, actor='local-user', source='legacy'))
    history.append(dict(text=text, reason=change.reason, at=now, actor=authorization['actor'],
                        source='chat' if thread_id != 'manual' else 'manual', thread_id=thread_id))
    fields = change.fields.model_dump(mode='json',exclude_unset=True) if change.fields else {}
    if any(value is None for key,value in fields.items() if key!='estimated_monthly_impact_usd'):
        raise ValueError('Los campos del ticket no pueden quedar vacíos.')
    target = change.target_status or old.status
    if target=='IMPLEMENTED' and old.status!='IMPLEMENTED' and old.followup:
        fields['followup'] = old.followup.model_copy(update={'event_date':datetime.now(timezone.utc).date()}).model_dump(mode='json')
    return FinOpsTicket.model_validate({**old.model_dump(), **fields, 'status':target,
        'needs_attention':target in ('PROPOSED','APPROVED'),
        'attention_reason':'Requiere una decisión o acción.' if target in ('PROPOSED','APPROVED') else '',
        'note_history':history, 'resolution_note':'\n\n'.join(filter(None,[old.resolution_note,text])), 'updated_at_utc':now})
