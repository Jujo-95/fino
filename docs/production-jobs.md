# Ejecución durable

La ruta canónica de análisis es `AnalysisJobs`: mide, crea o reevalúa tickets y guarda
`analysis/<run_id>.json`. El Markdown de Reportes es una vista determinista de ese mismo
resultado; el grafo narrativo anterior ya no se enruta por `/api/v1/runs/stream`.

En desarrollo FastAPI mantiene el worker embebido. En producción se puede arrancar el API
con `FINOPS_ANALYSIS_WORKER_MODE=external` y programar un Cloud Run Job (o cron equivalente)
con:

```bash
python -m finops_agent.worker
```

El proceso reclama un job de `analysis-jobs.sqlite`, ejecuta una sola unidad y termina.
El workspace y su base de coordinación deben estar en almacenamiento durable y con un
único escritor compatible con SQLite/DuckDB; no se debe montar una carpeta efímera distinta
por instancia. La cola conserva la clave diaria y evita duplicados.

Las acciones cloud pasan primero por `POST .../consulting/cloud-actions/simulate`. La aprobación
es explícita, queda registrada con una clave idempotente y el adaptador predeterminado no toca
ningún recurso. Un adaptador AWS, GCP o Azure se puede conectar después detrás de la misma
frontera, sin cambiar tickets ni el orquestador.

El ciclo de tickets conserva una semántica única: `IMPLEMENTED` registra la acción, `MONITORING`
espera la ventana de observación, `RESOLVED` exige que el criterio se cumpla y `FALSE_POSITIVE`
queda reservado para un hallazgo incorrecto. Un hallazgo nace con plan de verificación y al pasar
a `IMPLEMENTED` se crea de inmediato la tarea de verificación; el job diario reevalúa esa ventana.
