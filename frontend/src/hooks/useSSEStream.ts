import {useRef,useState,useEffect} from 'react';
import type {RunEvent} from '../types';
import {api,ApiError} from '../api';
import type {RepeatPrompt} from '../components/ReportRepeatDialog';

type RunSummary={run_id:string;status:string};
export function useSSEStream(activeClientId:string,onComplete:()=>void){
  const [clientId,setClientId]=useState('');const [events,setEvents]=useState<RunEvent[]>([]);
  const [running,setRunning]=useState(false);const [error,setError]=useState('');
  const [repeat,setRepeat]=useState<{prompt:RepeatPrompt;body:object}|null>(null);
  const activeRun=useRef('');const controller=useRef<AbortController|null>(null);const generation=useRef(0);
  const complete=useRef(onComplete);complete.current=onComplete;
  async function monitor(id:string,client:string,signal:AbortSignal){
    activeRun.current=id;setClientId(client);setRunning(true);setError('');
    while(!signal.aborted){
      try{
        const response=await fetch(`/api/v1/clients/${client}/runs/${id}/events`,{signal});
        if(!response.ok)throw new Error('No se pudo recuperar la ejecución');
        setEvents([]);setError('');
        const reader=response.body!.getReader();const decoder=new TextDecoder();let pending='';let terminal=false;
        while(true){
          const {value,done}=await reader.read();if(done)break;
          pending+=decoder.decode(value,{stream:true});const frames=pending.split('\n\n');pending=frames.pop()||'';
          for(const frame of frames){
            const line=frame.split('\n').find(line=>line.startsWith('data: '));if(!line)continue;
            const event=JSON.parse(line.slice(6)) as RunEvent;
            setEvents(previous=>[...previous,event]);
            if(event.node==='__error__'){setError(event.payload.status==='cancelled'?'':String(event.payload.message));terminal=true;}
            if(event.node==='__done__')terminal=true;
          }
        }
        if(terminal){activeRun.current='';setRunning(false);complete.current();return;}
      }catch(e){if(signal.aborted)return;setError('Restableciendo conexión. Tu informe sigue en curso.');}
      await new Promise(resolve=>setTimeout(resolve,1500));
    }
  }
  useEffect(()=>{
    const token=++generation.current;let alive=true;controller.current?.abort();activeRun.current='';
    setRunning(false);setEvents([]);setError('');setRepeat(null);if(!activeClientId)return;
    async function discover(){if(activeRun.current||!alive)return;try{const runs=await api<RunSummary[]>(`/clients/${activeClientId}/runs`);const active=runs.find(run=>['running','queued'].includes(run.status));if(active&&!activeRun.current&&alive&&generation.current===token){const next=new AbortController();controller.current=next;void monitor(active.run_id,activeClientId,next.signal)}}catch{}}
    void discover();const poll=setInterval(()=>void discover(),3000);
    return ()=>{alive=false;clearInterval(poll);controller.current?.abort()};
  },[activeClientId]);
  async function start(body:object,_onComplete?:()=>void){
    const token=generation.current;activeRun.current='starting';controller.current?.abort();const stop=new AbortController();controller.current=stop;
    const client=(body as {client_id:string}).client_id;setClientId(client);setRunning(true);setError('');setEvents([]);
    try{
      const run=await api<{run_id:string}>('/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!stop.signal.aborted&&generation.current===token)await monitor(run.run_id,client,stop.signal);
    }catch(e){if(!stop.signal.aborted){activeRun.current='';setRunning(false);if(e instanceof ApiError&&e.status===409&&(e.detail as {code?:string})?.code==='report_exists'){setRepeat({prompt:e.detail as RepeatPrompt,body});setError('')}else setError((e as Error).message);}}
  }
  async function stop(runId?:string){const key=runId||activeRun.current;if(key)await api(`/clients/${activeClientId}/runs/${key}/stop`,{method:'POST'})}
  async function confirmRepeat(){if(!repeat)return;const value=repeat;setRepeat(null);await start({...value.body,repeat_confirmation:value.prompt.confirmation_id})}
  return {clientId,events,running,error,start,stop,repeat,confirmRepeat,cancelRepeat:()=>setRepeat(null)};
}
