# Plan de implementación y aceptación: agentes FinOps con NVIDIA

Estado: ejecución del piloto local en curso. Ver `07-SCRIPTS-AGENTS-AND-EVIDENCE.md` para el contrato implementado y `08-ACCEPTANCE-RESULTS.md` para evidencia y pendientes.
Proveedor elegido: NVIDIA API Catalog. Modelo exacto solicitado: `z-ai/glm-5.3-flash`.
La interfaz visual actual se conserva; se añaden solamente controles y trazabilidad necesarios.
Base funcional existente: DuckDB local, LangGraph, CSV FOCUS, tickets, reportes y recuperación léxica.
Brechas: conectores cloud, prompts completos, herramientas del LLM, HippoRAG completo y pruebas live.
Referencia FinOps: https://www.finops.org/framework/capabilities/automation-tools-services/

## Configuración objetivo

```dotenv
FINOPS_LLM_PROVIDER=nvidia
FINOPS_LLM_MODEL=z-ai/glm-5.3-flash
NVIDIA_API_KEY=
FINOPS_MAX_TOKENS=4096
FINOPS_REASONING_EFFORT=low
```

La configuración NVIDIA ya activa el proveedor nativo en el backend.
El transporte OpenAI-compatible recibe la clave resuelta del entorno o `.env`, nunca el literal `"$NVIDIA_API_KEY"`.
Decisión implementada: `httpx` asíncrono, ya presente en el proyecto, en lugar de añadir otro SDK.
Endpoint NVIDIA fijo; temperatura 0.5, top_p 1 y stream false.
La API key se configura en el backend mediante entorno o archivo local ignorado por Git.
Autenticación del LLM y autenticación de S3/GCS/Azure son configuraciones independientes.

## Fase 1. Transporte NVIDIA y verificación del modelo

**Entregables**
- Adaptador NVIDIA con el SDK `openai`, preferentemente `AsyncOpenAI`, y cliente reutilizado por lifespan.
- Endpoint, modelo y parámetros anteriores configurables; carga explícita de configuración local.
- Timeouts, concurrencia, retries acotados para 429/5xx y errores visibles para 401/403/modelo inválido.
- Comprobación de conexión: proveedor, modelo, latencia, uso de tokens y capacidad de herramientas.
- Modo `mock` exclusivamente explícito; ningún fallo de NVIDIA se convierte en éxito simulado.

**Verificación de salida**
- Sin key: error de configuración claro; con key inválida: error de autenticación claro.
- Smoke real con la pregunta del ejemplo: resultado que identifique 9.8 como mayor que 9.11.
- Prueba real de un tool call y continuación con su resultado, usando datos sintéticos.
- Validar salida estructurada y las opciones realmente admitidas por el endpoint alojado.
- Registrar `finish_reason`; una salida truncada o vacía no genera hallazgos ni tickets.
- Los 1024 tokens se conservan para el smoke inicial; el presupuesto del ciclo se ajusta y documenta
  según pruebas de razonamiento/herramientas, sin confundir tokens de razonamiento con respuesta final.

## Fase 2. Definiciones y system prompts legibles

**Entregables**
- `backend/prompts/common.md`, `orchestrator.md`, `allocation.md`, `anomaly.md`, `forecasting.md`,
  `budgeting.md` y `commitment.md`, versionados y cargados desde archivos.
- Definiciones declarativas por especialista: función, alcance, entradas, herramientas y salida.
- Cada prompt: capacidad FinOps, fuentes oficiales/locales, semántica FOCUS, KPIs, madurez,
  Showback/Chargeback, moneda, UTC, criterios de evidencia y tratamiento de datos faltantes.
- Reglas particulares: eventos planeados para anomalías; baseline limpio para forecasting y compromisos;
  presupuesto/holdback para budgeting; propiedad y reparto compartido para allocation.
- El orquestador coordina contexto y síntesis; el grafo conserva las dependencias causales obligatorias.

**Verificación de salida**
- Los seis roles tienen definición auditable; ningún especialista usa solo una descripción de una línea.
- Pruebas de carga y contrato comprueban que el prompt correcto llega al proveedor.
- Documentos recuperados y notas son datos; no pueden redefinir herramientas, identidad ni permisos.

