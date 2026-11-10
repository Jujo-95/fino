import {Send} from 'lucide-react';
import type {Ticket} from '../types';
import {taskStateLabel,ticketActions} from '../ticketLifecycle';
type Props={ticket:Ticket;status:string;onStatus:(value:string)=>void;note:string;onNote:(value:string)=>void;until:string;onUntil:(value:string)=>void;busy:boolean;error:string;onSave:(event:React.FormEvent)=>void};
export function TicketNoteEditor({ticket,status,onStatus,note,onNote,until,onUntil,busy,error,onSave}:Props){
  return <form className="ticket-note-editor" onSubmit={onSave}>
    <label className="sr-only" htmlFor={'ticket-note-'+ticket.ticket_id}>Añadir nota al ticket</label>
    <textarea id={'ticket-note-'+ticket.ticket_id} required maxLength={4000} value={note} onChange={e=>onNote(e.target.value)} placeholder={status==='FALSE_POSITIVE'?'Explica por qué el hallazgo era incorrecto o no aplicaba…':'Añade una nota o registra lo que cambió…'} rows={4}/>
    {status==='SNOOZED'&&<label>Volver a revisar el<input required type="date" min={new Date().toLocaleDateString('en-CA')} value={until} onChange={e=>onUntil(e.target.value)}/></label>}
    {status==='IMPLEMENTED'&&<small>La acción quedará registrada; su resultado seguirá pendiente de verificación.</small>}
    {error&&<p role="alert" className="error">{error}</p>}
    <footer><label><span className="sr-only">Acción al guardar</span><select value={status} onChange={e=>onStatus(e.target.value)}><option value={ticket.status}>Añadir nota · {taskStateLabel(ticket)}</option>{ticketActions.filter(([value])=>value!==ticket.status).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><button className="primary" disabled={busy||!note.trim()} type="submit"><Send size={14}/>{busy?'Guardando…':'Guardar'}</button></footer>
  </form>;
}
