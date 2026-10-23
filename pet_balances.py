"""Read official account snapshots; never estimates money from token counts."""
from datetime import datetime,timezone,timedelta
from decimal import Decimal,InvalidOperation
from pathlib import Path
import json,math,os,queue,shutil,subprocess,threading,time
import urllib.request,urllib.error
from pet_companion_config import unprotect

TOKYO=timezone(timedelta(hours=9))

def parse_codex(raw):
    buckets=raw.get('rateLimitsByLimitId') or {};bucket=buckets.get('codex') or raw.get('rateLimits') or {}
    windows=[]
    for key in ('primary','secondary'):
        value=bucket.get(key)
        if value is None:continue
        used=value.get('usedPercent')
        if type(used) not in (int,float) or not math.isfinite(used):raise ValueError('额度百分比格式错误')
        reset=value.get('resetsAt');duration=value.get('windowDurationMins')
        if reset is not None and (type(reset) not in (int,float) or not math.isfinite(reset) or reset<0 or reset>32503680000):raise ValueError('重置时间格式错误')
        if duration is not None and (type(duration) not in (int,float) or duration<=0 or not math.isfinite(duration)):raise ValueError('额度窗口格式错误')
        windows.append(dict(remaining=max(0,min(100,100-used)),reset=reset,minutes=duration))
    if not windows:raise ValueError('当前登录未返回Codex额度；请确认本机Codex CLI已登录ChatGPT账户。')
    return dict(provider='codex',windows=windows)

def parse_deepseek(raw):
    rows=raw.get('balance_infos')
    if not isinstance(rows,list) or not rows:raise ValueError('平台未返回余额')
    balances=[]
    for row in rows:
        if not isinstance(row,dict) or row.get('currency') not in ('CNY','USD') or not isinstance(row.get('total_balance'),str):raise ValueError('余额数据格式错误')
        try:value=Decimal(row['total_balance'])
        except InvalidOperation:raise ValueError('余额金额格式错误') from None
        if not value.is_finite() or abs(value)>Decimal('1e12'):raise ValueError('余额金额格式错误')
        balances.append(dict(currency=row['currency'],amount=format(value,'.2f')))
    return dict(provider='deepseek',balances=balances)

def format_metric(value,now=None,detailed=False):
    now=time.time() if now is None else now
    if value['provider']=='deepseek':return 'DeepSeek 余额 '+ ' / '.join(row['currency']+' '+row['amount'] for row in value['balances'])
    rows=[]
    for i,window in enumerate(value['windows']):
        minutes=window['minutes'];label=(f'{minutes/1440:g}天' if minutes and minutes>=1440 else f'{minutes/60:g}小时' if minutes and minutes>=60 else f'{minutes:g}分钟' if minutes else f'窗口{i+1}')
        expired=window['reset'] is not None and window['reset']<=now
        row=label+('需刷新' if expired else f'剩余{window["remaining"]:g}%')
        if detailed:
            row+='；重置 '+(datetime.fromtimestamp(window['reset'],TOKYO).strftime('%m-%d %H:%M')+' 东京' if window['reset'] is not None else '时间暂不可用')
        rows.append(row)
    return 'Codex '+ ('\n'.join(rows) if detailed else ' / '.join(rows))

def find_codex():
    command=shutil.which('codex')
    if command and Path(command).suffix.lower()=='.exe':return command
    base=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'OpenAI/Codex/bin'
    candidates=list(base.glob('*/codex.exe'))
    if candidates:return str(max(candidates,key=lambda p:p.stat().st_mtime))
    raise ValueError('未找到本机Codex CLI；请先完成Codex安装和ChatGPT登录。')

