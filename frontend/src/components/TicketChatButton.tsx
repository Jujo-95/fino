import {MessageCircle,LoaderCircle} from 'lucide-react';
import type {TicketChatSummary} from '../chatTypes';
export function TicketChatButton({ticketId,summary,onOpen,expanded=false,started=false,prominent=false,compact=false}:{compact?:boolean;prominent?:boolean;ticketId:string;summary?:TicketChatSummary;onOpen:()=>void;expanded?:boolean;started?:boolean}){
  const active=summary?.status==='running';const waiting=summary?.status==='waiting';const unread=summary?.unread_count||0;
  const label=active?'Respondiendo…':unread?'Respuesta sin leer':waiting?'Revisar propuesta':summary?.status==='error'?'Reanudar':summary?.started||started||prominent?'Continuar':'Chatear';
  return <button className={'task-chat-button '+(compact?'compact-ticket-chat ':'')+(prominent?'primary task-chat-primary ':'')+(unread?'has-unread':'')} onClick={onOpen} aria-expanded={expanded} aria-label={label+' sobre '+ticketId}>{active?<LoaderCircle size={15} className="spin"/>:<MessageCircle size={15}/>}<span>{label}</span>{unread>0?<small className="chat-unread-count" aria-label={unread+' respuestas sin leer'}>{unread}</small>:!!summary?.reply_count&&<small>{summary.reply_count}{!compact&&' '+(summary.reply_count===1?'respuesta':'respuestas')}</small>}</button>;
}
