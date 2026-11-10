import {useEffect,useRef} from 'react';
import {Check,LockKeyhole} from 'lucide-react';
import type {ReactNode} from 'react';
import type {ProgressGoal} from '../progressTypes';
export function ObjectiveStepper({goals,selected,onSelect,isBlocked,activeContent}:{activeContent?:ReactNode;goals:ProgressGoal[];selected?:string;onSelect:(id:string)=>void;isBlocked:(goal:ProgressGoal)=>boolean}){
  const root=useRef<HTMLElement>(null);
  useEffect(()=>{root.current?.querySelector<HTMLElement>('[aria-current="step"]')?.scrollIntoView({block:'nearest',inline:'nearest',behavior:'auto'})},[selected]);
  return <nav ref={root} className="objective-stepper" aria-label="Pasos de tu plan"><ol>{goals.map((goal,index)=>{
    const blocked=isBlocked(goal)&&!goal.complete;const active=goal.id===selected;
    return <li key={goal.id} className={(goal.complete?'is-complete ':'')+(blocked?'is-blocked ':'')+(active?'is-active':'')}>
      <button className="objective-step-select" type="button" aria-current={active?'step':undefined} aria-controls="objective-tasks" onClick={()=>onSelect(goal.id)} title={blocked?'Las tareas pendientes de este paso requieren completar otros requisitos.':goal.title}>
        <span className="objective-step-number" aria-label={'Paso '+(index+1)+(goal.complete?' completado':blocked?' con requisitos pendientes':'')}>{goal.complete?<Check size={15}/>:index+1}</span>
        <strong>{blocked&&<LockKeyhole size={12} aria-hidden="true"/>}{goal.title}</strong><small>{goal.completed} de {goal.total} · {goal.percent===null?'Sin alcance':goal.percent+'%'}</small>
        <progress max={goal.total||1} value={goal.completed} aria-label={'Paso '+(index+1)+': '+goal.completed+' de '+goal.total+' tareas completadas'}/>
      </button>{active&&activeContent}
    </li>;
  })}</ol></nav>;
}
