import {useUrlState} from '../hooks/useUrlState';
import {useState,useEffect} from 'react';
import {TeamWorkspace,type ConversationRequest} from '../components/TeamWorkspace';
import {useTeamConversations} from '../hooks/useTeamConversations';
import type {ChatRequest} from '../chatTypes';
import {useAuditRun} from '../hooks/useAuditRun';

import type {Overview,RunEvent,Ticket} from '../types';

export function LiveView({tickets,onChanged,chatRequest,overview,events,running,error,onOpenReports,onChatRequestConsumed}:{tickets:Ticket[];onChanged:()=>void;chatRequest:ChatRequest;overview:Overview;events:RunEvent[];running:boolean;error:string;onOpenReports:(runId?:string)=>void;onChatRequestConsumed:()=>void}){
  const [ticketDraft,setTicketDraft]=useState<{ticketId:string;text:string;nonce:number}>();
  const [ticketThreadId,setTicketThreadId]=useUrlState('ticket');
  const team=useTeamConversations(overview.profile.client_id);const [conversation,setConversation]=useState<ConversationRequest>(null);
  const audit=useAuditRun(overview.profile.client_id,events,running);const agent='v2-finops-report-orchestrator';
  useEffect(()=>{sessionStorage.setItem(`finops-agent:${overview.profile.client_id}`,agent)},[overview.profile.client_id]);
  useEffect(()=>{if(chatRequest?.clientId===overview.profile.client_id&&chatRequest.ticketId){setTicketThreadId(chatRequest.ticketId);setTicketDraft(chatRequest.prompt?{ticketId:chatRequest.ticketId,text:chatRequest.prompt,nonce:chatRequest.nonce}:undefined);onChatRequestConsumed()}},[chatRequest]);
  function selectAgent(_next:string,thread?:string){setConversation(thread?{agentId:agent,id:thread,nonce:Date.now()}:null);}
  function selectTicketThread(id:string|null){setTicketDraft(undefined);setTicketThreadId(id)}

  const runId=audit.live?events.find(e=>e.run_id)?.run_id:audit.record?.run_id;
  return <div className="audit-console chat-first-console"><TeamWorkspace ticketDraft={ticketDraft} ticketThreadId={ticketThreadId} onTicketThread={selectTicketThread} onOpenReports={onOpenReports} key={agent} clientId={overview.profile.client_id} agentId={agent} runId={runId} tickets={tickets} ticketRefs={chatRequest?.clientId===overview.profile.client_id?chatRequest.ids:[]} onChanged={onChanged} onSelect={selectAgent} request={conversation} onConsumed={()=>setConversation(null)} team={team}>{null}</TeamWorkspace></div>;
}
