"""Small native panels, constructed only when explicitly opened."""
import os
from pathlib import Path

def open_panel(host,kind):
    if kind in ('inbox','buddy'):
        from pet_buddy_ui import open_panel as open_buddy_panel
        return open_buddy_panel(host,kind)
    panels=host.assistant_panels
    old=panels.get(kind)
    if old is not None and not old.IsDisposed:old.Show();old.Activate();return
    from System.Drawing import Color,Font,Size
    from System.Windows.Forms import (Form,FlowLayoutPanel,FlowDirection,DockStyle,Padding,
        Label,Button,CheckBox,AutoScaleMode,FormStartPosition,Screen,MessageBox,Timer)
    from pet_assistant import load_tools
    scale=max(1,float(getattr(host,'dpi_scale',1)))
    px=lambda value:round(value*scale)
    form=Form();form.Text=('常用工具' if kind=='tools' else '任务提醒设置')+' · Agent 桌宠'
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
    if kind=='tools':
        label('选择一个工具，已打开的窗口会被唤起。')
        try:tools=load_tools(host.assistant_base)
        except (OSError,ValueError) as exc:tools=[];label(str(exc),70)
        status=Label();status.Text='';status.ForeColor=Color.FromArgb(70,88,77)
        def launch(entry):
            try:status.Text=host.assistant_launcher.open(entry)['message']
            except (OSError,ValueError) as exc:status.Text=str(exc);error(exc)
        for entry in tools:button(entry['name'],lambda entry=entry:launch(entry))
        add(status,60)
        def logs():
            folder=Path(host.assistant_base)/'assistant_logs';folder.mkdir(exist_ok=True);os.startfile(str(folder))
        button('打开工具启动日志',logs)
        timer=Timer();timer.Interval=1000
        def update(sender,args):
            messages=host.assistant_launcher.poll()
            if messages:status.Text=messages[-1]
        timer.Tick+=update;timer.Start()
    else:
        label('新任务完成或需要回复时提醒；同一状态不反复弹出。',55)
        checks={}
        for key,text in (('done','任务完成时提醒'),('waiting','等待我确认或回复时提醒'),('sound','提醒时播放提示音'),('showTitle','在通知中显示任务名称')):
            item=CheckBox();item.Text=text;item.Checked=bool(host.assistant_settings[key]);add(item,30);checks[key]=item
        status=label(host.assistant_store.error or '默认无声，气泡显示8秒。隐藏/勿扰时只记录，可在提醒收件箱查看。',50)
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