## Fase 3. Herramientas SQL y evidencia verificable

**Entregables**
- Herramientas tipadas: `describe_focus_schema`, `list_kpis`, `run_kpi` y `query_focus`.
- Registro SQL por capacidad y fórmulas de los 13 KPIs; cálculos derivados en código comprobable.
- El LLM elige herramientas y solicita consultas; cliente, moneda y límites temporales los inyecta el backend.
- SQL de solo lectura, AST validado, tablas permitidas y límites de tiempo/filas/recursos.
- Acceso a archivos remotos, extensiones y secretos exclusivo del motor de ingesta, fuera del SQL del LLM.
- Cada resultado tiene `query_id`, parámetros, período, origen, columnas y filas necesarias como evidencia.
- Un hallazgo referencia evidencias existentes; sus cifras se validan contra los resultados calculados.

**Verificación de salida**
- Rechazo de mutaciones, lecturas de archivos arbitrarios y consultas fuera del cliente/período/moneda.
- Los cinco especialistas pueden obtener datos relevantes mediante herramientas, no solo recibir KPIs precalculados.
- Tests con fixtures comprueban fórmulas, datos faltantes, límites y aislamiento entre clientes.

## Fase 4. Contexto documental (alcance revisado: sin HippoRAG)

Decisión del piloto: sustituir los siguientes requisitos originales de grafo por guías directas de capacidad,
perfil, notas y decisiones estructuradas persistidas. No se implementan embeddings ni HippoRAG.
La alternativa está descrita y probada en el contrato de scripts/agentes.

Requisitos originales, conservados solo como referencia:

**Entregables**
- Integración explícita y versionada de HippoRAG; separar KB FinOps compartida y memoria por cliente.
- Ingesta de las 22 capacidades, perfil, notas, tickets y resoluciones con IDs estables y citas por pasaje.
- Herramientas `search_finops_guidance` y `search_client_context` accesibles a los especialistas.
- Definir y verificar modelo de embeddings; usar backend local para arrancar si es compatible.
- La elección del modelo de chat no implica disponibilidad de embeddings en NVIDIA.
- Actualización idempotente de documentos, persistencia de índices y recuperación tras reinicio.

**Verificación de salida**
- Consulta con recorrido cuenta → decisión previa → evento aprobado → ventana temporal recupera la evidencia.
- Una decisión nueva reemplaza la anterior en memoria; un evento vencido no suprime alertas actuales.
- Cero recuperación entre clientes. Distinguir en configuración HippoRAG real de la alternativa léxica actual.
- No marcar esta fase completa por renombrar el servicio existente o mantener solo coincidencias por palabras.

## Fase 5. Ejecución agentiva y orquestación real

**Entregables**
- Un `SpecialistRunner` compartido con ciclo modelo → herramientas → observaciones → respuesta estructurada.
- LangGraph: ingesta/perfil → asignación → anomalías → forecasting → budgeting → commitment → síntesis.
- El LLM interpreta contexto y recomienda; código determinista calcula, valida y persiste.
- Estado con evidencias, anomalías activas, exclusiones de baseline, incertidumbres y salidas por especialista.
- Límites de rondas, llamadas, tokens y duración; cancelación y estados de ejecución parcial/fallida.
- El orquestador sintetiza resultados verificados; el gestor atómico crea tickets idempotentes.

**Verificación de salida**
- Traza real demuestra llamadas NVIDIA y herramientas antes de producir una recomendación.
- Misma facturación con contexto de negocio distinto puede cambiar la recomendación, citando ese contexto.
- Un pico temporal aprobado queda fuera de compromisos aunque se descarte como anomalía accionable.
- Si faltan pruebas o falla el modelo, se informa el fallo; no se publican tickets como si el ciclo hubiera completado.

## Fase 6. Fuentes cloud por cliente (diferida; usuario eligió CSV locales)

No se declara implementada ni verificada esta fase. Los siguientes entregables aplicarán al futuro piloto cloud.

