import {ContextProposal} from './ContextProposal';
import type {ContextProposal as Proposal} from '../consultingTypes';
import type {ChatThread} from '../chatTypes';
export function ChatConsulting({thread,turnId,afterId}:{thread:ChatThread;turnId:string;afterId?:string}){
  const proposals=thread.activity.filter(a=>a.tool==='propose_context_changes'&&a.turn_id===turnId&&(afterId?a.after_message_id===afterId:!a.after_message_id)).map(a=>a.result as Proposal).filter(p=>p.proposal_id);
  const clientId=(thread as ChatThread&{client_id?:string}).client_id;if(!clientId)return null;
  return <>{proposals.map(p=><ContextProposal key={p.proposal_id} clientId={clientId} proposal={p} onChanged={()=>window.dispatchEvent(new Event('finops-context-changed'))}/>)}</>;
}
