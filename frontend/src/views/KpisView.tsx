import {useState} from 'react';
import {KpiMetricCard} from '../components/Primitives';
import {capabilityLabels} from '../presentation';
import type {Overview} from '../types';
export function KpisView({overview:o}:{overview:Overview}){
  const [filter,setFilter]=useState('all');const capabilities=[...new Set(o.metrics.map(m=>m.capability))];
  return <><label className="compact-filter">Capacidad<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">Todas las capacidades</option>{capabilities.map(cap=><option key={cap} value={cap}>{capabilityLabels[cap]||cap}</option>)}</select></label><div className="kpi-groups">{capabilities.filter(cap=>filter==='all'||cap===filter).map(cap=><MetricGroup key={cap} capability={cap} overview={o}/>)}</div></>;
}
function MetricGroup({capability,overview:o}:{capability:string;overview:Overview}){
  const [expanded,setExpanded]=useState(false);const metrics=o.metrics.filter(m=>m.capability===capability);const key=({allocation:'unallocated_cost_pct','anomaly-management':'anomaly_unpredicted_variance',forecasting:'forecast_drift_rate',budgeting:'budget_vs_forecast_variance','rate-optimization':'effective_savings_rate'} as Record<string,string>)[capability];const primary=metrics.find(m=>m.key===key)||metrics[0];const secondary=metrics.filter(m=>m!==primary);
  return <section className="panel kpi-group"><div className="panel-heading"><h2>{capabilityLabels[capability]||capability}</h2></div><div className="kpi-grid kpi-primary"><KpiMetricCard metric={primary} mode={o.profile.allocation_policy.mode} maturity={o.profile.target_maturity}/></div>{secondary.length>0&&<><button className="text-button metric-expand" aria-expanded={expanded} aria-controls={'metrics-'+capability} onClick={()=>setExpanded(!expanded)}>{expanded?'Ocultar indicadores secundarios':`Ver ${secondary.length} ${secondary.length===1?'indicador más':'indicadores más'}`}{!expanded&&secondary.some(m=>m.value===null)&&' · incluye datos no disponibles'}</button><div id={'metrics-'+capability} hidden={!expanded}><div className="kpi-grid">{secondary.map(metric=><KpiMetricCard key={metric.key} metric={metric} mode={o.profile.allocation_policy.mode} maturity={o.profile.target_maturity}/>)}</div></div></>}</section>;
}
