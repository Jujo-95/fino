# Consultor FinOps con Agents 2.0 — implementación y pruebas

Fecha: 22 de octubre de 2026.
Spec de referencia: SPEC-CONSULTOR-FINOPS-AGENTS-2.md.
Estado: seis fases implementadas en el piloto local; pruebas de proveedor sustituidas por dobles identificados.

## Qué cambió

El dashboard y Tickets comparten diagnóstico, requisitos y agenda. Cliente y datos conserva configuración/importación.
El acceso «Hablar con mi consultor» selecciona explícitamente el orquestador 2.0 y prepara un borrador; no envía mensajes ni consume tokens.
La antigua guía de siete booleanos y su CSS se retiraron. El endpoint onboarding conserva compatibilidad y devuelve el diagnóstico real.

## Entregables por fase

| Fase | Implementación verificable |
|---|---|
| 1. Diagnóstico | Fechas, cuentas esperadas, cadencia/latencia confirmadas, huecos, cobertura ponderada por coste, estado por capacidad y preflight de casos FOCUS. |
| 2. Onboarding | Siguiente requisito inline en dashboard/tablero, propuesta legible y confirmación; la misma confirmación está disponible en el chat. |
| 3. Agents 2.0 | Herramientas de diagnóstico, contexto, agenda, evidencia complementaria, evaluación analítica y resultados; contexto confirmado incorporado en cada turno. |
| 4. Tickets | Planes con pasos, responsable, riesgo, dependencias y criterio de cierre; validación de ciclos, existencia y revisión; nuevos tickets 2.0 requieren pasos y criterio. |
| 5. Agenda | Una lista determinista compartida; hasta tres prioridades, bloqueos y justificación; los datos/contexto/tickets actualizados invalidan el diagnóstico. |
| 6. Verificación | Declaración externa de cambio, baseline capturado, ventana posterior, observación conservadora y seguimiento en informes nuevos 2.0. |

## Cómo probarlo en la app

1. Refresca http://127.0.0.1:8000 y abre Resumen.
2. Observa «Tu siguiente paso», los costes disponibles y las prioridades existentes.
3. Pulsa Completar información. Responde un requisito y pulsa Revisar respuesta.
4. Comprueba que los datos todavía no estén aplicados. Confirma únicamente cuando sean correctos.
5. Refresca o vuelve a entrar: la respuesta confirmada se conserva y el requisito siguiente cambia.
6. Pulsa Resolver en el chat: verifica Equipo 2.0 y el borrador contextual. Enviar sí llama al proveedor.
7. Pregunta «¿Qué hago hoy?»; el agente debe consultar la agenda, no inventar otra lista.
8. En Tickets abre un hallazgo; revisa Plan de trabajo. Los tickets históricos muestran explícitamente el plan pendiente.
9. Pide al orquestador pasos y criterio de cierre para un ticket; revisa/aprueba su propuesta.
10. Después de ejecutar el cambio fuera de la app, registra IMPLEMENTED con nota y vuelve a abrir el ticket.
11. Usa Registrar seguimiento del cambio: fecha efectiva y evidencia. La app necesita datos posteriores para observar.
12. Un informe nuevo 2.0 conserva un apartado de próximas acciones, carencias y seguimiento.

No se confirmaron datos ficticios ni se modificaron decisiones de los clientes reales durante la QA.
La navegación prepara borradores en el navegador; las pruebas de mutaciones usaron workspaces temporales.

## Contratos y persistencia

DuckDB incorpora consulting_records(kind,id,document) mediante CREATE TABLE IF NOT EXISTS.
Reutiliza la separación física por cliente; todas las claves y consultas resuelven el cliente en backend.
Tipos de registros: contexto vigente/histórico, propuestas, recibos, evaluaciones, conclusiones de especialistas, verificaciones e importaciones complementarias.
Las mutaciones son transaccionales; contexto confirmado se proyecta además a context_documents.
Una propuesta requiere expected_revision y no aplica sus valores. Confirmar usa command_id idempotente y actor local.
Una revisión obsoleta no sustituye datos vigentes; rechazar una propuesta obsoleta sigue siendo posible.
Los presupuestos históricos siguen sin confirmar; el dashboard no los compara como aprobados.
Al confirmar un presupuesto, el overview utiliza el valor confirmado sin reescribir informes históricos.
El backend conserva documentos originales e informes previos. Los tickets antiguos se validan con valores nuevos opcionales.
Los nuevos campos viajan en el JSON del ledger y las exportaciones Markdown existentes.
Cambiar de cliente descarta respuestas frontend anteriores para evitar mezclar vistas por una carrera de solicitudes.

## API

Base: /api/v1/clients/{client_id}/consulting

