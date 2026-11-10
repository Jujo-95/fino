from typing import Any

CAPABILITY_METRICS = {
    "allocation": ("unallocated_cost_pct", "allocation_accuracy_index", "shared_cost_apportionment"),
    "anomaly": ("anomaly_unpredicted_variance", "anomaly_cost_avoidance", "genai_anomaly_detection_rate"),
    "forecasting": ("forecast_accuracy_usage", "forecast_drift_rate"),
    "budgeting": ("budget_burn_rate", "budget_vs_forecast_variance"),
    "commitment": ("commitment_utilization_score", "commitment_discount_waste_pct", "effective_savings_rate"),
}
QUERY_INPUTS = {"allocation": ("totals",), "anomaly": ("services",), "forecasting": ("daily", "services"),
                "budgeting": ("totals", "daily"), "commitment": ("totals", "services")}


def decision_summary(node: str, overview: dict[str, Any], findings: list[dict[str, Any]]) -> list[str]:
    profile = overview["profile"]
    summaries = {
        "allocation": [f"Se verificaron las etiquetas obligatorias: {', '.join(profile['allocation_policy']['required_tags'])}.",
            f"Política de asignación: {profile['allocation_policy']['mode']}. La regla emite un hallazgo si el costo sin asignar supera 5%."],
        "anomaly": ["Se comparó el último día de cada cuenta/servicio contra su media histórica; se requieren cuatro observaciones.",
            "Se exige un exceso mayor a 3 desviaciones, 30% de la media y USD 10; se consulta memoria de decisiones.",
            f"Picos accionables: {len(overview['spikes'])}. Pares excluidos de compromisos: {len(overview['excluded_baseload'])}."],
        "forecasting": ["Proyección = gasto actual + promedio diario ajustado por exceso anómalo × días restantes + drivers configurados.",
            f"Proyección mensual: USD {overview['forecast']:,.2f}. Escenario trimestral: USD {overview['quarterly_forecast']:,.2f}.",
            "El drift solo produce hallazgo si existe forecast previo y la variación absoluta supera 10%."],
        "budgeting": [f"Presupuesto mensual: USD {overview['budget']:,.2f}; holdback: {profile['budget_policy']['holdback_pct']}%.",
            f"Umbral de madurez {profile['target_maturity']}: "
            f"{ {'Crawl':20, 'Walk':15, 'Run':12}[profile['target_maturity']]}% de exceso; también se verifica el holdback."],
        "commitment": [f"Baseload diario on-demand estable: USD {overview['clean_baseload']:,.2f}.",
            f"Se excluyeron los pares anómalos: {', '.join(overview['excluded_baseload']) or 'ninguno'}.",
            f"Plazo máximo: {profile['commitment_policy']['max_term_months']} meses. No se ejecutan compras."],
    }
    if node == "anomaly":
        summaries[node].extend(f"{row['key']}: observado USD {row['cost']:,.2f}, baseline USD {row['baseline']:,.2f}, "
                              f"exceso USD {row['variance']:,.2f}." for row in overview["spikes"])
    return summaries[node] + [f"Resultado: {len(findings)} hallazgo(s) propuesto(s) por este especialista."]
