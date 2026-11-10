# Laboratorio sintético FOCUS y fuente S3

## Fases y aceptación

1. **Protocolo y acceso** — implementado. Moto Server en loopback con autenticación IAM activa, usuarios lectores por bucket y publicador separado. Listado por boto3, lectura directa de CSV y SHA-256 por DuckDB/httpfs. Pruebas de rechazo de acceso cruzado y escritura del lector.
2. **Fuente del backend** — implementado. Configuración por cliente, secretos locales 0600, descubrimiento de particiones, ingesta por transacción compartiendo la normalización existente. Auditoría `source_objects` con URI, ETag, SHA-256 y fecha. Reimportación idempotente. Las herramientas de agentes continúan leyendo `focus_usage` con filtro de cliente, período y moneda; no reciben credenciales ni URLs arbitrarias.
3. **Generador reproducible** — implementado. Dos perfiles, semilla, calendario, 90 días y seis registros diarios por cliente. Recursos estables, ruido determinista, crecimiento gradual, patrones de fin de semana distintos y costos derivados de cantidad × tarifa. Compromiso con capacidad diaria fija distribuida entre uso y desperdicio; base web On-Demand para evaluar nuevos compromisos.
4. **Publicación progresiva** — implementado. 75 días inicialmente publicados; comandos para avanzar hasta un día acumulado y control visual «Simular el siguiente día» en Cliente y datos. Publicar no llama al LLM. Reiniciar Moto reconstruye sus buckets desde las particiones y el cursor persistidos en disco.
5. **Verificación integrada** — implementada. Reproducibilidad, escenarios, permisos S3, ingesta incremental, rollback de archivo inválido y rehidratación probados sin NVIDIA. La validación semántica de los informes reales queda para las ejecuciones que lance el usuario.

## Escenarios y calendario predeterminado

Datos desde **2026-07-23 hasta 2026-10-20**, ambos inclusive. Inicialmente se publica hasta el **5 de octubre**; cada paso publica un día adicional. Dos clientes nuevos, sin modificar Acme:

- `lab-fintech`: Nébula Payments, consumo entre semana y Vertex AI; presupuesto USD 52,000.
- `lab-commerce`: Mercado Aurora, mayor actividad de fin de semana y Amazon Bedrock; presupuesto USD 63,000.

Eventos (índices de generación desde cero):

| Evento | Fechas | Efecto observable |
|---|---|---|
| Campaña aprobada | 26–29 septiembre | Web +80%; evento conocido en contexto |
| Anomalía IA | 6–10 octubre | Consumo AI 4×; normaliza desde 11 octubre |
| Corrección de etiquetas | desde 13 octubre | Storage recupera owner y cost_center; histórico previo permanece |
| Mejora de compromiso | desde 15 octubre | Utilización pasa de ~60% a ~95%; capacidad/costo contratado constante |
| Oportunidad de compromiso | todo el período | Base web On-Demand; excluir crecimiento de campaña al dimensionar |

Los valores son ilustrativos y **no representan precios oficiales de proveedores**. Exportan el subconjunto FOCUS que consume actualmente la app, no un dataset certificado de todas las columnas de una versión FOCUS. Las filas Used/Unused representan reparto diario amortizado simplificado; no se añaden compras iniciales para evitar doble contabilización. Presupuestos y condiciones de negocio están en el perfil/contexto, no inventados por el modelo.

## Ejecutar

Desde la raíz de la app, con dependencias ya instaladas:

```bash
backend/.venv/bin/python -m finops_agent.lab serve
```

Endpoint `http://127.0.0.1:9000`. No requiere Docker ni Supabase. Mantener este proceso junto al backend. Instalación reproducible:

```bash
UV_CACHE_DIR=/private/tmp/finops-uv-cache uv pip install --python backend/.venv/bin/python -e './backend[dev,lab]'
backend/.venv/bin/python -c "import duckdb; duckdb.connect().execute('INSTALL httpfs')"
```

Generar sin servidor: `backend/.venv/bin/python -m finops_agent.lab generate`.
Estado publicado: `backend/.venv/bin/python -m finops_agent.lab status`.
Publicar un rango acumulativo (76 equivale al primer día de anomalía):

```bash
backend/.venv/bin/python -m finops_agent.lab publish --client lab-fintech --through-day 76
```

En **Cliente y datos → Datos de laboratorio**, importar los días disponibles o simular el siguiente día (publica e importa). Después, **Ejecutar informe** para analizar con NVIDIA. La importación no consume tokens y el laboratorio no altera tickets automáticamente.

La CLI permite `--seed`, `--start`, `--days`, `--root`, `--workspaces` y `--port`. Para otra combinación usar directorios separados: se rechaza regenerar un laboratorio existente con parámetros distintos. La configuración predeterminada de API/UI apunta a `.lab` del proyecto; directorios alternativos son para CLI/pruebas. La UI avanza un día con control de versión para evitar doble clic concurrente.

