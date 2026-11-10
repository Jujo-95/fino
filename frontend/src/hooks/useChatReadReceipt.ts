import {useEffect} from 'react';
import type {RefObject} from 'react';
import {api} from '../api';
import type {ChatThread} from '../chatTypes';

export function useChatReadReceipt(clientId:string,thread:ChatThread|null,viewport:RefObject<HTMLDivElement|null>,hidden:boolean){
  const version=thread?.messages.filter(m=>m.role==='ai').map(m=>m.id).join('|');
  useEffect(()=>{
    const root=viewport.current;if(!root||hidden||!thread)return;
    const conversation=thread;let timer:number|undefined;let pending=false;let disposed=false;
    let acknowledged=conversation.last_read_message_id;const visible=new Set<string>();
    const messages=conversation.messages.filter(m=>m.role==='ai');
    async function acknowledge(){
      if(disposed||pending||document.hidden||!document.hasFocus())return;
      const latest=[...messages].reverse().find(m=>visible.has(m.id));if(!latest)return;
      const index=messages.findIndex(m=>m.id===acknowledged);if(messages.indexOf(latest)<=index)return;
      pending=true;
      try{const receipt=await api<{unread_count:number;last_read_message_id:string}>(`/clients/${clientId}/chat/threads/${conversation.thread_id}/read`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({message_id:latest.id})});acknowledged=receipt.last_read_message_id;
        if(!disposed)window.dispatchEvent(new CustomEvent('finops-chat-read',{detail:{clientId,threadId:conversation.thread_id,...receipt}}));
      }catch{/* Leave unread; retry when the user returns or scrolls. */}finally{pending=false}
    }
    function schedule(){clearTimeout(timer);timer=window.setTimeout(()=>void acknowledge(),600)}
    const observer=new IntersectionObserver(entries=>{for(const entry of entries){const id=(entry.target as HTMLElement).dataset.chatReadId!;if(entry.isIntersecting)visible.add(id);else visible.delete(id)}schedule()},{root,threshold:1});
    root.querySelectorAll('[data-chat-read-id]').forEach(node=>observer.observe(node));
    window.addEventListener('focus',schedule);document.addEventListener('visibilitychange',schedule);
    return()=>{disposed=true;clearTimeout(timer);observer.disconnect();window.removeEventListener('focus',schedule);document.removeEventListener('visibilitychange',schedule)};
  },[clientId,thread?.thread_id,version,hidden,viewport]);
}
