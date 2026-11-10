import {useState} from 'react';
import type {Consulting} from '../consultingTypes';
import {ContextAnswer} from './ContextAnswer';
const fields:Record<string,string>={expected_accounts:'Cuentas incluidas',owners:'Responsables por cuenta',objective:'Objetivo',monthly_budget:'Presupuesto mensual aprobado',cadence:'Frecuencia y retraso de datos'};
const names:Record<string,string>={...fields,source_cadence_days:'Frecuencia de actualización · días',data_latency_days:'Retraso esperado · días',allocation_target_pct:'Objetivo de asignación · %',minimum_history_days:'Histórico mínimo · días',known_events:'Eventos previstos',constraints:'Restricciones',non_billable_days:'Días confirmados sin uso'};
export function ConnectionContext({data,clientId,onChanged}:{data?:Consulting|null;clientId:string;onChanged:()=>void}){
  const [field,setField]=useState('owners');if(!data)return <p className="connection-help">Actualiza la conexión para consultar el contexto.</p>;
  const values=data.diagnosis.context.values;
  return <div className="connection-body"><dl className="connection-facts">{Object.entries(values).map(([key,value])=><div key={key}><dt>{names[key]||key}</dt><dd>{Array.isArray(value)?value.join(', '):value&&typeof value==='object'?Object.entries(value).map(([k,v])=>`${k}: ${v}`).join(' · '):String(value)}</dd></div>)}</dl>{!Object.keys(values).length&&<p className="connection-help">Aún falta confirmar información del negocio.</p>}
    <label className="connection-field">Información que quieres completar<select value={field} onChange={e=>setField(e.target.value)}>{Object.entries(fields).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>
    <ContextAnswer key={field} data={data} requirement={{id:field,capability:'allocation',question:fields[field],reason:'Información aportada desde Conexiones.',status:'missing'}} clientId={clientId} onChanged={onChanged}/>
  </div>;
}
