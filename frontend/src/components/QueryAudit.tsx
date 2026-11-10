import {useState} from 'react';
import {Copy,Check,Database} from 'lucide-react';
import {formatDuration,type QueryEvidence} from '../auditTypes';
export function JsonBlock({value}:{value:unknown}){return <pre className="audit-code">{JSON.stringify(value,null,2)}</pre>;}
const queryNames:Record<string,string>={totals:'Costos, asignación y compromisos',daily:'Gasto efectivo por día',services:'Costo por cuenta, servicio y día'};
export function QueryAudit({queries,shared}:{queries:QueryEvidence[];shared:boolean}){
  if(!queries.length)return <div className="audit-no-data"><Database size={24}/><h3>No hay consultas registradas para esta etapa</h3><p>Las consultas aparecerán cuando se ejecute el análisis con auditoría.</p></div>;
  return <div className="query-audit"><p className="audit-help">{shared?'Evidencia consultada por este especialista. Cada registro identifica al ejecutor y su origen.':'Evidencia del informe: cálculos de preparación y consultas de los agentes.'}</p>{queries.map((query)=><details className="query-record" key={query.query_id}><summary><Database size={16}/><span>{queryNames[query.name]||query.name}</span><small>{query.row_count} filas / {formatDuration(query.duration_ms)}</small></summary><div className="query-body"><div className="query-identity"><code>{query.query_id.slice(0,12)}</code><span>{query.source==='agent_tool'?'Herramienta del agente':'Cálculo de preparación'} / {query.executed_by}</span><CopySql sql={query.sql}/></div><pre className="sql-code">{query.sql}</pre><h4>Parámetros vinculados</h4><JsonBlock value={query.parameters}/><h4>Resultado guardado <span>{query.row_count} filas{query.truncated?`, muestra de ${query.sample_rows.length}`:''}</span></h4><ResultsTable rows={query.sample_rows}/><p className="query-timestamp">Ejecutada el {new Date(query.executed_at_utc).toLocaleString('es',{timeZone:'UTC'})} UTC</p></div></details>)}</div>;
}
function CopySql({sql}:{sql:string}){
  const [copied,setCopied]=useState(false);const [error,setError]=useState(false);
  async function copy(){try{await navigator.clipboard.writeText(sql);setCopied(true);setError(false);}catch{setError(true);}}
  return <button className="text-button" onClick={()=>void copy()}>{copied?<Check size={14}/>:<Copy size={14}/>} {error?'Selecciona el SQL para copiarlo':copied?'Copiado':'Copiar SQL'}</button>;
}
function ResultsTable({rows}:{rows:Record<string,unknown>[]}){
  if(!rows.length)return <p className="audit-help">La consulta no devolvió filas.</p>;
  const columns=Object.keys(rows[0]);
  return <div className="query-results"><table><thead><tr>{columns.map(column=><th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={index}>{columns.map(column=><td key={column}>{row[column]===null?'NULL':typeof row[column]==='object'?JSON.stringify(row[column]):String(row[column])}</td>)}</tr>)}</tbody></table></div>;
}
