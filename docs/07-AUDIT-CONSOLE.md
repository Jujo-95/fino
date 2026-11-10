# Equipo y auditoría

La sección **Equipo y auditoría** muestra el orquestador y los cinco especialistas con sus aportes
individuales. Las trazas se generan durante la ejecución y se guardan por cliente en
`workspaces/<client_id>/audit_runs/<run_id>.json` mediante reemplazo atómico.

## Qué registra

- Inicio, fin, duración y estado de cada etapa, junto con el modo/proveedor real.
- Consultas SQL efectivamente ejecutadas, sus parámetros vinculados y el resultado guardado.
- Conteo completo de filas y una muestra explícita de hasta 100 filas por consulta.
- KPIs, fórmulas, entradas derivadas, políticas y hallazgos de cada especialista, sin duplicar el acumulado.
- Resumen verificable de criterios y resultados; no captura razonamiento interno privado del modelo.
- Pasajes que se recuperaron de memoria, cuando hubo recuperación.
- Mensajes enviados y comentario final si se hizo una llamada LLM. En modo reglas se indica que no hubo prompt.
- Informe de la ejecución, con una sección de aportes por especialista y referencias a consultas.

## Atribución correcta de las consultas

El motor actual ejecuta tres consultas en `ingest_and_profile`: `totals`, `daily` y `services`.
Los especialistas consumen esos resultados. La ficha distingue consultas ejecutadas de referencias
compartidas; no atribuye generación de SQL al especialista cuando no ocurrió.
Los resultados auditados se conservan como snapshots; abrir una ejecución no vuelve a lanzar sus consultas.

## API

- `GET /api/v1/clients/{client_id}/runs`: últimas 100 ejecuciones registradas del cliente.
- `GET /api/v1/clients/{client_id}/runs/{run_id}`: traza, consultas, resultados y reporte de esa ejecución.
- `POST /api/v1/runs/stream`: mismo contrato existente, añadiendo `run_id` y trazas en los eventos SSE.

Errores y desconexiones conservan la traza parcial y un estado `failed` o `cancelled`.
El historial anterior a esta función no se reconstruye artificialmente desde reportes antiguos.
La UI permite exportar JSON de la auditoría y Markdown del informe de una ejecución concreta.

## Cobertura y límite

La prueba de navegador usa exclusivamente el cliente sintético Acme FinTech.
La suite verifica aportes individuales, consultas reales, errores parciales, aislamiento entre clientes,
persistencia y registro del prompt/final sin registrar campos de razonamiento interno.
Las pruebas de LLM usan un doble de prueba identificado; no validan conexión a NVIDIA.
Esta entrega implementa la observabilidad de la fase 7 del plan. Las fases de conexión NVIDIA,
herramientas agentivas y conectores cloud siguen pendientes.
Los archivos locales son un registro operativo, no un archivo firmado o un sistema de auditoría inmutable.