**Entregables**
- Perfil de fuente: proveedor, bucket/contenedor, prefijo, formato, región y referencia a credenciales.
- Tres adaptadores: S3 con identidad/rol AWS; GCS con identidad Google y mecanismo compatible con
  DuckDB; Azure Blob con identidad administrada/principal y extensión correspondiente.
- Resolver credenciales del lado servidor; permitir identidad federada/temporal cuando el despliegue lo soporte.
- Descubrimiento de objetos, permisos de lectura, manifiesto de versiones, cambios y sincronización incremental.
- Validación FOCUS y deduplicación transaccional; no recorrer indefinidamente todo el almacenamiento en cada ciclo.
- Registrar fuente/versión y distinguir una importación nueva de un reproceso o corrección del proveedor.

**Verificación de salida**
- Subpruebas independientes S3, GCS y Azure: leer un objeto autorizado, sincronizarlo y no duplicarlo al repetir.
- Denegación fuera del bucket/prefijo autorizado y ausencia de secretos en SQL visible, logs o navegador.
- Cada proveedor permanece pendiente de validación live hasta probarlo con sus credenciales reales.
- El primer piloto usa una fuente elegida; no se declara soporte productivo de las otras por simulaciones.

## Fase 7. Operación y trazabilidad en la UI existente

**Entregables**
- Configurar/probar LLM y fuente de datos sin exponer secretos; mostrar proveedor, modelo y modo reales.
- SSE con especialista, herramienta, evidencia y resultado; sin publicar razonamiento interno del modelo.
- Inspeccionar prompt/versiones, consulta ejecutada, pasajes citados y justificación final del hallazgo.
- Métricas de latencia, tokens, errores y uso; marcar costos como estimados solo con tarifa configurada.
- Para uso productivo compartido: autenticación, autorización por cliente, gestión de secretos,
  registros de auditoría, despliegue reproducible y restauración comprobada de datos/índices.

**Verificación de salida**
- Usuario identifica si un resultado proviene del LLM real, una prueba sintética o reglas locales.
- Un fallo de herramientas/modelo aparece como fallo; no queda un indicador de éxito genérico.
- Revisión funcional en escritorio/móvil conservando la dirección visual ya aceptada.

## Fase 8. Aceptación integrada y puesta en marcha

**Prueba A: agente conectado**
- Configurar `NVIDIA_API_KEY`, instalar dependencias y seleccionar el modelo indicado.
- Ejecutar onboarding y ciclo diario sobre un fixture FOCUS identificado como sintético.
- Verificar llamadas reales al modelo, consultas DuckDB, memoria citada y tickets estructurados.
- Resolver un ticket, reiniciar y comprobar que el siguiente ciclo recupera la decisión sin duplicar tickets.

**Prueba B: piloto con datos del cliente**
- Configurar identidad de almacenamiento y prefijo autorizado; validar la sincronización real.
- Ejecutar el ciclo con evidencia trazable a los objetos/particiones del cliente y a documentos FinOps.
- Verificar permisos, fallo de credenciales, truncamiento, límites, recuperación y aislamiento.
- La suite offline y los smokes live se reportan separados; sin credenciales, live queda pendiente.

**Aceptación final:** configuración y credenciales bastan para ejecutar agentes con herramientas,
memoria y evidencia; no hace falta reescribir el runner ni incorporar recomendaciones a mano.
El piloto requiere además fuente, permisos y datos válidos; una key de NVIDIA no autentica el almacenamiento.

## Orden, hitos y evidencia

Orden de integración: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8.
Hito A: fases 1–5 más traza mínima, validado con prueba A; agente LLM real sobre datos locales.
Hito B: fases 6–8, validado con prueba B; piloto cloud. Producción compartida requiere los controles de fase 7.
Cada fase termina con pruebas, archivos modificados y evidencia de lo comprobado; no solo declaración de finalización.
Mantener límites del repositorio: 180 líneas por módulo y 35 por función; lógica compartida y contratos tipados.

Fuentes: https://docs.api.nvidia.com/nim/reference/llm-apis
Modelo: https://build.nvidia.com/z-ai/glm-5-3-flash/modelcard
