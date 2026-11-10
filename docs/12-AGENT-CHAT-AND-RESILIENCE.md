# Conversaciones por agente y resiliencia NVIDIA

Implementado el 21 de octubre de 2026.

## Experiencia principal

**Equipo de análisis** contiene un chat por orquestador/especialista dentro de `audit-agent-detail`. La selección de agente cambia identidad, avatar, prompt y conversación. Historial, borrador, referencias y selección se conservan por cliente y agente; los chats anteriores sin `agent_id` se consideran del orquestador.

La evidencia del informe y sus consultas permanecen bajo **Aporte al informe y evidencia**. El chat funciona aunque no exista un informe completado. El informe seleccionado se valida contra el cliente y se incluye como contexto; el agente puede consultar más evidencia usando las herramientas existentes. Los fallos históricos del informe permanecen en sus detalles, sin presentarse como un fallo nuevo del chat.

Se retiraron el modal y el botón flotante. «Cómo aplicar» desde un ticket abre el orquestador en el equipo e incluye la referencia. Los tickets siguen abriéndose como diálogos al pulsar referencias del chat. Cambiar de pantalla o agente no cancela los trabajos del backend.

## Reutilización del backend

Un mismo grafo LangGraph con `MessagesState`, `ToolNode`, checkpoints SQLite e `interrupt/Command` atiende los seis roles. La identidad se guarda al crear la conversación y no se cambia mediante un mensaje. Cada especialista reutiliza su `SpecialistSpec`, instrucciones FinOps versionadas y las reglas del chat; el orquestador adapta sus instrucciones del informe al modo conversación, sin exigir una herramienta `submit_analysis` inexistente en el chat.

Todos acceden a consultas FOCUS controladas, scripts, tickets e historial. La auditoría SQL identifica `chat_<agent_id>`. Los especialistas no delegan recursivamente a otros especialistas; esa herramienta queda en el orquestador. Operaciones, autorización acotada, recibos idempotentes y aprobación pendiente se conservan en los servicios existentes. No se repiten modificaciones por reintentos HTTP del proveedor: dichos reintentos solo solicitan respuestas de inferencia; las herramientas se ejecutan después de recibir una respuesta completa.

## Protección compartida del proveedor

- `langchain_core.rate_limiters.InMemoryRateLimiter`: token bucket compartido por el proveedor del contenedor, **30 solicitudes/minuto**, ráfaga de una solicitud y **dos solicitudes concurrentes**.
- Cola máxima de ocho solicitudes; espera de admisión máxima de 30 segundos.
- Tenacity `AsyncRetrying`: hasta dos intentos, backoff exponencial aleatorio, estados transitorios y respeto de `Retry-After`. La cuenta de solicitudes incluye intentos y respaldo.
- HTTP 401/403/404 y otros errores permanentes no se reintentan. HTTP 429 establece una pausa compartida; no cambia de modelo para eludirla. Un `Retry-After` superior a 30 segundos se devuelve sin mantener un reintento largo en espera.
- Timeout de conexión 10 segundos; lectura configurada en 30 segundos. Errores distinguen credenciales, permisos, modelo inexistente, límites, timeout de lectura/conexión y corte de streaming.
- Circuit breaker: tres fallos transitorios finales consecutivos pausan el proveedor 30 segundos. Una clave nueva limpia este estado; la clave se lee del entorno/`.env` en cada solicitud.
- Una respuesta streaming que ya recibió HTTP 200 no se vuelve a solicitar automáticamente si se corta. No se ejecutan llamadas de herramienta incompletas ni se expone `reasoning_content`.

## Respaldo explícito verificado

Primario: `z-ai/glm-5.3-flash`. Respaldo configurado: `nvidia/nemotron-3.5-lightning-30b-a3b` en el mismo endpoint NVIDIA. Se usa `RunnableLambda.with_fallbacks` de LangChain para fallos de conexión, timeout y disponibilidad, antes de haber recibido respuesta parcial. No se usa para credenciales inválidas, rate limits, errores de formato ni cortes de streaming ya iniciado.

Con respaldo habilitado, el primario hace un intento antes del cambio. Después de responder el respaldo se prefiere durante cinco minutos de actividad; así no se repite el timeout del primario en cada ronda del mismo informe. Las respuestas, registros de uso y trazas guardan modelo efectivo, modelo solicitado, indicador y motivo de respaldo. No hay fallback a datos ni respuestas simuladas.

Pruebas reales mínimas con la clave actual: GLM siguió sin responder en 35 segundos; el respaldo respondió con herramienta nativa válida en 0,61 segundos y su ruta streaming con herramientas respondió en 3,1 segundos. Esto valida conectividad y protocolo; no equivale a validar la calidad de todos los análisis FinOps. No se ejecutó un informe real completo para esta entrega.

## Límites de la API

Se admite trabajo lógico en los gestores existentes; reconectar SSE y consultar historial no consume estas cuotas:

| Operación | Cuota por cliente | Máximo global activo |
|---|---:|---:|
| Mensaje, reanudación o reintento de chat | 12/minuto | 4 chats |
| Crear conversación | 20/minuto | — |
| Crear informe | 3/minuto | 2 informes, ejecución serial existente |

