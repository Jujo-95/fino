import {ChevronRight} from 'lucide-react';
import {TicketContributors} from './TicketContributors';
import {Disclosure} from './Disclosure';
import {money,type Metric,type Ticket} from '../types';
import {metricLabels,ticketTitle,severityLabels,capabilityLabels} from '../presentation';
export function Badge({children,tone='neutral'}:{children:React.ReactNode;tone?:string}){
  return <span className={'badge '+tone}>{children}</span>;
}
export function KpiMetricCard({metric}:{metric:Metric;mode:string;maturity:string}){
  const value=metric.value===null?'Sin datos':metric.unit.startsWith('USD')?money(metric.value):metric.value.toFixed(1)+'%';
  return <article className={'metric-card '+(metric.value===null?'unavailable':'')}><div className="metric-name"><h3>{metricLabels[metric.key]||metric.label}</h3></div><strong>{value}</strong>{metric.value!==null&&<p>{metric.unit==='USD/day'?'USD por día':metric.unit==='USD'?'USD':'Porcentaje'}</p>}<Disclosure title="Fórmula y referencia"><p>{metric.formula}</p><a href={metric.citation} target="_blank" rel="noreferrer">Referencia FinOps</a></Disclosure></article>;
}
export function TicketCard({ticket,onClick}:{ticket:Ticket;onClick:()=>void}){
  return <button className="ticket-card" onClick={onClick}><div className="row"><code>{ticket.ticket_id}</code><Badge tone={['HIGH','CRITICAL'].includes(ticket.severity)?'amber':'neutral'}>{severityLabels[ticket.severity]||ticket.severity}</Badge></div><h3>{ticketTitle(ticket)}</h3><p>{ticket.sub_account_id==='all'?'Todas las cuentas':ticket.sub_account_id}{ticket.service_name!=='all'&&` / ${ticket.service_name}`}</p><div className="ticket-impact"><span>{ticket.estimated_monthly_impact_usd!==null&&ticket.estimated_monthly_impact_usd>0?money(ticket.estimated_monthly_impact_usd)+'/mes':'Revisión de política'}</span><ChevronRight size={14}/></div><TicketContributors ticket={ticket} compact/><div className="ticket-meta"><span>{capabilityLabels[ticket.capability]||ticket.capability}</span></div><small>{new Date(ticket.updated_at_utc).toISOString().slice(0,10)} UTC</small></button>;
}
export function Empty({title,description,action,onAction}:{title:string;description:string;action?:string;onAction?:()=>void}){
  return <div className="empty"><h2>{title}</h2><p>{description}</p>{action&&<button className="primary" onClick={onAction}>{action}</button>}</div>;
}
