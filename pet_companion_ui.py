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
    """Compatibility entry: game quiet now lives in the unified DND panel."""
    host.open_buddy_dnd()


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


def _open_native_metric_card(host,toggle=False):
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
    bg=Color.FromArgb(27,30,38);ink=Color.White;muted=Color.FromArgb(228,231,237)
    form=Form();form.Text='额度浮窗 · Agent 桌宠';form.AutoScaleMode=getattr(AutoScaleMode,'None')
    form.FormBorderStyle=getattr(FormBorderStyle,'None');form.ShowInTaskbar=False
    from pet_typography import rounded_font
    form.StartPosition=FormStartPosition.Manual;form.Font=rounded_font(9.5)
    form.BackColor=bg;form.ForeColor=ink;form.TopMost=bool(host.settings.get('alwaysOnTop',True))
    form.ClientSize=Size(px(280),px(68))
    area=Screen.FromControl(host.form).WorkingArea
    form.Location=Point(max(area.Left,area.Right-form.Width-px(22)),max(area.Top,area.Bottom-form.Height-px(22)))
    path=GraphicsPath();r=px(60);w=form.Width;h=form.Height
    for rect,start in (((0,0,r,r),180),((w-r,0,r,r),270),((w-r,h-r,r,r),0),((0,h-r,r,r),90)):
        path.AddArc(*rect,start,90)
    path.CloseFigure();region=Region(path);form.Region=region;path.Dispose()
    def paint_bubble(sender,event):
        from pet_native_style import shape
        from System.Drawing.Drawing2D import SmoothingMode
        event.Graphics.SmoothingMode=SmoothingMode.AntiAlias
        shape(event.Graphics,(.5,.5,float(form.Width-1),float(form.Height-1)),px(30),bg,Color.FromArgb(58,62,73))
    form.Paint+=paint_bubble
    def label(name,text,x,y,w,h,size,color,bold=False):
        item=Label();item.Name=name;item.Text=text;item.Location=Point(px(x),px(y));item.Size=Size(px(w),px(h))
        item.Font=rounded_font(size,bold)
        item.ForeColor=color;item.AutoEllipsis=True;form.Controls.Add(item)
        from pet_native_style import decorate_label
        decorate_label(item);return item
    dot=label('status-dot','',14,9,12,21,9,Color.FromArgb(61,213,139))
    def paint_dot(sender,event):
        from System.Drawing import SolidBrush
        from System.Drawing.Drawing2D import SmoothingMode
        event.Graphics.SmoothingMode=SmoothingMode.AntiAlias
        brush=SolidBrush(dot.ForeColor)
        try:event.Graphics.FillEllipse(brush,0,px(6),px(7),px(7))
        finally:brush.Dispose()
    dot.Paint+=paint_dot;dot.AccessibleName='额度状态'
    heading=label('source','Codex',30,11,180,21,9,ink)
    heading.Visible=False
    summary=label('remaining','正在查询…',30,9,232,24,10.5,ink,True)
    detail=label('reset','',30,37,232,21,9,muted)
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
    action('关闭额度气泡',form.Close)
    from pet_theme import theme_menu
    theme_menu(menu,scale)
    form.ContextMenuStrip=menu
    def small_button(text,x,fn):
        item=Button();item.Text=text;item.Size=Size(px(23),px(23));item.Location=Point(px(x),px(35))
        item.FlatStyle=FlatStyle.Flat;item.FlatAppearance.BorderSize=0;item.ForeColor=muted
        item.FlatAppearance.MouseOverBackColor=Color.FromArgb(36,41,50)
        item.FlatAppearance.MouseDownBackColor=Color.FromArgb(52,58,70)
        item.BackColor=bg;item.TabStop=False;item.Click+=lambda sender,args:fn();form.Controls.Add(item);return item
    more=small_button('⋯',221,lambda:menu.Show(form,Point(px(140),px(31))))
    close=small_button('×',247,form.Close);tip.SetToolTip(more,'刷新、切换来源和设置');tip.SetToolTip(close,'关闭；可从桌宠右键菜单重新打开')
    more.Visible=False;close.Visible=False
    def hover_tools(sender=None,args=None):
        if form.IsDisposed:return
        inside=form.Bounds.Contains(Cursor.Position)
        more.Visible=inside;close.Visible=inside
        detail.Width=px(180 if inside else 232)
    for item in (form,dot,summary,detail,more,close):
        item.MouseEnter+=hover_tools;item.MouseLeave+=hover_tools
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
    for item in (form,dot,heading,summary,detail):
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
        heading.Text='额度不足提醒' if warning else {'codex':'Codex','deepseek':'DeepSeek API','off':'额度已关闭'}[mode]
        summary.ForeColor=ink
        bubble_text=heading.Text+' · '+headline
        if summary.Text!=bubble_text:summary.Text=bubble_text
        if detail.Text!=description:detail.Text=description
        for item in (heading,summary,detail):tip.SetToolTip(item,full)
        refresh.Enabled=not busy
        for key,item in mode_items.items():item.Checked=key==mode
    timer=Timer();timer.Interval=1000;timer.Tick+=update;timer.Start();update()
    def cleanup(sender,args):
        tip.Dispose();menu.Dispose();region.Dispose()
    form.FormClosed+=cleanup
    _attach(host,'metric-card',form,timer);host.metric_service.refresh()


def open_metric_card(host,toggle=False):
    from pet_metric_bubble import open_metric_bubble
    return open_metric_bubble(host,toggle=toggle)
