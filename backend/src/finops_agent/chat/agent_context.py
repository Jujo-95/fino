from typing import Any
from ..config import ROOT
from ..agents.specs import SPECIALIST_SPECS
from ..agents_v2.registry import definitions, system_prompt
from ..engine.run_audit import RunAuditStore

AGENT_IDS = ('orchestrator',*SPECIALIST_SPECS,*definitions())


def validate_agent(agent_id: str) -> str:
    if agent_id not in AGENT_IDS:
        raise ValueError('Especialista desconocido.')
    return agent_id


def validate_run(client: Any, run_id: str | None) -> None:
    if run_id:
        RunAuditStore(client.workspace).read(run_id)


def instructions(agent_id: str, include_specialty: bool | None = None) -> str:
    validate_agent(agent_id)
    if agent_id in definitions():
        return system_prompt(agent_id, include_specialty)
    base = (ROOT/'prompts/finops-chat.md').read_text()
    if agent_id=='orchestrator':
        role = (ROOT/'prompts/orchestrator.md').read_text()
        role = '\n'.join(line for line in role.splitlines() if 'submit_analysis' not in line.lower() and not line.startswith('The final evidence_ids'))
        role = role.replace("Do not change ticket states: this report supplies evidence for the analyst's next decision.","Use the chat authorization and ticket tools for requested ticket changes.")
        return base+'\n'+role
    spec = SPECIALIST_SPECS[agent_id]
    role = (ROOT/'prompts'/f'{spec.capability_slug}.md').read_text()
    return base+f'\nEres el especialista {spec.name}, no el orquestador. Responde en español desde tu especialidad.\n'+spec.reasoning_focus+'\n'+role


def report_context(client: Any, thread: dict[str, Any]) -> dict[str, Any]:
    run_id = thread.get('audit_run_id')
    if not run_id:
        return dict(available=False)
    record = RunAuditStore(client.workspace).read(run_id)
    if record.get('client_id')!=client.profile.client_id:
        raise ValueError('El informe no corresponde al cliente activo.')
    agent = thread.get('agent_id','orchestrator')
    traces = [e.get('payload',{}).get('trace') for e in record.get('events',[])]
    selected = [dict(node=t['node'],output=t.get('output'),findings=t.get('findings')) for t in traces
                if t and (agent=='orchestrator' or agent in definitions() or t['node']==agent)]
    return dict(run_id=run_id,status=record['status'],period_start=record['period_start_utc'],
                period_end=record['period_end_utc'],contribution_count=len(selected),
                instruction='Use read_analysis for measured findings and coverage; read_report only when the question requires the narrative.')


def runtime_details(client: Any, agent_id: str) -> dict[str, Any]:
    if agent_id not in definitions():
        return {}
    from ..consulting.diagnosis import diagnosis
    report = diagnosis(client)
    return dict(consulting=dict(revision=report['revision'], data_through=report['data_through'],
        confirmed_values=report['context']['values'], requirements=report['requirements'],
        monitoring_ticket_ids=[t.ticket_id for t in client.tickets.list() if t.status=='MONITORING'],
        instruction='Para diagnóstico o prioridades consulta read_diagnosis/read_action_plan. Antes de un informe consulta read_ticket_followups y reevalúa esos tickets; ningún cierre sin aprobación. Presupuesto del perfil sin confirmar no es aprobado.'),
        client_scope=dict(client_id=client.profile.client_id,billing_currency=client.profile.billing_currency),
        specialists=[dict(id=k,name=v['original_name']) for k,v in definitions().items() if k!='v2-finops-report-orchestrator'],
        instruction='Responde la pregunta concreta; consulta tickets solo si es una pregunta de tickets. No confundas snapshots con informes.')
