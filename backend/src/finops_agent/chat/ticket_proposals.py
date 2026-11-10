"""Shared entry point for agent and report proposals, never direct mutations."""
from typing import Any
from ..models import TicketContributor
from .models import PlanRequest, Change
from .presentation import public_plan


def propose(ctx: Any, changes: list[Change], report_id: str | None = None) -> dict[str,Any]:
    thread = ctx.store.read(ctx.thread_id)
    if thread.get('report_turn_id')==ctx.turn_id and thread.get('report_run_id'):
        from ..engine.run_audit import RunAuditStore
        if RunAuditStore(ctx.client.workspace).read(thread['report_run_id'])['status']=='running':
            raise ValueError('Guarda primero el informe con save_report; después se propondrán sus tickets para revisión.')
    known = {*thread['evidence_ids'],'message:'+ctx.turn_id}
    if any(ref not in known for change in changes for ref in change.evidence_refs):
        raise ValueError('Referencia de evidencia no consultada en esta conversación.')
    if any((c.action=='create' or c.fields) and not c.evidence_refs for c in changes):
        raise ValueError('Crear o actualizar campos requiere evidencia consultada.')
    agent = thread.get('agent_id','orchestrator')
    if agent.startswith('v2-'):
        for change in changes:
            if change.action=='create' and change.finding is not None:
                details = change.finding.action_details
                if not details.steps or not details.completion_criterion:
                    raise ValueError('Crear requiere finding.action_details con steps concretos y completion_criterion. Responsable/riesgo desconocidos pueden ser null; no inventes datos.')
    contributor = TicketContributor(agent_id=agent,role='consolidated' if 'orchestrator' in agent else 'detected',
        run_id=report_id or thread.get('report_run_id') or 'chat:'+ctx.thread_id)
    plan = ctx.ops.plan(PlanRequest(changes=changes),ctx.thread_id,ctx.turn_id,
        contributors=[contributor.model_dump()],report_run_id=report_id or thread.get('report_run_id'))
    return ctx.record('plan_ticket_changes',public_plan(plan))


def report_actions(ctx: Any, run_id: str) -> dict[str,Any]:
    from ..engine.run_audit import RunAuditStore
    record = RunAuditStore(ctx.client.workspace).read(run_id)
    if record['client_id']!=ctx.client.profile.client_id or record['status']!='completed':
        raise ValueError('Selecciona un informe completado del cliente activo.')
    ctx.record('read_report_changes',dict(evidence_id='run:'+run_id,run_id=run_id))
    actions = (record.get('structured_report') or {}).get('tickets',{}).get('proposedActions',[])
    changes,gaps = [],[]
    for index,action in enumerate(actions):
        try:
            changes.append(convert_action(ctx,action,run_id))
        except (ValueError,KeyError,TypeError,AttributeError) as error:
            gaps.append(dict(index=index,reason=str(error)))
    if gaps:
        return dict(status='needs_details',gaps=gaps,message='No se propuso un lote parcial. Completa los campos con evidencia y usa plan_ticket_changes.')
    if not changes:
        return dict(status='empty',message='El informe no contiene propuestas de tickets.')
    return propose(ctx,changes,run_id)


def convert_action(ctx: Any, action: dict[str,Any], run_id: str) -> Change:
    kind = action.get('action')
    base: dict[str,Any] = dict(action=kind,reason=action.get('reason') or 'Hallazgo del informe',evidence_refs=['run:'+run_id])
    if kind=='create':
        finding = action.get('finding') or action.get('ticket',{}).get('finding')
        if not finding:
            raise ValueError('Crear requiere finding completo (capacidad, cuenta, servicio, métrica y evidencia); no inventes datos.')
        return Change.model_validate({**base,'finding':finding,'proposal_key':action.get('findingKey') or action.get('ticket',{}).get('findingKey')})
    ticket_id = action.get('ticketId') or action.get('ticket_id')
    if not ticket_id or not ticket_id.startswith('FIN-'):
        raise ValueError('Usa un ticket FIN real del cliente, no un identificador HTS del documento.')
    ticket = ctx.ops.tickets([ticket_id])[0]
    states = {'todo':'PROPOSED','in_progress':'APPROVED','done':'IMPLEMENTED','fixed':'IMPLEMENTED','false_positive':'FALSE_POSITIVE','monitoring':'MONITORING','resolved':'RESOLVED'}
    prior = action.get('from')
    if prior and states.get(prior,prior)!=ticket['status']:
        raise ValueError('El estado del ticket cambió desde el informe; vuelve a validarlo.')
    fields = dict(action.get('fields') or {})
    if 'usdImpactMonthly' in fields:
        fields['estimated_monthly_impact_usd'] = fields.pop('usdImpactMonthly')
    target = action.get('to') or action.get('target_status')
    return Change.model_validate({**base,'ticket_id':ticket_id,'expected_revision':action.get('expected_revision') or ticket['revision'],
        'target_status':states.get(target or '',target),'fields':fields or None,'append_note':action.get('append_note','')})


def stage_saved_report(ctx: Any, run_id: str) -> dict[str,Any]:
    try:
        return report_actions(ctx,run_id)
    except (ValueError,KeyError,TypeError,AttributeError) as error:
        return dict(status='needs_details',message=str(error),report_saved=True)
