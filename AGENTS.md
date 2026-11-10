# FinOps Multi-Agent Platform (`finops-agent-app`)

> Aplicación Multi-Agente de FinOps basada en **LangGraph + DuckDB (FOCUS SQL) + Contexto estructurado + FastAPI (SSE) + React**.
> Diseñada bajo principios estrictos de **Clean Code, Transacciones Atómicas e Idempotentes, Composición DRY (`Extend, Don't Repeat`) y Eficiencia de Recursos**.

---

## Alcance vigente aprobado por el usuario (2026-10-20)

El piloto usa CSV locales y NVIDIA con herramientas DuckDB. No crear HippoRAG, embeddings o
un grafo sin un caso de uso demostrado. `docs/07-SCRIPTS-AGENTS-AND-EVIDENCE.md` sustituye
los requisitos anteriores de recuperación por grafo. Scripts versionados en `script_snapshots`;
contexto persistente en `context_documents`; conclusiones del modelo en la auditoría por ejecución.
Las demás reglas de atomicidad, DRY, límites y skills técnicos siguen vigentes.

## 🚨 MANDATORY EXECUTION GATE (Obligatorio para el Agente)

Antes de ejecutar `Write` o `StrReplace` en cualquier archivo de este proyecto, el agente **DEBE** cumplir estos 3 pasos sin excepción:

1. **Citar la FinOps Capability y leer su especificación**:
   - Consultar `finops_capabilities_md/capabilities/<slug>.md` (copia local portátil en la raíz de este proyecto) y citar su URL oficial de `finops.org`.
   - Leer las especificaciones completas del sistema en `docs/01-PRODUCT-AND-DOMAIN-SPEC.md`, `docs/02-DATA-AND-MEMORY-SCHEMAS.md`, `docs/03-AGENT-AND-API-CONTRACTS.md` y el plan de construcción paso a paso en `docs/04-IMPLEMENTATION-PLAYBOOK.md`.
2. **Leer (`Read`) la Skill técnica de la capa antes de escribir código**:
   | Capa del Stack | Skill Obligatoria a leer con `Read` | Rule Automática (`.cursor/rules/`) |
   |---|---|---|
   | **DuckDB, Ingesta CSV FOCUS y Queries KPI** | `.cursor/skills/finops-build-duckdb-engine/SKILL.md` | `duckdb-focus-idempotent.mdc` |
   | **Dual HippoRAG, Contexto y Tickets Atómicos** | `.cursor/skills/finops-build-atomic-memory/SKILL.md` | `clean-python-atomic-io.mdc` |
   | **Orquestador LangGraph y 5 Especialistas** | `.cursor/skills/finops-build-langgraph-fleet/SKILL.md` | `langgraph-dry-specialists.mdc` |
   | **Backend FastAPI, Lifespan, Multi-LLM y SSE** | `.cursor/skills/finops-build-fastapi-sse/SKILL.md` | `clean-python-atomic-io.mdc` |
   | **Frontend React y Tests Parametrizados** | `.cursor/skills/finops-build-lean-ui-tests/SKILL.md` | `frontend-lean-ui.mdc` |
   | **Consulta conceptual FinOps / KPIs** | `.cursor/skills/finops-capability-lookup/SKILL.md` | `00-mandatory-execution-gate.mdc` |
3. **Verificación de Clean Code, Atomicidad y Recursos**:
   - **Extender en vez de repetir**: Un único `SpecialistRunner` sirve a los 5 agentes especialistas mediante `SpecialistSpec` declarativos.
   - **Idempotencia determinista**: Toda ingesta CSV, ticket (`FIN-XXX.md`) y nodo en HippoRAG usa un `fingerprint` SHA-256 determinista. Re-ejecutar el pipeline nunca duplica costos ni tickets.
   - **Transacciones atómicas**: Escrituras en archivos vía `.tmp` + `os.replace()`; escrituras en DuckDB vía `BEGIN TRANSACTION ... COMMIT / ROLLBACK`.
   - **Límites de tamaño**: Máximo **35 líneas por función** y **180 líneas por archivo**.

---

## Mapa de Capabilities FinOps y KPIs Oficiales del Sistema

1. **Data Ingestion** (`@finops_capabilities_md/capabilities/data-ingestion.md` — [URL](https://www.finops.org/framework/capabilities/data-ingestion/))
   - Ingesta zero-copy de CSVs diarios en estándar **FOCUS** (`EffectiveCost`, `BilledCost`, `ListCost`, `ContractedCost`, `ChargePeriodStart`, `BillingCurrency`, `SubAccountId`, `ServiceName`, `CommitmentDiscountId`, `Tags`).
2. **Allocation** (`@finops_capabilities_md/capabilities/allocation.md` — [URL](https://www.finops.org/framework/capabilities/allocation/))
   - Distinción explícita entre **Showback** (informativo) y **Chargeback** (cargo contable real).
   - KPIs: *Percentage of Costs Associated with Unallocated CSP Cloud Resources*, *Allocation Accuracy Index (AAI)*, *Usage or Spend Apportionment Validation*.
3. **Anomaly Management** (`@finops_capabilities_md/capabilities/anomaly-management.md` — [URL](https://www.finops.org/framework/capabilities/anomaly-management/))
   - Detección de desviaciones estadísticas sobre `EffectiveCost` cruzadas con eventos planeados en HippoRAG.
   - KPIs: *Total Unpredicted Variance of Spend*, *Anomaly-Detected Cost Avoidance*, *Anomaly Detection Rate*.
4. **Forecasting** (`@finops_capabilities_md/capabilities/forecasting.md` — [URL](https://www.finops.org/framework/capabilities/forecasting/))
   - Proyección EOM y trimestral descontando anomalías puntuales y sumando drivers del negocio.
   - KPIs: *Forecast Accuracy Rate (Usage)*, *Forecast Drift Rate*.
5. **Budgeting** (`@finops_capabilities_md/capabilities/budgeting.md` — [URL](https://www.finops.org/framework/capabilities/budgeting/))
   - Evaluación de *Actual & Forecast vs. Budget* y gestión de *Holdbacks* (umbrales de varianza: 20% Crawl, 15% Walk, 12% Run).
   - KPIs: *CSP Cloud Budget Burn Rate*, *Percentage Variance of Budgeted vs. Forecasted CSP Cloud Spend*.
6. **Rate Optimization** (`@finops_capabilities_md/capabilities/rate-optimization.md` — [URL](https://www.finops.org/framework/capabilities/rate-optimization/))
   - Análisis de compromisos (CUDs, RIs, Savings Plans) sobre consumo base limpio (excluyendo anomalías activas).
   - KPIs: *Commitment Utilization Score*, *Percentage of Commitment Discount Waste*, *Effective Savings Rate (ESR) Percentage*.
