import {Fragment} from 'react';
import type {ChatThread,TicketChatSummary} from '../chatTypes';
import {ChatActivity} from './ChatActivity';
import {ChatContent} from './ChatContent';
import {ChatThreadTrace} from './ChatThreadTrace';
import {ChatConsulting} from './ChatConsulting';
export function ChatTimeline({thread,busy,onTicket,name='Orquestador',ticketThreads}:{name?:string;thread:ChatThread;busy:boolean;onTicket:(id:string)=>void;ticketThreads?:TicketChatSummary[]}){
  let turnId='';
  const ids=new Set(thread.messages.map(m=>m.id));
  const traces=(after:string|null)=>(thread.ticket_threads||[]).filter(t=>after===null?(!t.after_message_id||!ids.has(t.after_message_id)):t.after_message_id===after).map(t=><ChatThreadTrace key={t.thread_id} trace={t} summary={ticketThreads?.find(s=>s.thread_id===t.thread_id)} onTicket={onTicket}/>);
  return <>{traces(null)}{thread.messages.map((m,i)=>{if(m.role==='human')turnId=m.turn_id||m.id;return <Fragment key={m.id||i}><article className={'chat-message '+m.role}><small>{m.role==='human'?'Tú':name+(m.interrupted?' · respuesta detenida':'')}</small><ChatContent ticketThreads={ticketThreads} text={String(m.content)} onTicket={onTicket}/>{m.role==='ai'&&<span className="chat-read-marker" data-chat-read-id={m.id} aria-hidden="true"/>}</article><ChatActivity thread={thread} turnId={turnId} afterId={m.id} busy={false}/><ChatConsulting thread={thread} turnId={turnId} afterId={m.id}/>{m.role==='human'&&<><ChatActivity thread={thread} turnId={turnId} busy={false}/><ChatConsulting thread={thread} turnId={turnId}/></>}{traces(m.id)}</Fragment>})}{thread.streaming?.content&&<article className="chat-message ai streaming" aria-live="off"><small>{name}{['error','cancelled'].includes(thread.status)?' · respuesta interrumpida':''}</small><ChatContent text={thread.streaming.content} onTicket={onTicket}/>{busy&&<span className="stream-caret"/>}</article>}{busy&&<ChatActivity thread={{...thread,activity:[]}} turnId={thread.turn_id} busy={busy} live/>}</>;
}
