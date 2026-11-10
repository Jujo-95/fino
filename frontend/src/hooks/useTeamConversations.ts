import {useCallback,useEffect,useState} from 'react';
import {api} from '../api';
import {chatAgents} from '../auditTypes';
import type {ChatSummary} from '../chatTypes';
export function useTeamConversations(clientId:string){
  const [threads,setThreads]=useState<Record<string,ChatSummary[]>>({});const [error,setError]=useState('');const [archived,setArchived]=useState<Record<string,ChatSummary[]>>({});const [archiveLoading,setArchiveLoading]=useState<Record<string,boolean>>({});
  const update=useCallback((agentId:string,list:ChatSummary[])=>setThreads(old=>old[agentId]===list?old:{...old,[agentId]:list}),[]);
  const refresh=useCallback(async(agentId:string)=>{try{update(agentId,await api<ChatSummary[]>(`/clients/${clientId}/chat/threads?agent_id=${agentId}`));setError('')}catch{setError('No se pudo cargar el historial. Puedes reintentar desde el equipo.')}},[clientId,update]);
  const refreshArchived=useCallback(async(agentId:string)=>{setArchiveLoading(old=>({...old,[agentId]:true}));try{const list=await api<ChatSummary[]>(`/clients/${clientId}/chat/threads?agent_id=${agentId}&archived=true`);setArchived(old=>({...old,[agentId]:list}));setError('')}catch{setError('No se pudieron cargar las conversaciones archivadas.')}finally{setArchiveLoading(old=>({...old,[agentId]:false}))}},[clientId]);
  useEffect(()=>{let active=true;setThreads({});setArchived({});setError('');const load=()=>api<ChatSummary[]>(`/clients/${clientId}/chat/threads`).then(list=>{if(active)setThreads(Object.fromEntries(chatAgents.map(agent=>[agent.key,list.filter(t=>(t.agent_id||'orchestrator')===agent.key)])))}).catch(()=>{if(active)setError('No se pudo cargar el historial.')});void load();const changed=()=>{if(!document.hidden)void load()};const timer=window.setInterval(changed,10000);window.addEventListener('finops-chat-read',changed);window.addEventListener('focus',changed);return()=>{active=false;clearInterval(timer);window.removeEventListener('finops-chat-read',changed);window.removeEventListener('focus',changed)}},[clientId]);
  return {threads,update,refresh,error,archived,archiveLoading,refreshArchived};
}
