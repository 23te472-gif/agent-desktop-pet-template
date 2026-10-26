"""Agent ownership and selected-inbox views; no polling, credentials or GUI."""
import re

def normalize_agent(value):
    return value if isinstance(value,str) and re.fullmatch(r'[a-z0-9_-]{1,40}',value) else 'codex'

def selected_agent(host):
    settings=getattr(host,'settings',{})
    return normalize_agent(settings.get('agent')) if isinstance(settings,dict) else 'codex'

def agent_name(value):
    key=normalize_agent(value)
    try:
        import agent_state
        return next((str(x['name'])[:80] for x in agent_state.agent_list() if x['id']==key),key)
    except Exception:return key

def selected_items(host,items=None,agent=None):
    key=selected_agent(host) if agent is None else normalize_agent(agent)
    if items is None:items=host.buddy.snapshot()['inbox']
    return [x for x in items if normalize_agent(x.get('agent'))==key]

def selected_unread(host):
    return sum(1 for x in selected_items(host) if not x.get('read'))

def validate_scope(host,data):
    key=selected_agent(host)
    if 'agent' in data and data['agent']!=key:raise ValueError('Agent已切换，请在当前收件箱重试。')
    return key
