"""Small, credential-free view model and command boundary for the quota bubble."""
import json,math,time
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from datetime import datetime,timezone,timedelta

TOKYO=timezone(timedelta(hours=9))
ACTIONS=frozenset(('ready','refresh','more','close','drag'))

def bridge_action(raw,origin,expected):
    if origin!=expected or not isinstance(raw,str) or len(raw)>2048:return None
    try:value=json.loads(raw)
    except (ValueError,TypeError):return None
    if not isinstance(value,dict) or not isinstance(value.get('action'),str):return None
    return value['action'] if value['action'] in ACTIONS else None

def _number(value):
    return float(value) if type(value) in (int,float) and math.isfinite(value) else None

def _level(value):
    return 'green' if value>=50 else 'yellow' if value>=20 else 'red'

def _window_label(minutes):
    minutes=_number(minutes)
    if not minutes:return '窗口'
    if minutes>=1440:return f'{minutes/1440:g}天'
    if minutes>=60:return f'{minutes/60:g}小时'
    return f'{minutes:g}分'

def _reset_text(stamp,now):
    stamp=_number(stamp)
    if stamp is None:return '重置时间暂不可用'
    if stamp<=now:return '已到重置时间，请刷新'
    minutes=max(1,math.ceil((stamp-now)/60))
    if minutes>=1440:return f'{minutes//1440} 天 {minutes%1440//60} 小时后重置'
    if minutes>=60:return f'{minutes//60} 小时'+(f' {minutes%60} 分钟' if minutes%60 else '')+'后重置'
    return f'{minutes} 分钟后重置'

def metric_view(mode,row,busy,now=None):
    now=time.time() if now is None else now
    source={'codex':'Codex','deepseek':'DeepSeek API','off':'额度已关闭'}.get(mode,'额度')
    view=dict(source=source,amount='暂不可用',meta='可从更多菜单刷新或检查设置',status='unavailable',level='unknown')
    if mode=='off':return dict(source=source,amount='已关闭',meta='可从更多菜单切换来源',status='off',level='unknown')
    data=row.get('data') if isinstance(row,dict) else None
    if not data:
        if busy:view.update(amount='正在读取…',meta='稍后显示剩余信息',status='loading')
        return view
    try:
        if data.get('provider')!=mode:return view
        expired=False
        if mode=='deepseek':
            balances=data.get('balances') or []
            if not balances:return view
            money=[Decimal(str(item['amount'])) for item in balances[:3]]
            if not all(value.is_finite() for value in money):return view
            amount=' / '.join(str(item['currency'])+' '+format(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') for item,value in zip(balances[:3],money))
            view['amount']='余额 '+amount
            view['level']=_level(min(money))
            updated=_number(row.get('updated'))
            view['meta']='更新于 '+datetime.fromtimestamp(updated,TOKYO).strftime('%H:%M') if updated else '更新时间暂不可用'
            view['status']='normal'
        elif mode=='codex':
            windows=data.get('windows') or []
            if not windows:return view
            rows=[];remaining=[];resets=[]
            for window in windows[:2]:
                value=_number(window.get('remaining'));reset=_number(window.get('reset'))
                if value is None:return view
                remaining.append(value)
                is_expired=reset is not None and reset<=now
                expired=expired or is_expired
                rows.append((_window_label(window.get('minutes'))+' ' if len(windows)>1 else '剩余 ')+('需刷新' if is_expired else f'{value:g}%'))
                if reset is not None:resets.append(reset)
            view['amount']=' · '.join(rows)
            view['meta']=_reset_text(min(resets) if resets else None,now)
            view['status']='stale' if expired else 'low' if min(remaining)<20 else 'normal'
            view['level']='unknown' if expired else _level(min(remaining))
        stale=bool(row.get('error')) or now-(row.get('updated') or 0)>900
        if stale and not expired:view.update(meta='上次结果 · '+view['meta'],status='stale')
        if busy:view.update(meta='正在刷新 · 上次结果',status='loading')
        view['amount']=view['amount'][:256];view['meta']=view['meta'][:160]
        return view
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError,InvalidOperation):
        return dict(source=source,amount='暂不可用',meta='请刷新后重试',status='unavailable',level='unknown')
