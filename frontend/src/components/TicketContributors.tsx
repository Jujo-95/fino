import type {Ticket} from '../types';
import {AgentAvatar} from './AgentAvatar';
const names:Record<string,string>={allocation:'Asignación',anomaly:'Anomalías',forecasting:'Proyecciones',budgeting:'Presupuestos',commitment:'Compromisos',orchestrator:'Orquestador'};
export function TicketContributors({ticket,compact=false}:{ticket:Ticket;compact?:boolean}){
  const people=(ticket.contributors||[]).filter((person,index,all)=>all.findIndex(other=>other.agent_id===person.agent_id&&other.role===person.role)===index);
  if(!people.length)return compact?null:<p className="muted">Este ticket no tiene autoría registrada en su historial.</p>;
  return <div className={'ticket-contributors '+(compact?'compact':'')} aria-label="Equipo que aportó al ticket">{people.map(person=><span role="group" key={person.agent_id+person.role} aria-label={(person.role==='detected'?'Detectado por ':'Consolidado por ')+(names[person.agent_id]||person.agent_id)} title={(person.role==='detected'?'Detectado por ':'Consolidado por ')+(names[person.agent_id]||person.agent_id)}><AgentAvatar agent={person.agent_id}/>{!compact&&<span><strong>{names[person.agent_id]||person.agent_id}</strong><small>{person.role==='detected'?'Detectó el hallazgo':'Consolidó el ticket'}</small></span>}</span>)}{compact&&<small>Equipo del hallazgo</small>}</div>;
}
