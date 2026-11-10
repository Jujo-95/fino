import {AgentAvatar} from './AgentAvatar';
export function ReusedReport({onReport}:{onReport:()=>void}){
  return <section className="panel reused-report"><AgentAvatar agent="orchestrator"/><div><h2>Sin cambios desde el último informe</h2><p>Tus datos, políticas y decisiones siguen iguales. El informe vigente y los tickets conservan su seguimiento.</p><button className="secondary" onClick={onReport}>Ver informe vigente</button><small>No fue necesario volver a ejecutar el equipo.</small></div></section>;
}
