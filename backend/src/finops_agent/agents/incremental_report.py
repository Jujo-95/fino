from typing import Any

LABELS = {'new':'Nuevo', 'updated':'Actualizado', 'persistent':'En seguimiento',
          'coverage_changed':'Período actualizado', 'decision_preserved':'Decisión conservada'}


def delta_markdown(delta: dict[str, Any], state: dict[str, Any]) -> str:
    previous = delta['previous_run_id']
    lines = ['# FinOps · Novedades del análisis' if previous else '# FinOps · Primer análisis',
        f"Período: {state['period_start_utc']} → {state['period_end_utc']} · {state['billing_currency']}"]
    if previous:
        lines.append(f'Informe de referencia: `{previous}`. Disponible en el historial de informes.')
    novel = [item for item in delta['changes'] if item['kind'] in ('new', 'updated')]
    lines.append('## Novedades y decisiones necesarias')
    if not novel:
        lines.append('Datos actualizados; sin nuevas acciones. Los tickets abiertos continúan en seguimiento.')
    for item in novel:
        current = item['current']
        lines.append(f"### {item['ticket_id']} · {LABELS[item['kind']]} · {current['title']}\n"
            f"{current['recommended_action']}\n\nEvidencia: {current['evidence_summary']}")
    if not delta['comparable_period']:
        lines.append('## Cobertura temporal\nCambió el período analizado. Los importes acumulados no son directamente comparables; '
                     'los problemas conocidos conservan su ticket. Revisar los días añadidos y sus evidencias en el análisis.')
    elif delta['metric_changes']:
        lines.append('## Cambios en indicadores (mismo período)')
        lines.extend(f"- {item['label']}: {item['previous']} → {item['current']} {item['unit']}"
                     for item in delta['metric_changes'])
    lines.append('## Seguimiento de tickets conocidos')
    lines.extend(f"- {item['ticket_id']} · {LABELS[item['kind']]}: {item['reason']}"
                 for item in delta['changes'] if item['kind'] not in ('new', 'updated'))
    lines.extend(review_markdown(delta))
    return '\n\n'.join(lines)


def review_markdown(delta: dict[str, Any]) -> list[str]:
    lines = []
    pending = [item for item in delta['ticket_review'] if item['assessment'] == 'needs_validation']
    lines.append('## Tickets pendientes de revalidar')
    lines.extend(f"- {item['ticket_id']}: {item['reason']}" for item in pending)
    if not pending:
        lines.append('No hay tickets anteriores ausentes que requieran revalidación por este motivo.')
    candidates = [item for item in delta['ticket_review'] if item.get('candidate_obsolete')]
    if candidates:
        lines.append('## Posibles tickets obsoletos: requieren validación')
        lines.extend(f"- {item['ticket_id']}: {item['reason']} No se cambió su estado." for item in candidates)
    resolved = [item for item in delta['ticket_review'] if item['assessment'] == 'human_resolved']
    if resolved:
        lines.append('## Decisiones registradas (no se reabrieron tickets)')
        lines.extend(f"- {item['ticket_id']} · {item['status']}: {item['resolution_note']}" for item in resolved)
    return lines
