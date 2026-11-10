import {chatAgents} from '../auditTypes';
import type {ChatThread} from '../chatTypes';
export function V2Evidence({thread,agentId}:{thread:ChatThread|null;agentId:string}){
  const agent=chatAgents.find(a=>a.key===agentId)!;const activity=(thread?.activity||[]).filter(a=>a.tool!=='model_response');
  return <div className="v2-evidence"><h3>{agent.original_name}</h3><p>Equipo 2.0 · {(agent.use_case_ids||[]).length||60} casos de referencia disponibles</p><p>Los resultados pertenecen al cliente de esta conversación. Los informes guardados se encuentran en Reportes.</p>{activity.length?activity.map((item,index)=><details key={item.at+index}><summary>{({query_finance:'Consulta de facturación',read_use_case_snapshots:'Resultados del periodo',consult_specialist:'Aporte especializado',save_report:'Informe guardado',read_report_changes:'Informe anterior'} as Record<string,string>)[item.tool]||'Evidencia consultada'}</summary><pre>{JSON.stringify(item.result,(_key,value)=>['sql','executed_sql','reference_sql'].includes(_key)?undefined:value,2)}</pre></details>):<p>Aún no hay evidencia consultada en esta conversación.</p>}</div>;
}
