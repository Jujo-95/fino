"""Recoverable tool feedback without echoing arguments or internal exception objects."""
from typing import Any

FINDING_FIELDS = ('capability, maturity_tier, allocation_mode, severity, sub_account_id, service_name, '
    'period_bucket, kpi_name, kpi_value, estimated_monthly_impact_usd (o null), title, '
    'evidence_summary, recommended_action, capability_citation_url')


def proposal_validation_error(error: Any) -> str:
    locations = sorted({'.'.join(str(p) for p in item['loc']) for item in error.errors()})
    if any('fields.target_status' in loc for loc in locations):
        return ('Propuesta no registrada. target_status va al mismo nivel que ticket_id, no dentro de fields. '
            'Para transiciones usa preferentemente propose_ticket_transition; no incluyas finding.')
    is_create = any(isinstance(item.get('input'),dict) and item['input'].get('action')=='create'
                    for item in error.errors())
    if not is_create and not any('finding' in loc for loc in locations):
        return ('Propuesta no registrada. Para modificar: action="transition", ticket_id, expected_revision '
            'obtenida con get_tickets, target_status y reason, todos al mismo nivel. No incluyas finding. '
            'Para cambiar varios estados usa propose_ticket_transition.')
    return ('Propuesta no registrada; no se creó ni modificó ningún ticket. Corrige los campos: '
        +', '.join(locations)+'. Para cada action=create, reason no sustituye finding. '
        'Incluye finding como objeto con: '+FINDING_FIELDS+'. '
        'Usa únicamente datos y métricas consultados del cliente activo; si faltan, consulta la evidencia '
        'o pregunta al usuario. No inventes datos. evidence_refs debe contener IDs consultados únicos '
        '(máximo 20). No asignes ticket_id, expected_revision, fields ni target_status al crear. '
        'Para editar, lee el ticket FIN y su revisión. Reintenta la herramienta con el objeto completo; '
        'no presentes excepciones técnicas al usuario ni afirmes que ya creaste el ticket.')
