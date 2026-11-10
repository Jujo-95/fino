# Análisis estructurado, consultas remotas y revisión diaria

Implementación MVP del spec de optimización (26 octubre 2026).

## Flujo único

- Reportes pasa a llamarse **Análisis**. «Actualizar análisis», `start_analysis_job` del chat 2.0 y el horario llaman a `RunJobs` con `analysis_only=true`.
- El job persiste `AnalysisRun`: período, revisiones de fuente/contexto/política, indicadores, cobertura, hallazgos, acciones, seguimiento y evidencia. No necesita Markdown ni llamadas a modelos.
- El catálogo y los prompts 2.0 siguen disponibles para investigación e interpretación desde chat. Las contribuciones internas usan un contrato estructurado acotado; no concatenan todo el monólogo.
- Solicitar un informe narrativo desde el orquestador conserva las herramientas existentes, la persistencia y la confirmación de repetición. Los análisis automáticos no cuentan como informes narrativos repetidos.

## Conexión del cliente

En **Conexiones → Fuente de facturación FOCUS**, configurar:

1. Parquet S3/GCS/Azure: bucket/contenedor, prefijo literal, cuenta/región cuando corresponda. BigQuery: proyecto que paga/ejecuta, tabla completa y ubicación.
2. Ventana disponible `[inicio, fin)`. Actualmente es declarada por el operador; no se certifica completitud de la facturación.
3. Límite de bytes y tiempo. Explorar comprueba acceso/metadatos y muestra objetos paginados; no ejecuta agentes ni importa filas.
4. Identidad del entorno o credencial en el llavero del SO del servidor. La configuración JSON no almacena secretos. Los secretos no se devuelven al frontend ni al modelo.

S3 usa credenciales estándar AWS; GCS/BigQuery usan ADC o service account; Azure usa DefaultAzureCredential o SAS de lectura. BigQuery requiere permisos para leer la tabla y crear jobs en el proyecto de ejecución. Las extensiones de DuckDB proceden exclusivamente del repositorio oficial firmado; una instalación faltante usa el directorio de extensiones del workspace.

No hay ingesta de la fuente remota a `focus_usage`. Parquet transfiere bloques a la memoria de DuckDB; no existe una promesa de ejecución «sin transferencia». La tabla local continúa disponible para CSV/demo/laboratorio. Desconectar la fuente remota reactiva explícitamente el modo local y desactiva el horario.

## Límites y caché

- DuckDB remoto: memoria 512 MiB, sin spill a disco, prefijo autorizado, máximo 10.000 objetos descubiertos y presupuesto conservador por suma de tamaños seleccionados. Para grandes alcances, restringir particiones o consultar en BigQuery.
- BigQuery: dry run, máximo de bytes facturados, timeout, resultados acotados y registro del job/bytes/cache. Los límites de filas no se presentan como límites de escaneo.
- Consultas de agentes: guardrail SELECT, relaciones permitidas, cliente/moneda/ventana fijados por servidor y preview máximo 100 filas con truncamiento explícito.
- Base compartida: totales, coste diario, cuenta/servicio y agregados de cobertura por cuenta/día. No se ejecutan los 60 casos automáticamente. Los casos completos continúan accesibles por herramientas.
- Antes de releer, se comprueba la revisión de la fuente: las mediciones retenidas se reutilizan incluso con caché temporal caducada. Los cambios de contexto recalculan los indicadores derivados sin escanear nuevamente la facturación. Una prueba adicional verifica este caso con la caché eliminada.
- Clave de caché: cliente + revisión de objetos/tabla + SQL/versionado + parámetros. Cambios de responsables/contexto no invalidan una consulta idéntica.
- Metadatos en `query_results` del DuckDB del cliente; JSON pequeño o Parquet para más de 500 filas. Límite 16 MiB por resultado; caché limitada a 200 entradas/128 MiB y TTL. La evidencia retenida dentro del análisis no depende de conservar la caché.
- Se conservan numeradores/denominadores en la base remota. No se suman cantidades de unidades heterogéneas como si fueran una sola unidad.

## Jobs sin infraestructura adicional

Una instancia de backend y un worker. `analysis-jobs.sqlite` guarda coordinación separada de checkpoints LangGraph; DuckDB mantiene analítica. No requiere Redis, Celery, RAG ni otro servicio.

- Horario por cliente, inicialmente desactivado: 06:00 America/Bogota, retraso 2 días, editable.
- Desde Análisis → Revisión diaria se activa y guarda el horario. Una fuente remota debe haber pasado Exploración.
- Cola persistente, reclamación transaccional, exclusión por cliente, idempotencia diaria y recuperación tras reinicio. Se pone al día una vez; no se reproduce un trabajo por cada día de indisponibilidad.
- Los errores transitorios reconocidos tienen hasta 2 reintentos con backoff. Credenciales/permisos/contratos no entran en un bucle de reintentos.
- Detener cancela la cola y señala la consulta activa. Si la operación aún está dentro de una llamada SDK, el estado comunica cancelación pendiente hasta su timeout. No se inician nuevas consultas después de detectar la señal.
- Un reinicio conserva pendientes y resultados ya guardados; las operaciones se concilian idempotentemente. Un cancelado por el usuario no vuelve a la cola.
- Desplegar con un solo proceso/worker ASGI y almacenamiento persistente del workspace. No es un motor distribuido.

## Tareas y cobertura

- Los controles deterministas están identificados como tales; no se atribuye razonamiento o consumo de tokens a un agente que no se invocó.
- Se reutilizan los servicios de tickets y requisitos existentes. Las propuestas nuevas son PROPOSED; se actualiza el mismo hallazgo por alcance, conservando notas/decisiones.
- Datos insuficientes producen cobertura parcial. No se afirman salud, ahorro o normalización por falta de filas.
- Los seguimientos vuelven a comprobar su ventana/criterio. Un posible cierre genera atención y evidencia, sin cambiar silenciosamente el estado.
- «Nueva tarea» usa un recibo de ticket y desaparece al abrir detalle/hilo visible. «Necesita atención» es independiente de lectura del chat. Un ticket en observación esperando datos no recibe una alerta artificial.
- Los históricos no se marcan masivamente como nuevos. Los estados activos conservan atención cuando requieren una decisión.

## Verificación y límites reales

Suite completa: 287 pruebas con fixtures/dobles identificados; Ruff, mypy y build frontend correctos. Se comprobó el backend/estático con HTTP 200 y horarios de los tres clientes existentes desactivados. Sin validación visual ni ejecuciones reales de modelos.

Parquet se comprobó con archivos reales locales detrás de un adaptador de nube simulado; BigQuery con dobles del SDK y pruebas de SQL/UTC/JSON, dry run, presupuesto y cancelación. **No hay certificación de acceso a buckets o tablas reales** sin sus ubicaciones e identidades. Tampoco se declara que los 60 SQL de referencia estén certificados en BigQuery: el guardrail valida cada ejecución y registra incompatibilidades explícitamente.

No se certifica conformidad FOCUS formal, conciliación contable, causalidad de ahorros ni completitud de TB por una exploración o una muestra. La narrativa y la investigación especializada siguen siendo solicitudes explícitas; la revisión diaria base no necesita tokens.
