import {Check,LoaderCircle} from 'lucide-react';
const stages=['Preparar datos','Asignación','Anomalías','Proyecciones','Presupuesto','Compromisos','Consolidar informe'];
export function ReportProgress({completed,conversational=false}:{completed:number;conversational?:boolean}){
  return <div className="report-progress"><LoaderCircle className="spin" size={22}/><h3>El equipo está preparando tu informe</h3><p>Puedes seguir usando la app. La ejecución continúa en el backend.</p>{conversational?<p>El orquestador coordina a los especialistas. Puedes seguir sus avances en la conversación.</p>:<ol>{stages.map((stage,i)=><li key={stage} className={i<completed?'done':i===completed?'current':''}>{i<completed?<Check size={13}/>:<span>{i+1}</span>}{stage}</li>)}</ol>}</div>;
}
