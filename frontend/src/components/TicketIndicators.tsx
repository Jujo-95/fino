import type {Overview,Ticket} from '../types';
import type {Consulting} from '../consultingTypes';
import {money} from '../types';
import {metricLabels,periodLabel} from '../presentation';
import {Disclosure} from './Disclosure';
export function TicketIndicators({ticket,overview,consulting}:{ticket:Ticket;overview?:Overview;consulting?:Consulting|null}){
  if(!overview)return null;
  const capability=ticket.capability;
  const metrics=overview.metrics.filter(m=>m.capability===capability);
  const allocation=consulting?.diagnosis.facts.allocation;
  const confirmed=consulting?.diagnosis.context.values.monthly_budget;
  const values:[string,string][]=[];
  if(capability==='allocation'&&allocation){values.push(['Coste con responsable confirmado',allocation.owned_cost_pct===null?'Sin datos':allocation.owned_cost_pct.toFixed(1)+'%'],['Coste con etiquetas',allocation.tagged_cost_pct===null?'Sin datos':allocation.tagged_cost_pct.toFixed(1)+'%'])}
  if(['forecasting','budgeting'].includes(capability)){values.push(['Gasto del período',money(overview.actual)],['Proyección mensual estimada',money(overview.forecast)]);if(capability==='budgeting')values.push(['Presupuesto aprobado',typeof confirmed==='number'?money(confirmed):'Por confirmar'])}
  for(const m of metrics){if(capability==='budgeting'&&typeof confirmed!=='number')continue;values.push([metricLabels[m.key]||m.label,m.value===null?'Sin datos':m.unit.startsWith('USD')?money(m.value)+(m.unit==='USD/day'?'/día':''):m.value.toFixed(1)+'%'])}
  if(!values.length)return null;
  return <Disclosure title="Indicadores para esta tarea"><p>Contexto general del cliente · {periodLabel(overview)}. Las mediciones del alcance específico están en la evidencia del ticket.</p>{capability==='allocation'&&<small>Responsables y etiquetas: cobertura sobre todo el histórico disponible.</small>}<dl className="task-indicators">{values.map(([name,value])=><div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>{capability==='forecasting'&&<small>Una proyección es una estimación; no un ahorro ni un gasto ya realizado.</small>}</Disclosure>;
}
