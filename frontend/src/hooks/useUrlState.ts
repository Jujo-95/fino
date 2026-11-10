import {useLocation,useNavigate,useSearchParams} from 'react-router-dom';
// Resource identity uses paths; filters and panel preferences use search parameters.
export function useUrlState(key:string,fallback=''){
  const location=useLocation();const navigate=useNavigate();const [params,setParams]=useSearchParams();
  const parts=location.pathname.split('/').filter(Boolean);
  const resource=({tickets:'ticket',chat:'conversation',reports:'run'} as Record<string,string>)[parts[2]]===key;
  const value=resource&&parts[3]?decodeURIComponent(parts[3]):params.get(key)??fallback;
  function setValue(next:string|null){
    if(key==='goal'||key==='mode'){const search=new URLSearchParams(location.search);search.delete('ticket');search.delete('thread');if(next&&next!==fallback)search.set(key,next);else search.delete(key);navigate({pathname:'/'+parts.slice(0,3).join('/'),search:search.toString()});return}
    if(resource){const search=new URLSearchParams(location.search);search.delete(key);navigate({pathname:'/'+parts.slice(0,3).join('/')+(next?'/'+encodeURIComponent(next):''),search:search.toString()});return}
    setParams(current=>{if(next&&next!==fallback)current.set(key,next);else current.delete(key);return current});
  }
  return [value,setValue] as const;
}
