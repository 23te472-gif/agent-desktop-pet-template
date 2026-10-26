"""Small native panels, constructed only when explicitly opened."""

def open_panel(host,kind):
    if kind!='tools' and callable(getattr(host,'create_props',None)):
        from pet_desktop_panels import open_desktop_panel,open_control_center
        view={'inbox':'inbox','buddy':'companion'}.get(kind,'reminder')
        try:return open_control_center(host) if kind=='control' else open_desktop_panel(host,view)
        except Exception:pass
    return _open_native_panel(host,kind)

def _control_fallback_links(host):
    from pet_buddy_ui import _open_native_dnd,_open_native_panel
    return (('勿扰模式',lambda:_open_native_dnd(host)),
            ('陪伴与互动',lambda:_open_native_panel(host,'buddy')))

def _open_native_panel(host,kind):
    if kind=='tools':
        from pet_assistant import open_tool_center
        return open_tool_center(host.assistant_base,host.assistant_launcher)
    if kind in ('inbox','buddy'):
        from pet_buddy_ui import open_panel as open_buddy_panel
        return open_buddy_panel(host,kind)
    panels=host.assistant_panels
    old=panels.get(kind)
    if old is not None and not old.IsDisposed:old.Show();old.Activate();return
    from System.Drawing import Color,Font,Size
    from System.Windows.Forms import (Form,FlowLayoutPanel,FlowDirection,DockStyle,Padding,
        Label,Button,CheckBox,AutoScaleMode,FormStartPosition,Screen,MessageBox,Timer)
    scale=max(1,float(getattr(host,'dpi_scale',1)))
    px=lambda value:round(value*scale)
    form=Form();form.Text=('常用工具' if kind=='tools' else '桌宠控制台 · 兼容模式' if kind=='control' else '任务提醒设置')+' · Agent 桌宠'
    form.AutoScaleMode=getattr(AutoScaleMode,'None');form.StartPosition=FormStartPosition.CenterScreen
    area=Screen.FromControl(host.form).WorkingArea
    form.ClientSize=Size(min(px(460),area.Width-40),min(px(470 if kind=='tools' else 390),area.Height-70))
    form.MinimumSize=Size(min(px(340),area.Width-40),min(px(290),area.Height-70))
    form.Font=Font('Microsoft YaHei UI',11);form.BackColor=Color.FromArgb(248,247,241)
    form.TopMost=bool(host.settings.get('alwaysOnTop',True));form.ShowInTaskbar=True;form.MinimizeBox=False
    panel=FlowLayoutPanel();panel.Dock=DockStyle.Fill;panel.FlowDirection=FlowDirection.TopDown
    panel.WrapContents=False;panel.AutoScroll=True;panel.Padding=Padding(px(18));form.Controls.Add(panel)
    controls=[]
    def add(control,height=40):
        control.Width=form.ClientSize.Width-px(60);control.Height=px(height);control.Margin=Padding(0,0,0,px(9))
        panel.Controls.Add(control);controls.append(control);return control
    def label(text,height=44):
        item=Label();item.Text=text;item.ForeColor=Color.FromArgb(70,88,77);return add(item,height)
    def button(text,handler,height=42):
        item=Button();item.Text=text;item.BackColor=Color.FromArgb(235,241,227)
        item.Click+=lambda sender,args:handler();return add(item,height)
    def error(exc):MessageBox.Show(form,str(exc),'操作未完成')
    timer=None
    if kind!='tools':
        if kind=='control':
            for title,handler in _control_fallback_links(host):button(title,handler)
        label('通知偏好',30)
        checks={}
        for key,text in (('done','任务完成\n完成工作时提醒你查看结果。'),
                         ('waiting','需要确认\nAgent 等待你回复或操作时提醒。'),
                         ('sound','提示音\n收到通知时播放系统提示音。'),
                         ('showTitle','显示任务名称\n关闭后，也会隐藏历史提醒中的标题。')):
            item=CheckBox();item.Text=text;item.Checked=bool(host.assistant_settings[key]);add(item,30);checks[key]=item
        status=label(host.assistant_store.error or '提醒会保留在收件箱。隐藏或勿扰时不弹出。',50)
        def save():
            try:
                host.assistant_settings=host.assistant_store.save({k:bool(v.Checked) for k,v in checks.items()})
                if not host.assistant_settings.get('showTitle',True):
                    try:host.buddy.hide_titles()
                    except (OSError,ValueError) as exc:status.Text='设置已保存，但历史标题未能清除：'+str(exc);error(exc);return
                status.Text='已保存并立即生效。'
            except (OSError,ValueError) as exc:status.Text=str(exc);error(exc)
        button('保存设置',save)
        button('测试提醒',lambda:host.show_assistant_notification(dict(kind='test',title='测试提醒')))
        button('打开提醒收件箱…',lambda:host.open_assistant_panel('inbox'))
    def resize(sender,args):
        width=max(px(180),panel.ClientSize.Width-px(60))
        for item in controls:item.Width=width
    form.Resize+=resize
    def owner_closed(sender,args):
        if not form.IsDisposed:form.Close()
    def closed(sender,args):
        if timer is not None:timer.Stop();timer.Dispose()
        host.unregister_aux_window(form)
        host.form.FormClosed-=owner_closed
        if panels.get(kind) is form:panels.pop(kind,None)
    form.FormClosed+=closed;host.form.FormClosed+=owner_closed;panels[kind]=form
    from pet_theme import apply_window
    apply_window(host,form,'常用工具' if kind=='tools' else '任务提醒设置',
                 '常用入口，随手打开。' if kind=='tools' else '选择何时提醒，让桌宠按你的节奏陪伴。')
    form.Show();host.register_aux_window(form);form.Activate()
