# Propuestas nativas y confirmación de informes repetidos

Agents 2.0 reutiliza TicketOperations, las interrupciones de LangGraph y la aplicación atómica del tablero. No existe un segundo sistema de tickets en archivos JSON. El JSON del informe se conserva como evidencia de la entrega; las acciones se convierten en propuestas pendientes.

## Contrato operativo

- `plan_ticket_changes`: crear con `action=create` y `finding` completo; actualizar campos con `fields`; transicionar con `target_status`; añadir notas con `append_note`.
- Para editar se exige un FIN real leído del cliente activo y su `expected_revision`. Para crear o cambiar campos se exige evidencia consultada en la conversación.
- `save_report` conserva Markdown y JSON del informe y adapta `tickets.proposedActions` al mismo sistema de propuestas. `propose_report_tickets(run_id)` permite hacerlo con un informe ya guardado.
- Si la propuesta de origen usa identificadores HTS o carece de métricas/evidencia, devuelve `needs_details`. El agente debe completar con consultas del cliente y proponer mediante la herramienta nativa. El guardado del informe sigue siendo exitoso; no debe reintentarlo por una propuesta incompleta.
- El usuario revisa el lote antes de aplicarlo. El backend asigna FIN IDs, valida duplicados/revisiones y confirma todo o revierte todo. Una orden textual de transición no autoriza crear ni modificar campos adicionalmente.
- Las contribuciones y el `report_run_id` quedan en la propuesta y el recibo. La API de detalle del informe expone `ticket_ids` aplicados. La aplicación devuelve los tickets reales al contexto del chat y actualiza el tablero.

## Repetición de informes

Si ya existe un informe completado hoy, para el mismo cliente y periodo, el backend exige confirmar: «Ya existe un reporte para el periodo actual, ¿desea crear uno nuevamente?».

“Hoy” usa America/Bogota. Se compara el periodo por instantes normalizados y se consulta el historial completo. Otra fecha, otro periodo u otro cliente no activa la pregunta. Un job ya activo se reutiliza.

- Reportes: HTTP 409 con `code=report_exists`, ID del informe existente y confirmación vinculada al cliente, periodo, día e informes existentes. El frontend muestra Conservar existente / Crear nuevamente. Solo el segundo reenvía la solicitud confirmada.
- Chat: interrupción persistida de LangGraph antes de registrar el job. La decisión queda vinculada al turno, conversación y mensaje del usuario. La herramienta del modelo no acepta un booleano de aprobación.
- `force_reanalysis` no sustituye el consentimiento. Si apareció otro informe mientras se confirmaba, la confirmación anterior no permite repetirlo silenciosamente.
- Cancelar conserva el informe anterior y no inicia otro análisis. Confirmar conserva el anterior y permite iniciar otro job, sujeto a límites existentes e idempotencia incremental.

## Validación

Pruebas con modelos simulados: guardado → propuesta → aprobación → FIN real; lotes mixtos; duplicados concurrentes; rollback de archivos/DB; confirmación de chat aprobar/rechazar; HTTP 409 antes de abrir SSE; aislamiento y protección de versiones. Build TypeScript/Vite, ruff y mypy. Prueba visual aislada del modal sin NVIDIA.