Las peticiones rechazadas reciben HTTP 429 y `Retry-After`. Repetir un mensaje ya aceptado conserva su respuesta idempotente sin volver a ejecutar ni consumir cuota de trabajo. Los errores del proveedor se guardan con código y metadatos seguros; nunca con credenciales, cabeceras de autorización o cuerpos de error del proveedor.

Los limitadores y el circuit breaker viven en memoria del proceso. Este piloto funciona con un único backend local; para múltiples workers o instancias se requiere un limitador compartido y una identidad autenticada. Las cuotas son por solicitudes/trabajos, no por tokens de entrada/salida. Cada respuesta mantiene el límite de tokens ya existente.

## Configuración

```dotenv
FINOPS_LLM_FALLBACK_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b
FINOPS_LLM_RPM=30
FINOPS_LLM_CONCURRENCY=2
FINOPS_LLM_ATTEMPTS=2
FINOPS_LLM_READ_TIMEOUT=30
FINOPS_LLM_QUEUE_TIMEOUT=30
FINOPS_LLM_MAX_PENDING=8
```

Eliminar/vaciar `FINOPS_LLM_FALLBACK_MODEL` desactiva el respaldo. La configuración de presupuesto/modelos se aplica al inicializar el contenedor; cambiar solo `NVIDIA_API_KEY` no requiere reiniciar. La API no entrega la clave.

## Validación

126 pruebas completas aprobadas. Pruebas nuevas de reintentos transitorios, ausencia de replay de streaming parcial, Retry-After, circuito y rotación de clave, cola acotada, respaldo estándar y modelo efectivo, cuotas HTTP 429, aislamiento de historial por agente y prompts reutilizados. Ruff, mypy y compilación TypeScript/Vite correctos. Prueba visual de chat integrado en escritorio y móvil, sin modal global ni botón flotante.

Referencias oficiales: [LangChain rate limiters](https://reference.langchain.com/python/langchain-core/rate_limiters), [Tenacity](https://tenacity.readthedocs.io/en/stable/api.html), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence).


## Ajuste de navegación y densidad
Se eliminó el encabezado visual duplicado en Equipo de análisis (se conserva un h1 accesible). El único control superior del equipo son las pestañas Equipo/Informe. Selección de ejecución, estado, detalles y ejecución de informes están exclusivamente en Informe; también se retiró el CTA global de ejecutar informe de las demás cabeceras.

Tu equipo agrupa conversaciones bajo cada asistente, con título basado en el primer mensaje, fecha y acción de nueva conversación. Se eliminaron el selector de historial dentro del chat y los estados de ejecución del informe en la lista de asistentes. La misma instancia de useChat controla mensajes y selección del historial para evitar estados paralelos.

Validación de este ajuste: compilación Vite/TypeScript, Ruff, mypy y nueve pruebas focalizadas de conversaciones/API aprobadas. Verificación manual de apertura del historial, creación de conversación, separación Equipo/Informe y adaptación móvil sin desbordamiento horizontal. No se realizaron llamadas al modelo.


## Archivado e historial compacto
El historial de cada asistente puede plegarse pulsando de nuevo su fila, sin cerrar el chat. Las conversaciones tienen filas fijas de 52 px y una zona con scroll de máximo 208 px (cuatro filas). La acción Archivar oculta de las activas y mantiene mensajes, planes y checkpoints. Archivadas permite consultar y restaurar; el chat archivado es de solo lectura. La API bloquea archivar un trabajo activo (409) y ejecutar nuevos turnos en una conversación archivada. El filtrado sigue separado por cliente y especialista.

Pruebas: 16 pruebas focalizadas aprobadas, incluyendo persistencia, restauración, idempotencia, aislamiento y conflicto de trabajo activo. Ruff, mypy y build frontend correctos. Verificación desde navegador de plegado, archivo, restauración y tamaño de filas; sin llamadas NVIDIA.

### Navegación unificada y conversaciones vacías

Equipo se dedica a conversar con los seis agentes, sin pestañas Equipo/Informe.
Reportes concentra el historial de ejecuciones (incluidos fallos), informes diarios,
descargas, revisión y generación de línea base. El acceso superior derecho del panel
alterna entre chat y aporte/evidencia sin desmontar el chat ni perder el borrador.
Crear conversación reutiliza una vacía activa del mismo cliente y agente; la API
aplica la misma regla bajo el bloqueo compartido y solo cobra cuota si crea una nueva.
Las conversaciones archivadas no se reutilizan automáticamente.

### Equipo compacto

El lateral separa contactos y conversaciones: cuadrícula de seis agentes con filtro
por contacto y acción + que reutiliza conversaciones vacías. El historial sigue siendo
plegable y desplazable, limitado a cuatro filas de 34 px. Cada fila muestra avatar del
agente, título truncado y tiempo desde updated_at (se actualiza cada minuto); minutos
y meses usan M, con texto accesible completo para distinguirlos. Archivar aparece al
hover o foco de teclado; en pantallas táctiles permanece accesible. Equipo y chat
comparten límites sin márgenes entre paneles ni con la navegación. El compositor se
superpone al área desplazable sin una línea divisoria; el chat conserva espacio al final
para poder leer el último mensaje por encima del cuadro de entrada.
