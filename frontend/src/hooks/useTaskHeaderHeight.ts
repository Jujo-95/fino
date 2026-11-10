import {useLayoutEffect} from 'react';
import type {RefObject} from 'react';
export function useTaskHeaderHeight(root:RefObject<HTMLDivElement|null>){
  useLayoutEffect(()=>{
    const container=root.current;const heading=container?.querySelector<HTMLElement>('.tasks-column-heading');
    if(!container||!heading)return;
    const measure=()=>container.style.setProperty('--tasks-header-height',Math.ceil(heading.getBoundingClientRect().height)+'px');
    const observer=new ResizeObserver(measure);observer.observe(heading);measure();
    return()=>observer.disconnect();
  },[root]);
}
