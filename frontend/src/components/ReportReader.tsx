import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Disclosure,excerpt} from './Disclosure';
export function ReportReader({markdown,initiallyOpen=false}:{markdown:string;initiallyOpen?:boolean}){
  const lines=markdown.split('\n').map(line=>line.trim()).filter(Boolean);
  const start=lines.findIndex(line=>/^##?\s+.*(executive|ejecutivo|resumen)/i.test(line));
  const preview=(start>=0?lines.slice(start+1):lines.filter(line=>!line.startsWith('#'))).filter(line=>!line.startsWith('#')).slice(0,3);
  const action=lines.find(line=>/^[-*]\s+(FIN-|.*(acción|action|recomend))/i.test(line));
  const limitation=lines.find(line=>/missing|not available|faltan|limitaci[oó]n|sin datos/i.test(line)&&!line.startsWith('#'));
  return <div className="report-reader"><div className="report-preview"><h3>Vista previa</h3>{preview.map((line,i)=><p key={i}>{excerpt(line.replace(/^[-*]\s+/,''),260)}</p>)}{action&&<p><strong>Acción registrada · extracto</strong><br/>{excerpt(action.replace(/^[-*]\s+/,''),260)}</p>}{limitation&&!preview.includes(limitation)&&<p><strong>Limitación registrada · extracto</strong><br/>{excerpt(limitation,260)}</p>}</div><Disclosure title="Ver informe completo" initiallyOpen={initiallyOpen}><article className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{table:({children})=><div className="chat-table-scroll"><table>{children}</table></div>}}>{markdown}</ReactMarkdown></article></Disclosure></div>;
}
