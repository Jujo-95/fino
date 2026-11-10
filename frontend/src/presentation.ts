import type {Overview,Ticket} from './types';
const monthFormatter=new Intl.DateTimeFormat('es',{month:'long',timeZone:'UTC'});
export function periodLabel(o:Overview):string{
  const start=new Date(o.period_start_utc.slice(0,10)+'T00:00:00Z');
  const end=new Date(o.period_end_utc.slice(0,10)+'T00:00:00Z');end.setUTCDate(end.getUTCDate()-1);
  return `${start.getUTCDate()}–${end.getUTCDate()} de ${monthFormatter.format(start)} de ${start.getUTCFullYear()}`;
}
export function shortDate(day:string):string{
  return new Intl.DateTimeFormat('es',{day:'numeric',month:'short',timeZone:'UTC'}).format(new Date(day+'T00:00:00Z'));
}
export const capabilityLabels:Record<string,string>={'allocation':'Asignación','anomaly-management':'Anomalías','forecasting':'Proyecciones','budgeting':'Presupuesto','rate-optimization':'Compromisos'};
export const metricLabels:Record<string,string>={unallocated_cost_pct:'Costos sin asignar',allocation_accuracy_index:'Precisión de asignación',shared_cost_apportionment:'Reparto de costos compartidos',anomaly_unpredicted_variance:'Gasto no previsto',anomaly_cost_avoidance:'Costo potencialmente evitable',genai_anomaly_detection_rate:'Anomalías en consumo de IA',forecast_accuracy_usage:'Error de proyección de uso',forecast_drift_rate:'Desviación de la proyección',budget_burn_rate:'Consumo diario del presupuesto',budget_vs_forecast_variance:'Variación frente al presupuesto',commitment_utilization_score:'Utilización de compromisos',commitment_discount_waste_pct:'Compromisos sin utilizar',effective_savings_rate:'Tasa de ahorro efectiva'};
export function ticketTitle(t:Pick<Ticket,'title'|'service_name'>):string{
  if(t.title==='Close the cloud ownership gap')return 'Asignar responsable a los costos sin etiquetar';
  if(t.title.startsWith('Unexpected cost spike'))return `Revisar el pico de consumo en ${t.service_name}`;
  if(t.title==='Forecast is approaching the budget guardrail')return 'Revisar la proyección frente al presupuesto';
  if(t.title==='Review stable on-demand coverage')return 'Evaluar compromisos para el consumo estable';
  if(t.title==='Recover unused commitment value')return 'Reasignar los compromisos sin utilizar';
  if(t.title==='Review forecast drift')return 'Revisar los cambios en la proyección';
  return t.title;
}
export const severityLabels:Record<string,string>={LOW:'Baja',MEDIUM:'Media',HIGH:'Alta',CRITICAL:'Crítica'};
