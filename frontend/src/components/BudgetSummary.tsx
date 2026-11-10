import {ArrowRight,AlertCircle,Check} from 'lucide-react';
import {Disclosure} from './Disclosure';
import {money,type Overview,type Ticket} from '../types';
import {ticketTitle,severityLabels,capabilityLabels} from '../presentation';
import {isActiveTask} from '../ticketLifecycle';

export function BudgetSummary({overview:o,onIndicators}:{overview:Overview;onIndicators:()=>void}){
  if((o as Overview&{budget_confirmed?:boolean}).budget_confirmed===false)return <section className="panel budget-panel"><h2>Presupuesto por confirmar</h2><p className="panel-copy">Todavía no tenemos un presupuesto aprobado. Confírmalo con tu consultor para evaluar desviaciones.</p></section>;
  const spent=o.actual/o.budget*100;const remaining=o.budget-o.actual;const over=o.forecast-o.budget;
  return <section className="panel budget-panel"><h2>Presupuesto</h2><div className="budget-amount"><strong>{money(o.budget)}</strong><span>mensuales</span></div><div className="budget-progress" role="progressbar" aria-label="Presupuesto consumido" aria-valuenow={Math.round(spent)} aria-valuemin={0} aria-valuemax={Math.max(100,Math.round(spent))}><span style={{width:Math.min(100,spent)+'%'}}/><i style={{left:100-o.profile.budget_policy.holdback_pct+'%'}}/></div><div className="budget-progress-label"><strong>{spent.toFixed(1)}% consumido</strong><span>{o.profile.budget_policy.holdback_pct}% de reserva</span></div><Disclosure title="Detalle del presupuesto"><dl className="budget-details"><div><dt>Gasto actual</dt><dd>{money(o.actual)}</dd></div><div><dt>{remaining>=0?'Disponible':'Exceso actual'}</dt><dd>{money(Math.abs(remaining))}</dd></div><div><dt>Proyección de cierre</dt><dd>{money(o.forecast)}</dd></div></dl></Disclosure><div className={'budget-assessment '+(over>0?'at-risk':'within-budget')}>{over>0?<AlertCircle size={17}/>:<Check size={17}/>}<p>{over>0?<><strong>{money(over)} por encima</strong> del presupuesto al cierre del mes.</>:<>La proyección está dentro del presupuesto configurado.</>}</p></div><button className="text-button" onClick={onIndicators}>Ver indicadores <ArrowRight size={15}/></button></section>;
}

export function AllocationSummary({overview:o,onIndicators}:{overview:Overview;onIndicators:()=>void}){
  const metric=o.metrics.find(m=>m.key==='unallocated_cost_pct');const value=metric?.value;
  return <section className="panel allocation-panel"><div className="row"><h2>Asignación de costos</h2><span className="badge">{o.profile.allocation_policy.mode}</span></div><strong>{value===null||value===undefined?'Sin datos':value.toFixed(1)+'%'}<small>sin asignar</small></strong><p>Recursos que no cumplen la política de etiquetas del cliente.</p><button className="text-button" onClick={onIndicators}>Revisar asignación <ArrowRight size={15}/></button></section>;
}

export function PendingFindings({tickets,onTickets}:{tickets:Ticket[];onTickets:()=>void}){
  const pending=tickets.filter(isActiveTask);
  return <section className="panel pending-panel"><div className="panel-heading"><div><h2>Requieren revisión <span className="inline-count">{pending.length}</span></h2></div><button className="text-button" onClick={onTickets}>Ver tickets <ArrowRight size={15}/></button></div><div className="pending-list">{[...pending].sort((a,b)=>(({CRITICAL:0,HIGH:1,MEDIUM:2,LOW:3} as Record<string,number>)[a.severity]??4)-(({CRITICAL:0,HIGH:1,MEDIUM:2,LOW:3} as Record<string,number>)[b.severity]??4)).slice(0,3).map(ticket=><button key={ticket.ticket_id} className="pending-finding" onClick={onTickets}><div className="finding-context"><span>{ticket.ticket_id}</span><span className={ticket.severity==='HIGH'||ticket.severity==='CRITICAL'?'severity-high':''}>Prioridad {severityLabels[ticket.severity]?.toLowerCase()||ticket.severity}</span></div><h3>{ticketTitle(ticket)}</h3><span className="finding-capability">{capabilityLabels[ticket.capability]||ticket.capability}<ArrowRight size={15}/></span></button>)}{!pending.length&&<p className="panel-copy">No hay hallazgos pendientes. Puedes consultar las decisiones en Tickets.</p>}</div></section>;
}
