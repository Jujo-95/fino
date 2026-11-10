import type {Ticket} from '../types';
import type {Consulting} from '../consultingTypes';
import {ContextAnswer} from './ContextAnswer';
import {SupportingEvidence} from './SupportingEvidence';
export function TicketRequirement({ticket,data,clientId,onChanged,onSetup}:{ticket:Ticket;data?:Consulting|null;clientId:string;onChanged:()=>void;onSetup?:()=>void}){
  const key=ticket.workflow_key?.replace('requirement:','');
  const requirement=data?.diagnosis.requirements.find(r=>r.id===key);
  if(!requirement||!data)return null;
  return <section className="ticket-input"><h3>Completar esta tarea</h3>{['billing','missing_accounts','stale','gaps','history'].includes(key||'')?<><p>{requirement.reason}</p><button className="secondary" onClick={onSetup}>Revisar archivos de facturación</button></>:['utilization','contracts'].includes(key||'')?<SupportingEvidence clientId={clientId} onChanged={onChanged}/>:<ContextAnswer data={data} requirement={requirement} clientId={clientId} onChanged={onChanged}/>}</section>;
}
