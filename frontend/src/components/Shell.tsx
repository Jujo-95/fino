import {Link} from 'react-router-dom';
import { useState } from 'react';
import { Workflow, PanelsTopLeft, FileText, Plus, ChevronDown, LoaderCircle, ArrowUpRight, Plug, Menu, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import type { Profile, Overview } from '../types';
import { periodLabel } from '../presentation';
import {multiClientEnabled} from '../productConfig';
import { Disclosure } from './Disclosure';

const navigation = [{ key: 'live', label: 'Fino y su equipo', icon: Workflow }, { key: 'tickets', label: 'Tickets', icon: PanelsTopLeft }, { key: 'reports', label: 'Análisis', icon: FileText }, { key: 'connections', label: 'Conexiones', icon: Plug },];
export type NavigationProps = { collapsed?:boolean;onToggle?:()=>void;view: string; onNavigate: (view: string) => void; profiles: Profile[]; clientId: string; onClient: (id: string) => void; running: boolean; pending: number; provider: string };

export function ClientPicker({ profiles, clientId, onClient, running }: Pick<NavigationProps, 'profiles' | 'clientId' | 'onClient' | 'running'>) {
  return <div className="client-picker"><span className="client-avatar" aria-hidden="true">{profiles.find(p => p.client_id === clientId)?.client_name.slice(0, 1) || '+'}</span><select aria-label="Cliente activo" value={clientId} disabled={running} onChange={e => onClient(e.target.value)}>{!profiles.length && <option value="">Seleccionar cliente</option>}{profiles.map(p => <option key={p.client_id} value={p.client_id}>{p.client_name}</option>)}</select><ChevronDown size={14} aria-hidden="true" /></div>;
}

export function Sidebar(p: NavigationProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  function go(view: string) { p.onNavigate(view); setMenuOpen(false) }
  return <aside className={'sidebar ' + (menuOpen ? 'mobile-open' : '')}><div className="sidebar-collapse-row"><button className="icon-button sidebar-collapse" aria-label={p.collapsed?'Ampliar navegación':'Contraer navegación'} aria-expanded={!p.collapsed} onClick={p.onToggle} title={p.collapsed?'Ampliar navegación':'Contraer navegación'}>{p.collapsed?<PanelLeftOpen size={12}/>:<PanelLeftClose size={12}/>}</button></div><button className="brand" onClick={() => go('tickets')} aria-label="FinOps, ir a tus tareas"><img className="brand-mark" src="/finops-logo.svg" alt="" width={32} height={32}/><span>finops</span></button><button className="mobile-menu-toggle" aria-label="Menú de navegación" aria-expanded={menuOpen} aria-controls="main-navigation" onClick={() => setMenuOpen(!menuOpen)}><Menu size={20} /></button><nav id="main-navigation" aria-label="Navegación principal">{navigation.map(item => <Link to={'/clients/'+encodeURIComponent(p.clientId)+'/'+(item.key==='live'?'chat':item.key)} key={item.key} title={item.label} aria-label={item.label} aria-current={p.view === item.key ? 'page' : undefined} className={p.view === item.key ? 'active' : ''} onClick={() => setMenuOpen(false)}><item.icon size={18} /><span>{item.label}</span>{item.key === 'tickets' && p.pending > 0 && <span className="nav-count">{p.pending}</span>}{item.key === 'live' && p.running && <LoaderCircle size={14} className="spin nav-progress" />}</Link>)}</nav>{multiClientEnabled&&<div className="sidebar-settings"><details className="client-switcher"><summary>Cambiar cliente</summary><ClientPicker {...p}/></details><button disabled={p.running} onClick={() => go('new')}><Plus size={18} /><span>Nuevo cliente</span></button></div>}<div className="sidebar-bottom"><span className="storage-note">Tus costos, con decisiones claras.</span><a href="https://www.finops.org/framework/" target="_blank" rel="noreferrer">Guía FinOps <ArrowUpRight size={14} /></a></div></aside>;
}

const pageTitles: Record<string, [string, string]> = { connections: ['Conexiones', ''], provider: ['Conexiones', ''], scripts: ['Conexiones', ''], overview: ['Qué hacemos hoy', ''], live: ['Equipo de análisis', ''], kpis: ['Indicadores FinOps', 'Métricas calculadas a partir de tus datos de facturación.'], tickets: ['Tus tareas', ''], reports: ['Análisis', 'Indicadores, tareas y reportes opcionales.'], onboarding: ['Conexiones', ''], new: ['Nuevo cliente', 'Crea un espacio independiente para sus datos y decisiones.'] };
type HeaderProps = { titleAddon?:React.ReactNode; view: string; overview: Overview | null; provider: string; loading: boolean; running: boolean; onRun: () => void; onRefresh: () => void };

export function PageHeader({ view, titleAddon }: HeaderProps) {
  const [title] = pageTitles[view] || pageTitles.tickets;
  if(['provider','connections'].includes(view))return <div className="page-heading compact-heading"><h1 tabIndex={-1}>{title}</h1></div>;
  if(view==='live')return <h1 className="sr-only" tabIndex={-1}>Equipo de análisis</h1>;
  return <div className="page-heading compact-heading"><div className="heading-title-group"><h1 tabIndex={-1}>{title}</h1>{titleAddon}</div></div>;
}

export function DataContext({ overview, onSetup }: { overview: Overview | null; onSetup: () => void }) {
  return <Disclosure title="Datos del informe"><p>{overview ? periodLabel(overview) : 'Sin datos de facturación'}{overview?.profile.client_id === 'acme-demo' ? ' · Datos de ejemplo' : ''}</p>{overview?.profile.client_id === 'acme-demo' && <button className="text-button" onClick={onSetup}>Configurar mis datos</button>}</Disclosure>;
}
