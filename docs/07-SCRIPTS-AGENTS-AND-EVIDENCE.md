# Scripts, agentes y evidencia

## Alcance del piloto

CSV FOCUS locales, DuckDB por cliente y NVIDIA `z-ai/glm-5.3-flash`.
Los conectores S3/GCS/Azure se posponen hasta elegir la primera fuente cloud.
No se requieren HippoRAG, embeddings ni una base vectorial para este alcance.

## Dónde vive cada cosa

| Capa | Contenido | Persistencia | Acceso del agente |
|---|---|---|---|
| Datos importados | Registros FOCUS y huellas de archivos | `workspaces/<cliente>/storage/finops.duckdb`: `focus_usage`, `ingested_batches` | `query_focus` |
| Scripts | KPIs, anomalías estadísticas, forecast por run-rate y baseline limpio | Mismo DuckDB, tabla `script_snapshots` | `read_scripts` |
| Contexto | Perfil, notas, eventos aprobados y decisiones de tickets | YAML/Markdown y tabla `context_documents` | `read_context` |
| Definiciones | Instrucciones comunes, cinco especialistas y orquestador; guías FinOps | `prompts/*.md` y `finops_capabilities_md/capabilities/*.md` | System prompt del rol |
| Aportes | Interpretación, prioridades, justificación, propuestas y referencias | `workspaces/<cliente>/audit_runs/<run_id>.json` | Orquestador y revisión |
| Informe | Síntesis con métricas deterministas y aportes | `reports/*.md` y copia por ejecución en auditoría | UI y siguiente revisión |

Cada snapshot tiene ID independiente, versión de scripts, hash del código, hash del conjunto de archivos,
perfil utilizado, período, fórmulas y evidencia SQL original. Es un artefacto reproducible del cálculo;
no se presenta como una conclusión del modelo. Un nuevo análisis conserva su propio snapshot.
El dashboard calcula sus indicadores mediante estos mismos scripts; no llama al LLM.

## Lo que hace el modelo

Cada especialista ejecuta un ciclo nativo modelo → herramientas → observaciones → entrega validada.
Debe consultar DuckDB, leer los scripts y leer contexto antes de entregar un análisis, incluso si no encuentra hallazgos.
`describe_data` permite consultar el esquema, catálogo y fórmulas. `query_focus` admite plantillas
`totals`, `daily`, `services`, `accounts`, `resources`, `tag_gaps`, `commitments`, con filtros opcionales de cuenta/servicio.
El servidor fija cliente, moneda y ventana temporal. El modelo no puede acceder a archivos, secretos,
DDL, extensiones o SQL arbitrario. La consulta SQL concreta y sus parámetros quedan visibles.
Se validan referencias de evidencia, capacidad del KPI y disponibilidad del valor. Las cifras estructuradas
se toman del snapshot, no del texto generado. Los impactos no calculados permanecen en `null`.
Las explicaciones y recomendaciones siguen siendo interpretaciones del modelo y requieren revisión humana.

El orquestador revisa los cinco aportes y puede usar `request_refinement` hasta dos veces.
El especialista vuelve a consultar las herramientas y su contribución revisada reemplaza la anterior en el informe.
Se conserva la revisión anterior en la auditoría. También se puede solicitar una nueva revisión desde la pestaña Informe.
No hay compras, cambios cloud ni aprobaciones financieras automáticas.

## Contexto sin grafo

La guía FinOps de cada capacidad se carga directamente en el prompt del especialista.
El perfil y las decisiones se recuperan por cliente. La supresión de anomalías cruza metadatos estructurados
con identidad cuenta/servicio, estado y fechas; no depende de ranking léxico o embeddings.
La tabla antigua `graph_documents`, si existe, se migra a `context_documents` sin sobrescribir documentos actuales.
El módulo antiguo conserva únicamente un alias de importación para compatibilidad.

## Operación y límites

- `.env` está ignorado por Git. `NVIDIA_API_KEY` se lee en el backend; no se envía al navegador.
- El proveedor por defecto es NVIDIA. `FINOPS_LLM_PROVIDER=mock` activa explícitamente la demostración por reglas.
- Cliente HTTP OpenAI-compatible mediante `httpx`; no se necesita LangChain para NVIDIA.
- Temperatura 0.5, top_p 1, sin streaming del modelo; SSE publica las etapas del grafo.
- Máximo 10 rondas, 8 llamadas por ronda, 360 segundos por agente, 90 segundos por petición HTTP.
- Un reintento en 429/5xx; los errores no activan reglas como reemplazo.
- `reasoning_effort=low` por defecto; configurable mediante `FINOPS_REASONING_EFFORT`.
- 4096 tokens de salida por petición, configurable mediante `FINOPS_MAX_TOKENS`; se detecta truncamiento.
- Consultas de agentes: límite SQL 101 filas, muestra de 100 con indicador de truncamiento, timeout de 15 segundos.
- DuckDB: 2 threads y límite de buffer de 512 MB por base. No representa un límite absoluto del proceso.
- Se auditan prompts, hash, herramientas, observaciones, uso de tokens y conclusión verificable.
  No se registra `reasoning_content` ni una cadena privada de pensamiento.
- Esta instalación sirve en loopback y no incorpora autorización multiusuario. No se declara lista para exposición pública.

Referencias: [Function calling](https://developers.openai.com/api/docs/guides/function-calling),
[NVIDIA API](https://docs.api.nvidia.com/nim/reference/llm-apis),
[DuckDB configuración](https://duckdb.org/docs/stable/configuration/overview).

## Ejecuciones independientes del navegador

`POST /api/v1/runs` crea una tarea propiedad del backend y devuelve el run_id inmediatamente.
`GET /api/v1/clients/{client_id}/runs/{run_id}/events` observa y reproduce sus eventos persistidos.
Cerrar o refrescar la página cancela solamente la suscripción HTTP; no cancela la tarea.
La UI recupera el cliente seleccionado, descubre su ejecución activa y se vuelve a suscribir.
Iniciar nuevamente mientras exista una tarea activa para el mismo cliente devuelve ese mismo run_id.
El endpoint antiguo POST /runs/stream conserva compatibilidad, usando el mismo administrador de tareas.

Esta instalación usa un solo proceso backend. Detener ese proceso interrumpe el trabajo; los registros y
los eventos anteriores permanecen en disco. No se presenta como recuperación automática tras una caída del servidor.
