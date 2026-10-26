"""Installation resources and per-user state are deliberately separate."""
from pathlib import Path
import hashlib,os,ctypes

SOURCE_DIR=Path(__file__).resolve().parent

def data_dir(create=False):
    override=os.environ.get('AGENT_PET_DATA_DIR')
    if override:
        result=Path(override).expanduser()
        if not result.is_absolute():raise ValueError('AGENT_PET_DATA_DIR must be an absolute path')
    else:
        base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'.local/share')
        result=base/'AgentDesktopPet'
    result=result.resolve()
    # A user may run from a read-only installation; never store state in it.
    if result==SOURCE_DIR or result.is_relative_to(SOURCE_DIR) or SOURCE_DIR.is_relative_to(result):
        raise ValueError('Source and data directories must be separate, without containing each other')
    if create:result.mkdir(parents=True,exist_ok=True)
    return result

def cache_dir():return data_dir()/'cache'/'webview2'
def profile_id():return hashlib.sha256(os.path.normcase(str(data_dir())).encode('utf-8')).hexdigest()[:12]
def mutex_name():return 'Local\\AgentDesktopPet.'+profile_id()

def shortcut_path(kind):
    if kind not in ('desktop','startup'):raise ValueError('Unknown shortcut folder')
    if os.name=='nt':
        buffer=ctypes.create_unicode_buffer(32768)
        api=ctypes.windll.shell32.SHGetFolderPathW
        if api(None,0x10 if kind=='desktop' else 0x07,None,0,buffer)==0:
            return Path(buffer.value)/('AgentDesktopPet-'+profile_id()+'.lnk')
    root=Path.home()/'Desktop' if kind=='desktop' else Path(os.environ.get('APPDATA') or Path.home())/'Microsoft/Windows/Start Menu/Programs/Startup'
    return root/('AgentDesktopPet-'+profile_id()+'.lnk')