## Rutas y almacenamiento

- CSV: `s3://finops-lab-fintech/focus/2026/10/06/usage.csv` y bucket independiente `finops-lab-commerce`.
- Disco fuente de verdad: `.lab/<cliente>/focus/YYYY/MM/DD/usage.csv`, manifiesto SHA-256 y cursor `published.json`.
- Calendario conocido: `workspaces/<cliente>/context_notes/known-events.md`, indexado por el mecanismo existente.
- Oráculo de pruebas: `.lab/<cliente>/expected-results.json`, separado de las notas y de cualquier contexto del agente.
- Credenciales lectoras: `workspaces/<cliente>/storage/s3-credentials.json`, modo 0600. Publicador: `.lab/publisher.json`, modo 0600. No se devuelven por API ni se inyectan en prompts.
- API: `GET /api/v1/clients/{id}/source`, `POST .../source/sync` con `{"through":"2026-10-06"}` opcional, `POST .../source/advance` con `{"expected_days":75}` para laboratorio local.

## Conectar otro almacenamiento S3

Crear primero el cliente. Configurar las variables locales `FINOPS_S3_ACCESS_KEY` y `FINOPS_S3_SECRET_KEY`, y ejecutar:

```bash
backend/.venv/bin/python -m finops_agent.sources --client mi-cliente --endpoint https://s3.example.com --bucket mis-costos --prefix focus/ --region us-east-1
```

El conector acepta particiones `YYYY/MM/DD/usage.csv` y `year=YYYY/month=MM/day=DD/usage.csv`. Los endpoints actualmente deben ser orígenes sin path: Supabase tiene un endpoint con `/storage/v1/s3`, por lo que requiere una adaptación específica antes de conectarlo. S3 local quedó validado; no se afirma una validación en AWS/Supabase real.

## Límites comprobados y decisiones

Moto mantiene los objetos en memoria; el laboratorio los rehidrata desde disco al reiniciar. Es un emulador de desarrollo, no un almacenamiento de producción. Su modo IAM es una simulación básica. Se mantiene en loopback; sus APIs administrativas no deben exponerse a redes externas.

Moto 5.2.2 presenta problemas de firma con caracteres `=` y ciertos parámetros de consulta codificados. Por eso el laboratorio usa particiones por fecha sin `=` y el SDK lista el bucket propio; DuckDB lee objetos exactos. En fuentes no sintéticas el SDK lista por prefijo. No se desactiva la autenticación para resolver esta incompatibilidad. La configuración temporal sin autenticación se utiliza solo durante bootstrap, antes de anunciar el servicio listo; luego permanece activa.

Cada partición es una unidad transaccional: una partición inválida no añade sus filas ni su registro de auditoría. Particiones anteriores válidas pueden permanecer si falla una posterior. Las particiones publicadas son inmutables: si cambia su contenido, la importación lo rechaza. No se implementan borrados de líneas históricas mediante correcciones de objetos: publicar días nuevos es el flujo del laboratorio. El ETag se comprueba antes de confirmar una lectura para detectar cambios concurrentes; no sustituye la garantía de snapshot/versionado de un proveedor real. Para producción faltan identidades administradas, versionado y contratos específicos del proveedor.

Referencias: [DuckDB S3](https://duckdb.org/docs/current/core_extensions/httpfs/s3api), [Moto Server](https://docs.getmoto.org/en/latest/docs/server_mode.html), [Moto IAM](https://docs.getmoto.org/en/latest/docs/iam.html), [FinOps Data Ingestion](https://www.finops.org/framework/capabilities/data-ingestion/).


## Evidencia de esta entrega

- Suite completa: **108 pruebas aprobadas**. Ruff, mypy y compilación TypeScript/Vite correctos.
- 180 CSV generados (90 por cliente), con 1,080 filas sintéticas.
- Importación inicial real vía S3 → DuckDB: 450 filas por cliente, hasta 2026-10-05.
- Avance desde el navegador de Nébula al 2026-10-06: seis filas nuevas, 76 particiones y 456 filas acumuladas. Mercado Aurora conserva 75 particiones y 450 filas.
- El resumen de Nébula detecta Vertex AI con costo diario de USD 1,274.97 frente a línea base aproximada de USD 293.59. El cliente Commerce sigue sin ese pico en su último día publicado.
- Verificación visual en 1440 × 1000 y 390 × 844; sin desbordamiento horizontal.
- No se iniciaron informes ni llamadas NVIDIA. El siguiente informe lo ejecuta el usuario desde la app.

El servicio S3 de laboratorio quedó activo en el puerto 9000 y la app en el 8000. Si se cierran los procesos, arrancar nuevamente el laboratorio con el comando `serve` y el backend con el comando habitual. `run.sh` conserva las dependencias opcionales del laboratorio cuando existe `.lab`; el proceso S3 se inicia por separado con `serve`.
