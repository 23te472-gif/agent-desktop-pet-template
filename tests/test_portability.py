"""No GUI, network, credentials, real profile, shortcuts or startup writes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
from unittest.mock import patch
import os,json,tempfile,subprocess,unittest,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pet_paths import data_dir,mutex_name,cache_dir
import maintenance

class PortableTests(unittest.TestCase):
    def test_profile_outside_install_and_separate_locks(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ,AGENT_PET_DATA_DIR=str(Path(td)/'first')):
                first=mutex_name();self.assertFalse(data_dir().exists())
            with patch.dict(os.environ,AGENT_PET_DATA_DIR=str(Path(td)/'second')):
                self.assertNotEqual(first,mutex_name())
        with patch.dict(os.environ,AGENT_PET_DATA_DIR=str(ROOT/'data')):
            with self.assertRaises(ValueError):data_dir()
        with patch.dict(os.environ,AGENT_PET_DATA_DIR=str(ROOT.parent)):
            with self.assertRaises(ValueError):data_dir()
    def test_cache_target_boundary_without_deleting(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,AGENT_PET_DATA_DIR=td):
            self.assertEqual(maintenance.checked_cache_target(),Path(td).resolve()/'cache/webview2')
            with patch.object(maintenance,'cache_dir',return_value=Path(td).parent/'elsewhere'):
                with self.assertRaises(ValueError):maintenance.checked_cache_target()
    def test_profiles_have_no_live_defaults(self):
        from pet_companion_config import DEFAULTS
        self.assertEqual(DEFAULTS['metricMode'],'off')
        self.assertEqual(DEFAULTS['keyCipher'],'')
        self.assertEqual(DEFAULTS['gameRoots'],[])
        self.assertEqual(json.loads((ROOT/'assistant_tools.example.json').read_text()),[])
    def test_account_free_preflight_in_relocated_source(self):
        with tempfile.TemporaryDirectory() as td:
            new=Path(td)/"中文 source's copy";new.mkdir()
            # Only code is needed for the intentional missing-resource branch.
            for p in ROOT.glob('*.py'):shutil.copy2(p,new/p.name)
            profile=Path(td)/'fresh profile'
            env=dict(os.environ,AGENT_PET_DATA_DIR=str(profile),PYTHONDONTWRITEBYTECODE='1')
            r=subprocess.run([sys.executable,'-X','utf8',str(new/'run.py'),'--check'],cwd=td,env=env,capture_output=True,text=True,encoding='utf-8',timeout=20)
            self.assertEqual(r.returncode,2,r.stdout+r.stderr)
            self.assertIn('模型',r.stdout)
            self.assertFalse(profile.exists())
            self.assertFalse((new/'pet.pid').exists())
            self.assertFalse((new/'__pycache__').exists())
            r=subprocess.run([sys.executable,'-X','utf8',str(new/'maintenance.py'),'--paths'],cwd=td,env=env,capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(Path(json.loads(r.stdout)['data']),profile.resolve())
            self.assertFalse(profile.exists())
    def test_writes_go_to_selected_profile(self):
        with tempfile.TemporaryDirectory() as td:
            profile=Path(td)/'profile'
            env=dict(os.environ,AGENT_PET_DATA_DIR=str(profile),PYTHONDONTWRITEBYTECODE='1')
            code="import settings_store;from pet_paths import data_dir;from pet_buddy import BuddyStore;settings_store.save({});BuddyStore(data_dir()).record_interaction('pat')"
            r=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=15)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue((profile/'pet_settings.json').exists())
            self.assertTrue((profile/'pet_buddy.json').exists())
            self.assertFalse((ROOT/'pet_settings.json').exists())
    def test_status_bridge_without_bytecode_environment(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'source';source.mkdir()
            for name in ('pet_paths.py','status-bridge.py'):shutil.copy2(ROOT/name,source/name)
            profile=Path(td)/'profile'
            env=dict(os.environ,AGENT_PET_DATA_DIR=str(profile))
            env.pop('PYTHONDONTWRITEBYTECODE',None)
            r=subprocess.run([sys.executable,'-X','utf8',str(source/'status-bridge.py'),'--agent','demo','--state','working','--quiet'],cwd=td,env=env,capture_output=True,text=True,encoding='utf-8',timeout=10)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue((profile/'status/demo.json').is_file())
            self.assertFalse((source/'__pycache__').exists(),'status bridge wrote bytecode into source')

if __name__=='__main__':unittest.main()