| Método / ruta | Uso |
|---|---|
| GET / | Diagnóstico, agenda y verificaciones con revisión, fecha de evaluación y fecha de datos. |
| POST /context/proposals | Crear propuesta tipada con values, expected_revision y reason. |
| GET /context/proposals/{id} | Consultar el estado durable de una propuesta. |
| POST /context/proposals/{id}/decision | Confirmar/descartar con decision y command_id. |
| POST /tickets/{id}/implementation | Registrar evidencia/fecha/ventanas y revisión de un ticket IMPLEMENTED. |
| GET /verifications | Observar ventanas, conservar baseline y explicar limitaciones. |
| POST /supporting-data | Importación manual tipada de utilización/contratos, sin credenciales cloud. |
| GET /supporting-data | Evidencia complementaria del mismo cliente con procedencia y límite de resultados. |

OpenAPI mantiene los modelos Pydantic de solicitudes y respuesta principal; errores de contrato son 422 y conflictos de revisión 409.

## Herramientas de Agents 2.0

read_diagnosis, read_confirmed_context, read_action_plan, read_supporting_data y read_action_verification.
propose_context_changes prepara un cambio confirmado por la tarjeta del chat; no existe herramienta de autoaprobación.
record_capability_assessment conserva una conclusión con consultas reales, no truncadas, del cliente y turno.
NO_ISSUES_DETECTED se rechaza con carencias/tickets pendientes o frescura desconocida; se limita al período consultado.
Las conclusiones caducan al cambiar datos/contexto y al pasar al día siguiente.
Las delegaciones internas reciben herramientas analíticas; no pueden proponer cambios al contexto del usuario.
plan_ticket_changes y su autorización existente siguen siendo el único camino del agente para crear/modificar tickets.
Los prompts fuente importados se preservan; consulting.md amplía su contrato de ejecución.
La disponibilidad de herramientas no garantiza interpretación perfecta del modelo: las pruebas vivas de calidad conversacional siguen a cargo del piloto.

## Evidencia complementaria mínima

Se admite un JSON con source, evidence_reference y listas utilization/commitments.
Utilización: account, resource_id, day (YYYY-MM-DD), cpu_pct y memory_pct.
Compromisos: account, commitment_id, starts_at, expires_at y committed_amount_usd.
Ejemplo de utilización:
```json
{"source":"Exportación Monitoring","evidence_reference":"monitoring-octubre","utilization":[{"account":"platform","resource_id":"vm-123","day":"2026-10-06","cpu_pct":15,"memory_pct":25}]}
```
Una fila no habilita rightsizing: las observaciones deben coincidir con identidades facturadas y cubrir el histórico mínimo.
Los términos deben corresponder a IDs/cuentas facturados y estar vigentes en la fecha de datos.
Esto habilita investigación; el especialista todavía valida cobertura, demanda, riesgo y pertinencia.
Reimportar el mismo lote devuelve el recibo sin cambiar el diagnóstico.
Conectores automáticos de Monitoring/CMDB/contratos por proveedor quedan fuera de este spec.

## Criterios de interpretación

Cobertura de tags y responsables son distintas. Asignación utiliza coste positivo; créditos se excluyen y denominador cero es desconocido.
Gaps pueden ser particiones faltantes o ausencia de uso. non_billable_days permite confirmar cuenta/fecha sin inventar coste cero.
El histórico mínimo predeterminado es una política del piloto ajustable, no un requisito oficial FOCUS.
El preflight FOCUS revisa campos disponibles/referenciados; no acredita ejecución SQL exitosa ni conformidad formal.
Conciliación con facturas permanece no verificada hasta contar con evidencia y una integración específica.
La agenda prioriza urgencia, gravedad, anomalías, impacto estimado conocido y dependencias; no estima esfuerzo ni vencimientos inexistentes.
No hay puntaje global de salud ni avance de madurez automático.
Los tickets previos conservan títulos, capacidades y decisiones: la app no los reclasifica por el texto de su título.
Una dependencia IMPLEMENTED desbloquea trabajo, pero no representa ahorro validado.
La verificación compara coste diario del mismo alcance cuenta/servicio: siete días previos y tres posteriores por defecto, ajustables vía API.
Sin días completos/latencia confirmada espera; con baseline insuficiente queda no concluyente.
La diferencia se presenta como reducción observada o sin mejora; attributed_savings permanece null.
No atribuye causalidad, no prueba rendimiento ni agrega reducciones superpuestas.

## Evidencia de validación

Suite completa: 240 pruebas pasan; además se verificaron los cambios finales de propuestas/tickets con 30 pruebas focalizadas.
Incluye flujo LangGraph con doble, DuckDB real, propuesta sin aplicar, confirmación, persistencia, idempotencia, aislamiento, gaps, presupuesto heredado, ciclos, ventanas tardías y caducidad.
Ruff de source y nuevos tests: correcto. Mypy de 125 módulos: correcto. Build TypeScript/Vite: correcto.
Permanece el aviso previo de bundle mayor a 500 kB; no bloquea el build.
QA visual: dashboard escritorio/móvil, formulario inline, acceso explícito al orquestador 2.0 con borrador, tablero compacto y modal de ticket.
No se enviaron preguntas al LLM durante la QA ni se compraron/cambiaron recursos cloud.
