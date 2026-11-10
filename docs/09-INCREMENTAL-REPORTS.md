# Fase nueva — Informes incrementales y seguimiento de hallazgos

Estado: implementada y verificada con pruebas locales. No se ha ejecutado NVIDIA para validar esta fase; esa ejecución la inicia el usuario.
Capability: Reporting & Analytics — https://www.finops.org/framework/capabilities/reporting-analytics/

## Resultado esperado
Cada informe responde «¿qué cambió desde el análisis anterior y qué decisión requiere?».
No vuelve a presentar como descubrimientos los hallazgos conocidos. Los problemas persistentes siguen visibles en el tablero y en el seguimiento; no desaparecen por ser antiguos.

## Implementación disponible
El grafo comprueba las firmas antes de ejecutar especialistas. Selecciona automáticamente el último informe completado del cliente/moneda, conserva su referencia y entrega a cada especialidad su contribución anterior y los tickets correspondientes. Las comprobaciones idénticas se auditan sin crear otro archivo de informe ni llamar al modelo.

Las firmas incluyen filas FOCUS efectivas del período (también correcciones de un CSV con el mismo nombre), perfil, contexto, identidad/estado/notas de tickets, código/guías/prompts utilizados y configuración del proveedor. Los tickets nuevos del propio informe se incorporan a la firma final; las decisiones humanas concurrentes siguen invalidando la reutilización. Las ejecuciones fallidas no se usan como línea base.

Cada informe nuevo tiene un archivo por ejecución y su copia durable en la auditoría. `incremental` almacena observaciones, cambios, comparación temporal, materialidad y `ticket_review`; las comprobaciones sin cambios apuntan al informe vigente. El historial de reportes lista únicamente informes completados, sin duplicar las comprobaciones reutilizadas.

Los tickets conservan su identidad entre meses, incluso si cambia el período de observación. Las decisiones implementadas, descartadas, pospuestas o clasificadas como falsos positivos se conservan. No se reabren automáticamente. Los candidatos a obsolescencia se marcan solo cuando una condición conocida puede comprobarse con scripts (ciertos indicadores en cero, mismo período y al menos cuatro días observados); esto no demuestra por sí solo una implementación ni autoriza una transición.

`ClientProfile.incremental_policy` configura umbrales por métrica y valores por defecto: cambio absoluto mínimo de 1 en la unidad del indicador y relativo de 5%, ambos necesarios; cambios de severidad/disponibilidad también cuentan. Las diferencias de redacción no constituyen novedades. Si cambió el período, se informa la cobertura y no se presenta una variación acumulada como comparación equivalente.

`RunRequest.force_reanalysis=true` exige `force_reason`; una revisión explícita del informe también evita reutilizar silenciosamente su respuesta. El chat se describe en la fase 10 y no se ha implementado aquí.

Límite de migración: los informes anteriores a esta implementación no tienen firma. La primera ejecución que el usuario inicie con esta versión establece la nueva línea base; después se podrá reutilizar si sus entradas no cambian. El piloto mantiene CSV locales y trabajos en un único backend. No se afirma recuperación de un informe a mitad de ejecución tras reiniciar el proceso.

## 1. Línea base y memoria de ejecución
Seleccionar automáticamente la última ejecución completada del mismo cliente y moneda. Guardar su identificador como referencia del nuevo análisis. Nunca usar ejecuciones fallidas o incompletas como línea base. Si cambió el período, indicar la comparabilidad y los días nuevos; no comparar totales de períodos diferentes como si fueran equivalentes.

Entregar a cada especialista un contexto acotado: conclusiones anteriores de su especialidad, evidencia referenciada, tickets existentes, estados, notas de resolución y cambios posteriores. El orquestador recibe el resumen anterior y las diferencias consolidadas. Toda referencia conserva el identificador de la ejecución y sus fuentes.

## 2. Detección de cambios antes de llamar al modelo
Calcular una firma determinista de datos relevantes al período, políticas, contexto, decisiones humanas, versión de scripts y versión de prompts/modelo. Detectar filas nuevas y correcciones tardías aunque el nombre del CSV sea idéntico. Las instrucciones nuevas del usuario también invalidan la reutilización.

Si la firma es idéntica, devolver «Sin cambios desde el último informe», enlazar el informe existente y registrar la comprobación. No crear otro informe sustantivo, otros tickets ni consumir tokens. Un reanálisis forzado debe ser una acción explícita y conservar su motivo.

## 3. Hallazgos y tickets con continuidad
Clasificar las diferencias como: nuevo, actualizado, persistente sin cambios o resuelto con evidencia. Usar una identidad estable del problema separada del período de observación y de las revisiones del ticket. Un mes nuevo no debe duplicar automáticamente un problema pendiente del mes anterior.

Actualizar evidencia e impacto del ticket existente cuando haya cambios materiales. Conservar decisiones humanas, responsables y aportes de los agentes. No reabrir un falso positivo o una implementación sin evidencia nueva y motivo explícito. La ausencia de un hallazgo en la respuesta del modelo no demuestra resolución.

Los umbrales de materialidad deben ser configurables por métrica y cliente; los cambios de redacción no constituyen novedades. Un riesgo conocido sin cambios sigue disponible como seguimiento, sin inflar el número de descubrimientos.

## 4. Informe de novedades y persistencia
Mostrar primero las novedades y decisiones necesarias, después los cambios de impacto/pronóstico y por último el seguimiento de problemas abiertos. Enlazar el detalle previo en lugar de repetirlo. Si cambian los datos pero no existen novedades accionables, registrar «Datos actualizados; sin nuevas acciones» con la evidencia pertinente.

Persistir cada versión inmutable, su referencia anterior, las firmas de entrada, la clasificación de cambios y los vínculos a tickets/contribuyentes. La comparación y publicación deben quedar serializadas por cliente y ser idempotentes ante reintentos. Un fallo no debe convertir un informe parcial en la nueva línea base.

## Criterios de aceptación
- Primera ejecución: informe inicial y tickets con autoría registrada.
- Segunda ejecución idéntica: cero llamadas al modelo, cero tickets nuevos y enlace al informe previo.
- CSV con un costo nuevo: analizar la diferencia y actualizar el ticket relacionado o crear uno únicamente si es un problema distinto.
- Corrección tardía: revisar la evidencia aunque se conserve el nombre del archivo.
- Decisión humana nueva: incluirla en el contexto; no reiterar una recomendación ya descartada sin fundamento nuevo.
- Hallazgo persistente: mismo ticket, evidencia versionada y seguimiento sin anunciarlo como descubrimiento.
- Problema distinto, o agravamiento material: reflejar novedad y vincular sus especialistas y evidencia.
- Cambio de mes: mantener continuidad del problema y distinguir cambio de cobertura temporal de cambio real del gasto.
- Falta de datos: no declarar resuelto un problema por ausencia de evidencia.
- Reintento, concurrencia o reinicio: no duplicar informes/tickets ni perder decisiones.
- Pruebas con proveedores de prueba y contador de llamadas. La validación NVIDIA real la inicia el usuario.

Verificación: pruebas con proveedor de prueba y contador de llamadas, firmas modificadas por datos/contexto/decisiones, persistencia tras recrear el contenedor, continuidad entre meses, fallo de ejecución, materialidad y candidatos sin transiciones automáticas. Queda pendiente la ejecución NVIDIA iniciada por el usuario.