def read_codex():
    process=subprocess.Popen([find_codex(),'app-server'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        text=True,encoding='utf-8',bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    inbox=queue.Queue(maxsize=32)
    def reader():
        try:
            for line in process.stdout:
                if len(line)>262144:break
                try:value=json.loads(line)
                except ValueError:continue
                if isinstance(value,dict) and value.get('id') in (1,2):inbox.put(value,timeout=1)
        except (OSError,ValueError,queue.Full):pass
    thread=threading.Thread(target=reader,name='pet-quota-response',daemon=True);thread.start()
    deadline=time.monotonic()+20
    def send(value):process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
    def response(expected):
        while time.monotonic()<deadline:
            try:value=inbox.get(timeout=max(.1,deadline-time.monotonic()))
            except queue.Empty:break
            if value.get('id')==expected:
                if 'error' in value:raise ValueError('Codex额度暂不可用；请确认本机CLI已登录ChatGPT，且账户支持额度查询。')
                return value.get('result') or {}
        raise ValueError('Codex额度查询超时，请稍后刷新。')
    try:
        send(dict(id=1,method='initialize',params=dict(clientInfo=dict(name='agent_pet_quota',version='1.0.0'))));response(1)
        send(dict(method='initialized',params={}))
        send(dict(id=2,method='account/rateLimits/read'));return parse_codex(response(2))
    finally:
        try:process.stdin.close()
        except OSError:pass
        try:process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=2)
        thread.join(timeout=1);process.stdout.close()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def read_deepseek(cipher):
    if not cipher:raise ValueError('请在本机设置中配置DeepSeek官方API密钥。其他平台的密钥不能用于此接口。')
    key=unprotect(cipher)
    if not 8<=len(key)<=512 or any(ord(c)<=32 or ord(c)>=127 for c in key):raise ValueError('本机DeepSeek密钥格式不正确，请重新配置。')
    request=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+key,'Accept':'application/json'},method='GET')
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=12) as response:
            raw=response.read(65537)
            if len(raw)>65536:raise ValueError('余额响应过大')
        return parse_deepseek(json.loads(raw))
    except urllib.error.HTTPError as exc:
        raise ValueError('DeepSeek密钥无效或未授权。' if exc.code in (401,403) else 'DeepSeek查询限流，请稍后重试。' if exc.code==429 else 'DeepSeek余额查询暂不可用。') from None
    except (urllib.error.URLError,TimeoutError,OSError):raise ValueError('DeepSeek网络连接失败，请稍后重试。') from None

class MetricService:
    def __init__(self,config):self.config=config;self.cache={};self.busy=False;self.attempts={};self.lock=threading.Lock()
    def refresh(self,force=False):
        mode=self.config['metricMode'];now=time.monotonic()
        if mode=='off':return False
        with self.lock:
            if self.busy or (not force and now-self.attempts.get(mode,-10000)<300):return False
            self.busy=True;self.attempts[mode]=now;cipher=self.config.get('keyCipher','')
        def work():
            try:
                data=read_codex() if mode=='codex' else read_deepseek(cipher)
                self.cache[mode]=dict(data=data,updated=time.time(),error='')
            except Exception as exc:
                # Only explicit sanitized domain messages reach the UI; never log credentials or response bodies.
                message=str(exc) if isinstance(exc,ValueError) else '查询失败，请检查登录或网络后重试。'
                previous=dict(self.cache.get(mode,{}));previous['error']=message;self.cache[mode]=previous
            finally:
                with self.lock:self.busy=False
        threading.Thread(target=work,name='pet-account-snapshot',daemon=True).start();return True
    def text(self,detailed=False):
        mode=self.config['metricMode']
        if mode=='off':return '额度显示已关闭'
        row=self.cache.get(mode,{})
        if not row.get('data'):return row.get('error') or ('正在查询…' if self.busy else '尚未刷新')
        text=format_metric(row['data'],detailed=detailed)
        stale=bool(row.get('error')) or time.time()-row['updated']>900
        if stale:text+='（上次结果，需刷新）'
        if detailed:
            text+='\n更新：'+datetime.fromtimestamp(row['updated'],TOKYO).strftime('%m-%d %H:%M:%S')+' 东京'
            if row.get('error'):text+='\n'+row['error']
        return text
