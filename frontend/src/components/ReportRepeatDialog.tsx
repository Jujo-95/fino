import {useEffect,useRef} from 'react';
import {createPortal} from 'react-dom';
export type RepeatPrompt={confirmation_id:string;message:string;existing_run_id:string};
export function ReportRepeatDialog({prompt,onConfirm,onCancel}:{prompt:RepeatPrompt;onConfirm:()=>void;onCancel:()=>void}){
  const ref=useRef<HTMLDialogElement>(null);
  useEffect(()=>{ref.current?.showModal();return()=>ref.current?.close()},[]);
  return createPortal(<dialog ref={ref} className="report-repeat-dialog" aria-labelledby="repeat-report-title" onCancel={e=>{e.preventDefault();onCancel()}}><h2 id="repeat-report-title">Ya existe un informe</h2><p>{prompt.message}</p><p>El informe anterior se conservará. La nueva ejecución volverá a consultar al equipo.</p><div><button className="secondary" onClick={onCancel}>Conservar existente</button><button className="primary" onClick={onConfirm}>Crear nuevamente</button></div></dialog>,document.body);
}
