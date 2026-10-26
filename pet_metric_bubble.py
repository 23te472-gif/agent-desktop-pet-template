"""Small WebView2 surface sharing the pet's existing runtime and account service."""
import ctypes,json,time,sys
from ctypes import wintypes
from pet_metric_model import metric_view,bridge_action

def _log(host,message):
    logger=getattr(sys.modules.get(type(host).__module__),'log',None)
    if callable(logger):logger('额度气泡：'+message)

def _fallback(host):
    from pet_companion_ui import _open_native_metric_card
    return _open_native_metric_card(host)

def open_metric_bubble(host,toggle=False):
    old=host.assistant_panels.get('metric-card')
    if old is not None and not old.IsDisposed:
        if toggle:old.Close()
        else:old.Show();old.Activate()
        return old
    if not callable(getattr(host,'create_props',None)):
        return _fallback(host)
    controller=None
    try:
        controller=MetricBubble(host)
        controller.show()
        return controller.form
    except Exception as exc:
        host._metric_webview_error=type(exc).__name__
        if controller is not None:controller.close()
        return _fallback(host)

class MetricBubble:
    def __init__(self,host):
        from System.Drawing import Color,Size,Point,Region,Font
        from System.Drawing.Drawing2D import GraphicsPath
        from System.Windows.Forms import (Form,FormBorderStyle,AutoScaleMode,FormStartPosition,
            Screen,DockStyle,Timer,ContextMenuStrip,ToolStripMenuItem,ToolStripSeparator)
        from Microsoft.Web.WebView2.WinForms import WebView2
        self.host=host;self.closed=False;self.ready=False;self.core=None;self.last_view=None;self.pending_mode=None
        self.startup_deadline=time.monotonic()+15;self.bindings=[]
        self.page='http://127.0.0.1:%d/metric.html'%host.port
        self.scale=max(1,float(getattr(host,'dpi_scale',1)));self.px=lambda n:round(n*self.scale)
        self.form=Form();form=self.form;form.Text='额度气泡 · Agent 桌宠'
        form.AutoScaleMode=getattr(AutoScaleMode,'None');form.FormBorderStyle=getattr(FormBorderStyle,'None')
        form.StartPosition=FormStartPosition.Manual;form.ShowInTaskbar=False;form.MinimizeBox=False;form.MaximizeBox=False
        form.TopMost=bool(host.settings.get('alwaysOnTop',True));form.ClientSize=Size(self.px(292),self.px(68))
        # Unlike the pet silhouette, this entire rounded surface receives input.
        # A color-keyed layered parent makes its WebView child look visible while
        # WindowFromPoint still hits the application behind it.
        form.BackColor=Color.FromArgb(18,22,33)
        area=Screen.FromControl(host.form).WorkingArea
        form.Location=Point(max(area.Left,area.Right-form.Width-self.px(22)),max(area.Top,area.Bottom-form.Height-self.px(22)))
        path=GraphicsPath();d=min(self.px(44),form.Height)
        for x,y,start in ((0,0,180),(form.Width-d,0,270),(form.Width-d,form.Height-d,0),(0,form.Height-d,90)):
            path.AddArc(x,y,d,d,start,90)
        path.CloseFigure();self.region=Region(path);path.Dispose();form.Region=self.region
        from pet_edge import EdgeHalo
        self.edge=EdgeHalo(form,scale=self.scale,radius=22)
        self.web=WebView2();self.web.CreationProperties=host.create_props();self.web.Dock=DockStyle.Fill
        self.web.DefaultBackgroundColor=form.BackColor;form.Controls.Add(self.web)
        self.menu=ContextMenuStrip();self.menu.Font=Font('Microsoft YaHei UI',10)
        self.menu.BackColor=Color.FromArgb(27,30,38);self.menu.ForeColor=Color.White
        def action(text,fn):
            item=ToolStripMenuItem(text);item.ForeColor=Color.White;item.BackColor=self.menu.BackColor
            item.Click+=lambda s,e:fn();self.menu.Items.Add(item);return item
        self.refresh_item=action('刷新额度',lambda:host.metric_service.refresh(force=True))
        self.menu.Items.Add(ToolStripSeparator());self.mode_items={}
        for mode,text in (('codex','Codex 剩余额度'),('deepseek','DeepSeek API 余额'),('off','关闭额度显示')):
            self.mode_items[mode]=action(text,lambda value=mode:self.switch(value))
        self.menu.Items.Add(ToolStripSeparator())
        action('完整额度与更新时间…',self.details)
        action('API 设置…',self.api_settings)
        action('关闭额度气泡',self.close)
        self.timer=Timer();self.timer.Interval=1000;self.timer.Tick+=self.tick
        self.web.CoreWebView2InitializationCompleted+=self.initialized
        form.Shown+=self.shown;form.FormClosed+=self.cleanup
        host.form.FormClosed+=self.owner_closed

    def show(self):
        self.host.assistant_panels['metric-card']=self.form
        self.host._metric_bubble_controller=self
        self.form.Show(self.host.form);self.host.register_aux_window(self.form)
        self.timer.Start();self.host.metric_service.refresh()
        self.web.EnsureCoreWebView2Async(None)

    def shown(self,sender,args):
        # Paint only inside the rounded Region; no rectangular accent backdrop.
        desktops=getattr(self.host,'desktops',None)
        if desktops is not None:
            try:desktops.align_to(int(self.form.Handle.ToInt64()),int(self.host.form.Handle.ToInt64()))
            except Exception:pass

    def initialized(self,sender,args):
        if self.closed:return
        core=sender.CoreWebView2
        if core is None:
            self.host._metric_webview_error='InitializationFailed'
            self.close();_fallback(self.host);return
        self.core=core
        try:
            core.Settings.AreDefaultContextMenusEnabled=False
            core.Settings.AreDevToolsEnabled=False;core.Settings.IsStatusBarEnabled=False
            core.Settings.IsZoomControlEnabled=False
            for name,handler in (('WebMessageReceived',self.message),('NavigationStarting',self.navigation),
                                 ('NavigationCompleted',self.navigation_completed),('NewWindowRequested',self.new_window)):
                event=getattr(core,name);event+=handler;self.bindings.append((name,handler))
            core.Navigate(self.page)
        except Exception:self.recover('PageInitializationFailed')

    def navigation(self,sender,args):
        if args.Uri!=self.page:args.Cancel=True

    def new_window(self,sender,args):args.Handled=True

    def navigation_completed(self,sender,args):
        if not self.closed and not self.ready and not args.IsSuccess:self.recover('PageLoadFailed')

    def recover(self,reason):
        if self.closed:return
        host=self.host;host._metric_webview_error=reason
        _log(host,'使用兼容显示，原因 '+reason)
        self.close();_fallback(host)

    def message(self,sender,args):
        if self.closed:return
        try:action=bridge_action(args.WebMessageAsJson,str(args.Source),self.page)
        except Exception:return
        if action=='ready':
            self.ready=True;self.update(force=True);_log(self.host,'页面已就绪，共享渲染器正常')
        elif action=='close':self.close()
        elif action=='refresh':self.host.metric_service.refresh(force=True);self.update(force=True)
        elif action=='more':self.show_menu()
        elif action=='drag':self.drag()

    def update(self,force=False):
        if self.closed or not self.ready or self.core is None or not self.form.Visible:return
        host=self.host;mode=host.companion_config.get('metricMode','codex')
        view=metric_view(mode,host.metric_service.cache.get(mode,{}),host.metric_service.busy)
        detail=host.metric_service.text(detailed=True)
        view['detail']=str(detail)[:4096]
        message=json.dumps(dict(t='metric',data=view),ensure_ascii=False)
        if force or message!=self.last_view:
            self.core.PostWebMessageAsJson(message);self.last_view=message
        self.refresh_item.Enabled=not bool(host.metric_service.busy)
        for key,item in self.mode_items.items():item.Checked=key==mode

    def tick(self,sender=None,args=None):
        if self.closed:return
        if not self.ready and time.monotonic()>=self.startup_deadline:
            self.recover('PageReadyTimeout');return
        if self.pending_mode is not None and not self.host.metric_service.busy:
            mode=self.pending_mode;self.pending_mode=None
            if mode==self.host.companion_config.get('metricMode'):self.host.metric_service.refresh(force=True)
        self.update()

    def switch(self,mode):
        if mode not in ('codex','deepseek','off'):return
        from System.Windows.Forms import MessageBox
        try:
            host=self.host;clean=host.companion_store.save(dict(host.companion_config,metricMode=mode))
            host.companion_config=clean;host.metric_service.config=clean
            if host.metric_service.busy:self.pending_mode=mode
            else:host.metric_service.refresh(force=True)
            self.update(force=True)
        except (OSError,ValueError) as exc:MessageBox.Show(self.form,str(exc),'来源未保存')

    def show_menu(self):
        from System.Drawing import Point
        self.menu.Show(self.form,Point(self.px(110),self.px(52)))

    def details(self):
        from System.Windows.Forms import MessageBox
        MessageBox.Show(self.form,self.host.metric_service.text(detailed=True),'额度详情')

    def api_settings(self):
        from pet_companion_ui import open_api_settings
        open_api_settings(self.host)

    def drag(self):
        api=ctypes.WinDLL('user32',use_last_error=True)
        api.ReleaseCapture()
        api.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
        api.SendMessageW.restype=wintypes.LPARAM
        api.SendMessageW(wintypes.HWND(int(self.form.Handle.ToInt64())),0xA1,2,0)

    def owner_closed(self,sender,args):self.close()

    def close(self):
        if not self.form.IsDisposed:self.form.Close()

    def cleanup(self,sender,args):
        if self.closed:return
        self.closed=True;self.ready=False
        self.timer.Stop();self.timer.Tick-=self.tick;self.timer.Dispose()
        self.web.CoreWebView2InitializationCompleted-=self.initialized
        if self.core is not None:
            for name,handler in self.bindings:
                event=getattr(self.core,name);event-=handler
            self.bindings=[]
        self.host.form.FormClosed-=self.owner_closed
        self.host.unregister_aux_window(self.form)
        if self.host.assistant_panels.get('metric-card') is self.form:self.host.assistant_panels.pop('metric-card',None)
        if getattr(self.host,'_metric_bubble_controller',None) is self:self.host._metric_bubble_controller=None
        self.menu.Dispose();self.region.Dispose()
        if not self.web.IsDisposed:self.web.Dispose()
        self.core=None;self.last_view=None
