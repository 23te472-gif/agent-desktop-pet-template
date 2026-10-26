"""On-demand WebView2 panels, sharing the pet runtime and local state stores."""
import ctypes,json,time
from pet_agent_reminders import validate_scope
from pet_panel_actions import decode_message,panel_snapshot,apply_action,VIEWS,resize_bounds,panel_theme

def open_control_center(host):
    native=getattr(host,'assistant_panels',{}).get('control')
    if native is not None and not native.IsDisposed:
        native.Show();native.Activate();return native
    old=getattr(host,'_desktop_panel_controller',None)
    view=old.view if old is not None and not old.closed else getattr(host,'_desktop_panel_last_view','reminder')
    result=open_desktop_panel(host,view if view in VIEWS else 'reminder')
    controller=getattr(host,'_desktop_panel_controller',None)
    if controller is not None and not controller.closed:controller.control_entry=True
    return result

def open_desktop_panel(host,view='reminder'):
    if view not in VIEWS:raise ValueError('未知面板')
    old=getattr(host,'_desktop_panel_controller',None)
    if old is not None and not old.closed:
        old.view=view;old.form.Show();old.form.Activate();old.update(force=True);return old.form
    controller=DesktopPanel(host,view)
    try:controller.show()
    except Exception:
        controller.close();raise
    return controller.form

