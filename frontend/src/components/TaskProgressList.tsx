import {useUrlState} from '../hooks/useUrlState';
import {useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {ResizeHandle} from './ResizeHandle';
import {useTaskHeaderHeight} from '../hooks/useTaskHeaderHeight';
import type {TaskProgress as Progress,ProgressGoal} from '../progressTypes';
import type {Ticket} from '../types';
import type {TicketChatSummary} from '../chatTypes';
import {taskStateLabel,isActiveTask} from '../ticketLifecycle';
import {TaskRow} from './TaskRow';
import {ObjectiveStepper} from './ObjectiveStepper';
import {nextStepQuestion} from '../nextStepQuestion';
import {taskNextStep} from '../taskGuidance';
import {orderFocusSteps} from '../focusTaskOrder';
import {api} from '../api';
type Props={onReturn?:()=>void;workspace:(list:ReactNode,defaultTicket?:Ticket)=>ReactNode;header:ReactNode;value:Progress;tickets:Ticket[];summaries:TicketChatSummary[];clientId:string;onRefresh:()=>void;onInspect:(ticket:Ticket)=>void;onChat:(ticket:Ticket,draft?:string)=>void;blocked:(ticket:Ticket)=>boolean};
export function TaskProgressList({onReturn,workspace,header,value,tickets,summaries,clientId,onRefresh,onInspect,onChat,blocked}:Props){
  const root=useRef<HTMLDivElement>(null);
  useTaskHeaderHeight(root);
  const widths={['--steps-width' as string]:Math.max(240,Math.min(520,Number(localStorage.getItem('finops-layout:steps'))||341))+'px'};
  const [confirm,setConfirm]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const [selected,setSelected]=useUrlState('goal',value.objective?.id||'');
  const goal=value.objectives.find(g=>g.id===selected)||value.objective||value.objectives[0];
  async function change(path:string,body?:object){
    setBusy(true);setError('');
    try{await api('/clients/'+clientId+'/consulting/progress/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});setConfirm('');onRefresh()}
    catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  function row(id:string){
    const ticket=tickets.find(t=>t.ticket_id===id);if(!ticket)return null;
    return <TaskRow nextStep={id===nextTicketId} key={id} ticket={ticket} summary={summaries.find(s=>s.ticket_id===id)} blocked={blocked(ticket)} status={taskStateLabel(ticket)} selected={false} onInspect={()=>onInspect(ticket)} onChat={()=>onChat(ticket,id===nextTicketId?nextStepQuestion(ticket):undefined)}/>;
  }
  function groupBlocked(group:ProgressGoal){
    const pending=group.steps.filter(s=>!s.excluded&&s.state==='todo').map(s=>tickets.find(t=>t.ticket_id===s.ticket_id)).filter((t):t is Ticket=>!!t);
    return pending.length>0&&pending.every(blocked);
  }
  const orderedSteps=orderFocusSteps(goal?.steps||[],tickets,value.next_action?.ticket_id,blocked);
  const nextTicketId=orderedSteps.find(step=>{const ticket=tickets.find(t=>t.ticket_id===step.ticket_id);return !step.excluded&&ticket&&isActiveTask(ticket)&&!blocked(ticket)})?.ticket_id;
  const nextTicket=tickets.find(t=>t.ticket_id===nextTicketId);
  return <div ref={root} style={widths} id="task-progress-list" className="task-list task-progress-list">
    <aside className="focus-steps-column" aria-label="Objetivos y modo de tareas">{header}
    <ObjectiveStepper goals={value.objectives} selected={goal?.id} onSelect={id=>{setSelected(id);setConfirm('');onReturn?.()}} isBlocked={groupBlocked} activeContent={<div className="objective-step-context">{nextTicket?<><p><strong>Siguiente paso: </strong>{nextTicket.title}</p><small>{taskNextStep(nextTicket)}</small><button type="button" className="primary" onClick={()=>onChat(nextTicket,nextStepQuestion(nextTicket))}>Continuar con Fino</button></>:<p>{goal?.complete?'Objetivo completado.':'Esperamos datos o completar requisitos para continuar.'}</p>}</div>}/>
    </aside><ResizeHandle root={root} variable="--steps-width" storageKey="finops-layout:steps" label="Ancho de la columna de pasos" min={240} max={520} fallback={341}/>
    <section id="objective-tasks" aria-label={goal?.title||'Tareas del objetivo'}>
      {workspace(<>
      <header className="tasks-column-heading task-tickets-heading"><h1 tabIndex={-1}>Tus tickets</h1></header>
      <div className="ticket-list-scroll">
      {goal&&orderedSteps.map(step=><div key={step.ticket_id}>{row(step.ticket_id)}{step.excluded&&<p className="task-scope-note">Fuera del objetivo: {step.reason}</p>}{step.state==='dismissed'&&!step.excluded&&<button className="task-scope-action" disabled={busy} onClick={()=>confirm===step.ticket_id?void change(goal.id+'/exclude',{ticket_id:step.ticket_id,version:goal.version}):setConfirm(step.ticket_id)}>{confirm===step.ticket_id?'Confirmar ajuste de alcance':'Excluir del objetivo'}</button>}</div>)}
      </div></>,nextTicket||tickets.find(t=>goal?.steps.some(step=>step.ticket_id===t.ticket_id)))}
    </section>
    {error&&<p role="alert">{error}</p>}
  </div>;
}
