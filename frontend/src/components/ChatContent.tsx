import ReactMarkdown from 'react-markdown';
import type {TicketChatSummary} from '../chatTypes';
import remarkGfm from 'remark-gfm';
type MarkdownNode={type:string;value?:string;url?:string;children?:MarkdownNode[]};
function linkTickets(){return (tree:unknown)=>walk(tree as MarkdownNode)}
function walk(node:MarkdownNode){
  if(['link','code','inlineCode'].includes(node.type)||!node.children)return;
  node.children=node.children.flatMap(child=>{if(child.type!=='text'){walk(child);return [child]}return (child.value||'').split(/(#?FIN-\d+)/g).filter(Boolean).map(value=>/^#?FIN-\d+$/.test(value)?{type:'link',url:'#ticket-'+value.replace('#',''),children:[{type:'text',value:value.replace('#','')}]}:{type:'text',value})});
}
export function ChatContent({text,onTicket,ticketThreads}:{text:string;onTicket:(id:string)=>void;ticketThreads?:TicketChatSummary[]}){
  return <ReactMarkdown remarkPlugins={[remarkGfm,linkTickets]} components={{table:({children})=><div className="chat-table-scroll"><table>{children}</table></div>,a:({href,children})=>href?.startsWith('#ticket-')?<button className="inline-ticket" title="Abrir hilo del ticket" onClick={()=>onTicket(href.slice(8))}>{children}{ticketThreads?.find(t=>t.ticket_id===href.slice(8)&&t.started)&&<small> · {ticketThreads.find(t=>t.ticket_id===href.slice(8))!.reply_count} respuestas</small>}</button>:<a href={href} target="_blank" rel="noreferrer">{children}</a>}}>{text}</ReactMarkdown>;
}
