import {useEffect,useState} from 'react';
import {Archive,ArchiveRestore,Ticket} from 'lucide-react';
import {AgentAvatar} from './AgentAvatar';
import type {ChatSummary} from '../chatTypes';
function timeAgo(iso:string,now:number){
  const seconds=Math.max(0,Math.floor((now-new Date(iso).getTime())/1000));
  if(!Number.isFinite(seconds)||seconds<60)return {short:'Ahora',label:'Actualizada hace un momento'};
  const [size,unit,suffix]=seconds>=31536000?[31536000,'year','A']:seconds>=2592000?[2592000,'month','M']:seconds>=86400?[86400,'day','D']:seconds>=3600?[3600,'hour','H']:[60,'minute','M'];
  const value=Math.floor(seconds/Number(size));
  return {short:`${value}${suffix}`,label:'Actualizada '+new Intl.RelativeTimeFormat('es',{numeric:'always'}).format(-value,unit as Intl.RelativeTimeFormatUnit)};
}
export function ConversationList({agentId,entries,archived,selectedThread,busy,loading,onOpen,onArchive}:{agentId:string;entries:ChatSummary[];archived:boolean;selectedThread?:string;busy:boolean;loading:boolean;onOpen:(id:string)=>void;onArchive:(id:string,archived:boolean)=>void}){
  const [now,setNow]=useState(Date.now);
  useEffect(()=>{const timer=window.setInterval(()=>setNow(Date.now()),60000);return()=>window.clearInterval(timer)},[]);
  return <div className="conversation-scroll" role="list" aria-label={archived?'Conversaciones archivadas':'Historial de conversaciones'} tabIndex={0}>{loading?<p>Cargando conversaciones…</p>:entries.length?entries.map(thread=>{const ago=timeAgo(thread.updated_at,now);return <div role="listitem" key={thread.thread_id} className={'conversation-row '+(thread.thread_id===selectedThread?'active':'')}><button className="roster-conversation" aria-current={thread.thread_id===selectedThread?'true':undefined} disabled={busy} onClick={()=>onOpen(thread.thread_id)} title={thread.title||'Conversación'}><AgentAvatar agent={agentId}/><span>{thread.title||'Conversación'}</span>{!thread.unread_count&&thread.needs_attention&&<Ticket className="ticket-needs-attention" size={14} role="img" aria-label="Ticket necesita atención"><title>Ticket pendiente de acción</title></Ticket>}{!!thread.unread_count&&<i className="conversation-unread" role="img" aria-label={thread.unread_count+' respuestas sin leer'} title="Respuesta sin leer"/>}<time dateTime={thread.updated_at} title={ago.label} aria-label={ago.label}>{ago.short}</time></button><button className="conversation-archive" disabled={busy||thread.status==='running'} aria-label={`${archived?'Restaurar':'Archivar'} ${thread.title||'conversación'}`} title={archived?'Restaurar conversación':'Archivar conversación'} onClick={()=>onArchive(thread.thread_id,!archived)}>{archived?<ArchiveRestore size={13}/>:<Archive size={13}/>}</button></div>}):<p>{archived?'No hay conversaciones archivadas':'Sin conversaciones todavía'}</p>}</div>;
}
