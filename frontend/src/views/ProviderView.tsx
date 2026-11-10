import {useEffect,useState} from 'react';
import {Check,KeyRound,LoaderCircle,ShieldCheck} from 'lucide-react';
import {api} from '../api';
type Profile={id:'nvidia'|'gemini'|'groq';provider:string;model:string;fallback_model:string;configured:boolean;project:string;location:string;model_options?:string[];read_timeout_seconds:number};
type Options={active:Profile['id']|null;providers:Profile[]};
export function ProviderView({onConfigured,initialProvider,embedded=false}:{onConfigured:()=>void;initialProvider?:Profile['id'];embedded?:boolean}){
  const [options,setOptions]=useState<Options|null>(null);const [selected,setSelected]=useState<Profile|null>(null);
  const [key,setKey]=useState('');const [persist,setPersist]=useState(true);const [busy,setBusy]=useState('');const [error,setError]=useState('');const [notice,setNotice]=useState('');const [dirty,setDirty]=useState(false);
  useEffect(()=>{api<Options>('/runtime/providers').then(r=>{setOptions(r);setSelected(r.providers.find(p=>p.id===(initialProvider||r.active))||r.providers[0])}).catch(e=>setError(e.message))},[]);
  function choose(id:string){setSelected(options?.providers.find(p=>p.id===id)||null);setKey('');setError('');setNotice('');setDirty(false)}
  function edit(values:Partial<Profile>){setSelected(p=>p?{...p,...values}:p);setDirty(true);setNotice('')}
  async function save(){
    if(!selected)return;setBusy('save');setError('');setNotice('');
    try{await api('/runtime/provider',{method:'PUT',headers:{'Content-Type':'application/json','X-Finops-Config':'1'},body:JSON.stringify({provider:selected.id,model:selected.model,fallback_model:selected.fallback_model,project:selected.project,location:selected.location,read_timeout_seconds:selected.read_timeout_seconds,persist_key:persist,...(key.trim()?{api_key:key.trim()}:{})})});
      const next=await api<Options>('/runtime/providers');setOptions(next);setSelected(next.providers.find(p=>p.id===next.active)||null);setKey('');setDirty(false);setNotice(`${selected.provider} activo. Las siguientes solicitudes usarán este proveedor.`);onConfigured()
    }catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  async function check(){setBusy('check');setError('');setNotice('');try{const r=await api<{model:string}>('/runtime/check',{method:'POST',headers:{'X-Finops-Config':'1'}});setNotice(`Conexión y herramientas verificadas · ${r.model}`)}catch(e){setError((e as Error).message)}finally{setBusy('')}}
  const active=options?.providers.find(p=>p.id===options.active);const changed=dirty||!!key.trim()||selected?.id!==options?.active;
  return <section className="connection-settings">{!embedded&&<div className="connection-intro"><KeyRound size={20}/><div><h2>Conexión IA</h2><p>Elige el proveedor de tu equipo. Cada uno conserva su configuración.</p></div></div>}{active&&<div className="connection-status"><ShieldCheck size={16}/><span>Activo: {active.provider} · {active.model}</span></div>}
    {!selected?<p>{error||'Cargando conexiones…'}</p>:<form onSubmit={e=>{e.preventDefault();void save()}}>
      {!embedded&&<label htmlFor="llm-provider">Proveedor<select id="llm-provider" value={selected.id} disabled={!!busy} onChange={e=>choose(e.target.value)}>{options?.providers.map(p=><option key={p.id} value={p.id}>{p.provider}{p.configured?' · Clave configurada':''}</option>)}</select></label>}
      <p className="connection-hint">{selected.configured?'Ya hay una clave configurada. No necesitas volver a ingresarla.':'Añade una clave para usar este proveedor.'}</p>
      <label htmlFor="runtime-key">{selected.configured?'API key opcional':'API key'}<input id="runtime-key" type="password" autoComplete="new-password" spellCheck={false} value={key} maxLength={512} onChange={e=>setKey(e.target.value)} placeholder={selected.configured?'Solo para reemplazar la clave actual':selected.id==='groq'?'gsk_…':'Introduce tu API key'}/></label>
      <p className="connection-hint">Las claves guardadas nunca se muestran ni se envían al navegador.</p>
      {key&&<><label className="connection-checkbox"><input type="checkbox" checked={persist} onChange={e=>setPersist(e.target.checked)}/> Guardar la nueva clave en el llavero de macOS</label>{!persist&&<p className="connection-hint">La nueva clave estará disponible solo durante esta sesión del backend.</p>}</>}
      <label htmlFor="provider-model">Modelo principal<input id="provider-model" list="provider-model-options" value={selected.model} onChange={e=>edit({model:e.target.value})} required/></label><datalist id="provider-model-options">{selected.model_options?.map(model=><option key={model} value={model}/>)}</datalist>{selected.id==='groq'&&<p className="connection-hint">Opciones con herramientas en el plan gratuito de Groq. La disponibilidad y las cuotas dependen de tu cuenta.</p>}
      {selected.id==='gemini'?<><label>Proyecto de Google Cloud<input value={selected.project} onChange={e=>edit({project:e.target.value})} required/></label><details className="connection-advanced"><summary>Ubicación</summary><label>Ubicación<input value={selected.location} onChange={e=>edit({location:e.target.value})} required/></label></details></>:selected.id==='nvidia'?<details className="connection-advanced"><summary>Modelo de respaldo</summary><label>Respaldo opcional<input value={selected.fallback_model} onChange={e=>edit({fallback_model:e.target.value})} placeholder="Sin respaldo"/></label></details>:null}
      {error&&<p className="connection-error" role="alert">{error}</p>}{notice&&<p className="connection-success" role="status"><Check size={15}/>{notice}</p>}
      <div className="connection-actions"><button className="primary" disabled={!!busy||!changed||!selected.model.trim()||(!selected.configured&&!key.trim())}>{busy==='save'&&<LoaderCircle size={14} className="spin"/>}{selected.id===options?.active?'Guardar configuración':`Usar ${selected.provider}`}</button><button type="button" className="secondary" disabled={!!busy||!selected.configured||changed} onClick={()=>void check()}>{busy==='check'?'Comprobando…':'Probar conexión'}</button></div>
    </form>}
  </section>;
}
