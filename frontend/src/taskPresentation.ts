import type {Ticket} from './types';
import {taskState} from './ticketLifecycle';
export const topics:Record<string,string>={'data-ingestion':'Datos','allocation':'Responsables','anomaly-management':'Anomalías','forecasting':'Proyecciones','budgeting':'Presupuesto','usage-optimization':'Recursos','rate-optimization':'Compromisos','reporting-analytics':'Reportes'};
export function taskPhase(t:Ticket){return taskState(t)==='monitoring'||t.ticket_kind==='verification'?'Operar':['usage-optimization','rate-optimization'].includes(t.capability)?'Optimizar':'Informar'}
export function taskTopic(t:Ticket){return t.ticket_kind==='verification'?'Resultados':topics[t.capability]||'Datos'}
export function taskType(t:Ticket){return taskState(t)==='monitoring'?'Revisar seguimiento':t.ticket_kind==='onboarding'?'Completar información':t.ticket_kind==='analysis'?'Revisar':t.ticket_kind==='verification'?'Verificar resultado':'Resolver hallazgo'}
