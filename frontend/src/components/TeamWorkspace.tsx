import {useEffect,useRef,useState} from 'react';
import {useChat} from '../hooks/useChat';
import type {useTeamConversations} from '../hooks/useTeamConversations';
import {ResizeHandle} from './ResizeHandle';
import {AuditRoster} from './AuditRoster';
import {useTicketThreads} from '../hooks/useTicketThreads';
import {TicketThreadPanel} from './TicketThreadPanel';
import {AgentWorkspace} from './AgentWorkspace';
import type {Ticket} from '../types';
export type ConversationRequest={agentId:string;id:string;nonce:number}|null;
export function TeamWorkspace({clientId,agentId,runId,tickets,ticketRefs,onChanged,onSelect,request,onConsumed,team,children,onOpenReports,ticketThreadId,onTicketThread,ticketDraft}:{ticketDraft?:{ticketId:string;text:string;nonce:number};clientId:string;agentId:string;runId?:string;tickets:Ticket[];ticketRefs:string[];onChanged:()=>void;onSelect:(agent:string,thread?:string)=>void;request:ConversationRequest;onConsumed:()=>void;team:ReturnType<typeof useTeamConversations>;children:React.ReactNode;onOpenReports?:(id:string)=>void;ticketThreadId:string|null;onTicketThread:(id:string|null)=>void}){
  const root=useRef<HTMLDivElement>(null);const [specialist,setSpecialist]=useState<string|null>(null);const [draftRequest,setDraftRequest]=useState<{text:string;nonce:number}>();
  const widths={['--team-rail' as string]:`${Math.max(180,Math.min(480,Number(localStorage.getItem('finops-layout:rail'))||260))}px`,['--thread-width' as string]:`${Math.max(280,Math.min(800,Number(localStorage.getItem('finops-layout:thread'))||420))}px`};
  const {summaries}=useTicketThreads(clientId);
  const chat=useChat(clientId,onChanged,agentId,runId);const handled=useRef(0);
  useEffect(()=>{if(!chat.loading)team.update(agentId,chat.threads)},[chat.loading,chat.threads,agentId,team.update]);
  useEffect(()=>{if(chat.thread&&!chat.busy)void team.refresh(agentId)},[chat.thread?.updated_at,chat.busy,agentId,team.refresh]);
  useEffect(()=>{if(!chat.loading&&request?.agentId===agentId&&handled.current!==request.nonce){handled.current=request.nonce;void(request.id==='new'?chat.newThread():chat.select(request.id)).finally(onConsumed)}},[request,chat.loading,agentId]);
  function open(agent:string,id:string){setSpecialist(null);if(agent===agentId){if(id==='new')void chat.newThread();else void chat.select(id)}else onSelect(agent,id)}
  async function archive(agent:string,id:string,archived:boolean){if(agent!==agentId)return false;const changed=await chat.archive(id,archived);if(changed)await Promise.all([team.refresh(agent),team.refreshArchived(agent)]);return changed}
  useEffect(()=>{if(ticketThreadId&&!chat.loading&&!chat.thread&&!chat.error)void chat.ensureThread()},[ticketThreadId,chat.loading,chat.thread?.thread_id]);
  const traceVersion=summaries.map(s=>[s.thread_id,s.started,s.parent_thread_ids?.includes(chat.thread?.thread_id||'')].join(':')).sort().join('|');
  useEffect(()=>{if(chat.thread)void chat.reload()},[traceVersion,chat.thread?.thread_id]);
  const ticketThread=tickets.find(t=>t.ticket_id===ticketThreadId);
  return <div ref={root} style={widths} className={'audit-workspace team-conversations fino-workspace '+(ticketThread?'with-ticket-thread':'')}><AuditRoster selected={specialist||agentId} onSelect={key=>setSpecialist(key===agentId?null:key)} conversations={team.threads} archived={team.archived} archiveLoading={team.archiveLoading} onLoadArchived={team.refreshArchived} onArchive={archive} selectedThread={chat.thread?.thread_id} onConversation={open} busy={chat.busy||chat.loading} historyError={team.error} onRetry={()=>void team.refresh(agentId)}/><ResizeHandle root={root} variable="--team-rail" storageKey="finops-layout:rail" label="Ancho del listado de conversaciones" min={180} max={480} fallback={260}/><AgentWorkspace specialistId={specialist} onClearSpecialist={()=>setSpecialist(null)} draftRequest={draftRequest} onAskSpecialist={text=>{setSpecialist(null);setDraftRequest({text,nonce:Date.now()})}} ticketThreads={summaries} onTicketThread={onTicketThread} onOpenReports={onOpenReports} key={agentId} chat={chat} clientId={clientId} agentId={agentId} tickets={tickets} ticketRefs={ticketRefs} onChanged={onChanged}>{children}</AgentWorkspace>{ticketThread&&<ResizeHandle root={root} variable="--thread-width" storageKey="finops-layout:thread" label="Ancho del hilo" min={280} max={800} fallback={420} reverse/>}{ticketThread&&<TicketThreadPanel draftRequest={ticketDraft?.ticketId===ticketThreadId?ticketDraft:undefined} parentThreadId={chat.thread?.thread_id} key={clientId+ticketThread.ticket_id} ticket={ticketThread} tickets={tickets} clientId={clientId} onChanged={onChanged} onClose={()=>{onTicketThread(null);requestAnimationFrame(()=>document.getElementById('audit-agent-detail')?.focus({preventScroll:true}))}} onTicket={id=>onTicketThread(id)}/>}</div>;
}
