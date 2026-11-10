# NVIDIA en runtime y recuperación de informes

## Diagnóstico verificado

El 21 de octubre de 2026, las ejecuciones interrumpidas fallaban en Asignación por
read_timeout. Con la misma clave, una prueba mínima de native tool calling obtuvo
HTTP 200 en Nemotron en 0,7 s, mientras GLM no respondió en 35 s. No era un error de
DuckDB ni una prueba de credenciales inválidas. Se configuró Nemotron como principal;
el modelo y el respaldo son editables desde Conexión IA.

## Credenciales

La clave se guarda mediante keyring en el Keychain nativo de macOS, servicio
FinOps Agent App · NVIDIA. La clave actual fue guardada y recuperada para verificar
la migración; después se retiró NVIDIA_API_KEY del .env. No hay copias nuevas en
archivos de configuración ni en localStorage/sessionStorage. El campo del navegador
se limpia tras guardar y la API solo devuelve estado y fuente, nunca la clave.
Los errores de validación no incluyen el cuerpo de la petición.

PUT /api/v1/runtime/provider aplica clave/modelo/timeout a la instancia compartida,
sin reiniciar el servidor ni las conversaciones. Los metadatos no secretos viven en
.runtime/nvidia.json. El modo solo sesión guarda la clave únicamente en memoria.
Las escrituras requieren host local, origen coincidente y encabezado X-Finops-Config;
las peticiones cross-site se rechazan. La comprobación del proveedor tiene cuota
propia, además de los límites globales de concurrencia y solicitudes existentes.

## Generación de informes

Los agentes de informes usan recepción SSE de NVIDIA aunque su entrega final sea
atómica: se evita esperar todo el cuerpo sin recibir actividad. El límite de lectura
configurado es 90 segundos de inactividad; cada ciclo de análisis tiene un máximo
de 600 segundos. Las respuestas parciales de herramientas nunca se ejecutan.
Recibir cabeceras HTTP no cuenta como haber publicado texto: un timeout antes de
texto visible puede reintentarse o usar respaldo. Los borradores internos de un
informe son reintentables; una respuesta parcial ya visible del chat no se repite.

Reportes separa historial, documento, progreso y recuperación. Conserva los fallos
históricos; Reintentar informe crea una ejecución nueva con la conexión actual.
La selección del historial ya no queda forzada al informe en curso. Se muestran
las fechas de cobertura de los datos y las horas en America/Bogota. Los informes
renderizan tablas Markdown y las exportaciones quedan en un detalle plegable.
El fondo del chat coincide con el navbar: rgb(241,243,246).

## Verificación y límite

171 pruebas pasaron, incluidas rotación de clave sin reinicio, almacenamiento sin
plaintext, origen de escritura, errores sin secretos, streaming, reintentos y el
pipeline de informes con dobles. Build TypeScript/Vite, Ruff y mypy correctos.
La prueba real de conexión desde la UI confirmó native tool calling en Nemotron.
No se ejecutó un informe real completo tras la corrección. La revisión automática
rechazó una prueba acotada de Asignación por consumo de cuota y la instrucción previa
del usuario de limitar ejecuciones; requiere aprobación explícita antes de realizarla.
