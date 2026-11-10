import json
import re
from typing import Any, Callable
from uuid import uuid4
from ..config import atomic_write_text
from ..agents.audit_trace import timestamp
from .agent_context import validate_agent, validate_run


class ChatStore:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.directory = client.workspace/'chat/threads'
        self.client_id = client.profile.client_id
        self.lock = client.engine.lock

    def path(self, thread_id: str) -> Any:
        if not re.fullmatch(r'[a-f0-9]{32}', thread_id):
            raise ValueError('Conversación inválida.')
        return self.directory/(thread_id+'.json')

    def create(self, agent_id: str = 'orchestrator', audit_run_id: str | None = None, thread_id: str | None = None, ticket_id: str | None = None) -> dict[str, Any]:
        validate_agent(agent_id)
        validate_run(self.client,audit_run_id)
        thread = dict(ticket_id=ticket_id,ticket_refs=[ticket_id] if ticket_id else [],agent_id=agent_id,audit_run_id=audit_run_id,thread_id=thread_id or uuid4().hex, client_id=self.client_id, actor='local-user', status='ready',
            messages=[], pending=[], activity=[], evidence_ids=[], error=None, created_at=timestamp(),
            updated_at=timestamp(), turn_id=None, seen_messages={}, authorization={}, changed=False)
        self.save(thread)
        return thread

    def get_or_create(self, agent_id: str, audit_run_id: str | None, admit: Callable[[], None]) -> dict[str, Any]:
        validate_agent(agent_id)
        validate_run(self.client,audit_run_id)
        with self.lock:
            from .thread_traces import thread_traces
            for path in sorted(self.directory.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
                thread = dict(json.loads(path.read_text()))
                if (not thread.get('ticket_id') and thread.get('agent_id','orchestrator')==agent_id and not thread.get('archived')
                        and not thread['messages'] and thread['status']=='ready' and not thread['pending']):
                    if thread_traces(self.client,thread['thread_id']):
                        continue
                    if audit_run_id and thread.get('audit_run_id')!=audit_run_id:
                        thread['audit_run_id'] = audit_run_id
                        self.save(thread)
                    return thread
            admit()
            return self.create(agent_id,audit_run_id)

    def read(self, thread_id: str) -> dict[str, Any]:
        path = self.path(thread_id)
        if not path.exists():
            raise KeyError('Conversación no encontrada en este cliente.')
        return dict(json.loads(path.read_text()))

    def save(self, thread: dict[str, Any]) -> None:
        thread['updated_at'] = timestamp()
        atomic_write_text(self.path(thread['thread_id']), json.dumps(thread, default=str, ensure_ascii=False))

    def list(self, agent_id: str | None = None, archived: bool = False) -> list[dict[str, Any]]:
        if agent_id:
            validate_agent(agent_id)
        paths = sorted(self.directory.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        from .thread_traces import conversation_summary
        return [conversation_summary(self.client,t) for path in paths for t in [json.loads(path.read_text())]
                if not t.get('ticket_id') and (agent_id is None or t.get('agent_id','orchestrator')==agent_id) and not t.get('internal') and bool(t.get('archived',False))==archived][:30]

    def set_archived(self, thread_id: str, archived: bool) -> dict[str, Any]:
        with self.lock:
            thread = self.read(thread_id)
            if bool(thread.get('archived',False))==archived:
                return thread
            thread.update(archived=archived,archived_at=timestamp() if archived else None)
            self.save(thread)
            return thread

    def activity(self, thread_id: str, name: str, result: Any) -> None:
        with self.lock:
            thread = self.read(thread_id)
            anchor = thread.get('activity_anchor')
            thread['activity'].append(dict(tool=name, result=result, at=timestamp(), turn_id=thread['turn_id'], after_message_id=anchor))
            if isinstance(result, dict):
                refs = [result[key] for key in ('evidence_id','snapshot_id') if result.get(key)]
                if name=='read_ticket_followups':
                    refs.extend(item['evidence_id'] for item in result.get('observations',[]) if item.get('evidence_id'))
                thread['evidence_ids'] = list(dict.fromkeys([*thread['evidence_ids'], *refs]))
            self.save(thread)
            from .report_jobs import report_progress
            report_progress(self,thread,name)

    def working(self, thread_id: str, call_id: str, name: str, active: bool) -> None:
        with self.lock:
            thread = self.read(thread_id)
            work = {item['id']:item for item in thread.get('working_tools', [])}
            if active:
                work[call_id] = dict(id=call_id,tool=name,after_message_id=thread.get('activity_anchor'))
            else:
                work.pop(call_id,None)
            thread['working_tools'] = list(work.values())
            self.save(thread)
