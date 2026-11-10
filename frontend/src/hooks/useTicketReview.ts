import {useEffect} from 'react';
import {api} from '../api';
export function useTicketReview(clientId:string,ticketId:string,onChanged?:()=>void){
  useEffect(()=>{
    let done=false;let active=true;
    function visible(){if(document.visibilityState!=='visible'||done)return;done=true;api(`/clients/${clientId}/tickets/${ticketId}/reviewed`,{method:'POST'}).then(()=>{if(active)onChanged?.()}).catch(()=>{done=false})}
    visible();document.addEventListener('visibilitychange',visible);
    return()=>{active=false;document.removeEventListener('visibilitychange',visible)};
  },[clientId,ticketId]);
}
