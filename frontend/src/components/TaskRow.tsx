import {Link,useLocation} from 'react-router-dom';
import type {MouseEvent} from 'react';
import {SquareCheck,Square,Clock3,LockKeyhole,Minus,ChevronUp,ChevronDown,CircleAlert} from 'lucide-react';
import {TicketChatButton} from './TicketChatButton';
import type {Ticket} from '../types';
import type {TicketChatSummary} from '../chatTypes';
import {AgentAvatar} from './AgentAvatar';
import {chatAgents} from '../auditTypes';
import {ticketTitle,severityLabels} from '../presentation';
import {taskState,isDeferred} from '../ticketLifecycle';
import {taskNextStep} from '../taskGuidance';
const recommended:Record<string,string>={'forecasting':'v2-forecast-estimation-analyst','usage-optimization':'v2-platform-sre-cost-lead','data-ingestion':'v2-cloud-billing-analyst','allocation':'v2-allocation-policy-architect','anomaly-management':'v2-budget-anomaly-operator','budgeting':'v2-budget-anomaly-operator','rate-optimization':'v2-commitment-discount-strategist'};
export function TaskRow({ticket,summary,blocked,status,onInspect,onChat,selected,nextStep=false}:{nextStep?:boolean;ticket:Ticket;summary?:TicketChatSummary;blocked:boolean;status:string;onInspect:()=>void;onChat:()=>void;selected:boolean}){
  const location=useLocation();const params=new URLSearchParams(location.search);params.set('thread',ticket.ticket_id);params.delete('ticket');
  const href=location.pathname.split('/').slice(0,3).join('/')+'/tickets/'+encodeURIComponent(ticket.ticket_id)+'?'+params.toString();
  function open(event:MouseEvent<HTMLAnchorElement>){if(event.button===0&&!event.metaKey&&!event.ctrlKey&&!event.shiftKey&&!event.altKey){event.preventDefault();onInspect()}}
  const contributors=[...new Set((ticket.contributors||[]).map(c=>c.agent_id))];
  const people=contributors.length?contributors:[recommended[ticket.capability]||'v2-finops-report-orchestrator'];
  const state=taskState(ticket);const completed=state==='resolved';const locked=blocked&&state==='todo';
  const Icon=completed?SquareCheck:locked?LockKeyhole:state==='monitoring'?Clock3:state==='dismissed'?Minus:Square;
  const Priority=ticket.severity==='CRITICAL'?CircleAlert:ticket.severity==='HIGH'?ChevronUp:ticket.severity==='LOW'?ChevronDown:Minus;
  const indicator=completed?'Completada':locked?'Bloqueada por requisitos':state==='monitoring'?'Esperando verificación':state==='dismissed'?'Descartada':'Pendiente';
  const marker=<span className="task-check" role="img" aria-label={indicator} title={indicator}><Icon size={14} strokeWidth={1.8}/></span>;
  return <div className={'task-row ticket-list-row '+(selected?'thread-selected':'')} data-complete={completed} data-blocked={locked} data-state={state} data-next-step={nextStep}>
    <Link to={href} className="task-open task-row-heading" onClick={open} title={taskNextStep(ticket)}><span className="task-copy"><strong>{nextStep&&<span className="next-step-chip">Siguiente paso</span>}{ticketTitle(ticket)}</strong></span><time dateTime={ticket.updated_at_utc} title={'Actualizado '+new Date(ticket.updated_at_utc).toLocaleString('es')}>{new Date(ticket.updated_at_utc).toLocaleDateString('es',{day:'numeric',month:'short'})}</time></Link>
    <div className="task-row-footer"><Link to={href} className="task-identity" onClick={open} aria-label={'Abrir '+ticket.ticket_id}>{marker}<span>{ticket.ticket_id}</span></Link><div className="task-row-actions">
      <span className="task-status">{isDeferred(ticket)?'Pospuesta':locked?'Requisitos pendientes':status}</span>
      <span className={'task-priority-icon '+ticket.severity} role="img" aria-label={'Prioridad '+(severityLabels[ticket.severity]||ticket.severity)} title={'Prioridad '+(severityLabels[ticket.severity]||ticket.severity)}><Priority size={14}/></span>
      <span className="task-team" aria-label={contributors.length?'Equipo que aportó':'Especialista recomendado'}>{people.slice(0,2).map(id=><span key={id} title={(contributors.length?'Aportó: ':'Recomendado: ')+(chatAgents.find(a=>a.key===id)?.name||id)}><AgentAvatar agent={id}/></span>)}</span>
      <TicketChatButton compact prominent={nextStep} ticketId={ticket.ticket_id} summary={summary} expanded={selected} onOpen={onChat}/>
    </div></div>
  </div>;
}
