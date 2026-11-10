import type {FollowupPlan} from '../types';
import type {MonitoringObservation} from '../consultingTypes';
const labels:Record<string,string>={pending_data:'Faltan datos',persists:'El problema continúa',needs_review:'Requiere revisión',criterion_met:'Candidato a cierre'};
export function TicketFollowup({plan,observation}:{plan:FollowupPlan;observation?:MonitoringObservation}){
  const start=new Date(plan.event_date+'T00:00:00Z');start.setUTCDate(start.getUTCDate()+1);
  const end=new Date(start);end.setUTCDate(end.getUTCDate()+plan.observation_days-1);
  return <section className="ticket-followup"><strong>Plan de seguimiento</strong>{observation&&<p><strong>{labels[observation.status]}</strong> · {observation.observed_days}/{observation.required_days} días recibidos. {observation.summary}</p>}<p>{plan.reason}</p><p>Observar del {start.toISOString().slice(0,10)} al {end.toISOString().slice(0,10)} · {plan.observation_days} días completos, según el retraso confirmado de los datos.</p><p>Para proponer el cierre: {plan.closure_criterion}</p>{plan.check==='return_to_baseline'&&<small>Cada día debe quedar por debajo de la media de los {plan.baseline_days} días previos al evento + {plan.tolerance_pct}%. El día del evento queda excluido.</small>}<p>Se revisará con los nuevos datos e informes. El cierre requiere tu aprobación.</p></section>;
}