class DesktopPanel:
    def __init__(self,host,view):
        from System.Drawing import Color,Size,Point
        from System.Windows.Forms import Form,FormBorderStyle,AutoScaleMode,FormStartPosition,Screen,DockStyle,Timer
        from Microsoft.Web.WebView2.WinForms import WebView2
        self.host=host;self.view=view;self.closed=False;self.ready=False;self.core=None;self.bindings=[];self.last=None;self.resizing=None;self.control_entry=False
        self.deadline=time.monotonic()+15;self.page='http://127.0.0.1:%d/desktop-panel.html'%host.port
        self.scale=max(1,float(getattr(host,'dpi_scale',1)));self.px=lambda n:round(n*self.scale)
        self.form=Form();f=self.form;f.Text='Agent 桌宠 · 控制台'
        f.AutoScaleMode=getattr(AutoScaleMode,'None');f.FormBorderStyle=getattr(FormBorderStyle,'None')
        f.StartPosition=FormStartPosition.Manual;f.ShowInTaskbar=True;f.TopMost=bool(host.settings.get('alwaysOnTop',True))
        self.theme=panel_theme(host)
        f.BackColor=Color.FromArgb(*( (243,247,252) if self.theme=="ice" else (251,249,243) ))
        area=Screen.FromControl(host.form).WorkingArea
        f.ClientSize=Size(min(self.px(390),area.Width-30),min(self.px(530),area.Height-40))
        f.MinimumSize=Size(min(self.px(320),area.Width-30),min(self.px(380),area.Height-40))
        f.Location=Point(area.Left+(area.Width-f.Width)//2,area.Top+(area.Height-f.Height)//2)
        self.web=WebView2();self.web.CreationProperties=host.create_props();self.web.Dock=DockStyle.Fill
        self.web.DefaultBackgroundColor=f.BackColor;f.Controls.Add(self.web)
        self.region=None;self.round_region();f.SizeChanged+=self.round_region
        from pet_edge import EdgeHalo
        self.edge=EdgeHalo(f,scale=self.scale,radius=24)
        self.timer=Timer();self.timer.Interval=1000;self.timer.Tick+=self.tick
        self.web.CoreWebView2InitializationCompleted+=self.initialized
        f.FormClosed+=self.cleanup;host.form.FormClosed+=self.owner_closed

    def round_region(self,*_):
        from System.Drawing import Region
        from pet_banner_style import rounded_path
        path=rounded_path(0,0,self.form.Width,self.form.Height,self.px(24))
        old=self.region;self.region=Region(path);path.Dispose();self.form.Region=self.region
        if old is not None:old.Dispose()

    def show(self):
        h=self.host;h._desktop_panel_controller=self;h.assistant_panels['desktop-panel']=self.form
        self.form.Show(h.form);h.register_aux_window(self.form);self.timer.Start();self.web.EnsureCoreWebView2Async(None)
        desktops=getattr(h,'desktops',None)
        if desktops is not None:
            try:desktops.align_to(int(self.form.Handle.ToInt64()),int(h.form.Handle.ToInt64()))
            except Exception:pass

    def initialized(self,sender,args):
        if self.closed:return
        self.core=sender.CoreWebView2
        if self.core is None:self.recover();return
        try:
            s=self.core.Settings;s.AreDefaultContextMenusEnabled=False;s.AreDevToolsEnabled=False;s.IsStatusBarEnabled=False;s.IsZoomControlEnabled=False
            for name,handler in (('WebMessageReceived',self.message),('NavigationStarting',self.navigation),('NavigationCompleted',self.loaded),('NewWindowRequested',self.new_window)):
                event=getattr(self.core,name);event+=handler;self.bindings.append((name,handler))
            self.core.Navigate(self.page)
        except Exception:self.recover()

    def navigation(self,sender,args):
        if args.Uri!=self.page:args.Cancel=True
    def new_window(self,sender,args):args.Handled=True
    def loaded(self,sender,args):
        if not self.ready and not args.IsSuccess:self.recover()

    def recover(self):
        if self.closed:return
        h=self.host;view=self.view;self.close()
        if self.control_entry:
            from pet_assistant_ui import _open_native_panel
            _open_native_panel(h,'control');return
        if view=='dnd':
            from pet_buddy_ui import _open_native_dnd
            _open_native_dnd(h)
        elif view in ('inbox','companion'):
            from pet_buddy_ui import _open_native_panel
            _open_native_panel(h,'buddy' if view=='companion' else 'inbox')
        else:
            from pet_assistant_ui import _open_native_panel
            _open_native_panel(h,'reminders')

    def message(self,sender,args):
        if self.closed:return
        try:data=decode_message(args.WebMessageAsJson,str(args.Source),self.page)
        except Exception:return
        if data is None:return
        action=data['action']
        try:
            if action=='ready':self.ready=True;self.update(force=True);self.web.Focus();return
            if action=='close':self.close();return
            if action=='drag':self.drag();return
            if action=='resize':self.resize(data);return
            if action=='view':
                if data.get('view') not in VIEWS:raise ValueError('未知页面')
                self.view=data['view'];self.update(force=True);return
            if action=='clear':
                agent=validate_scope(self.host,data)
                from System.Windows.Forms import MessageBox,MessageBoxButtons,DialogResult
                if MessageBox.Show(self.form,'清空当前 Agent 的提醒历史？其他 Agent 的消息将保留。','清空提醒收件箱',MessageBoxButtons.YesNo)!=DialogResult.Yes:
                    self.core.PostWebMessageAsJson(json.dumps(dict(t='result',ok=True,action=action,text='已取消清空。'),ensure_ascii=False));return
                validate_scope(self.host,dict(agent=agent))
                self.host.buddy.clear_inbox(agent=agent);self.host.update_buddy_badge()
            elif action=='folder':self.folder()
            else:apply_action(self.host,data)
            self.update(force=True)
            self.core.PostWebMessageAsJson(json.dumps(dict(t='result',ok=True,action=action,text='已保存并生效。' if action=='save' else '已更新。'),ensure_ascii=False))
        except Exception as exc:
            self.core.PostWebMessageAsJson(json.dumps(dict(t='result',ok=False,action=action,text='操作未完成：'+str(exc)[:200]),ensure_ascii=False))

    def folder(self):
        from System.Windows.Forms import FolderBrowserDialog,DialogResult
        from pet_quiet import steam_roots
        dialog=FolderBrowserDialog()
        try:
            if dialog.ShowDialog(self.form)!=DialogResult.OK:return
            h=self.host;roots=list(h.companion_config['gameRoots']);value=str(dialog.SelectedPath)
            if value not in roots:roots.append(value)
            clean=h.companion_store.save(dict(h.companion_config,gameRoots=roots))
            h.companion_config=clean;h.metric_service.config=clean;h.game_detector.roots=steam_roots(clean['gameRoots'])
        finally:dialog.Dispose()

    def update(self,force=False):
        if self.closed or not self.ready or self.core is None or not self.form.Visible:return
        value=dict(t='state',view=self.view,data=panel_snapshot(self.host))
        theme=value['data']['settingsTheme']
        if theme!=self.theme:
            from System.Drawing import Color
            self.theme=theme
            self.form.BackColor=Color.FromArgb(*( (243,247,252) if theme=='ice' else (251,249,243) ))
            self.web.DefaultBackgroundColor=self.form.BackColor
        raw=json.dumps(value,ensure_ascii=False)
        if force or raw!=self.last:self.core.PostWebMessageAsJson(raw);self.last=raw
    def tick(self,*_):
        if self.closed:return
        if not self.ready and time.monotonic()>self.deadline:self.recover();return
        self.update()
    def drag(self):
        from pet_metric_bubble import MetricBubble
        MetricBubble.drag(self)
    def resize(self,data):
        if not isinstance(data,dict):raise ValueError('缩放消息无效')
        phase=data.get('phase')
        if phase=='end':self.resizing=None;return
        if phase=='start':
            edge=data.get('edge')
            if not isinstance(edge,str) or edge not in ('n','ne','e','se','s','sw','w','nw'):raise ValueError('缩放方向无效')
            from System.Windows.Forms import Screen
            b=self.form.Bounds;a=Screen.FromControl(self.form).WorkingArea
            self.resizing=dict(bounds=(b.Left,b.Top,b.Width,b.Height),edge=edge,
                minimum=(self.form.MinimumSize.Width,self.form.MinimumSize.Height),area=(a.Left,a.Top,a.Right,a.Bottom))
            return
        if phase!='move':raise ValueError('缩放阶段无效')
        state=self.resizing
        if state is None:return
        bounds=resize_bounds(state['bounds'],state['edge'],data.get('dx'),data.get('dy'),state['minimum'],state['area'])
        b=self.form.Bounds
        if bounds!=(b.Left,b.Top,b.Width,b.Height):self.form.SetBounds(*bounds)

    def owner_closed(self,*_):self.close()
    def close(self):
        if not self.form.IsDisposed:self.form.Close()
    def cleanup(self,*_):
        if self.closed:return
        self.host._desktop_panel_last_view=self.view
        self.closed=True;self.timer.Stop();self.timer.Tick-=self.tick;self.timer.Dispose()
        self.web.CoreWebView2InitializationCompleted-=self.initialized
        if self.core is not None:
            for name,handler in self.bindings:
                event=getattr(self.core,name);event-=handler
        self.bindings=[];self.host.form.FormClosed-=self.owner_closed;self.host.unregister_aux_window(self.form)
        if self.host.assistant_panels.get('desktop-panel') is self.form:self.host.assistant_panels.pop('desktop-panel',None)
        if getattr(self.host,'_desktop_panel_controller',None) is self:self.host._desktop_panel_controller=None
        if self.region is not None:self.region.Dispose()
        if not self.web.IsDisposed:self.web.Dispose()
        self.core=None
