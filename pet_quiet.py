"""Steam game foreground/fullscreen detection. No game files or process memory read."""
from pathlib import Path
import ctypes,ntpath,os,re,time
from ctypes import wintypes

def covers_monitor(rect,monitor):
    a,b,c,d=rect;x,y,z,w=monitor
    return a<=x+12 and b<=y+12 and c>=z-12 and d>=w-12

def is_game_path(path,roots):
    normalized=ntpath.normcase(ntpath.abspath(path))
    if not normalized.endswith('.exe'):return False
    for root in roots:
        base=ntpath.normcase(ntpath.abspath(str(root))).rstrip('\\')+'\\'
        if normalized.startswith(base):return True
    return False

def steam_roots(extra=()):
    candidates=[Path(os.environ[key])/'Steam' for key in ('ProgramFiles(x86)','ProgramFiles') if os.environ.get(key)]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:candidates.insert(0,Path(winreg.QueryValueEx(key,'SteamPath')[0]))
    except OSError:pass
    libraries=list(candidates)
    for root in candidates:
        try:
            file=root/'steamapps/libraryfolders.vdf'
            if file.stat().st_size>1024*1024:continue
            text=file.read_text(encoding='utf-8-sig')
            for path in re.findall(r'"path"\s*"((?:\\.|[^"\\])*)"',text):libraries.append(Path(path.replace('\\\\','\\')))
        except (OSError,UnicodeError):pass
    roots=[p/'steamapps/common' for p in libraries if (p/'steamapps/common').is_dir()]
    return list(dict.fromkeys(str(p) for p in roots))+list(extra)

class MonitorInfo(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('monitor',wintypes.RECT),('work',wintypes.RECT),('flags',wintypes.DWORD)]

class GameDetector:
    def __init__(self,extra=()):
        self.roots=steam_roots(extra);self.last=0;self.value=False
        self.user=ctypes.WinDLL('user32',use_last_error=True);self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.user.GetForegroundWindow.restype=wintypes.HWND
        self.user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        self.user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        self.user.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD];self.user.MonitorFromWindow.restype=wintypes.HANDLE
        self.user.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MonitorInfo)]
        self.kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];self.kernel.OpenProcess.restype=wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
        self.kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    def poll(self,now=None):
        now=time.monotonic() if now is None else now
        if now-self.last<2:return self.value
        self.last=now;self.value=False
        hwnd=self.user.GetForegroundWindow()
        if not hwnd:return False
        rect=wintypes.RECT();monitor=MonitorInfo();monitor.size=ctypes.sizeof(monitor)
        if not self.user.GetWindowRect(hwnd,ctypes.byref(rect)) or not self.user.GetMonitorInfoW(self.user.MonitorFromWindow(hwnd,2),ctypes.byref(monitor)):return False
        if not covers_monitor((rect.left,rect.top,rect.right,rect.bottom),(monitor.monitor.left,monitor.monitor.top,monitor.monitor.right,monitor.monitor.bottom)):return False
        pid=wintypes.DWORD();self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        handle=self.kernel.OpenProcess(0x1000,False,pid.value)
        if not handle:return False
        try:
            size=wintypes.DWORD(32768);buffer=ctypes.create_unicode_buffer(size.value)
            if self.kernel.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(size)):self.value=is_game_path(buffer.value,self.roots)
        finally:self.kernel.CloseHandle(handle)
        return self.value

class QuietState:
    def __init__(self):self.active=False;self.restore_pet=False;self.restore_card=False;self.override=False
    def user_hide(self):self.restore_pet=False;self.restore_card=False
    def user_show(self):self.override=True;self.restore_pet=True
    def update(self,game,enabled,pet_visible,card_visible):
        if not game:self.override=False
        wanted=bool(game and enabled and not self.override)
        if wanted==self.active:return None
        self.active=wanted
        if wanted:self.restore_pet=pet_visible;self.restore_card=card_visible;return 'enter'
        return 'exit'
