import {MessageSquare} from 'lucide-react';
import type {Ticket} from '../types';
export function TicketActivity({ticket}:{ticket:Ticket}){
  const entries=ticket.note_history?.length?ticket.note_history:ticket.resolution_note?[{text:ticket.resolution_note,actor:'',at:''}]:[];
  return <section className="ticket-activity" aria-label="Actividad del ticket">{entries.length?[...entries].reverse().map((entry,index)=><article className="ticket-activity-entry" key={entry.at+':'+index}>
    <span className="ticket-activity-icon" aria-hidden="true"><MessageSquare size={15}/></span>
    <div><header><strong>{entry.actor==='local-user'?'Tu equipo':entry.actor==='system'?'Fino':'Nota registrada'}</strong>{entry.at&&<time dateTime={entry.at}>{new Date(entry.at).toLocaleString('es',{dateStyle:'medium',timeStyle:'short'})}</time>}</header><p>{entry.text}</p></div>
  </article>):<p className="ticket-activity-empty">Aún no hay notas. Registra lo que descubriste o conversa con Fino.</p>}{ticket.evidence_summary&&<article className="ticket-activity-entry"><span className="ticket-activity-icon" aria-hidden="true"><MessageSquare size={15}/></span><div><header><strong>Contexto de la tarea</strong></header><p>{ticket.evidence_summary}</p></div></article>}</section>;
}
