"""Companion preferences. Keys are entered locally and encrypted with user DPAPI."""
from pathlib import Path
import base64,ctypes,json,os,tempfile
from ctypes import wintypes

DEFAULTS=dict(quietEnabled=False,metricMode='off',gameRoots=[],keyCipher='')

def validate(value):
    if not isinstance(value,dict) or type(value.get('quietEnabled')) is not bool or value.get('metricMode') not in ('codex','deepseek','off'):raise ValueError('安静模式或额度设置格式错误')
    roots=value.get('gameRoots')
    if not isinstance(roots,list) or len(roots)>12 or any(not isinstance(p,str) or not Path(p).is_absolute() for p in roots):raise ValueError('游戏目录格式错误')
    if not isinstance(value.get('keyCipher'),str) or len(value['keyCipher'])>8192:raise ValueError('本机授权设置格式错误')

class CompanionStore:
    def __init__(self,base):self.path=Path(base)/'companion_settings.json';self.error=''
    def load(self):
        default=dict(DEFAULTS,gameRoots=[]);self.error=''
        try:
            if not self.path.exists():return default
            if self.path.stat().st_size>16384:raise ValueError('设置文件过大')
            value=json.loads(self.path.read_text(encoding='utf-8-sig'));validate(value);return value
        except (OSError,ValueError,UnicodeError) as exc:self.error=str(exc);return default
    def save(self,value):
        if self.error:raise ValueError('原设置文件损坏并已保留，请先备份修复：'+self.error)
        validate(value);clean={k:value[k] for k in DEFAULTS};self.path.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='.companion-',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(clean,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:Path(name).unlink(missing_ok=True)
        return clean

class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

def _crypt(value,decrypt=False):
    raw=base64.b64decode(value,validate=True) if decrypt else value.encode('utf-8')
    buffer=ctypes.create_string_buffer(raw);incoming=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
    api=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        function=api.CryptUnprotectData
        function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        ok=function(ctypes.byref(incoming),None,None,None,None,1,ctypes.byref(out))
    else:
        function=api.CryptProtectData
        function.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        ok=function(ctypes.byref(incoming),'AgentPet DeepSeek balance',None,None,None,1,ctypes.byref(out))
    if not ok:raise ValueError('本机授权无法读取或保存，请在当前Windows账户重新填写。')
    try:
        result=ctypes.string_at(out.data,out.size)
        return result.decode('utf-8') if decrypt else base64.b64encode(result).decode('ascii')
    finally:kernel.LocalFree(ctypes.cast(out.data,ctypes.c_void_p))

def protect(value):return _crypt(value)
def unprotect(value):return _crypt(value,True)
