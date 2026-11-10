import pytest
from finops_agent.chat.tools import chat_tools
from finops_agent.chat.store import ChatStore


@pytest.mark.asyncio
async def test_chat_uses_existing_scoped_queries_and_script_snapshots(container,csv_path):
    client = container.client('acme')
    client.engine.ingest_focus_csv('acme',csv_path)
    thread = ChatStore(client).create()
    thread.update(turn_id='test-turn',ticket_refs=[])
    ChatStore(client).save(thread)
    tools = {t.name:t for t in chat_tools(container,'acme',thread['thread_id'],'test-turn')}
    query = await tools['query_focus'].ainvoke(dict(query_id='totals'))
    assert query['parameters']['client_id']=='acme'
    assert query['source']=='agent_tool'
    scripts = await tools['read_scripts'].ainvoke({})
    assert scripts['source']=='script_snapshot'
    assert scripts['data']['actual']==49110
    saved = ChatStore(client).read(thread['thread_id'])
    assert query['evidence_id'] in saved['evidence_ids']
    with pytest.raises(ValueError):
        await tools['query_focus'].ainvoke(dict(query_id='DROP TABLE focus_usage'))
