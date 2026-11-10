import {useEffect,useState,useCallback} from 'react';
import {api} from '../api';
import type {ConnectionInventory,SourceStatus,ProviderOptions,ConnectionEntry} from '../connectionTypes';
import type {Consulting} from '../consultingTypes';
export function useConnections(clientId:string,consulting?:Consulting|null){
  const [inventory,setInventory]=useState<ConnectionInventory|null>(null);const [source,setSource]=useState<SourceStatus|null>(null);const [providers,setProviders]=useState<ProviderOptions|null>(null);const [error,setError]=useState('');const [loading,setLoading]=useState(true);
  const load=useCallback(async()=>{
    setLoading(true);setError('');
    const results=await Promise.allSettled([api<ConnectionInventory>(`/clients/${clientId}/connections`),api<SourceStatus>(`/clients/${clientId}/source`),api<ProviderOptions>('/runtime/providers')]);
    if(results[0].status==='fulfilled')setInventory(results[0].value);if(results[1].status==='fulfilled')setSource(results[1].value);if(results[2].status==='fulfilled')setProviders(results[2].value);
    if(results.some(r=>r.status==='rejected'))setError('No se pudo actualizar todo el inventario. Reintenta para comprobar su estado.');setLoading(false);
  },[clientId]);
  useEffect(()=>{void load()},[load]);
  const scope='Cliente actual';const imports=inventory?.imports||[];const documents=inventory?.documents||[];
  const entries:ConnectionEntry[]=[
    {id:'focus',name:'Fuente de facturación FOCUS',category:'Facturación',status:inventory?.remote_source?(inventory.remote_source.verified_at?'Acceso comprobado':'Conexión por comprobar'):inventory?(imports.length?'CSV locales':'Sin configurar'):'Sin comprobar',scope,updated:imports[0]?.updated_at,description:'Conecta Parquet de tu nube o una tabla BigQuery. Los CSV locales son una alternativa.'},
    {id:'storage',name:source?.synthetic?'Almacenamiento de laboratorio':'Almacenamiento conectado',category:'Facturación',status:source?(source.configured?'Configurado':'Sin configurar'):'Sin comprobar',scope,updated:source?.last_sync?.through,description:'Importa las particiones disponibles de la fuente configurada. La importación no genera un informe.'},
    {id:'profile',name:'Perfil y políticas',category:'Contexto',status:'Configurado',scope,description:'Identidad del cliente y políticas de análisis. El presupuesto del perfil no sustituye su confirmación.'},
    {id:'context',name:'Información confirmada del negocio',category:'Contexto',status:consulting?(consulting.diagnosis.requirements.some(r=>r.status!=='confirmed')?'Información pendiente':'Disponible'):'Sin comprobar',scope,description:'Alcance, responsables, presupuesto y condiciones confirmados por el cliente.'},
    {id:'documents',name:'Documentos de contexto',category:'Contexto',status:inventory?(documents.length?'Documentos disponibles':'Sin documentos'):'Sin comprobar',scope,updated:documents.map(d=>d.updated_at).sort().at(-1),description:'Aporta notas del negocio en Markdown para que el equipo consulte el contexto de este cliente.'},
    {id:'tools',name:'Herramientas del equipo',category:'Herramientas',status:inventory?'Disponibles':'Sin comprobar',scope,description:'Consultas de facturación, casos de uso, historial y propuestas sobre tickets. Las modificaciones requieren aprobación.'},
    {id:'mcp',name:'Servidores MCP externos',category:'Herramientas',status:'No disponible',scope,description:'Esta versión utiliza herramientas internas. Todavía no permite registrar conexiones a servidores MCP externos.'},
    ...(providers?.providers.map(p=>({id:p.id,name:p.provider,category:'IA' as const,status:p.id===providers.active?'Activo':p.configured?'Clave configurada':'Sin configurar',scope:'Toda la instalación',description:`Proveedor de IA · ${p.model}. Su configuración se comparte entre clientes.`,provider:p.id}))||[]),
  ];
  return {entries,inventory,source,providers,error,loading,load};
}
