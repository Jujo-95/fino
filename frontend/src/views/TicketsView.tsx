import {useLocation,useNavigate} from 'react-router-dom';
import {useUrlState} from '../hooks/useUrlState';
import {TicketWorkbench} from '../components/TicketWorkbench';
export {TicketDetails as TicketDialog} from '../components/TicketDetails';
import type {ReactNode} from 'react';
import {useState,useRef} from 'react';
import type {Ticket,Overview} from '../types';
import type {ActionDetails,Consulting} from '../consultingTypes';
import {taskPhase,taskTopic} from '../taskPresentation';
import {TaskToolbar,type TaskSort} from '../components/TaskToolbar';
import {TaskRow} from '../components/TaskRow';
import {TicketListLayout} from '../components/TicketListLayout';
import {TaskModeSwitch,type TaskMode} from '../components/TaskModeSwitch';
import {TaskProgressList} from '../components/TaskProgressList';
import {useRecentResolutions} from '../hooks/useRecentResolutions';
import {useTicketThreads} from '../hooks/useTicketThreads';
import {taskStateLabel,taskState,isActiveTask,isDeferred} from '../ticketLifecycle';
export function TicketsView({onModeChange,mode,tickets,clientId,onRefresh,onAsk,overview,consulting,onSetup}:{onModeChange:(mode:TaskMode)=>void;mode:TaskMode;tickets:Ticket[];clientId:string;onRefresh:()=>void;onAsk:(ticket:Ticket,draft?:string)=>void;overview?:Overview;consulting?:Consulting|null;onSetup?:()=>void}){
  const location=useLocation();const navigate=useNavigate();
  const [selectedId]=useUrlState('ticket');const selected=tickets.find(t=>t.ticket_id===selectedId)||null;const [query,setQuery]=useUrlState('query','');const [all,setAll]=useState(true);const [phase,setPhase]=useUrlState('phase','Todas');const [topic,setTopic]=useUrlState('topic','Todos');const [priority,setPriority]=useUrlState('priority','Todas');const [sort,setSort]=useState<TaskSort>('recommended');
  const [threadTicket]=useUrlState('thread');
  const [draft,setDraft]=useState<{text:string;nonce:number}>();
  const [state,setState]=useUrlState('state','all');const progressOpen=mode==='focus';
  void onAsk;
  const recentResolved=useRecentResolutions(clientId,tickets);
  function changeMode(next:TaskMode){setDraft(undefined);setQuery('');setPhase('Todas');setTopic('Todos');setPriority('Todas');setState('all');setAll(true);onModeChange(next)}
  const opener=useRef<HTMLElement|null>(null);
  const {summaries}=useTicketThreads(clientId);
  function inspect(ticket:Ticket,text?:string){const params=new URLSearchParams(location.search);params.set('thread',ticket.ticket_id);params.delete('ticket');setDraft(text?{text,nonce:Date.now()}:undefined);opener.current=document.activeElement as HTMLElement;navigate({pathname:'/clients/'+encodeURIComponent(clientId)+'/tickets/'+encodeURIComponent(ticket.ticket_id),search:params.toString()})}
  function close(restore=true){const params=new URLSearchParams(location.search);if(selectedId)params.set('thread',selectedId);params.delete('ticket');navigate({pathname:'/clients/'+encodeURIComponent(clientId)+'/tickets',search:params.toString()});if(restore)requestAnimationFrame(()=>opener.current?.focus())}
  const matching=tickets.filter(t=>(!isDeferred(t)||all)&&(state==='all'||(state==='active'?isActiveTask(t)||recentResolved.has(t.ticket_id)||(all&&isDeferred(t))||summaries.some(s=>s.ticket_id===t.ticket_id&&(s.unread_count||0)>0):taskState(t)===state))&&(topic==='Todos'||taskTopic(t)===topic)&&(priority==='Todas'||t.severity===priority)&&(t.title+' '+t.ticket_id+' '+t.service_name).toLowerCase().includes(query.toLowerCase()));
  const ranks=new Map(consulting?.agenda.actions.map((t,i)=>[t.ticket_id,i]));const blocked=(t:Ticket)=>((t as Ticket&{action_details?:ActionDetails}).action_details?.dependencies||[]).some(id=>!['IMPLEMENTED','RESOLVED'].includes(tickets.find(x=>x.ticket_id===id)?.status||''));
  const filtered=matching.filter(t=>phase==='Todas'||taskPhase(t)===phase);const counts=Object.fromEntries(['Todas','Informar','Optimizar','Operar'].map(p=>[p,matching.filter(t=>p==='Todas'||taskPhase(t)===p).length]));
  const severity:Record<string,number>={CRITICAL:0,HIGH:1,MEDIUM:2,LOW:3};
  filtered.sort((a,b)=>{const order=sort==='priority'?(severity[a.severity]??4)-(severity[b.severity]??4):sort==='recent'?b.updated_at_utc.localeCompare(a.updated_at_utc):sort==='impact'?Number(a.estimated_monthly_impact_usd===null)-Number(b.estimated_monthly_impact_usd===null)||(b.estimated_monthly_impact_usd||0)-(a.estimated_monthly_impact_usd||0):(ranks.get(a.ticket_id)??999)-(ranks.get(b.ticket_id)??999);return order||a.ticket_id.localeCompare(b.ticket_id)});
  const current=selected&&(tickets.find(t=>t.ticket_id===selected.ticket_id)||selected);
  function workspace(list:ReactNode,defaultTicket?:Ticket){
    const active=current||tickets.find(t=>t.ticket_id===threadTicket)||defaultTicket;
    return active?<TicketWorkbench ticket={active} listContent={list} showDetail={!!current} tickets={tickets} clientId={clientId} overview={overview} consulting={consulting} draftRequest={draft} onBack={close} onRefresh={onRefresh} onSelect={inspect} onSetup={onSetup}/>:list;
  }
  if(selectedId&&!selected)return <p role="alert">Este ticket no existe o no está disponible para este cliente.</p>;
  const heading=<div className="tasks-column-heading"><h1 tabIndex={-1}>Tus tareas</h1><TaskModeSwitch mode={mode} onChange={changeMode}/></div>;
  const listTicket=current||filtered.find(t=>t.ticket_id===threadTicket)||filtered[0];
  const toolbar=<TaskToolbar state={state} onState={setState} phase={phase} onPhase={setPhase} counts={counts} query={query} onQuery={setQuery} topics={[...new Set(tickets.map(taskTopic))]} topic={topic} onTopic={setTopic} priority={priority} onPriority={setPriority} all={all} onAll={setAll} sort={sort} onSort={setSort}/>;
  const rows=<div className="task-list" id="tasks-results" role="tabpanel" aria-labelledby={'tasks-tab-'+phase}>{filtered.map(ticket=><TaskRow key={ticket.ticket_id} ticket={ticket} summary={summaries.find(s=>s.ticket_id===ticket.ticket_id)} blocked={blocked(ticket)} status={taskStateLabel(ticket)} selected={ticket.ticket_id===listTicket?.ticket_id} onInspect={()=>inspect(ticket)} onChat={()=>inspect(ticket)}/>)}{!filtered.length&&<p className="task-list-empty">No hay tareas con estos filtros. Puedes revisar otros estados o consultar a Fino.</p>}</div>;
  return <div className="ticket-task-layout"><div className="tasks-feed">{progressOpen&&consulting?.agenda.progress?<TaskProgressList onReturn={()=>setDraft(undefined)} workspace={workspace} header={heading} value={consulting.agenda.progress} tickets={tickets} summaries={summaries} clientId={clientId} onRefresh={onRefresh} onInspect={inspect} onChat={inspect} blocked={blocked}/>:<TicketListLayout header={heading} toolbar={toolbar} list={rows}>{listTicket?<TicketWorkbench persistentThread ticket={listTicket} tickets={tickets} clientId={clientId} overview={overview} consulting={consulting} draftRequest={draft} onBack={close} onRefresh={onRefresh} onSelect={inspect} onSetup={onSetup}/>:<p className="ticket-list-empty-detail">No hay tickets para mostrar con estos filtros.</p>}</TicketListLayout>}</div></div>;
}
