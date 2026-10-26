"""Local profile maintenance; never reads Agent accounts or launches the GUI."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,ctypes,json,os,shutil,stat
from pet_paths import SOURCE_DIR,data_dir,cache_dir,profile_id,shortcut_path

def checked_cache_target():
    root=data_dir().resolve();target=cache_dir()
    expected=root/'cache'/'webview2'
    if target!=expected or target.resolve()!=expected or not target.resolve().is_relative_to(root):
        raise ValueError('Refusing cache outside this profile')
    if SOURCE_DIR==target.resolve() or SOURCE_DIR.is_relative_to(target.resolve()):
        raise ValueError('Refusing cache that contains source installation')
    for p in (root/'cache',target):
        if p.exists() or p.is_symlink():
            info=p.lstat()
            if p.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Refusing linked cache path')
    if target.exists():
        if not target.is_dir():raise ValueError('Cache target is not a directory')
        for p in target.rglob('*'):
            if p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&0x400:
                raise ValueError('Refusing reparse points within cache')
    return target

def pending_cache():
    request=data_dir()/'clear-cache.request'
    if not request.exists():return
    if request.stat().st_size>64:raise ValueError('Invalid cache request')
    pid=int(request.read_text(encoding='ascii').strip())
    if not 0<pid<2**32:raise ValueError('Invalid request PID')
    if os.name!='nt':raise RuntimeError('Cache restart requires Windows')
    from ctypes import wintypes as W
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
    k.CloseHandle.argtypes=[W.HANDLE]
    handle=k.OpenProcess(0x100000,False,pid)
    if handle:
        try:
            if k.WaitForSingleObject(handle,20000)!=0:raise RuntimeError('Pet is still closing; cache preserved')
        finally:k.CloseHandle(handle)
    elif ctypes.get_last_error()!=87:raise ctypes.WinError(ctypes.get_last_error())
    target=checked_cache_target()
    if target.exists():shutil.rmtree(target)
    request.unlink()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--paths',action='store_true')
    group.add_argument('--profile-id',action='store_true')
    group.add_argument('--stop',action='store_true')
    group.add_argument('--pending-cache',action='store_true')
    args=parser.parse_args()
    if args.profile_id:print(profile_id());return 0
    if args.stop:
        pid=data_dir()/'pet.pid'
        if not pid.exists():print('No running profile recorded');return 0
        (data_dir()/'stop.request').write_text('User requested graceful stop',encoding='utf-8');return 0
    if args.pending_cache:pending_cache();return 0
    print(json.dumps(dict(source=str(Path(__file__).resolve().parent),data=str(data_dir()),cache=str(cache_dir()),desktop=str(shortcut_path('desktop')),startup=str(shortcut_path('startup'))),ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError) as exc:print(str(exc),file=sys.stderr);raise SystemExit(2)
