"""Persistent threshold deduplication for fresh official Codex quota snapshots."""
import json,math,os,tempfile,time
from pathlib import Path


class LowQuotaAlerts:
    def __init__(self,base):
        self.path=Path(base)/'quota_alert_state.json';self.seen={};self.error=''
        try:
            if self.path.exists():
                if self.path.stat().st_size>65536:raise ValueError('提醒记录过大')
                value=json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(value,dict) or len(value)>128:raise ValueError('提醒记录无效')
                if any(not isinstance(k,str) or len(k)>160 or type(v) not in (int,float) or not math.isfinite(v) for k,v in value.items()):raise ValueError('提醒记录无效')
                self.seen=value
        except (OSError,ValueError):self.error='额度提醒记录不可用，本次运行仍会去重；原文件保留。'

    def _save(self):
        if self.error:return
        temp=None
        try:
            fd,temp=tempfile.mkstemp(prefix='.quota-alert-',suffix='.tmp',dir=self.path.parent)
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(self.seen,f);f.flush();os.fsync(f.fileno())
            os.replace(temp,self.path);temp=None
        except OSError:self.error='额度提醒记录未能保存，本次运行仍会去重。'
        finally:
            if temp:
                try:os.unlink(temp)
                except OSError:pass

    def _plan(self,row,now):
        """Return (candidates, next_seen, changed) without mutating self.seen."""
        if not isinstance(row,dict) or row.get('error'):return [],dict(self.seen),False
        updated=row.get('updated')
        if type(updated) not in (int,float) or not math.isfinite(updated) or not -60<=now-updated<=900:return [],dict(self.seen),False
        data=row.get('data') or {}
        if data.get('provider')!='codex':return [],dict(self.seen),False
        seen={k:v for k,v in self.seen.items() if v>now}
        changed=len(seen)!=len(self.seen)
        candidates=[]
        for index,window in enumerate(data.get('windows') or []):
            remaining=window.get('remaining');reset=window.get('reset');minutes=window.get('minutes')
            if type(remaining) not in (int,float) or not math.isfinite(remaining) or not 0<=remaining<=100:continue
            if reset is not None and (type(reset) not in (int,float) or not math.isfinite(reset) or reset<=now):continue
            identity=str(minutes)+':'+str(reset)+':'+str(index)
            if reset is None and remaining>=20:
                for threshold in (20,10):
                    if seen.pop(identity+':'+str(threshold),None) is not None:changed=True
            thresholds=[t for t in (20,10) if remaining<t]
            unseen=[t for t in thresholds if identity+':'+str(t) not in seen]
            if not unseen:continue
            for threshold in thresholds:seen[identity+':'+str(threshold)]=reset if reset is not None else now+30*86400
            changed=True
            candidates.append(dict(threshold=min(unseen),remaining=remaining,window=dict(window),key=identity+':'+str(min(unseen))))
        if len(seen)>128:
            seen=dict(sorted(seen.items(),key=lambda item:item[1],reverse=True)[:128]);changed=True
        return candidates,seen,changed

    def peek(self,row,now=None):
        """Return the next alert without consuming it (DND/quiet safe)."""
        now=time.time() if now is None else now
        candidates,_,_=self._plan(row,now)
        return min(candidates,key=lambda item:item['remaining']) if candidates else None

    def acknowledge(self,keys,now=None):
        """Acknowledge only the exact quota events included in a delivered summary."""
        now=time.time() if now is None else now
        seen={k:v for k,v in self.seen.items() if v>now}
        before=dict(seen)
        for key in keys:
            if not isinstance(key,str) or len(key)>160:continue
            try:
                identity,threshold_text=key.rsplit(':',1)
                minutes,reset_text,index=identity.split(':')
                threshold=int(threshold_text)
                if threshold not in (20,10) or not index.isdigit():continue
                expiry=now+30*86400 if reset_text=='None' else float(reset_text)
                if not math.isfinite(expiry) or expiry<=now:continue
            except (ValueError,TypeError):continue
            for level in (20,10):
                if level>=threshold:seen[identity+':'+str(level)]=expiry
        if seen!=before:
            self.seen=dict(sorted(seen.items(),key=lambda item:item[1],reverse=True)[:128]);self._save()

    def observe(self,row,now=None,quiet=False):
        now=time.time() if now is None else now
        if quiet or not isinstance(row,dict) or row.get('error'):return
        candidates,seen,changed=self._plan(row,now)
        if changed:
            self.seen=seen;self._save()
        if candidates:return min(candidates,key=lambda item:item['remaining'])
