import {chatAgents} from '../auditTypes';
import orchestrator from '../assets/image.png';
import budgeting from '../assets/image copy.png';
import allocation from '../assets/image copy 2.png';
import anomaly from '../assets/image copy 3.png';
import assistant from '../assets/image copy 4.png';
import forecasting from '../assets/image copy 5.png';
import commitment from '../assets/image copy 6.png';
const avatars:Record<string,string>={orchestrator,allocation,anomaly,forecasting,budgeting,commitment,assistant};
export function AgentAvatar({agent}:{agent:string}){
  return <img className={'agent-avatar illustrated-avatar '+agent} src={avatars[chatAgents.find(a=>a.key===agent)?.avatar||agent]||assistant} alt="" width={48} height={48}/>;
}
