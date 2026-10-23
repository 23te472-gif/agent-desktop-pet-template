"""Local reminders and explicit tool launching, independent of the Live2D host."""
from collections import OrderedDict
from pathlib import Path
import ctypes,json,os,re,subprocess,sys,tempfile,time
from ctypes import wintypes

DEFAULTS=dict(done=True,waiting=True,sound=False,showTitle=True)
ACTIVE=frozenset(('thinking','working','review','syncing'))
# These titles belong to pywebview/WinForms windows. A matching title alone is
# not trusted: data/instance.json must name the PID that owns the window.
WEBVIEW_TITLES=frozenset(('个人工具中心 · 2.0',))

class ReminderGate:
    def __init__(self,clock=time.monotonic):self.clock=clock;self.contexts=OrderedDict()
    def observe(self,agent,payload,options):
        now=self.clock();state=payload.get('state');thread=str(payload.get('threadId') or payload.get('title') or 'current')
        key=(agent,thread)
        if key not in self.contexts:self.contexts[key]=dict(state=state,changed=now,armed=state in ACTIVE,last={})
        entry=self.contexts[key];self.contexts.move_to_end(key)
        while len(self.contexts)>128:self.contexts.popitem(last=False)
        if state!=entry['state']:entry.update(state=state,changed=now)
        if state in ACTIVE:entry['armed']=True;return None
        if state in ('idle','error','interrupted'):entry['armed']=False;return None
        if state not in ('done','waiting') or not entry['armed'] or now-entry['changed']<2:return None
        entry['armed']=False
        previous=entry['last'].get(state)
        if previous is not None and now-previous<30:return None
        if not options.get(state,True):return None
        entry['last'][state]=now
        title=' '.join(str(payload.get('title') or '').split())[:80]
        return dict(kind=state,title=title,agent=agent,thread=thread)

class AssistantStore:
    def __init__(self,base):self.path=Path(base)/'assistant_settings.json';self.error=''
    def load(self):
        self.error=''
        try:
            if not self.path.exists():return dict(DEFAULTS)
            if self.path.stat().st_size>8192:raise ValueError('提醒设置文件过大')
            value=json.loads(self.path.read_text(encoding='utf-8-sig'))
            if not isinstance(value,dict) or any(type(value.get(k,v)) is not bool for k,v in DEFAULTS.items()):raise ValueError('提醒设置格式错误')
            return {k:value.get(k,v) for k,v in DEFAULTS.items()}
        except (OSError,ValueError,UnicodeError) as exc:self.error=str(exc);return dict(DEFAULTS)
    def save(self,value):
        if self.error:raise ValueError('原提醒设置未读取，文件保留；请先备份并修复：'+self.error)
        if not isinstance(value,dict) or any(type(value.get(k)) is not bool for k in DEFAULTS):raise ValueError('提醒设置格式错误')
        clean={k:value[k] for k in DEFAULTS};self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.assistant-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(clean,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:Path(name).unlink(missing_ok=True)
        return clean

def load_tools(base):
    path=Path(base)/'assistant_tools.json'
    if not path.exists():return []
    if path.stat().st_size>65536:raise ValueError('工具菜单文件过大')
    entries=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(entries,list) or len(entries)>20:raise ValueError('工具菜单格式错误')
    ids=set()
    for entry in entries:
        if not isinstance(entry,dict) or any(not isinstance(entry.get(k),str) or not entry[k] for k in ('id','name','kind','path')):raise ValueError('工具菜单字段缺失')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',entry['id']) or len(entry['name'])>80:raise ValueError('工具标识或名称无效')
        if entry['id'] in ids or entry['kind'] not in ('app','folder') or not Path(entry['path']).is_absolute():raise ValueError('工具菜单包含重复项或无效路径')
        if entry['kind']=='app' and (not isinstance(entry.get('title'),str) or not entry['title'] or Path(entry['path']).suffix.lower()!='.py'):raise ValueError('工具入口需为本地Python脚本及准确窗口名称')
        ids.add(entry['id'])
    return entries

class ToolWindows:
    def __init__(self):
        self.api=ctypes.WinDLL('user32',use_last_error=True) if os.name=='nt' else None
        if self.api:
            self.api.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR];self.api.FindWindowW.restype=wintypes.HWND
            self.api.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int];self.api.ShowWindow.restype=wintypes.BOOL
            self.api.SetForegroundWindow.argtypes=[wintypes.HWND];self.api.SetForegroundWindow.restype=wintypes.BOOL
            self.api.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)];self.api.GetWindowThreadProcessId.restype=wintypes.DWORD
    def _instance_pid(self,app_dir):
        """Read only the PID from the app's single-instance file; never the token."""
        try:
            path=Path(app_dir)/'data/instance.json'
            if path.stat().st_size>4096:return None
            value=json.loads(path.read_text(encoding='utf-8-sig'))
            pid=value.get('pid')
            return pid if type(pid) is int and pid>0 else None
        except (OSError,ValueError,TypeError,AttributeError):
            return None
    def _window_pid(self,hwnd):
        pid=wintypes.DWORD()
        if not self.api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid)):return None
        return pid.value or None
    def find(self,title,app_dir=None):
        if not self.api:return None
        if title in WEBVIEW_TITLES:
            if app_dir is None:return None
            expected=self._instance_pid(app_dir)
            if expected is None:return None
            hwnd=self.api.FindWindowW(None,title)
            if not hwnd:return None
            return hwnd if self._window_pid(hwnd)==expected else None
        # Legacy Tk tools keep the original exact class/title lookup.
        return self.api.FindWindowW('TkTopLevel',title)
    def focus(self,hwnd):
        if self.api:self.api.ShowWindow(hwnd,9);self.api.SetForegroundWindow(hwnd)

class ToolLauncher:
    def __init__(self,base,windows=None,spawn=None,open_folder=None):
        self.base=Path(base);self.windows=windows or ToolWindows();self.spawn=spawn or subprocess.Popen;self.open_folder=open_folder or os.startfile;self.processes={};self.entries={}
    def open(self,entry):
        path=Path(entry['path'])
        if entry['kind']=='folder':
            if not path.is_dir():raise FileNotFoundError('文件夹已移动或不存在：'+str(path))
            self.open_folder(str(path));return dict(action='folder',message='已打开 '+entry['name'])
        try:hwnd=self.windows.find(entry['title'],path.parent)
        except TypeError:hwnd=self.windows.find(entry['title'])
        if hwnd:self.windows.focus(hwnd);return dict(action='focused',message='已唤起 '+entry['name'])
        current=self.processes.get(entry['id'])
        if current and current.poll() is None:return dict(action='pending',message='工具正在运行或启动中，请从任务栏查看；未重复启动。')
        if not path.is_file():raise FileNotFoundError('工具入口已移动或不存在：'+str(path))
        folder=self.base/'assistant_logs';folder.mkdir(exist_ok=True)
        log=folder/(entry['id']+'-'+str(time.time_ns())+'.log')
        with log.open('wb') as stream:
            process=self.spawn([sys.executable,str(path)],cwd=str(path.parent),stdout=stream,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.processes[entry['id']]=process
        self.entries[entry['id']]=entry
        return dict(action='started',message='正在打开 '+entry['name'])
    def poll(self):
        messages=[]
        for key,process in list(self.processes.items()):
            code=process.poll()
            if code is not None:
                name=self.entries.pop(key)['name'];self.processes.pop(key,None)
                messages.append(name+('已关闭。' if code==0 else '启动或运行失败，请打开工具启动日志查看详情。'))
        return messages
