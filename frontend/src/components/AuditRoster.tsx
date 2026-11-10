import {AgentAvatar} from './AgentAvatar';
import {Plus,ChevronDown,ChevronRight} from 'lucide-react';
import {useState} from 'react';
import {ConversationList} from './ConversationList';
import type {ChatSummary} from '../chatTypes';
import {chatAgents,executionOrder,type AuditTrace} from '../auditTypes';
export function agentTraces(key:string,traces:AuditTrace[]){return traces.filter(t=>key==='orchestrator'?['ingest_and_profile','synthesize'].includes(t.node):t.node===key);}
export function agentStatus(key:string,traces:AuditTrace[],running:boolean,failedNode?:string|null){
  if(failedNode&&(key==='orchestrator'?['ingest_and_profile','synthesize'].includes(failedNode):failedNode===key))return 'failed';
  if(key==='orchestrator'&&traces.some(t=>t.node==='synthesize'))return 'completed';
  if(key!=='orchestrator'&&traces.some(t=>t.node===key))return 'completed';
  const next=executionOrder.find(node=>!traces.some(t=>t.node===node));
  if(running&&(key==='orchestrator'?true:next===key))return 'running';
  return 'pending';
}
export function AuditRoster({selected,onSelect,conversations,archived,archiveLoading,onLoadArchived,onArchive,selectedThread,onConversation,busy,historyError,onRetry}:{selected:string;onSelect:(key:string)=>void;conversations:Record<string,ChatSummary[]>;archived:Record<string,ChatSummary[]>;archiveLoading:Record<string,boolean>;onLoadArchived:(agent:string)=>Promise<void>;onArchive:(agent:string,id:string,archived:boolean)=>Promise<boolean>;selectedThread?:string;onConversation:(agent:string,id:string)=>void;busy:boolean;historyError:string;onRetry:()=>void}){
  const [collapsed,setCollapsed]=useState(false);const [showArchived,setShowArchived]=useState(false);
  const fino='v2-finops-report-orchestrator';const agents=chatAgents.filter(agent=>agent.key.startsWith('v2-'));
  const entries=(showArchived?archived:conversations)[fino]||[];
  function toggleArchive(){if(!showArchived)void onLoadArchived(fino);setShowArchived(value=>!value)}
  return <aside className="audit-roster panel conversation-roster" aria-label="Fino, especialistas y conversaciones"><h2 className="team-section-label">Tu equipo</h2><div className="agent-list" aria-label="Orquestador y especialistas">{agents.map(agent=><div key={agent.key} className={'agent-list-row '+(selected===agent.key?'selected':'')}><button className="agent-list-select" aria-pressed={selected===agent.key} onClick={()=>onSelect(agent.key)} title={agent.role}><AgentAvatar agent={agent.key}/><span><strong>{agent.name}</strong><small>{agent.key===fino?'Tu asistente FinOps':'Especialista · Ver capacidades'}</small></span>{agent.key!==fino&&<ChevronRight size={13}/>}</button>{agent.key===fino&&<button className="agent-list-new icon-button" aria-label="Nueva conversación con Fino" title="Nueva conversación con Fino" disabled={busy||(conversations[fino]||[]).some(t=>t.empty&&t.thread_id===selectedThread)} onClick={()=>onConversation(fino,'new')}><Plus size={15}/></button>}</div>)}</div>{historyError&&<button className="history-retry" onClick={onRetry}>{historyError} Reintentar</button>}<div className="conversation-section-heading"><button className="conversation-collapse" aria-expanded={!collapsed} aria-controls="team-conversation-history" onClick={()=>setCollapsed(value=>!value)}><span>Conversaciones con Fino</span><ChevronDown size={12}/></button><button className="archived-toggle" aria-pressed={showArchived} onClick={toggleArchive}>{showArchived?'Activas':'Archivadas'}</button></div>{!collapsed&&<div id="team-conversation-history"><ConversationList agentId={fino} entries={entries} archived={showArchived} selectedThread={selectedThread} busy={busy} loading={showArchived&&!!archiveLoading[fino]} onOpen={id=>onConversation(fino,id)} onArchive={(id,value)=>{void onArchive(fino,id,value).then(changed=>{if(changed&&!value)setShowArchived(false)})}}/></div>}</aside>;
}
