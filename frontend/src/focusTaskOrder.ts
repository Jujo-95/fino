import type {ProgressStep} from './progressTypes';
import type {Ticket} from './types';
import {taskState,isDeferred} from './ticketLifecycle';
export function orderFocusSteps(steps:ProgressStep[],tickets:Ticket[],nextId:string|undefined,blocked:(ticket:Ticket)=>boolean){
  function rank(step:ProgressStep){
    const ticket=tickets.find(t=>t.ticket_id===step.ticket_id);
    const state=ticket?taskState(ticket):step.state;
    if(state==='resolved')return 5;
    if(step.excluded||state==='dismissed'||!ticket)return 4;
    if(blocked(ticket)||isDeferred(ticket))return 3;
    if(step.ticket_id===nextId)return 0;
    return state==='todo'?1:2;
  }
  return [...steps].sort((a,b)=>rank(a)-rank(b));
}
