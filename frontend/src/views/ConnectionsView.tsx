import {useUrlState} from '../hooks/useUrlState';
import {useState} from 'react';
import {Database,FileText,Wrench,BrainCircuit,RefreshCw,ChevronRight} from 'lucide-react';
import {useConnections} from '../hooks/useConnections';
import type {Profile} from '../types';
import type {Consulting} from '../consultingTypes';
import type {ConnectionEntry} from '../connectionTypes';
import {ConnectionDetail} from '../components/ConnectionDetail';
const icons={Facturación:Database,Contexto:FileText,Herramientas:Wrench,IA:BrainCircuit};
export function ConnectionsView({clientId,profile,consulting,onChanged,initialSelection='focus'}:{clientId:string;profile?:Profile;consulting?:Consulting|null;onChanged:()=>void;initialSelection?:string}){
  const connections=useConnections(clientId,consulting);const [category,setCategory]=useState('Todas');const [selected,setSelected]=useUrlState('source',initialSelection);
  const rows=connections.entries.filter(e=>category==='Todas'||e.category===category);const current=connections.entries.find(e=>e.id===(selected==='ai'?connections.providers?.active:selected));
  function changed(){void connections.load();onChanged()}
  function filter(value:string){setCategory(value);const first=connections.entries.find(e=>value==='Todas'||e.category===value);if(!rows.some(e=>e.id===selected)||value!=='Todas'&&current?.category!==value)setSelected(first?.id||'focus')}
  return <div className="connections-page"><div className="connections-toolbar"><div role="group" aria-label="Filtrar conexiones">{['Todas','Facturación','Contexto','Herramientas','IA'].map(value=><button key={value} aria-pressed={category===value} onClick={()=>filter(value)}>{value}</button>)}</div><button className="icon-button" disabled={connections.loading} onClick={()=>void connections.load()} aria-label="Actualizar conexiones"><RefreshCw size={16} className={connections.loading?'spin':''}/></button></div>
    {connections.error&&<p className="error-banner" role="alert">{connections.error}</p>}
    <div className="connections-workspace"><nav className="connections-list" aria-label="Conexiones disponibles">{rows.map(entry=><ConnectionRow key={entry.id} entry={entry} selected={current?.id===entry.id} onSelect={()=>setSelected(entry.id)}/>)}{connections.loading&&<p className="connection-help" role="status">Actualizando conexiones…</p>}</nav>
      <section className="connection-detail" aria-label={current?.name||'Detalle de conexión'}>{current&&<><header><div><span>{current.category} · {current.scope}</span><h2>{current.name}</h2><p>{current.description}</p></div><span className="connection-state">{current.status}</span></header><ConnectionDetail key={current.id+clientId} entry={current} profile={profile} clientId={clientId} consulting={consulting} inventory={connections.inventory} source={connections.source} onChanged={changed}/></>}</section>
    </div>
  </div>;
}
function ConnectionRow({entry,selected,onSelect}:{entry:ConnectionEntry;selected:boolean;onSelect:()=>void}){
  const Icon=icons[entry.category];const updated=entry.updated?new Date(/^\d{4}-\d{2}-\d{2}$/.test(entry.updated)?entry.updated+'T12:00:00Z':entry.updated).toLocaleDateString('es',{day:'numeric',month:'short',timeZone:'America/Bogota'}):'Sin actualización registrada';
  return <button className="connection-row" aria-current={selected?'true':undefined} onClick={onSelect}><Icon size={18}/><span><strong>{entry.name}</strong><small>{entry.category} · {entry.scope}</small><small>{entry.status} · {updated}</small></span><ChevronRight size={14}/></button>;
}
