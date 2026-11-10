"""Small human view over the canonical structured analysis.

The analysis JSON remains the source of truth. This renderer is deliberately
deterministic so the report route cannot run a second measurement engine.
"""
from typing import Any


def render_analysis(result: dict[str, Any]) -> str:
    period = result.get('period', {})
    lines = [
        f"# Análisis FinOps · {result.get('client_id', '')}",
        f"Período: {period.get('start', '')} → {period.get('end', '')}",
        '',
        '## Indicadores',
    ]
    for metric in result.get('measurements', []):
        value = metric.get('value')
        lines.append(f"- **{metric.get('name', metric.get('key', 'Indicador'))}:** {value}")
    lines.extend(['', '## Hallazgos y tareas'])
    findings = result.get('findings', [])
    if not findings:
        lines.append('- No hay hallazgos nuevos para este período.')
    for finding in findings:
        lines.append(f"- **{finding.get('title', 'Hallazgo')}** — {finding.get('recommended_action', '')}")
    lines.extend(['', '## Limitaciones'])
    for limitation in result.get('limitations', []):
        lines.append(f'- {limitation}')
    return '\n'.join(lines) + '\n'
