# Gemini intercambiable con NVIDIA

El backend acepta `FINOPS_LLM_PROVIDER=gemini` (alias `vertex`) y usa el SDK oficial `google-genai`. El contrato complete/stream_complete/complete_for_report se mantiene: mismos agentes, herramientas, LangGraph, consultas DuckDB, propuestas/aprobaciones y jobs. No se envían datos al otro proveedor como fallback.

## Configuración

En el `.env` del backend:

```
FINOPS_LLM_PROVIDER=gemini
GOOGLE_CLOUD_PROJECT=your-google-cloud-project
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=gemini-3.6-flash
GOOGLE_API_KEY=<clave local, nunca incluir en documentación>
```

Usa una clave propia vinculada al proyecto de despliegue y restringida a `aiplatform.googleapis.com`. El archivo local debe tener permisos 0600. El navegador, los prompts y los endpoints de configuración pública nunca reciben la clave. La cuenta de facturación del proyecto recibe el consumo; el saldo promocional no impone un límite automático de gasto.

El SDK usa el proyecto indicado y la clave vinculada, sin un token OAuth fijo que caduque. ADC sigue disponible para otras aplicaciones, pero no es la credencial elegida en este proveedor API key. Para cambiar de modelo edita GEMINI_MODEL y reinicia el backend. Para volver a NVIDIA cambia FINOPS_LLM_PROVIDER=nvidia; su configuración/llavero existentes permanecen disponibles. Las preferencias NVIDIA guardadas en runtime no sobrescriben la configuración Gemini.

## Herramientas y streaming

- JSON Schema nativo, ejecución automática del SDK deshabilitada: las herramientas siguen controladas por LangGraph.
- El adaptador conserva el contenido nativo y las firmas opacas en checkpoints para responder a herramientas en turnos posteriores. No expone ni conserva texto privado de pensamiento.
- Se transmite texto visible en orden; herramientas solo se ejecutan tras una respuesta completa. Truncamiento/cancelación no ejecutan llamadas parciales.
- Se reutiliza ProviderPolicy para límites RPM, concurrencia, cola acotada, reintentos transitorios y circuito. El proveedor se identifica correctamente en errores y estado público.
- Reportes usa el flujo de herramientas con cualquier proveedor nativo; Gemini no cae en el modo de comentarios legado.
- La pantalla Conexión IA muestra proveedor, proyecto y modelo. El formulario NVIDIA no puede cambiar accidentalmente el proveedor Gemini activo.

## Comprobación

Pruebas reales mínimas con datos de conectividad: autenticación, function call y respuesta de herramienta en segundo turno, más aceptación del esquema real de creación/edición de tickets. No se ejecutó un informe ni se envió información de clientes. Pruebas unitarias: selección, serialización de firmas entre checkpoints, filtrado de pensamiento, errores, streaming incompleto, cancelación y liberación de slots, aislamiento de preferencias de proveedor.

Referencias: https://docs.cloud.google.com/docs/authentication/api-keys y https://googleapis.github.io/python-genai/ .

## Selector de proveedor sin reinicio

En **Conexión IA**, selecciona NVIDIA o Gemini y pulsa **Usar proveedor**. Cambiar la selección del formulario no cambia el motor hasta guardar. La interfaz recupera el modelo, proyecto y configuración propios de cada proveedor, y nunca recupera sus claves. Una clave vacía conserva la existente.

La selección activa y preferencias Gemini se guardan sin secretos en `.runtime/provider.json`. NVIDIA conserva sus preferencias en `.runtime/nvidia.json` y su clave en el llavero. La clave Gemini inicial permanece en `.env`; claves nuevas introducidas desde la interfaz pueden guardarse en el llavero o solo en memoria. La selección runtime tiene prioridad sobre el proveedor de `.env` y se conserva en el siguiente arranque.

`GET /runtime/providers` expone únicamente perfiles públicos; `PUT /runtime/provider` acepta provider, model, fallback_model (NVIDIA), project/location (Gemini) y credencial opcional. Se aplican las mismas restricciones de origen local y límites de configuración. Los jobs activos bloquean el cambio con HTTP 409; nunca se cambia el motor a mitad de un análisis. Las instancias del proveedor se reutilizan para conservar sus limitadores y circuito.

Los checkpoints conservan el contenido nativo de Gemini; NVIDIA recibe solo mensajes estándar, sin metadata Gemini. Para historial importado sin firmas se usa el marcador documentado por Google exclusivamente en llamadas históricas de otro motor: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/thought-signatures .

La pantalla sustituye el formulario dedicado a NVIDIA y la vista Gemini de solo lectura descritos antes: ambos proveedores se administran desde el mismo selector y no requieren reiniciar para cambiar de motor/modelo.
