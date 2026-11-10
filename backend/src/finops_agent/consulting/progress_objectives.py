"""Bounded objectives with frozen scope. Reading never grows the denominator."""
from typing import Any
from .store import ConsultingStore
from .ticket_lifecycle import task_state
from ..agents.audit_trace import timestamp
from ..engine.incremental_inputs import digest

OBJECTIVES = {
    'data-ingestion':'Confirmar los datos que vamos a analizar',
    'allocation':'Asignar responsables al gasto',
    'anomaly-management':'Aclarar los cambios de consumo',
    'budgeting':'Poner el gasto bajo un presupuesto confirmado',
    'forecasting':'Entender la proyección de gasto',
    'rate-optimization':'Revisar los compromisos contratados',
    'usage-optimization':'Comprobar oportunidades de uso',
    'reporting-analytics':'Completar el diagnóstico del período',
}


def objective_view(record: dict[str, Any], tickets: dict[str, Any]) -> dict[str, Any]:
    steps = []
    for identity in record['ticket_ids']:
        ticket = tickets.get(identity)
        state = task_state(ticket) if ticket else 'missing'
        steps.append(dict(ticket_id=identity,title=ticket['title'] if ticket else identity,
            state=state,excluded=identity in record.get('excluded',{}),
            reason=record.get('excluded',{}).get(identity),
            summary=ticket.get('resolution_note','') if ticket else 'La tarea ya no está disponible.'))
    applicable = [s for s in steps if not s['excluded']]
    done = sum(s['state']=='resolved' for s in applicable)
    return dict(record,steps=steps,completed=done,total=len(applicable),
        percent=round(done/len(applicable)*100) if applicable else None,
        complete=bool(applicable) and done==len(applicable))


def objectives(client: Any, tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    store = ConsultingStore(client)
    with client.engine.atomic_tx() as tx:
        saved = store.all('progress_objective')
        known = {i for r in saved for i in r['ticket_ids']}
        for capability,title in OBJECTIVES.items():
            if any(r['capability']==capability for r in saved):
                continue
            ids = [t['ticket_id'] for t in tickets if t['capability']==capability and t['ticket_id'] not in known]
            if not ids:
                continue
            key = digest([client.profile.client_id,capability,ids])
            record = dict(id=key,version=1,title=title,capability=capability,ticket_ids=ids,
                          excluded={},created_at=timestamp(),history=[])
            store.put(tx,'progress_objective',key,record)
            saved.append(record)
    current = {t['ticket_id']:t for t in tickets}
    saved.sort(key=lambda r:(list(OBJECTIVES).index(r['capability']),r['created_at']))
    return [objective_view(r,current) for r in saved]


def exclude_step(client: Any, identity: str, ticket_id: str, version: int) -> dict[str, Any]:
    store = ConsultingStore(client)
    with client.engine.atomic_tx() as tx:
        record = store.get('progress_objective',identity)
        ticket = next((t for t in client.tickets.list() if t.ticket_id==ticket_id),None)
        if not record or ticket_id not in record['ticket_ids']:
            raise KeyError('El paso no pertenece al objetivo de este cliente.')
        if ticket_id in record.get('excluded',{}):
            return record
        if record['version']!=version or not ticket or ticket.status!='FALSE_POSITIVE' or not ticket.resolution_note:
            raise ValueError('El alcance cambió o falta un descarte justificado. Actualiza el objetivo.')
        record['history'].append(dict(version=version,ticket_id=ticket_id,reason=ticket.resolution_note,at=timestamp()))
        record['excluded'][ticket_id] = ticket.resolution_note
        record['version'] += 1
        store.put(tx,'progress_objective',identity,record)
        return record


def next_cycle(client: Any) -> dict[str, Any]:
    tickets = [t.model_dump(mode='json') for t in client.tickets.list()]
    store = ConsultingStore(client)
    with client.engine.atomic_tx() as tx:
        goals = store.all('progress_objective')
        current = {t['ticket_id']:t for t in tickets}
        known = {i for g in goals for i in g['ticket_ids']}
        for capability,title in OBJECTIVES.items():
            previous = [g for g in goals if g['capability']==capability]
            if any((view:=objective_view(g,current))['total'] and not view['complete'] for g in previous):
                continue
            ids = [t['ticket_id'] for t in tickets if t['capability']==capability and t['ticket_id'] not in known]
            if not ids:
                continue
            key = digest([client.profile.client_id,capability,ids])
            record = dict(id=key,version=1,title=title,capability=capability,ticket_ids=ids,
                          excluded={},created_at=timestamp(),history=[])
            store.put(tx,'progress_objective',key,record)
            return record
    raise ValueError('No hay un nuevo objetivo disponible; continúa los pasos pendientes o espera el próximo análisis.')
