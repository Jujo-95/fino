import type {Ticket} from '../types';
import {Info,ArrowRight} from 'lucide-react';
import {taskNextStep,missingInputHelp} from '../taskGuidance';
export function TicketNarrative({ticket}:{ticket:Ticket}){
  const missing=ticket.ticket_kind==='onboarding';
  return <section className="ticket-narrative" aria-label="Cómo avanzar con esta tarea">
    <div className="ticket-context-block"><h3><Info size={14}/>{missing?'Por confirmar':'Hallazgo'}</h3><p>{ticket.evidence_summary}</p>
    {ticket.status==='REJECTED'&&<p>Una acción anterior se canceló. La tarea sigue pendiente hasta revisar el hallazgo.</p>}
    {ticket.status==='IMPLEMENTED'&&(!ticket.ticket_kind||ticket.ticket_kind==='finding')&&<p>La acción está registrada. Falta comprobar su resultado con datos posteriores.</p>}
    </div><div className="ticket-action-block"><h3><ArrowRight size={14}/>Siguiente acción</h3><p>{taskNextStep(ticket)}</p>
    {missing&&<p className="ticket-source-hint">{missingInputHelp(ticket)}</p>}</div>
  </section>;
}
