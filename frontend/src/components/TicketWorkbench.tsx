import {useRef} from 'react';
import type {ReactNode} from 'react';
import {ArrowLeft} from 'lucide-react';
import type {Ticket,Overview} from '../types';
import type {Consulting} from '../consultingTypes';
import {TicketDetails} from './TicketDetails';
import {TicketThreadPanel} from './TicketThreadPanel';
import {ResizeHandle} from './ResizeHandle';
type Props={persistentThread?:boolean;listContent?:ReactNode;showDetail?:boolean;ticket:Ticket;tickets:Ticket[];clientId:string;overview?:Overview;consulting?:Consulting|null;draftRequest?:{text:string;nonce:number};onBack:()=>void;onRefresh:()=>void;onSelect:(ticket:Ticket)=>void;onSetup?:()=>void};
export function TicketWorkbench({ticket,tickets,clientId,overview,consulting,draftRequest,onBack,onRefresh,onSelect,onSetup,listContent,showDetail=true,persistentThread=false}:Props){
  const root=useRef<HTMLDivElement>(null);
  const widths={['--ticket-detail-width' as string]:Math.max(240,Math.min(580,Number(localStorage.getItem('finops-layout:ticket-details'))||320))+'px'};
  function focusChat(){root.current?.querySelector<HTMLTextAreaElement>('.ticket-thread-panel textarea')?.focus()}
  return <div className="ticket-workbench chat-first-console">
    <div className="ticket-workbench-columns with-ticket-thread" ref={root} style={widths}>
      <section className="ticket-workbench-details" aria-label={showDetail?'Detalle de '+ticket.ticket_id:'Tus tickets'}>{showDetail?<><header className="ticket-workbench-heading"><button className="text-button" onClick={onBack}><ArrowLeft size={15}/>Volver a las tareas</button></header><div className="ticket-detail-scroll"><TicketDetails key={ticket.ticket_id} inline ticket={ticket} sourceTicket={ticket.workflow_key?.startsWith('verification:')?tickets.find(t=>t.ticket_id===ticket.workflow_key?.split(':')[1]):undefined} clientId={clientId} overview={overview} consulting={consulting} onClose={onBack} onAsk={focusChat} onSaved={onRefresh} onChanged={onRefresh} onSetup={onSetup}/></div></>:listContent}</section>
      <ResizeHandle root={root} variable="--ticket-detail-width" storageKey="finops-layout:ticket-details" label="Ancho del detalle del ticket" min={240} max={580} fallback={320}/>
      <TicketThreadPanel persistent={persistentThread||!!listContent} key={clientId+ticket.ticket_id} ticket={ticket} tickets={tickets} clientId={clientId} draftRequest={draftRequest} onChanged={onRefresh} onClose={onBack} onTicket={id=>{const target=tickets.find(t=>t.ticket_id===id);if(target)onSelect(target)}}/>
    </div>
  </div>;
}
