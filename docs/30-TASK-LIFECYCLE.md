# Ciclo visible de tareas

Implementa `outputs/spec-ciclo-tareas-fino.md` del workspace. Los datos históricos conservan
sus estados internos; no se reescriben ni se borran tickets.

| Estado interno | Estado del usuario |
|---|---|
| PROPOSED, APPROVED, REJECTED | Por hacer |
| MONITORING, IMPLEMENTED de un hallazgo | En seguimiento |
| RESOLVED, IMPLEMENTED de una tarea de información/diagnóstico verificada | Resuelto |
| FALSE_POSITIVE | Descartado |
| SNOOZED | Por hacer; oculto hasta `snoozed_until` o incluido mediante filtro de recordatorios |

Un `REJECTED` histórico no demuestra que el hallazgo era falso. Su decisión permanece
en las notas. Cancelar una acción propuesta solo modifica la propuesta; el ticket queda intacto.
Un recordatorio histórico sin fecha se mantiene recuperable con el filtro correspondiente.

La presentación se centraliza en `frontend/src/ticketLifecycle.ts` y su proyección del backend
en `consulting/ticket_lifecycle.py`. Los filtros aceptan etiquetas visibles y conservan los
valores internos de la API. Las revisiones e idempotencia del motor de tickets se mantienen.

La acción registrada no exige pasar primero por APPROVED. Un hallazgo IMPLEMENTED sigue
en evaluación; solo se puede cerrar después de comprobar su plan. El rechazo de una acción
o un evento puntual/planeado no constituye un falso positivo. Las tareas explican qué se
observó, qué falta confirmar y cuál es el siguiente paso. Fino propone fuentes concretas
para obtener lo que falta, en lugar de preguntar si la tarea merece atención.

Validación sin navegador:

```sh
backend/.venv/bin/pytest backend/tests/test_task_lifecycle.py backend/tests/test_transition_contract.py backend/tests/test_ticket_followup.py -q
cd frontend
node --test tests/ticketLifecycle.test.mjs
npm run build
```
