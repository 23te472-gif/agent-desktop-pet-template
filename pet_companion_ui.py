"""Separate quiet settings, local credentials, and a lightweight floating quota card."""
from pathlib import Path


def _existing(host, name):
    form=host.assistant_panels.get(name)
    if form is not None and not form.IsDisposed:
        form.Show();form.Activate();return form


def _attach(host,name,form,timer=None):
    def owner_closed(sender,args):
        if not form.IsDisposed:form.Close()
    def closed(sender,args):
        if timer is not None:timer.Stop();timer.Dispose()
        host.unregister_aux_window(form);host.form.FormClosed-=owner_closed
        if host.assistant_panels.get(name) is form:host.assistant_panels.pop(name,None)
    form.FormClosed+=closed;host.form.FormClosed+=owner_closed
    host.assistant_panels[name]=form
    if name != 'metric-card':
        from pet_theme import apply_window
        apply_window(host,form,'游戏安静模式' if name=='companion' else 'API 余额设置',
                     '全屏游戏时安静陪伴，结束后自动恢复。' if name=='companion' else '在本机配置，随时查看余额。')
    form.Show();host.register_aux_window(form)


def _settings(host,title,height):
    from System.Drawing import Color,Font,Size
    from System.Windows.Forms import Form,FlowLayoutPanel,FlowDirection,DockStyle,Padding,Label,Button,AutoScaleMode,FormStartPosition,Screen
    scale=max(1,float(getattr(host,'dpi_scale',1)));px=lambda n:round(n*scale)
    form=Form();form.Text=title+' · Agent 桌宠';form.AutoScaleMode=getattr(AutoScaleMode,'None')
    form.Font=Font('Microsoft YaHei UI',11);form.StartPosition=FormStartPosition.CenterScreen
    area=Screen.FromControl(host.form).WorkingArea
    form.ClientSize=Size(min(px(490),area.Width-40),min(px(height),area.Height-70))
    form.MinimumSize=Size(min(px(350),area.Width-40),min(px(280),area.Height-70))
    form.BackColor=Color.FromArgb(248,247,241);form.TopMost=bool(host.settings.get('alwaysOnTop',True))
    panel=FlowLayoutPanel();panel.Dock=DockStyle.Fill;panel.FlowDirection=FlowDirection.TopDown
    panel.WrapContents=False;panel.AutoScroll=True;panel.Padding=Padding(px(18));form.Controls.Add(panel)
    def add(item,h=40):
        item.Width=panel.ClientSize.Width-px(42);item.Height=px(h);item.Margin=Padding(0,0,0,px(8));panel.Controls.Add(item);return item
    def label(text,h=40):
        item=Label();item.Text=text;item.ForeColor=Color.FromArgb(65,86,74);return add(item,h)
    def button(text,fn):
        item=Button();item.Text=text;item.BackColor=Color.FromArgb(235,241,227);item.Click+=lambda s,a:fn();return add(item,42)
    def resize(s,a):
        for item in panel.Controls:item.Width=max(px(180),panel.ClientSize.Width-px(42))
    form.Resize+=resize
    return form,add,label,button


def open_companion(host):
    """Compatibility entry point; only quiet mode settings live here now."""
    if _existing(host,'companion'):return
    from System.Windows.Forms import CheckBox,FolderBrowserDialog,DialogResult,MessageBox
    from pet_quiet import steam_roots
    form,add,label,button=_settings(host,'游戏安静模式',330)
    quiet=CheckBox();quiet.Text='游戏全屏时隐藏桌宠并暂停动画';quiet.Checked=host.companion_config['quietEnabled'];add(quiet,36)
    label('切出全屏后恢复原来的显示状态；手动隐藏的桌宠不会被强行显示。',54)
    extra=list(host.companion_config['gameRoots'])
    roots=label('已识别游戏目录：'+str(len(host.game_detector.roots))+' 个',32)
    def folder():
        dialog=FolderBrowserDialog();dialog.Description='选择其他游戏的安装目录'
        try:
            if dialog.ShowDialog(form)==DialogResult.OK:
                selected=str(Path(dialog.SelectedPath).resolve())
                if selected not in extra and len(extra)<12:extra.append(selected)
                roots.Text='额外目录：'+str(len(extra))+' 个，保存后生效。'
        finally:dialog.Dispose()
    button('添加其他游戏目录…',folder)
    status=label(host.companion_store.error or '自动识别 Steam 游戏库，每2秒检查一次。',42)
    def save():
        try:
            clean=host.companion_store.save(dict(host.companion_config,quietEnabled=bool(quiet.Checked),gameRoots=list(extra)))
            host.companion_config=clean;host.metric_service.config=clean
            host.game_detector.roots=steam_roots(clean['gameRoots']);host.update_game_quiet();status.Text='安静模式已保存并应用。'
        except (OSError,ValueError) as exc:MessageBox.Show(form,str(exc),'设置未保存')
    button('保存并应用',save);_attach(host,'companion',form)


