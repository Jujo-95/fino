import {useEffect,useState} from 'react';
import {LoaderCircle,FileText,Square} from 'lucide-react';
import {api} from '../api';
type Job={run_id:string;status:string;error?:string};
export function ChatReportJob({clientId,runId,onOpen}:{clientId:string;runId:string;onOpen?:(id:string)=>void}){
  const [job,setJob]=useState<Job|null>(null);const [stopping,setStopping]=useState(false);const [error,setError]=useState('');
  useEffect(()=>{let active=true;let timer:ReturnType<typeof setTimeout>;async function read(){try{const value=await api<Job>(`/clients/${clientId}/runs/${runId}`);if(!active)return;setJob(value);if(value.status==='running')timer=setTimeout(()=>void read(),1500)}catch(e){if(active)setError((e as Error).message)}}void read();return()=>{active=false;clearTimeout(timer)}},[clientId,runId]);
  async function stop(){setStopping(true);try{setJob(await api<Job>(`/clients/${clientId}/runs/${runId}/stop`,{method:'POST'}));setError('')}catch(e){setError((e as Error).message)}finally{setStopping(false)}}
  const labels:Record<string,string>={running:'Informe en preparación',completed:'Informe guardado',cancelled:'Informe detenido',failed:'Informe incompleto'};
  return <div className="chat-report-job" role="status">{job?.status==='running'?<LoaderCircle size={14} className="spin"/>:<FileText size={14}/>}<span>{labels[job?.status||'running']}</span>{onOpen&&<button className="text-button" onClick={()=>onOpen(runId)}>Ver en Reportes</button>}{job?.status==='running'&&<button className="text-button" disabled={stopping} onClick={()=>void stop()}><Square size={11}/> Detener informe</button>}{error&&<small role="alert">{error}</small>}</div>;
}
