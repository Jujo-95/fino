export type TaskMode='focus'|'list';
export function TaskModeSwitch({mode,onChange}:{mode:TaskMode;onChange:(mode:TaskMode)=>void}){
  return <div className="task-mode-switch" role="group" aria-label="Modo de tus tareas">{([['focus','Modo enfoque'],['list','Modo listado']] as const).map(([value,label])=><button type="button" key={value} aria-pressed={mode===value} onClick={()=>onChange(value)}>{label}</button>)}</div>;
}