def open_api_settings(host):
    if _existing(host,'metric-key'):return
    from System.Windows.Forms import TextBox,CheckBox,MessageBox
    from pet_companion_config import protect
    form,add,label,button=_settings(host,'API 余额设置',350)
    label('DeepSeek 官方 API 密钥',32)
    key=TextBox();key.UseSystemPasswordChar=True;key.MaxLength=512;add(key,34)
    label('留空保留原密钥。仅当前 Windows 账户加密保存，只发送到 api.deepseek.com 查询余额。',62)
    clear=CheckBox();clear.Text='移除已保存的密钥';add(clear,32)
    status=label('已配置本机密钥。' if host.companion_config['keyCipher'] else '尚未配置密钥；请在此处本机输入。',48)
    def save():
        try:
            draft=dict(host.companion_config);entered=str(key.Text).strip()
            if clear.Checked:draft['keyCipher']=''
            elif entered:
                if not 8<=len(entered)<=512 or any(ord(c)<=32 or ord(c)>=127 for c in entered):raise ValueError('请只粘贴密钥本身，不含空格、换行或 Bearer 前缀。')
                draft['keyCipher']=protect(entered)
            clean=host.companion_store.save(draft);host.companion_config=clean;host.metric_service.config=clean
            key.Text='';clear.Checked=False;host.metric_service.refresh(force=True);status.Text='已保存，余额会在后台刷新。'
        except (OSError,ValueError) as exc:MessageBox.Show(form,str(exc),'设置未保存')
    button('保存密钥设置',save);_attach(host,'metric-key',form)


