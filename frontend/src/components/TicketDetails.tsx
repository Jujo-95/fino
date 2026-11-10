import {useState,useEffect,useRef} from 'react';
import {X,ArrowUpRight,MessageCircle,BarChart3,FileSearch,ListChecks,Clock3} from 'lucide-react';
import {TicketActivity} from './TicketActivity';
import {TicketNoteEditor} from './TicketNoteEditor';
import {TicketContributors} from './TicketContributors';
import {TicketWorkPlan} from './TicketWorkPlan';
import {Disclosure} from './Disclosure';
import {api} from '../api';
import {money,type Ticket,type Overview} from '../types';
import {ticketTitle,severityLabels} from '../presentation';
import type {Consulting} from '../consultingTypes';
import {TicketFollowup} from './TicketFollowup';
import {TicketIndicators} from './TicketIndicators';
import {TicketRequirement} from './TicketRequirement';
import {useTicketReview} from '../hooks/useTicketReview';
import {taskStateLabel} from '../ticketLifecycle';
import {TicketNarrative} from './TicketNarrative';
export function TicketDetails({ticket:t,clientId,onClose,onSaved,onAsk,overview,consulting,onSetup,onChanged,sourceTicket,inline=false}:{inline?:boolean;sourceTicket?:Ticket;ticket:Ticket;clientId:string;onClose:()=>void;onSaved:()=>void;onAsk:()=>void;overview?:Overview;consulting?:Consulting|null;onSetup?:()=>void;onChanged?:()=>void}){
  const [status,setStatus]=useState(t.status);const [note,setNote]=useState('');const [until,setUntil]=useState(t.snoozed_until||'');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const [tab,setTab]=useState<'activity'|'details'>('activity');const [saved,setSaved]=useState(false);
  useTicketReview(clientId,t.ticket_id,onChanged);
  useEffect(()=>setStatus(t.status),[t.status]);
  const heading=useRef<HTMLHeadingElement>(null);const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{if(inline)return;const modal=dialog.current;modal?.showModal();heading.current?.focus();return()=>modal?.close()},[inline]);
  async function save(e:React.FormEvent){e.preventDefault();setBusy(true);try{await api(`/clients/${clientId}/tickets/${t.ticket_id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status,resolution_note:note,...(status==='SNOOZED'?{snoozed_until:until}:{})})});setNote('');setError('');setSaved(true);onSaved();}catch(error){setError((error as Error).message);}finally{setBusy(false);}}
  const content=<section className="ticket-modal-content ticket-record">
    <header className="ticket-record-header"><div className="ticket-record-title"><h2 id="ticket-dialog-title" ref={heading} tabIndex={-1}>{ticketTitle(t)}</h2><button className="icon-button" onClick={onClose} aria-label="Cerrar detalle"><X size={17}/></button></div><div className="ticket-record-meta"><span>{t.ticket_id}</span><span className="ticket-record-status">{taskStateLabel(t)}</span><span>{severityLabels[t.severity]||t.severity}</span></div><div className="ticket-record-byline"><time dateTime={t.updated_at_utc}>Actualizado {new Date(t.updated_at_utc).toLocaleDateString('es',{dateStyle:'medium'})}</time><TicketContributors ticket={t} compact/></div></header>
    <div className="ticket-record-toolbar"><div className="ticket-record-tabs" role="tablist" aria-label="Contenido del ticket" onKeyDown={e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();const next=tab==='activity'?'details':'activity';setTab(next);e.currentTarget.querySelector<HTMLButtonElement>('[data-tab="'+next+'"]')?.focus()}}}>{([['activity','Actividad'],['details','Detalle']] as const).map(([key,label])=><button key={key} data-tab={key} id={'ticket-tab-'+key} role="tab" aria-selected={tab===key} aria-controls={'ticket-panel-'+key} tabIndex={tab===key?0:-1} onClick={()=>setTab(key)}>{label}</button>)}</div><button className="ticket-record-chat" onClick={onAsk} title="Conversar con Fino"><MessageCircle size={15}/><span>Fino</span></button></div>
    <div className="ticket-record-body" role="tabpanel" id={'ticket-panel-'+tab} aria-labelledby={'ticket-tab-'+tab}>
    {tab==='activity'?<><TicketNoteEditor ticket={t} status={status} onStatus={setStatus} note={note} onNote={setNote} until={until} onUntil={setUntil} busy={busy} error={error} onSave={save}/>{saved&&<p className="ticket-note-saved" role="status">Nota guardada.</p>}<TicketActivity ticket={t}/></>:<>
      <TicketNarrative ticket={t}/>
      <Disclosure title="Indicadores y requisitos" icon={<BarChart3 size={15}/>}><TicketIndicators ticket={t} overview={overview} consulting={consulting}/><TicketRequirement ticket={t} data={consulting} clientId={clientId} onChanged={onChanged||onSaved} onSetup={onSetup}/></Disclosure>
      {t.followup&&<Disclosure title="Seguimiento y verificación" icon={<Clock3 size={15}/>}><TicketFollowup plan={t.followup} observation={consulting?.agenda.monitoring?.find(o=>o.ticket_id===t.ticket_id)}/></Disclosure>}
      <Disclosure title="Evidencia del hallazgo" icon={<FileSearch size={15}/>}><p>{t.evidence_summary}</p>{t.estimated_monthly_impact_usd!==null&&t.estimated_monthly_impact_usd>0&&<p>{money(t.estimated_monthly_impact_usd)}/mes de impacto estimado</p>}<a href={t.capability_citation_url} target="_blank" rel="noreferrer">Guía FinOps Foundation <ArrowUpRight size={13}/></a></Disclosure>
      <Disclosure title="Plan de acción" icon={<ListChecks size={15}/>}><TicketWorkPlan ticket={sourceTicket||t} clientId={clientId}/></Disclosure>
    </>}
    </div>
  </section>;
  if(inline)return content;
  return <dialog ref={dialog} className="ticket-modal" aria-labelledby="ticket-dialog-title" onCancel={e=>{e.preventDefault();onClose()}} onClick={e=>{if(e.target===e.currentTarget){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose()}}}>{content}</dialog>;
}
