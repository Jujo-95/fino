import {useRef,type ReactNode} from 'react';
import {ResizeHandle} from './ResizeHandle';
import {useTaskHeaderHeight} from '../hooks/useTaskHeaderHeight';

export function TicketListLayout({header,toolbar,list,children}:{header:ReactNode;toolbar:ReactNode;list:ReactNode;children:ReactNode}){
  const root=useRef<HTMLDivElement>(null);
  useTaskHeaderHeight(root);
  const widths={['--steps-width' as string]:Math.max(240,Math.min(520,Number(localStorage.getItem('finops-layout:steps'))||341))+'px'};
  return <div ref={root} style={widths} className="ticket-list-layout">
    <aside className="ticket-list-column" aria-label="Listado y filtros de tickets">
      {header}{toolbar}<div className="ticket-list-scroll">{list}</div>
    </aside>
    <ResizeHandle root={root} variable="--steps-width" storageKey="finops-layout:steps" label="Ancho del listado de tickets" min={240} max={520} fallback={341}/>
    <section className="ticket-list-workspace" aria-label="Detalle e hilo del ticket">{children}</section>
  </div>;
}
