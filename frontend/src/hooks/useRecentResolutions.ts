import {useEffect,useRef,useState} from 'react';
import type {Ticket} from '../types';
import {taskState} from '../ticketLifecycle';
export function useRecentResolutions(clientId:string,tickets:Ticket[]){
  const previous=useRef<{client:string;states:Map<string,string>}>({client:clientId,states:new Map()});
  const [recent,setRecent]=useState<Record<string,number>>({});
  useEffect(()=>{
    const states=new Map(tickets.map(t=>[t.ticket_id,taskState(t)]));
    if(previous.current.client!==clientId)setRecent({});
    else{
      const closed=tickets.filter(t=>previous.current.states.has(t.ticket_id)&&previous.current.states.get(t.ticket_id)!=='resolved'&&taskState(t)==='resolved');
      if(closed.length)setRecent(old=>({...old,...Object.fromEntries(closed.map(t=>[t.ticket_id,Date.now()+5000]))}));
    }
    previous.current={client:clientId,states};
  },[clientId,tickets]);
  useEffect(()=>{
    const times=Object.values(recent);if(!times.length)return;
    const timer=setTimeout(()=>setRecent(old=>Object.fromEntries(Object.entries(old).filter(([,until])=>until>Date.now()))),Math.max(0,Math.min(...times)-Date.now()));
    return()=>clearTimeout(timer);
  },[recent]);
  return new Set(Object.keys(recent));
}
