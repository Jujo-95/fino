import {useCallback,useEffect,useState,useRef} from 'react';
import {deploymentClientId} from '../productConfig';
import {api} from '../api';
import type {Overview,Profile,Report,Ticket} from '../types';
import type {Consulting} from '../consultingTypes';
export function useConsole(requestedClientId=''){
  const [profiles,setProfiles]=useState<Profile[]>([]);const [clientId,setClientId]=useState('');
  const [overview,setOverview]=useState<Overview|null>(null);const [tickets,setTickets]=useState<Ticket[]>([]);const [reports,setReports]=useState<Report[]>([]);
  const [error,setError]=useState('');const [loading,setLoading]=useState(true);const [provider,setProvider]=useState('');
  const [consulting,setConsulting]=useState<Consulting|null>(null);
  const currentClient=useRef(clientId);currentClient.current=clientId;const sequence=useRef(0);
  const loadProfiles=useCallback(async(preferred?:string)=>{
    try{const [list,health]=await Promise.all([api<Profile[]>('/clients'),api<{provider:string}>('/health')]);setProfiles(list);setProvider(health.provider);if(deploymentClientId&&!list.some(p=>p.client_id===deploymentClientId))throw new Error('El cliente configurado para esta instalación no está disponible.');if(requestedClientId&&((deploymentClientId&&requestedClientId!==deploymentClientId)||!list.some(p=>p.client_id===requestedClientId)))throw new Error('El cliente de este enlace no está disponible.');setClientId(old=>requestedClientId||deploymentClientId||preferred||old||(list.some(p=>p.client_id===localStorage.getItem('finops-client'))?localStorage.getItem('finops-client'):null)||list[0]?.client_id||'');}catch(e){setError((e as Error).message);}finally{setLoading(false);}
  },[requestedClientId]);
  const refresh=useCallback(async()=>{
    if(!clientId)return;const request=++sequence.current;const active=()=>request===sequence.current&&currentClient.current===clientId;setLoading(true);setError('');
    try{const [o,t,r,g]=await Promise.all([api<Overview>(`/clients/${clientId}/overview`),api<Ticket[]>(`/clients/${clientId}/tickets`),api<Report[]>(`/clients/${clientId}/reports`),api<Consulting>(`/clients/${clientId}/consulting`)]);if(active()){setOverview(o);setTickets(t);setReports(r);setConsulting(g)}}catch(e){if(active())setError((e as Error).message);}finally{if(active())setLoading(false);}
  },[clientId]);
  useEffect(()=>{if(clientId)localStorage.setItem('finops-client',clientId)},[clientId]);
  useEffect(()=>{void loadProfiles()},[loadProfiles]);
  useEffect(()=>{const changed=()=>void refresh();window.addEventListener('finops-context-changed',changed);return()=>window.removeEventListener('finops-context-changed',changed)},[refresh]);
  useEffect(()=>{setOverview(null);setTickets([]);setReports([]);setConsulting(null);void refresh()},[refresh]);
  async function saved(id:string){await loadProfiles(id);if(id===clientId)await refresh();}
  return {profiles,clientId,setClientId,overview,tickets,reports,consulting,error,loading,provider,refresh,saved};
}
