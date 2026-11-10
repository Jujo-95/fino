import type {Profile} from '../types';
import type {Consulting} from '../consultingTypes';
import type {ConnectionEntry,ConnectionInventory,SourceStatus} from '../connectionTypes';
import {ProviderView} from '../views/ProviderView';
import {OnboardingView} from '../views/OnboardingView';
import {DataSource} from './DataSource';
import {ConnectionUploads} from './ConnectionUploads';
import {ConnectionContext} from './ConnectionContext';
import {RemoteSource} from './RemoteSource';
const tools:Record<string,string>={get_schema:'Consultar estructura de facturación',query_finance:'Consultar costes del cliente',get_data_preview:'Revisar muestra de datos',get_use_case:'Leer casos de uso FinOps',execute_use_case:'Ejecutar un caso de uso',read_use_case_snapshots:'Consultar resultados del período',list_reports:'Consultar historial de informes',list_tickets:'Buscar tickets',get_tickets:'Consultar tickets y notas',read_report_changes:'Comparar informes anteriores',plan_ticket_changes:'Proponer cambios en tickets',propose_report_tickets:'Proponer tickets desde un informe',read_context:'Leer contexto del cliente'};
export function ConnectionDetail({entry,profile,clientId,consulting,inventory,source,onChanged}:{entry:ConnectionEntry;profile?:Profile;clientId:string;consulting?:Consulting|null;inventory:ConnectionInventory|null;source:SourceStatus|null;onChanged:()=>void}){
  if(entry.provider)return <ProviderView initialProvider={entry.provider} embedded onConfigured={onChanged}/>;
  if(!profile)return <p className="connection-help">Selecciona o crea un cliente para configurar sus fuentes.</p>;
  if(entry.id==='profile')return <div className="connection-body"><OnboardingView profileOnly profile={profile} onSaved={onChanged}/></div>;
  if(entry.id==='focus')return <><RemoteSource clientId={clientId} onChanged={onChanged}/><details className="connection-body"><summary>Alternativa · Subir CSV locales</summary><ConnectionUploads kind="focus" profile={profile} inventory={inventory} onChanged={onChanged}/></details></>;
  if(entry.id==='documents')return <ConnectionUploads kind="documents" profile={profile} inventory={inventory} onChanged={onChanged}/>;
  if(entry.id==='context')return <ConnectionContext data={consulting} clientId={clientId} onChanged={onChanged}/>;
  if(entry.id==='storage')return <div className="connection-body">{source?.configured?<><dl className="connection-facts"><div><dt>Origen</dt><dd>{source.synthetic?'Laboratorio de datos sintéticos':'Almacenamiento compatible con S3'}</dd></div><div><dt>Ubicación</dt><dd>{source.bucket}{source.prefix?'/'+source.prefix:''}</dd></div><div><dt>Última importación</dt><dd>{source.last_sync?.through||'Todavía no se ha importado'}</dd></div></dl><DataSource clientId={clientId} onChanged={onChanged} expanded/></>:<p className="connection-help">No hay un almacenamiento configurado para este cliente. Puedes importar sus CSV desde «Archivos de facturación FOCUS». Esta versión todavía no ofrece un formulario para registrar nuevas conexiones cloud.</p>}</div>;
  if(entry.id==='tools')return <div className="connection-body"><ul className="connection-records">{inventory?.tools.map(tool=><li key={tool.name}><span>{tools[tool.name]||tool.name}</span><small>Integrada · {tool.name.startsWith('propose')||tool.name==='plan_ticket_changes'?'Propone cambios; requiere tu aprobación':'Solo lectura y análisis'}</small></li>)}</ul>{!inventory&&<p className="connection-help">Actualiza para consultar las herramientas disponibles.</p>}</div>;
  return <div className="connection-body"><p className="connection-help">Las herramientas del equipo funcionan mediante servicios internos. El registro de servidores MCP externos requiere añadir autenticación, permisos por cliente y comprobaciones de conexión al backend.</p></div>;
}
