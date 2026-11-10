import {useCallback,useEffect,useRef,useState} from 'react';
import {api} from '../api';
import type {ChatThread,TicketChatSummary} from '../chatTypes';
export function useTicketThreads(clientId:string){
  const [summaries,setSummaries]=useState<TicketChatSummary[]>([]);
  const active=useRef(true);const sequence=useRef(0);
  const refresh=useCallback(async()=>{const current=++sequence.current;try{const rows=await api<TicketChatSummary[]>(`/clients/${clientId}/chat/threads/ticket-summaries`);if(active.current&&current===sequence.current)setSummaries(rows)}catch{/* The chat displays connection errors when opened. */}},[clientId]);
  useEffect(()=>{active.current=true;void refresh();const timer=window.setInterval(()=>{if(!document.hidden)void refresh()},5000);
    function changed(event:Event){const {clientId:client,thread}= (event as CustomEvent<{clientId:string;thread:ChatThread}>).detail;if(client!==clientId||!thread.ticket_id)return;sequence.current++;
      const turns=new Set(thread.messages.filter(m=>m.role==='ai').map(m=>m.turn_id||m.id));
      const row:TicketChatSummary={unread_count:thread.unread_count,last_read_message_id:thread.last_read_message_id,ticket_id:thread.ticket_id,thread_id:thread.thread_id,status:thread.status,started:!!thread.messages.length||!!thread.turn_id,archived:!!thread.archived,reply_count:turns.size,updated_at:thread.updated_at,parent_thread_ids:Object.keys(thread.parent_links||{})};
      setSummaries(previous=>[...previous.filter(t=>t.ticket_id!==row.ticket_id),row])}
    window.addEventListener('finops-ticket-chat-updated',changed);const read=()=>void refresh();window.addEventListener('finops-chat-read',read);
    return()=>{active.current=false;clearInterval(timer);sequence.current++;window.removeEventListener('finops-ticket-chat-updated',changed);window.removeEventListener('finops-chat-read',read)}},[clientId,refresh]);
  return {summaries,refresh};
}
