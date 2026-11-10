import type {Ticket} from './types';
import type {ActionDetails} from './consultingTypes';
import {taskState} from './ticketLifecycle';
export function taskNextStep(ticket:Ticket){
  if(taskState(ticket)==='resolved')return ticket.resolution_note||'Resultado comprobado. Puedes consultar la evidencia del cierre.';
  if(taskState(ticket)==='dismissed')return ticket.resolution_note||'Hallazgo descartado; consulta el motivo en la tarea.';
  if(ticket.status==='IMPLEMENTED'&&(!ticket.ticket_kind||ticket.ticket_kind==='finding'))return 'Comprobar el resultado con datos posteriores; la acción ya está registrada.';
  if(ticket.status==='MONITORING')return 'Revisar la ventana de datos y el criterio acordado con Fino.';
  const details=(ticket as Ticket&{action_details?:ActionDetails}).action_details;
  return details?.steps?.[0]||ticket.recommended_action;
}
export function missingInputHelp(ticket:Ticket){
  if(ticket.ticket_kind!=='onboarding')return '';
  const sources:Record<string,string>={
    owners:'Comparte una lista de equipos y responsables, un organigrama o la matriz de cuentas. Si no la tienes, Fino te ayuda a pedirla al área de tecnología.',
    expected_accounts:'Comparte la lista de cuentas o proyectos de la consola de tu nube, o pídela a quien administra la facturación.',
    monthly_budget:'Comparte el presupuesto del período aprobado por finanzas. Si no existe, Fino te ayuda a preparar la pregunta para tu responsable financiero.',
    cadence:'Pregunta a quien configuró la conexión cada cuánto llegan los datos y con cuántos días de retraso.',
    invoice:'Comparte el total y período de la factura de la nube o pídeselos al equipo de finanzas.',
    utilization:'Pide al equipo técnico las métricas de uso del recurso antes de cambiar su capacidad.',
    contracts:'Comparte las condiciones de los compromisos o contratos vigentes, disponibles en compras o facturación.'
  };
  return sources[ticket.workflow_key?.replace('requirement:','')||'']||'Comparte el dato en el chat. Si no sabes dónde obtenerlo, Fino te ayuda a identificar la fuente y preparar la pregunta para tu equipo.';
}