def open_metric_card(host,toggle=False):
    old=host.assistant_panels.get('metric-card')
    if old is not None and not old.IsDisposed:
        if toggle:old.Close()
        else:old.Show();old.Activate()
        return
    from System.Drawing import Color,Font,FontStyle,Size,Point,Region
    from System.Drawing.Drawing2D import GraphicsPath
    from System.Windows.Forms import (Form,FormBorderStyle,AutoScaleMode,Screen,Label,Button,Timer,
        FormStartPosition,MessageBox,FlatStyle,ContextMenuStrip,ToolStripMenuItem,ToolStripSeparator,ToolTip,MouseButtons,Cursor)
    scale=max(1,float(getattr(host,'dpi_scale',1)));px=lambda n:round(n*scale)
    bg=Color.FromArgb(248,252,250);ink=Color.FromArgb(32,62,53);muted=Color.FromArgb(99,123,114)
    form=Form();form.Text='额度浮窗 · Agent 桌宠';form.AutoScaleMode=getattr(AutoScaleMode,'None')
    form.FormBorderStyle=getattr(FormBorderStyle,'None');form.ShowInTaskbar=False
    form.StartPosition=FormStartPosition.Manual;form.Font=Font('Microsoft YaHei UI',9)
    form.BackColor=bg;form.ForeColor=ink;form.TopMost=bool(host.settings.get('alwaysOnTop',True))
    form.ClientSize=Size(px(280),px(112))
    area=Screen.FromControl(host.form).WorkingArea
    form.Location=Point(max(area.Left,area.Right-form.Width-px(22)),max(area.Top,area.Bottom-form.Height-px(22)))
    path=GraphicsPath();r=px(18);w=form.Width;h=form.Height
    for rect,start in (((0,0,r,r),180),((w-r,0,r,r),270),((w-r,h-r,r,r),0),((0,h-r,r,r),90)):
        path.AddArc(*rect,start,90)
    path.CloseFigure();region=Region(path);form.Region=region;path.Dispose()
    def label(name,text,x,y,w,h,size,color,bold=False):
        item=Label();item.Name=name;item.Text=text;item.Location=Point(px(x),px(y));item.Size=Size(px(w),px(h))
        item.Font=Font('Microsoft YaHei UI',size,FontStyle.Bold if bold else FontStyle.Regular)
        item.ForeColor=color;item.AutoEllipsis=True;form.Controls.Add(item);return item
    heading=label('source','●  Codex',14,11,196,21,9,muted)
    summary=label('remaining','正在查询…',14,37,252,30,12,ink,True)
    detail=label('reset','',14,76,252,24,9,muted)
    tip=ToolTip();tip.AutoPopDelay=15000;tip.InitialDelay=400;tip.ReshowDelay=150
    menu=ContextMenuStrip();menu.Font=form.Font
    def action(text,fn):
        item=ToolStripMenuItem(text);item.Click+=lambda sender,args:fn();menu.Items.Add(item);return item
    refresh=action('刷新额度',lambda:host.metric_service.refresh(force=True))
    mode_items={}
    def switch(mode):
        try:
            clean=host.companion_store.save(dict(host.companion_config,metricMode=mode))
            host.companion_config=clean;host.metric_service.config=clean;host.metric_service.refresh(force=True);update()
        except (OSError,ValueError) as exc:MessageBox.Show(form,str(exc),'来源未保存')
    menu.Items.Add(ToolStripSeparator())
    for mode,text in (('codex','Codex 剩余额度'),('deepseek','DeepSeek API 余额'),('off','关闭额度显示')):
        mode_items[mode]=action(text,lambda m=mode:switch(m))
    menu.Items.Add(ToolStripSeparator())
    action('完整额度与更新时间…',lambda:MessageBox.Show(form,host.metric_service.text(detailed=True),'额度详情'))
    action('API 设置…',lambda:open_api_settings(host))
    from pet_theme import theme_menu
    theme_menu(menu,scale)
    form.ContextMenuStrip=menu
    def small_button(text,x,fn):
        item=Button();item.Text=text;item.Size=Size(px(23),px(23));item.Location=Point(px(x),px(8))
        item.FlatStyle=FlatStyle.Flat;item.FlatAppearance.BorderSize=0;item.ForeColor=muted
        item.BackColor=bg;item.TabStop=False;item.Click+=lambda sender,args:fn();form.Controls.Add(item);return item
    more=small_button('⋯',221,lambda:menu.Show(form,Point(px(140),px(31))))
    close=small_button('×',247,form.Close);tip.SetToolTip(more,'刷新、切换来源和设置');tip.SetToolTip(close,'关闭；可从桌宠右键菜单重新打开')
    # Dragging the card uses managed mouse capture, without a system title bar.
    drag={}
    def down(sender,e):
        if e.Button==MouseButtons.Left:
            drag['cursor']=Cursor.Position;drag['origin']=form.Location;sender.Capture=True
    def move(sender,e):
        if drag and sender.Capture:
            pos=Cursor.Position;start=drag['cursor'];origin=drag['origin']
            form.Location=Point(origin.X+pos.X-start.X,origin.Y+pos.Y-start.Y)
    def up(sender,e):sender.Capture=False;drag.clear()
    for item in (form,heading,summary,detail):
        item.MouseDown+=down;item.MouseMove+=move;item.MouseUp+=up
    def update(sender=None,args=None):
        mode=host.companion_config['metricMode'];full=host.metric_service.text(detailed=True)
        lines=full.splitlines() or ['尚未刷新'];first,separator,reset=lines[0].partition('；重置 ')
        headline=first.replace('Codex ','').replace('DeepSeek 余额 ','')
        if len(headline)>23:headline='额度暂不可用'
        description=('重置 '+reset if separator else next((line for line in lines[1:] if line.startswith('更新')), '点击 ⋯ 查看详情或设置'))
        busy=bool(host.metric_service.busy)
        if busy:description='正在刷新…'
        import time
        warning=mode=='codex' and time.monotonic()<getattr(host,'quota_warning_until',0)
        heading.Text='●  '+('额度不足提醒' if warning else {'codex':'Codex','deepseek':'DeepSeek API','off':'额度已关闭'}[mode])
        summary.ForeColor=Color.FromArgb(161,91,19) if warning else ink
        if summary.Text!=headline:summary.Text=headline
        if detail.Text!=description:detail.Text=description
        for item in (heading,summary,detail):tip.SetToolTip(item,full)
        refresh.Enabled=not busy
        for key,item in mode_items.items():item.Checked=key==mode
    timer=Timer();timer.Interval=1000;timer.Tick+=update;timer.Start();update()
    def cleanup(sender,args):
        tip.Dispose();menu.Dispose();region.Dispose()
    form.FormClosed+=cleanup
    _attach(host,'metric-card',form,timer);host.metric_service.refresh()
