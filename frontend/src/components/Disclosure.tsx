import type {ReactNode} from 'react';
import {ChevronDown} from 'lucide-react';
export function Disclosure({title,meta,children,initiallyOpen=false,icon}:{title:string;meta?:string;children:ReactNode;initiallyOpen?:boolean;icon?:ReactNode}){
  return <details className={'disclosure'+(icon?' has-icon':'')} open={initiallyOpen}><summary>{icon&&<span className="disclosure-icon" aria-hidden="true">{icon}</span>}<span>{title}</span>{meta&&<small>{meta}</small>}{icon&&<ChevronDown className="disclosure-chevron" size={14} aria-hidden="true"/>}</summary><div className="disclosure-content">{children}</div></details>;
}
export function excerpt(text:string,limit=220){return text.length>limit?text.slice(0,limit).trimEnd()+'…':text;}
