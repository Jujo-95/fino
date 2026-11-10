import type {Overview,Ticket} from '../types';
import {money} from '../types';
import type {Consulting} from '../consultingTypes';
import {stateLabels} from '../consultingTypes';
import {AgentAvatar} from './AgentAvatar';
import {chatAgents} from '../auditTypes';


type Indicator={label:string;capability:string;agent:string;value:number|null;display:string;description:string};
function indicators(o:Overview,c?:Consulting|null):Indicator[]{
  const metric=(key:string)=>o.metrics.find(m=>m.key===key)?.value??null;
  const percent=(n:number|null)=>n===null?'Sin datos':n.toFixed(1)+'%';
  const unallocated=metric('unallocated_cost_pct');const coverage=unallocated===null?null:100-unallocated;
  const anomaly=metric('anomaly_unpredicted_variance');const drift=metric('forecast_drift_rate');
  const confirmed=c?.diagnosis.context.values.monthly_budget;const budget=typeof confirmed==='number'&&confirmed>0?o.forecast/confirmed*100:null;
  const usage=metric('commitment_utilization_score');
  return [
    {label:'Coste etiquetado',capability:'allocation',agent:'v2-allocation-policy-architect',value:coverage,display:percent(coverage),description:'Cobertura de etiquetas del período; no confirma responsables.'},
    {label:'Gasto no previsto',capability:'anomaly-management',agent:'v2-budget-anomaly-operator',value:anomaly===null||o.actual<=0?null:anomaly/o.actual*100,display:anomaly===null?'Sin datos':money(anomaly),description:'Barra: proporción del gasto del período atribuida a desviaciones no previstas.'},
    {label:'Cambio de proyección',capability:'forecasting',agent:'v2-finops-benchmarking-analyst',value:drift===null?null:Math.abs(drift),display:percent(drift),description:'Variación frente a la proyección anterior. Barra: magnitud absoluta, escala 0–100%.'},
    {label:'Presupuesto previsto',capability:'budgeting',agent:'v2-budget-anomaly-operator',value:budget,display:budget===null?'Por confirmar':percent(budget),description:'Proyección mensual / presupuesto confirmado. Por encima del 100% supera el presupuesto.'},
    {label:'Uso de compromisos',capability:'rate-optimization',agent:'v2-commitment-discount-strategist',value:usage,display:percent(usage),description:'Coste de compromisos utilizado / coste total de compromisos.'},
  ];
}
export function TicketPulse({tickets,overview,consulting,selectedCapabilities,onToggleCapability}:{tickets:Ticket[];overview?:Overview;consulting?:Consulting|null;selectedCapabilities:string[];onToggleCapability:(capability:string)=>void}){
  void tickets;
  return <section className="ticket-pulse" aria-label="Resolución de tareas e indicadores FinOps">
    {overview&&<div className="ticket-kpi-strip">{indicators(overview,consulting).map(k=>{const assessment=consulting?.diagnosis.capabilities.find(c=>c.key===k.capability);const state=k.value===null?'INSUFFICIENT_DATA':assessment?.state||'ASSESSABLE';const agent=chatAgents.find(a=>a.key===k.agent);return <button type="button" className={'ticket-kpi ticket-kpi-filter '+state.toLowerCase()} key={k.capability} aria-pressed={selectedCapabilities.includes(k.capability)} aria-controls="tasks-results" aria-label={'Filtrar tareas: '+k.label} onClick={()=>onToggleCapability(k.capability)} title={`${selectedCapabilities.includes(k.capability)?'Quitar':'Añadir'} filtro · ${k.description} ${assessment?.reason||''}`}>
      <div className="ticket-kpi-owner"><AgentAvatar agent={k.agent}/><span>{agent?.name}</span></div>
      <div className="ticket-kpi-reading"><span>{k.label}</span><strong>{k.display}</strong></div>
      <div className="ticket-kpi-bar" role="img" aria-label={`${k.label}: ${k.display}. ${k.description}`}><span style={{width:k.value===null?'0%':Math.max(0,Math.min(100,k.value))+'%'}}/></div>
      <small>{stateLabels[state]}</small>
    </button>})}</div>}
  </section>;
}
