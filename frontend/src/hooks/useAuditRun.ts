import {useEffect,useState} from 'react';
import {api} from '../api';
import type {RunEvent} from '../types';
import type {AuditRun,AuditRunSummary,AuditTrace,QueryEvidence} from '../auditTypes';
export function useAuditRun(clientId:string,events:RunEvent[],running:boolean,initialSelection=''){
  const [runs,setRuns]=useState<AuditRunSummary[]>([]);const [selected,setSelected]=useState(initialSelection);const [record,setRecord]=useState<AuditRun|null>(null);const [error,setError]=useState('');const [listing,setListing]=useState(false);const [reading,setReading]=useState(false);
  const [version,setVersion]=useState(0);const refresh=()=>setVersion(v=>v+1);
  const liveRunId=events.find(event=>event.run_id)?.run_id;const live=selected==='live'&&running;
  useEffect(()=>{let active=true;setListing(true);api<AuditRunSummary[]>(`/clients/${clientId}/runs`).then(list=>{if(active){setRuns(list)}}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setListing(false)});return()=>{active=false}},[clientId,running,version]);
  useEffect(()=>{if(running)setSelected('live')},[running]);
  useEffect(()=>{let active=true;const id=selected==='live'?(running?null:liveRunId||runs[0]?.run_id):selected||runs[0]?.run_id;setRecord(null);setError('');if(!id){setReading(false);return}setReading(true);api<AuditRun>(`/clients/${clientId}/runs/${id}`).then(value=>{if(active)setRecord(value)}).catch(e=>{if(active)setError(e.message)}).finally(()=>{if(active)setReading(false)});return()=>{active=false}},[clientId,selected,runs,running,liveRunId]);
  const latest=[...events].reverse().find(e=>Array.isArray(e.payload.audit_traces))?.payload.audit_traces as AuditTrace[]|undefined;
  const traces=live?[...new Map((latest||[]).map(t=>[t.node,t])).values()]:record?.events.flatMap(e=>e.payload.trace?[e.payload.trace]:[])||[];
  const snapshot=events.find(e=>e.node==='ingest_and_profile')?.payload.kpi_snapshots as {query_evidence?:QueryEvidence[]}|undefined;
  const queries=live?[...(snapshot?.query_evidence||[]),...traces.filter(t=>t.node!=='ingest_and_profile').flatMap(t=>t.queries||[])]:record?.queries||[];
  const report=live?String(events.find(e=>e.node==='synthesize')?.payload.report_markdown||''):record?.report_markdown||'';
  const status=live?'running':record?.status||'pending';
  return {refresh,runs,selected,select:setSelected,record,error,loading:listing||reading,live,traces,queries,report,status};
}
