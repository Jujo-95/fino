import type {AuditRun} from '../auditTypes';
import {Disclosure} from './Disclosure';
export function AnalysisResult({value}:{value:NonNullable<AuditRun['analysis']>}){
  return <div className="connection-body">{value.skip_reason&&<p>{value.skip_reason}</p>}<h3>Indicadores revisados</h3><ul className="connection-records">{value.measurements.map(metric=><li key={metric.key}><span>{metric.label}</span><strong>{metric.value===null?'Falta información':Number(metric.value).toLocaleString('es',{maximumFractionDigits:2})+' '+metric.unit}</strong></li>)}</ul><h3>Tareas</h3><p>{value.actions.length?`${value.actions.length} tareas creadas o reevaluadas. Continúa desde Tus tareas o su conversación con el equipo.`:'No se detectaron tareas nuevas con los controles ejecutados.'}</p><Disclosure title="Cobertura y límites"><ul>{value.coverage.map(row=><li key={row.specialty}>{row.specialty} · {row.status}</li>)}{value.limitations.map(text=><li key={text}>{text}</li>)}</ul></Disclosure></div>;
}
