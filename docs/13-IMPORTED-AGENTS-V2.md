# Equipo 2.0: integración MVP

## Fuente y coexistencia

Se importaron las 16 definiciones Markdown de agents.zip, incluidos el orquestador,
14 especialistas y el curador. Se conservan íntegros los textos fuente, con ruta y
SHA-256, dentro de prompts/agents-v2/registry.json. No se importó infraestructura,
credenciales, conexiones GEAI ni herramientas de escritura del proyecto original.
Los seis agentes anteriores y sus conversaciones permanecen disponibles en Actual;
los importados se seleccionan con Equipo → 2.0. No se añade RAG ni se elimina la
recuperación anterior. La integración reutiliza el grafo de chat LangGraph, ToolNode,
checkpoints SQLite, proveedor NVIDIA, rate limits y SSE existentes.

Capacidad de referencia: Automation, Tools & Services
https://www.finops.org/framework/capabilities/automation-tools-services/

## Adaptación de los prompts

El cuerpo original conserva identidad, lineamientos, SQL playbook y entregables.
app-adapter.md añade el contrato de la app: español, preguntas breves con respuestas
breves, alcance de cliente inmutable, rutas .coda sustituidas por herramientas del
backend y datos internos separados de la narrativa. Benchmarking no permite leer
otros clientes. No se importó el modelo o la estrategia de razonamiento de GEAI.

## Herramientas

- get_schema: columnas reales, cobertura y configuración del cliente.
- query_finance: SQL DuckDB de lectura sobre focus_data_table/focus_usage.
- get_data_preview: hasta 20 filas del cliente y periodo actual.
- get_use_case: definición y SQL de referencia importado.
- execute_use_case: ejecución con adaptación de parámetros y sintaxis; admite fechas.
- read_use_case_snapshots: materializa/reutiliza resultados del periodo actual.
- list_reports: identificadores y periodos de informes completados del cliente.
- read_report_changes: informe completado del mismo cliente; no confunde snapshots.
- read_context, list_tickets, get_tickets, plan_ticket_changes: servicio actual.
- consult_specialist: solo orquestador 2.0, delegación en roles importados.
- save_report: solo orquestador 2.0, entrega humana y JSON en Reportes.

Las consultas pueden cambiar periodo, nunca cliente/moneda. El árbol SQL se restringe
a SELECT/UNION y CTEs sobre la relación FOCUS; cada fuente física se sustituye por
una subconsulta con cliente, fechas y moneda impuestos por el servidor. No se permiten
archivos, funciones externas, tablas internas, escrituras ni múltiples sentencias.
Límite de 100 filas de resultado y 15 segundos por consulta. Las fechas son [inicio,fin).

## Use cases y snapshots

El archivo importado contiene 60 casos con SQL de referencia, conservado sin cambios
en use-cases.json; no implica que sean todos los casos existentes en la comunidad.
Se usa la primera variante SQL de cada caso para el snapshot automático; get_use_case
expone todas las variantes originales para adaptación explícita con query_finance.
Los snapshots se crean bajo demanda, sin LLM, por cliente/periodo/moneda/datos/catálogo,
en workspaces/<cliente>/use_case_snapshots/<firma>.json mediante escritura atómica.
Se devuelve una vista de hasta cinco filas por caso; los resultados conservados incluyen
hasta 100. Estados: ok, empty, unavailable, error. Una carencia no equivale a cero.
El catálogo de referencia exige muchas columnas no incluidas en el esquema MVP actual;
con el fixture de 24 columnas, 1 caso se ejecuta y 59 quedan no disponibles por columnas,
parámetros o incompatibilidades. No se fabrican proveedores, unidades o presupuestos.
Los agentes pueden adaptar consultas a las columnas realmente disponibles.

## Delegación y entrega

Los subagentes usan el mismo grafo, prompts y herramientas; sus hilos internos no
llenan el historial del usuario y no tienen herramientas de mutación. Los checkpoints
y el identificador determinista permiten recuperar/reutilizar una delegación. Máximo
16 delegaciones por turno del orquestador. El proveedor conserva sus límites globales.

save_report conserva Markdown y JSON original en workspaces/<cliente>/reports y la
referencia en audit_runs. La entrega JSON puede descargarse desde Detalles de la
ejecución. Guardar es idempotente por conversación/turno/contenido; no crea tickets ni
aplica memoryUpdates/proposedActions. El curador devuelve propuestas, no escribe memoria.
Las transiciones de tickets existentes usan exclusivamente el servicio autorizado actual.
El botón Ejecutar informe de Reportes conserva el pipeline original; para usar el nuevo
orquestador se conversa con él desde Equipo 2.0 y se solicita el informe.

## Validación

Pruebas con dobles de modelo y consultas reales a DuckDB: importación, prompts originales,
coexistencia, filtros de cliente/periodo, SQL adversario, snapshots, delegación, informe dual,
idempotencia y ausencia de mutaciones automáticas. No se ejecutó una flota real NVIDIA.
