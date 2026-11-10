import {useRef,useState} from 'react';
import {Upload} from 'lucide-react';
import {api} from '../api';
import type {Profile} from '../types';
import type {ConnectionInventory} from '../connectionTypes';
export function ConnectionUploads({kind,profile,inventory,onChanged}:{kind:'focus'|'documents';profile:Profile;inventory:ConnectionInventory|null;onChanged:()=>void}){
  const [files,setFiles]=useState<File[]>([]);const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [notice,setNotice]=useState('');const input=useRef<HTMLInputElement>(null);
  async function submit(e:React.FormEvent){
    e.preventDefault();setBusy(true);setError('');setNotice('');
    try{const data=new FormData();if(kind==='documents')data.append('profile',JSON.stringify(profile));files.forEach(file=>data.append(kind==='focus'?'files':'notes',file));
      const result=await api<{ingested_rows:number}>(kind==='focus'?`/clients/${profile.client_id}/uploads`:'/clients/onboard',{method:'POST',body:data});setNotice(kind==='focus'?`${result.ingested_rows} registros nuevos importados.`:'Documentos de contexto guardados.');setFiles([]);if(input.current)input.current.value='';onChanged();
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  const rows=kind==='focus'?inventory?.imports:inventory?.documents;
  return <div className="connection-body"><form className="connection-form" onSubmit={submit}><label>{kind==='focus'?'Archivos CSV FOCUS':'Notas de contexto · Markdown'}<input ref={input} type="file" multiple accept={kind==='focus'?'.csv':'.md'} disabled={busy} onChange={e=>{setFiles(Array.from(e.target.files||[]));setNotice('')}}/></label><p className="connection-help">Hasta 50 MB por archivo. Las cargas repetidas no duplican los datos.</p>{files.length>0&&<p>{files.length} archivos seleccionados</p>}{error&&<p className="error" role="alert">{error}</p>}{notice&&<p className="success" role="status">{notice}</p>}<div className="connection-actions"><button className="primary" disabled={busy||!files.length}><Upload size={14}/>{busy?'Importando…':'Importar archivos'}</button></div></form>
    <details className="connection-advanced"><summary>{kind==='focus'?'Cargas realizadas':'Documentos disponibles'} · {rows?.length??'—'}</summary>{rows?.length?<ul className="connection-records">{rows.map((row,i)=><li key={row.name+i}><span>{kind==='focus'?'Carga de facturación':'Nota de contexto'} {i+1}</span><small>{'rows' in row&&typeof row.rows==='number'?row.rows.toLocaleString('es')+' registros · ':''}{new Date(row.updated_at).toLocaleDateString('es',{timeZone:'America/Bogota'})}</small></li>)}</ul>:<p className="connection-help">Todavía no hay archivos registrados.</p>}</details>
  </div>;
}
