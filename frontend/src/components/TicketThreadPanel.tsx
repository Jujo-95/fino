import {useEffect,useRef,useState} from 'react';
import {X,SquareCheck} from 'lucide-react';
import {ticketTitle} from '../presentation';
import type {Ticket} from '../types';
import {useChat} from '../hooks/useChat';
import {ChatPanel} from './ChatPanel';
import {taskState} from '../ticketLifecycle';
import {useTicketReview} from '../hooks/useTicketReview';
export function TicketThreadPanel({ticket,tickets,clientId,onChanged,onClose,onTicket,parentThreadId,draftRequest,persistent=false}:{persistent?:boolean;draftRequest?:{text:string;nonce:number};ticket:Ticket;tickets:Ticket[];clientId:string;onChanged:()=>void;onClose:()=>void;onTicket:(id:string)=>void;parentThreadId?:string}){
  const resolved=taskState(ticket)==='resolved';const [resumed,setResumed]=useState(false);
  useEffect(()=>setResumed(false),[ticket.ticket_id,resolved]);
  const close=useRef<HTMLButtonElement>(null);
  useTicketReview(clientId,ticket.ticket_id,onChanged);
  const agentId='v2-finops-report-orchestrator';
  const chat=useChat(clientId,onChanged,agentId,undefined,ticket.ticket_id,parentThreadId);
  useEffect(()=>{const frame=requestAnimationFrame(()=>close.current?.focus({preventScroll:true}));return()=>cancelAnimationFrame(frame)},[]);
  const prompt=`Guíame paso a paso para resolver **${ticket.ticket_id}**: ${ticketTitle(ticket)}. Revisa sus requisitos e indicadores antes de recomendar cambios.`;
  const notice=resolved&&!resumed&&!chat.busy?<div className="resolved-thread-notice"><SquareCheck size={18}/><div><strong>Este ticket está resuelto</strong><p>¿Quieres retomar la conversación?</p><small>El ticket conservará su estado resuelto.</small></div><button className="secondary" onClick={()=>setResumed(true)}>Retomar conversación</button></div>:undefined;
  const heading='Hilo — '+ticket.ticket_id+': '+ticketTitle(ticket);
  return <aside className="ticket-thread-panel" aria-label={'Hilo de '+ticket.ticket_id} onKeyDown={e=>{if(!persistent&&e.key==='Escape'&&!e.defaultPrevented){e.stopPropagation();onClose()}}}><ChatPanel composerNotice={notice} key={clientId+ticket.ticket_id} chat={chat} clientId={clientId} agentId={agentId} tickets={tickets} ticketRefs={[ticket.ticket_id]} conversationKey={'ticket:'+ticket.ticket_id} initialDraft={draftRequest?.text||prompt} draftRequest={draftRequest} title={heading} onTicket={onTicket} headerAction={persistent?undefined:<button ref={close} className="icon-button" onClick={onClose} title="Cerrar hilo; la ejecución continúa" aria-label="Cerrar hilo"><X size={18}/></button>}/></aside>;
}
