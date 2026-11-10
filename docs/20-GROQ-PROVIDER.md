# Groq como tercer proveedor

Groq, el servicio de inferencia de groq.com, se integra junto con NVIDIA y Gemini en Conexión IA. No es xAI Grok. Se usa el SDK oficial groq, el endpoint https://api.groq.com/openai/v1 y la variable GROQ_API_KEY.

## Uso

1. Selecciona Groq en Conexión IA.
2. Ingresa tu API key de Groq. Puedes conservarla en el llavero de macOS o solo durante la sesión del backend; nunca se devuelve al navegador.
3. Elige el modelo y pulsa Usar Groq. El campo vacío de clave conserva la que ya guardaste.
4. Probar conexión comprueba una herramienta mínima usando el proveedor activo. La aplicación no activa Groq sin una clave en el formulario; Gemini/NVIDIA conservan sus perfiles y claves.

El modelo inicial es openai/gpt-oss-20b. Se sugieren también openai/gpt-oss-120b y qwen/qwen3.8-27b. Las referencias oficiales consultadas el 2026-10-21 indican que estos modelos admiten herramientas y figuran en los límites del plan gratuito. La gratuidad y cuotas efectivas dependen del plan/cuenta de Groq; un modelo no implica una garantía de consumo ilimitado ni que una cuenta de pago no genere cargos. No se modifican planes ni se habilitan herramientas remotas facturables.

Referencias: https://console.groq.com/docs/tool-use/overview y https://console.groq.com/docs/rate-limits .

## Contrato y límites

- Mismas herramientas locales de consultas, informes, historial y propuestas de tickets, con autorizaciones en el backend. No se trasladan a Groq funciones de ejecución de nuestra app.
- El SDK devuelve streaming OpenAI compatible; se reutiliza el ensamblador existente. Solo se ejecutan herramientas completas y se excluyen razonamiento privado y metadata nativa Gemini.
- Tool calling secuencial para compatibilidad con GPT OSS; sin herramientas built-in ni fallback a otros proveedores. Parámetros de NVIDIA no se envían a Groq.
- ProviderPolicy conserva límites, cola, cancelación, circuito y reintentos transitorios. Los reintentos internos del SDK están deshabilitados para no multiplicarlos.
- Groq HTTP 429 respeta Retry-After. Errores de autenticación/modelo/contexto no se reintentan indiscriminadamente ni muestran secretos. Un contexto demasiado grande para la cuota gratuita puede requerir una consulta más acotada.
- GROQ_MODEL controla el modelo inicial si no hay preferencias runtime; GROQ_MAX_TOKENS controla el máximo de salida (4096 por defecto).
- La selección y modelo sin secretos persisten en .runtime/provider.json. La clave puede leerse de .env/GROQ_API_KEY o del llavero; las credenciales de cada proveedor están separadas.

## Verificación

Pruebas con SDK oficial y transporte simulado: payload de herramientas, streaming, ensamblado de argumentos, exclusión de razonamiento privado, errores/cuotas, keychain/session-only, persistencia y convivencia con otros perfiles. No se hizo una llamada real a Groq al no disponer todavía de la clave del usuario.
