import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {MessageCircle} from 'lucide-react';
import {ChatReportRepeat} from './ChatReportRepeat';
import {ChatReportJob} from './ChatReportJob';
import {ChatTimeline} from './ChatTimeline';
import {ChatComposer} from './ChatComposer';
import {useChatReadReceipt} from '../hooks/useChatReadReceipt';
import {ChatPlan} from './ChatPlan';
import type {ChatController} from '../hooks/useChat';
import {chatAgents} from '../auditTypes';
import type {TicketChatSummary} from '../chatTypes';
import type {Ticket} from '../types';
export function ChatPanel({chat,clientId,tickets,ticketRefs,agentId,onTicket,headerAction,hidden=false,onOpenReports,conversationKey,initialDraft,title,ticketThreads,draftRequest,composerNotice}:{composerNotice?:React.ReactNode;draftRequest?:{text:string;nonce:number};chat:ChatController;clientId:string;tickets:Ticket[];ticketRefs:string[];agentId:string;onTicket:(id:string)=>void;headerAction?:React.ReactNode;hidden?:boolean;onOpenReports?:(id:string)=>void;conversationKey?:string;initialDraft?:string;title?:string;ticketThreads?:TicketChatSummary[]}){
  const agent=chatAgents.find(a=>a.key===agentId)!;const storage=`${clientId}:${agentId}${conversationKey?':'+conversationKey:''}`;const [refs,setRefs]=useState<string[]>(()=>{try{return [...new Set([...JSON.parse(sessionStorage.getItem(`finops-chat-refs:${storage}`)||'[]'),...ticketRefs])].filter(id=>tickets.some(t=>t.ticket_id===id))}catch{return ticketRefs}});const [draft,setDraft]=useState(()=>sessionStorage.getItem(`finops-chat-draft:${storage}`)||'');const panel=useRef<HTMLDivElement>(null);const end=useRef<HTMLDivElement>(null);const viewport=useRef<HTMLDivElement>(null);const pinned=useRef(true);
  useChatReadReceipt(clientId,chat.thread,viewport,hidden);
  const lastRequest=useRef(0);
  useEffect(()=>{if(draftRequest&&draftRequest.nonce!==lastRequest.current){lastRequest.current=draftRequest.nonce;setDraft(previous=>previous.trim()?previous+'\n\n'+draftRequest.text:draftRequest.text)}},[draftRequest?.nonce]);
  useEffect(()=>{
    if(!initialDraft||chat.loading||!chat.thread)return;
    const marker='finops-chat-seeded:'+storage;
    if(sessionStorage.getItem(marker))return;
    sessionStorage.setItem(marker,'1');
    if(!chat.thread.messages.length)setDraft(previous=>previous||initialDraft);
  },[initialDraft,chat.loading,chat.thread?.thread_id,storage]);
  useEffect(()=>{
    const root=panel.current;const composer=root?.querySelector<HTMLElement>('.chat-composer');if(!root||!composer)return;
    const resize=()=>{const style=getComputedStyle(composer);root.style.setProperty('--chat-composer-space',Math.ceil(composer.getBoundingClientRect().height+parseFloat(style.marginTop)+parseFloat(style.marginBottom)+24)+'px')};
    const observer=new ResizeObserver(resize);observer.observe(composer);resize();return()=>observer.disconnect();
  },[!!composerNotice]);
  useEffect(()=>setRefs(previous=>[...new Set([...previous,...ticketRefs])]),[ticketRefs]);
  useEffect(()=>{sessionStorage.setItem(`finops-chat-draft:${storage}`,draft)},[draft,storage]);
  useEffect(()=>{sessionStorage.setItem(`finops-chat-refs:${storage}`,JSON.stringify(refs))},[refs,storage]);
  const openedThread=useRef<string|undefined>(undefined);
  useLayoutEffect(()=>{
    const box=viewport.current;if(!box||hidden)return;
    if(openedThread.current!==chat.thread?.thread_id){openedThread.current=chat.thread?.thread_id;pinned.current=true}
    if(pinned.current)box.scrollTop=box.scrollHeight;
  },[chat.thread?.thread_id,chat.thread?.messages.length,chat.thread?.pending.length,chat.thread?.streaming?.content,chat.thread?.activity.length,chat.thread?.working_tools?.length,hidden]);
  const blocked=chat.thread?.archived||chat.busy||chat.loading||chat.thread?.status==='waiting'||chat.thread?.status==='error';const messages=chat.thread?.messages||[];
  const suggestions=agentId==='v2-finops-report-orchestrator'?['¿Qué debo priorizar hoy?','Revisa qué tickets necesitan atención','Consulta a un especialista para investigar un hallazgo']:agentId==='orchestrator'?['¿Qué debo hacer hoy?','Revisa qué tickets necesitan validarse','Explícame cómo aplicar una optimización']:[`¿Qué debería revisar hoy en ${agent.name.toLowerCase()}?`,'Explica tu aporte al informe seleccionado','Ayúdame a validar los tickets de tu especialidad'];
  return <div ref={panel} className="chat-panel embedded-chat" hidden={hidden} aria-label={`Chat con ${agent.name}`}><header className="chat-heading"><div><h2 title={messages.find(message=>message.role==='human')?.content}>{title||messages.find(message=>message.role==='human')?.content||chat.thread?.ticket_threads?.[0]?.initial_message||'Nueva conversación'}</h2>{(chat.busy||chat.thread?.status==='waiting')&&<span>{chat.busy?'Revisando tu consulta…':'Tu decisión está pendiente'}</span>}</div>{headerAction}</header><div ref={viewport} onScroll={e=>{const box=e.currentTarget;pinned.current=box.scrollHeight-box.scrollTop-box.clientHeight<100}} className="chat-messages" aria-live="polite" aria-relevant="additions text">{chat.thread?.archived&&<p className="chat-archived" role="status">Conversación archivada. Restáurala desde Tu equipo para continuar.</p>}{!messages.length&&!chat.thread?.ticket_threads?.length&&!conversationKey&&<div className="chat-welcome"><MessageCircle size={25}/><h3>{(agentId==='orchestrator'||agentId==='v2-finops-report-orchestrator')?'¿Qué resolvemos hoy?':`Hablemos de ${agent.name.toLowerCase()}`}</h3><p>{(agentId==='orchestrator'||agentId==='v2-finops-report-orchestrator')?'Prioriza tu día, valida hallazgos y convierte recomendaciones en acciones.':'Consulta los datos, revisa mis conclusiones y definamos el siguiente paso.'}</p>{suggestions.map(text=><button key={text} disabled={!!blocked} onClick={()=>setDraft(text)}>{text}</button>)}</div>}{chat.thread&&<ChatTimeline ticketThreads={ticketThreads} name={agent.name} thread={chat.thread} busy={chat.busy} onTicket={onTicket}/>}{chat.thread?.report_run_id&&<ChatReportJob clientId={clientId} runId={chat.thread.report_run_id} onOpen={onOpenReports}/>}{chat.thread?.pending_report&&<ChatReportRepeat prompt={chat.thread.pending_report} busy={chat.busy} onDecision={decision=>void chat.resume(decision)} onOpen={onOpenReports}/>}{chat.thread?.pending.length?<ChatPlan plans={chat.thread.pending} busy={chat.busy||!!chat.thread?.archived} onDecision={decision=>void chat.resume(decision)} onTicket={onTicket}/>:null}{(chat.error||chat.thread?.error)&&<div className="chat-error" role="alert"><p>{chat.thread?.error||chat.error}</p>{chat.thread?.status==='error'&&!chat.thread?.archived&&<button className="secondary" onClick={()=>void chat.retry()}>Reanudar consulta</button>}</div>}{chat.thread?.status==='cancelled'&&<p role="status" className="chat-archived">Respuesta detenida. Conservamos los avances; puedes enviar otro mensaje.</p>}<div ref={end}/></div>{composerNotice?<div className="chat-composer chat-composer-notice">{composerNotice}</div>:<ChatComposer onStop={chat.thread?.status==='running'?()=>void chat.stop():undefined} stopping={chat.stopping} tickets={tickets} refs={refs} setRefs={setRefs} disabled={!!blocked} onSend={chat.send} onTicket={onTicket} draft={draft} setDraft={setDraft}/>}</div>;
}
