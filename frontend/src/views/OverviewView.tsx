import {Wallet,ChartNoAxesCombined,ShieldCheck,Tags,Activity} from 'lucide-react';
import {Disclosure} from '../components/Disclosure';
import {SpendChart,ServiceChart} from '../components/Charts';
import {BudgetSummary,AllocationSummary,PendingFindings} from '../components/BudgetSummary';
import type {Overview,Ticket} from '../types';
export const agents=[{key:'allocation',name:'Asignación',detail:'Propiedad y etiquetado',icon:Tags},{key:'anomaly',name:'Anomalías',detail:'Detección de desviaciones',icon:Activity},{key:'forecasting',name:'Proyecciones',detail:'Estimación de consumo',icon:ChartNoAxesCombined},{key:'budgeting',name:'Presupuesto',detail:'Control de variaciones',icon:Wallet},{key:'commitment',name:'Compromisos',detail:'Optimización de tarifas',icon:ShieldCheck}];
export function OverviewView({overview:o,tickets,onNavigate}:{overview:Overview;tickets:Ticket[];onNavigate:(view:string)=>void}){
  return <div className="overview-layout"><div className="overview-main"><SpendChart overview={o}/><Disclosure title="Desglose por servicio" meta={`${o.services.length} servicios`}><ServiceChart overview={o}/></Disclosure></div><aside className="overview-aside" aria-label="Presupuesto y acciones"><BudgetSummary overview={o} onIndicators={()=>onNavigate('kpis')}/><PendingFindings tickets={tickets} onTickets={()=>onNavigate('tickets')}/><AllocationSummary overview={o} onIndicators={()=>onNavigate('kpis')}/></aside></div>;
}
