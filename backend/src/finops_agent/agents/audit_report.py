from typing import Any

NAMES = {"allocation": "Asignación", "anomaly": "Anomalías", "forecasting": "Proyecciones",
         "budgeting": "Presupuesto", "commitment": "Compromisos"}


def contribution_markdown(state: dict[str, Any]) -> str:
    sections = ["## Aportes por especialista", f"Ejecución auditada: {state.get('run_id', 'invocación directa del grafo')}"]
    latest = {trace["node"]: trace for trace in state.get("audit_traces", [])}
    for trace in latest.values():
        if trace["node"] not in NAMES:
            continue
        sections.append(f"### {NAMES[trace['node']]} — {len(trace['findings'])} hallazgo(s)")
        sections.extend(f"- {line}" for line in trace["rationale"])
        sections.extend(f"- Hallazgo: {finding['title']}" for finding in trace["findings"])
        if trace["query_refs"]:
            sections.append("Evidencias SQL consultadas: " + ", ".join(trace["query_refs"]))
        sections.append("Motor: " + trace["engine"])
    return "\n\n".join(sections)
