import {useEffect,useRef,useState} from 'react';
export function useChartWidth(){
  const ref=useRef<HTMLDivElement>(null);
  const [width,setWidth]=useState(890);
  useEffect(()=>{
    if(!ref.current)return;
    const observer=new ResizeObserver(entries=>{
      const value=entries[0]?.contentRect.width;
      if(value)setWidth(Math.max(240,Math.round(value)));
    });
    observer.observe(ref.current);
    return ()=>observer.disconnect();
  },[]);
  return {ref,width};
}
