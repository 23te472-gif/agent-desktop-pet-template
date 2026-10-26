"""Credential-free view and narrowly scoped commands for the desktop panels."""
import json,math
from pet_agent_reminders import selected_agent,selected_items,selected_unread,validate_scope,agent_name

ACTIONS=frozenset(('ready','close','drag','resize','view','save','dnd','cancel-dnd','game','folder','read','read-all','clear','pet','feedback','goal','test'))
VIEWS=frozenset(('reminder','dnd','companion','inbox'))

def decode_message(raw,origin,expected):
    if origin!=expected or not isinstance(raw,str) or len(raw)>8192:return None
    try:data=json.loads(raw)
    except (ValueError,TypeError):return None
    if not isinstance(data,dict) or not isinstance(data.get('action'),str) or data['action'] not in ACTIONS:return None
    return data

def panel_theme(h):
    settings=getattr(h,"settings",{})
    return "ice" if isinstance(settings,dict) and settings.get("settingsTheme")=="ice" else "paper"

def panel_snapshot(h):
    agent=selected_agent(h)
    items=selected_items(h,agent=agent)
    settings={key:bool(h.assistant_settings.get(key)) for key in ('done','waiting','sound','showTitle')}
    inbox=[]
    for item in items[:100]:
        inbox.append(dict(id=str(item['id'])[:128],kind=str(item.get('kind',''))[:32],at=item.get('at',0),read=bool(item.get('read')),
            title=str(item.get('title') or '任务标题已隐藏')[:300] if settings['showTitle'] else '任务标题已隐藏'))
    return dict(settingsTheme=panel_theme(h),agent=agent,agentName=agent_name(agent),settings=settings,inbox=inbox,unread=sum(1 for x in items if not x.get("read")),
        dnd=bool(h.buddy.dnd_active()),remaining=h.buddy.dnd_remaining(),
        game=bool(h.companion_config.get('quietEnabled')),gameActive=bool(h.quiet_state.active),
        roots=len(h.companion_config.get('gameRoots',[])),interaction=h.buddy.interaction_snapshot(),
        error=str(getattr(h.buddy,'last_error','') or getattr(h.buddy,'error',''))[:240])

def apply_action(h,data):
    action=data.get('action')
    if action=='save':
        values=data.get('settings');keys=('done','waiting','sound','showTitle')
        if not isinstance(values,dict) or set(values)!=set(keys) or any(type(values[k]) is not bool for k in keys):raise ValueError('提醒设置格式无效')
        h.assistant_settings=h.assistant_store.save(values)
        if not h.assistant_settings['showTitle']:h.buddy.hide_titles()
    elif action=='dnd':
        minutes=data.get('minutes')
        if minutes is not None and (type(minutes) is not int or not 1<=minutes<=60):raise ValueError('勿扰时长无效')
        h.buddy.set_dnd(minutes)
    elif action=='cancel-dnd':h.buddy.cancel_dnd();h.on_buddy_timer()
    elif action=='game':
        value=data.get('enabled')
        if type(value) is not bool:raise ValueError('游戏设置格式无效')
        clean=h.companion_store.save(dict(h.companion_config,quietEnabled=value))
        h.companion_config=clean;h.metric_service.config=clean;h.update_game_quiet()
    elif action=='read':
        item_id=data.get('id')
        if not isinstance(item_id,str) or len(item_id)>128:raise ValueError('提醒编号无效')
        h.buddy.mark_read(item_id,agent=validate_scope(h,data));h.update_buddy_badge()
    elif action=='read-all':h.buddy.mark_all_read(agent=validate_scope(h,data));h.update_buddy_badge()
    elif action in ('feedback','goal'):
        enabled=data.get('enabled')
        if type(enabled) is not bool:raise ValueError('互动设置格式无效')
        (h.buddy.set_feedback if action=='feedback' else h.buddy.set_goal)(enabled)
    elif action=='pet':
        kind=data.get('kind')
        if kind=='pat':h.user_interaction('pat')
        elif kind=='face':h.post({'t':'cycle-expression'})
        elif kind=='move':h.post({'t':'react','kind':'motion'})
        else:raise ValueError('互动操作无效')
    elif action=='test':h.show_assistant_notification(dict(kind='test',title='测试提醒'))
    else:raise ValueError('未知操作')


def resize_bounds(original,edge,dx,dy,minimum,area):
    """Constrain pointer deltas to this panel and the current working area."""
    if not isinstance(edge,str) or edge not in ('n','ne','e','se','s','sw','w','nw'):raise ValueError('缩放方向无效')
    if any(type(value) not in (int,float) or not math.isfinite(value) or abs(value)>20000 for value in (dx,dy)):raise ValueError('缩放位移无效')
    def axis(position,length,delta,minimum,low,high,leading,trailing):
        minimum=min(max(1,minimum),high-low)
        if leading:
            fixed=max(low+minimum,min(high,position+length))
            origin=max(low,min(fixed-minimum,position+round(delta)))
            return origin,fixed-origin
        if trailing:
            origin=max(low,min(high-minimum,position))
            end=max(origin+minimum,min(high,position+length+round(delta)))
            return origin,end-origin
        size=max(minimum,min(high-low,length))
        return max(low,min(high-size,position)),size
    x,y,width,height=original;left,top,right,bottom=area
    new_x,new_width=axis(x,width,dx,minimum[0],left,right,'w' in edge,'e' in edge)
    new_y,new_height=axis(y,height,dy,minimum[1],top,bottom,'n' in edge,'s' in edge)
    return int(new_x),int(new_y),int(new_width),int(new_height)
