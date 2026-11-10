# FinOps Agent Console

Aplicación local: React + TypeScript, FastAPI/SSE, DuckDB y LangGraph.
Cinco especialistas y un orquestador usan NVIDIA `z-ai/glm-5.3-flash` con herramientas reales.
El piloto usa CSV FOCUS locales y contexto estructurado; no necesita HippoRAG ni embeddings.

## Ejecutar

Requisitos: Python 3.11+, uv, Node 20.19+ y npm.

1. Copia `.env.example` a `.env` si todavía no existe y configura `NVIDIA_API_KEY` localmente.
2. Ejecuta `bash run.sh`; abre http://127.0.0.1:8000.
3. **Nuevo cliente**: configura sus políticas e importa CSV FOCUS y notas Markdown opcionales.
4. **Scripts y conexión**: verifica NVIDIA y consulta los snapshots guardados.
5. **Analizar costos**: ejecuta los agentes; inspecciona **Equipo y auditoría**.
6. Revisa tickets, registra decisiones y consulta o solicita revisión de informes.

`bash run.sh --demo` prepara 60 filas sintéticas de octubre de 2026, claramente identificadas,
y arranca la app. Preparar la demostración no ejecuta llamadas al modelo automáticamente.
La ingesta y el dashboard funcionan sin clave; el análisis NVIDIA falla explícitamente si falta.
Solo `FINOPS_LLM_PROVIDER=mock` activa la demostración offline por reglas. No hay fallback silencioso.

Si las dependencias y frontend ya están preparados:

```bash
backend/.venv/bin/uvicorn finops_agent.api.server:app --host 127.0.0.1 --port 8000
```

`.env` está ignorado por Git. La clave se resuelve en el backend y no se envía al navegador.
El modelo recibe observaciones y contexto financiero del cliente seleccionado como parte del análisis.

## Datos, scripts y agentes

Cada cliente conserva `workspaces/<client_id>/storage/finops.duckdb`:

- `focus_usage`, `ingested_batches`: CSV normalizados y huellas de ingesta.
- `script_snapshots`: métricas, forecast por run-rate, anomalías estadísticas y baseline limpio,
  con versión, código, configuración y procedencia. Los scripts son deterministas.
- `context_documents`, `tickets_ledger`: perfil, notas y decisiones persistentes.

El modelo usa `describe_data`, `query_focus`, `read_scripts` y `read_context` para examinar los datos.
`query_focus` ejecuta plantillas SQL de solo lectura con filtros vinculados; el servidor fija cliente,
período UTC y moneda. Se registran actor, SQL, parámetros, resultados, truncamiento y duración.
Las propuestas usan valores de métricas disponibles y referencias a evidencia existente.
Un impacto no calculado se guarda como `null`; no se inventa un ahorro estimado.

El grafo conserva el orden asignación → anomalías → forecasting → presupuesto → compromisos → síntesis.
El orquestador puede pedir hasta dos revisiones y consolida el informe. Una revisión desde la UI
crea una nueva ejecución vinculada al informe anterior y conserva su período.
Los prompts están en `prompts/*.md` y cargan las guías FinOps de la capacidad correspondiente.

`audit_runs/<run_id>.json` conserva cada informe, sus contribuciones, prompts, herramientas y uso.
Las etapas completadas y fallidas se distinguen. No se registra `reasoning_content` privado del modelo.
Los tickets se deduplican por cliente, capacidad, cuenta, servicio, período y métrica; las resoluciones
se preservan. Los archivos usan reemplazo atómico y el ledger es la fuente durable de recuperación.

## Verificar

```bash
uv sync --project backend --extra dev
backend/.venv/bin/pytest backend/tests -q
backend/.venv/bin/ruff check backend
backend/.venv/bin/mypy backend/src
npm --prefix frontend ci
npm --prefix frontend run build
```

OpenAPI: http://127.0.0.1:8000/docs. Para desarrollo, Uvicorn en 8000 y
`npm --prefix frontend run dev` en otra terminal.

## Alcance y documentación

Piloto local con presupuestos en USD y fechas UTC. Sin autenticación multiusuario ni exposición pública.
S3/GCS/Azure están diferidos: el usuario eligió comenzar con CSV locales.
No realiza compras, cargos contables, cambios cloud ni aprobaciones financieras.
El forecast es un escenario de run-rate ajustado; el trimestral es 3× mensual, sin modelo estacional.
Las métricas sin historial o datos suficientes aparecen no disponibles.

- `docs/07-SCRIPTS-AGENTS-AND-EVIDENCE.md`: contrato implementado y almacenamiento.
- `docs/08-ACCEPTANCE-RESULTS.md`: pruebas, aceptación real y pendientes.
- `docs/06-ACCEPTANCE-PLAN-NVIDIA.md`: fases y cambios de alcance.
- Los cuatro documentos originales se conservan como referencia histórica.


## Informes incrementales
Antes de ejecutar el equipo, el backend compara datos, contexto, políticas, decisiones y versiones con el último informe completado. Si no hay cambios, devuelve el informe vigente sin llamadas al modelo ni tickets/informes duplicados. Con cambios, registra novedades y seguimiento, conserva los tickets entre períodos y no modifica decisiones humanas automáticamente. Los informes anteriores a esta versión necesitan una primera ejecución para establecer su firma.

Detalles: `docs/09-INCREMENTAL-REPORTS.md`. Fase del chat lateral y sus herramientas: `docs/10-ORCHESTRATOR-CHAT-PHASE.md`; borrador de lineamientos en `prompts/finops-chat.md` (prompt activo del chat).


## Chat del orquestador
Desde **Equipo de análisis**, selecciona al orquestador o un especialista y pregunta qué priorizar, cita tickets con `#FIN-001` o usa **Cómo aplicar esta mejora** en su modal. El chat consulta tickets, informes incrementales, scripts, SQL permitido y al especialista pertinente. Puede preparar/aplicar lotes de estados y notas, conservando el historial. Las propuestas incluyen revisión Aplicar/Descartar; órdenes explícitas con IDs, estado y motivo tienen autorización acotada comprobada en el backend.

Conversaciones en `workspaces/<cliente>/chat/threads/`, checkpoints LangGraph SQLite en `storage/chat-checkpoints.sqlite`; planes y recibos idempotentes en DuckDB. La API y el chat comparten `TicketOperations`. La identidad actual es el usuario local del piloto; no es un despliegue multiusuario con roles. No se ejecutan cambios cloud, solo consultas, orientación y operaciones de tickets. Abrir el panel no consume llamadas al modelo. El chat es el contenido principal de cada agente; la actividad se despliega dentro de cada turno y el aporte al informe queda como detalle. El texto llega en streaming desde NVIDIA y se reconecta mediante SSE.

## Laboratorio de datos sintéticos

`backend/.venv/bin/python -m finops_agent.lab serve` arranca S3 local autenticado y prepara **Nébula Payments** y **Mercado Aurora**, con 90 CSV diarios por cliente y 75 días inicialmente publicados. En **Cliente y datos → Datos de laboratorio**, importa particiones o pulsa **Simular el siguiente día**; después ejecuta el informe cuando quieras. No se llama al modelo al generar, publicar o importar. Instalación, fases, calendario y límites: `docs/11-SYNTHETIC-S3-LAB.md`.


Conversaciones por especialista, límites de uso, reintentos y respaldo NVIDIA: `docs/12-AGENT-CHAT-AND-RESILIENCE.md`.
