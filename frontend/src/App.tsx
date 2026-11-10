import {type TaskMode} from './components/TaskModeSwitch';
import {ReportRepeatDialog} from './components/ReportRepeatDialog';
import {useState,useEffect} from 'react';
import {useLocation,useNavigate} from 'react-router-dom';
import {useUrlState} from './hooks/useUrlState';
import {Sidebar,PageHeader} from './components/Shell';
import {useConsole} from './hooks/useConsole';
import {useSSEStream} from './hooks/useSSEStream';
import {LiveView} from './views/LiveView';
import {TicketsView} from './views/TicketsView';
import {OnboardingView} from './views/OnboardingView';
import {ReportsView} from './views/ReportsView';
import {ConnectionsView} from './views/ConnectionsView';
import type {ChatRequest} from './chatTypes';
import {Empty} from './components/Primitives';
import {isActiveTask} from './ticketLifecycle';

const normalizeView=(value:string)=>['overview','kpis'].includes(value)?'tickets':['scripts','provider','onboarding'].includes(value)?'connections':value;
export default function App(){
  const [navCollapsed,setNavCollapsed]=useState(()=>localStorage.getItem('finops-nav-collapsed')==='true');
  function toggleNav(){setNavCollapsed(value=>{localStorage.setItem('finops-nav-collapsed',String(!value));return !value})}
  const location=useLocation();const go=useNavigate();const parts=location.pathname.split('/').filter(Boolean);
  const requested=parts[0]==='clients'&&parts[1]!=='new'?decodeURIComponent(parts[1]||''):'';
  const view=parts[1]==='new'?'new':normalizeView(parts[2]==='chat'?'live':parts[2]||'tickets');
  const c=useConsole(requested);const stream=useSSEStream(c.clientId,()=>void c.refresh());
  const [mode,setTaskMode]=useUrlState('mode','focus');const taskMode:TaskMode=mode==='list'?'list':'focus';
  const [chatRequest,setChatRequest]=useState<ChatRequest>(null);
  useEffect(()=>{if(location.pathname==='/'&&c.clientId)go('/clients/'+encodeURIComponent(c.clientId)+'/tickets',{replace:true})},[location.pathname,c.clientId,go]);
  const o=c.overview;const profile=c.profiles.find(p=>p.client_id===c.clientId);
  function navigate(next:string,client=c.clientId){const source=next==='provider'?'ai':'focus';next=normalizeView(next);go(next==='new'?'/clients/new':'/clients/'+encodeURIComponent(client)+'/'+(next==='live'?'chat':next)+(next==='connections'?'?source='+source:''));window.scrollTo({top:0,behavior:'auto'})}
  function run(mode='daily',instruction='',reference_run_id?:string){if(!o||stream.running)return;navigate('reports');void stream.start({client_id:c.clientId,run_mode:mode,analysis_only:true,period_start_utc:o.period_start_utc,period_end_utc:o.period_end_utc,billing_currency:'USD',instruction,reference_run_id},()=>void c.refresh());}
  function openTicketThread(ticketId:string,prompt?:string){sessionStorage.setItem(`finops-agent:${c.clientId}`,'v2-finops-report-orchestrator');setChatRequest({ids:[],ticketId,prompt,nonce:Date.now(),clientId:c.clientId,forceV2:true});navigate('live')}
  function content(){
    if(view==='new')return <OnboardingView onSaved={id=>{void c.saved(id);navigate('connections',id)}}/>;
    if(['connections','scripts','provider','onboarding'].includes(view))return <ConnectionsView key={c.clientId} initialSelection="focus" profile={profile} consulting={c.consulting} clientId={c.clientId} onChanged={()=>void c.saved(c.clientId)}/>;
    if(!['new','live','tickets','reports','connections'].includes(view))return <Empty title="Página no encontrada" description="Revisa el enlace o vuelve a tus tareas." action="Tus tareas" onAction={()=>navigate('tickets')}/>;
    if(!o||o.profile.client_id!==c.clientId||requested&&requested!==c.clientId)return <Empty title={(c.loading||!!c.clientId&&!c.error)?'Cargando datos…':'Añade tus datos de facturación'} description={(c.loading||!!c.clientId&&!c.error)?'Consultando el espacio de trabajo local.':'Crea un cliente e importa sus archivos de facturación para revisar costos y detectar oportunidades.'} action={(c.loading||!!c.clientId&&!c.error)?undefined:'Crear cliente'} onAction={()=>navigate('new')}/>;
    if(view==='live')return <LiveView onChatRequestConsumed={()=>setChatRequest(null)} tickets={c.tickets} onChanged={()=>void c.refresh()} chatRequest={chatRequest} onOpenReports={runId=>{go('/clients/'+encodeURIComponent(c.clientId)+'/reports'+(runId?'/'+encodeURIComponent(runId):''))}} key={c.clientId} overview={o} events={stream.clientId===c.clientId?stream.events:[]} running={stream.running} error={stream.clientId===c.clientId?stream.error:''}/>;
    if(['overview','tickets','kpis'].includes(view))return <TicketsView onModeChange={setTaskMode} mode={taskMode} overview={o} consulting={c.consulting} onSetup={()=>navigate('onboarding')} onAsk={(ticket,draft)=>openTicketThread(ticket.ticket_id,draft)} key={c.clientId} tickets={c.tickets} clientId={c.clientId} onRefresh={()=>void c.refresh()}/>;
    return <ReportsView onStop={stream.stop} onConnection={()=>navigate('provider')} key={c.clientId} reports={c.reports} overview={o} events={stream.clientId===c.clientId?stream.events:[]} running={stream.running} error={stream.error} onRun={run}/>;
  }
  const navigation={collapsed:navCollapsed,onToggle:toggleNav,view,onNavigate:navigate,profiles:c.profiles,clientId:c.clientId,onClient:(id:string)=>{c.setClientId(id);navigate('tickets',id)},running:stream.running,pending:c.tickets.filter(isActiveTask).length,provider:c.provider};
  return <div className={'app-shell '+(navCollapsed?'nav-collapsed':'')}>{stream.repeat&&<ReportRepeatDialog prompt={stream.repeat.prompt} onConfirm={()=>void stream.confirmRepeat()} onCancel={stream.cancelRepeat}/>}<a className="skip-link" href="#main-content">Ir al contenido</a><Sidebar {...navigation}/><main id="main-content">{!['tickets','overview','kpis'].includes(view)&&<PageHeader view={view} overview={o} provider={c.provider} loading={c.loading} running={stream.running} onRun={()=>run()} onRefresh={()=>void c.refresh()}/>}<div className="page">{c.error&&<div className="error-banner" role="alert"><span>{c.error}</span><button onClick={()=>void c.refresh()}>Reintentar</button></div>}{content()}</div></main></div>;
}
