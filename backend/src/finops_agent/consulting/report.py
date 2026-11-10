from typing import Any
from .agenda import agenda
from .verification import verifications


def report_followup(client: Any) -> tuple[dict[str, Any], str]:
    plan = agenda(client)
    outcomes = verifications(client)
    lines = ['\n\n## Próximas acciones y seguimiento',
             'Estado del plan en el momento de guardar el informe.']
    for action in plan['top_actions']:
        lines.append(f"- {action['ticket_id']}: {action['title']} · Responsable: {action['owner'] or 'por confirmar'}.")
    if not plan['top_actions']:
        lines.append('- No hay tareas listas para actuar; revisa si falta información o si estamos esperando nuevos datos.')
    if plan['next_requirement']:
        lines.append('- Información pendiente: '+plan['next_requirement']['question'])
    for outcome in outcomes:
        lines.append(f"- {outcome['ticket_id']}: {outcome['status']}. {outcome.get('reason', 'En observación.')}")
    for observation in plan['monitoring']:
        labels = dict(pending_data='Faltan datos',persists='El problema continúa',needs_review='Requiere revisión',criterion_met='Candidato a cierre')
        lines.append(f"- Seguimiento {observation['ticket_id']}: {labels[observation['status']]}. {observation['summary']} Cualquier cierre requiere aprobación.")
    lines.append('Las estimaciones y las reducciones observadas no equivalen a ahorro atribuible verificado.')
    return dict(agenda_revision=plan['revision'], data_through=plan['data_through'],
                actions=plan['top_actions'], requirements=plan['requirements'], verifications=outcomes, monitoring=plan['monitoring']), '\n'.join(lines)
