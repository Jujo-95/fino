from typing import Any
from langgraph.types import interrupt
from ..engine.report_guard import repeat_prompt


def confirm_repeat(ctx: Any) -> bool:
    scope = ctx.evidence.current().state
    thread = ctx.store.read(ctx.thread_id)
    if thread.get('declined_report_turn')==ctx.turn_id:
        return False
    prompt = repeat_prompt(ctx.client,scope['period_start_utc'],scope['period_end_utc'])
    if not prompt or repeat_token(thread)==prompt['confirmation_id']:
        return True
    decision = interrupt(prompt)
    thread = ctx.store.read(ctx.thread_id)
    if decision.get('plan_ids')!=[prompt['confirmation_id']] or decision.get('message_id')!=thread.get('resume_message_id'):
        raise ValueError('La confirmación no corresponde a este informe y conversación.')
    if decision['decision']!='approve':
        thread['declined_report_turn']=ctx.turn_id
        ctx.store.save(thread)
        return False
    current = repeat_prompt(ctx.client,scope['period_start_utc'],scope['period_end_utc'])
    if current and current['confirmation_id']!=prompt['confirmation_id']:
        raise ValueError('Se creó otro informe mientras confirmabas; revisa la nueva confirmación.')
    thread['report_repeat_authorization'] = dict(turn_id=ctx.turn_id,confirmation_id=prompt['confirmation_id'],
        message_id=decision['message_id'],actor='local-user')
    ctx.store.save(thread)
    return True


def repeat_token(thread: dict[str,Any]) -> str | None:
    auth = thread.get('report_repeat_authorization') or {}
    if auth.get('turn_id')==thread.get('turn_id') and auth.get('actor')=='local-user':
        return auth.get('confirmation_id')
    return None
