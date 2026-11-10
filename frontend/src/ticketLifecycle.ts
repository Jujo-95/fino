import type {Ticket} from './types';

export type TaskState='todo'|'monitoring'|'resolved'|'dismissed';
export const taskStateLabels:Record<TaskState,string>={todo:'Por hacer',monitoring:'En seguimiento',resolved:'Resuelto',dismissed:'Descartado'};
type StateInput={status:string;ticket_kind?:string;snoozed_until?:string|null};
export function taskState(t:StateInput):TaskState{
  if(t.status==='RESOLVED')return 'resolved';
  if(t.status==='FALSE_POSITIVE')return 'dismissed';
  if(t.status==='MONITORING')return 'monitoring';
  if(t.status==='IMPLEMENTED')return t.ticket_kind&&t.ticket_kind!=='finding'?'resolved':'monitoring';
  return 'todo';
}
export function taskStateLabel(t:StateInput){return taskStateLabels[taskState(t)]}
export function isDeferred(t:StateInput,today=new Date().toLocaleDateString('en-CA')){
  return t.status==='SNOOZED'&&(!t.snoozed_until||t.snoozed_until>today);
}
export function isActiveTask(t:StateInput){return !isDeferred(t)&&['todo','monitoring'].includes(taskState(t))}
export function taskCounts(tickets:Ticket[]){
  return Object.fromEntries((Object.keys(taskStateLabels) as TaskState[]).map(state=>[state,tickets.filter(t=>!isDeferred(t)&&taskState(t)===state).length])) as Record<TaskState,number>;
}
export const ticketActions=[['PROPOSED','Volver a por hacer'],['IMPLEMENTED','Registrar acción realizada'],['MONITORING','Esperar datos y revisar'],['RESOLVED','Cerrar con resultado verificado'],['FALSE_POSITIVE','Descartar hallazgo incorrecto'],['SNOOZED','Recordar más adelante']];
