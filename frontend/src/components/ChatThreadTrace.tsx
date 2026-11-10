import type {TicketThreadTrace,TicketChatSummary} from '../chatTypes';
import {ChatContent} from './ChatContent';
import {TicketChatButton} from './TicketChatButton';
export function ChatThreadTrace({trace,summary,onTicket}:{trace:TicketThreadTrace;summary?:TicketChatSummary;onTicket:(id:string)=>void}){
  return <article className="chat-message human chat-thread-trace" aria-label={'Hilo de '+trace.ticket_id}><small>Tú · Hilo</small><ChatContent text={trace.initial_message} onTicket={onTicket}/><TicketChatButton ticketId={trace.ticket_id} summary={summary} started onOpen={()=>onTicket(trace.ticket_id)}/></article>;
}
