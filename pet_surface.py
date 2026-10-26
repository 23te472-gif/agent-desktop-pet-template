"""Native companion surfaces: measured text, quiet color and fixed actions."""
PALETTE = dict(bg='#F5F7FC', surface='#FFFFFF', ink='#33445F', muted='#738099',
               accent='#7D8FE0', accentStrong='#6578CD', hover='#F0F3FF', pressed='#E5EAFE',
               edge='#E3E8F3', focus='#9EADEC', toggleOff='#CBD3E2')

def color(name):
    from System.Drawing import ColorTranslator
    return ColorTranslator.FromHtml(PALETTE.get(name, name))

def style_button(button, scale=1):
    from pet_native_style import decorate_button
    decorate_button(button, color, scale)

def style_tree(control, scale=1):
    from System.Windows.Forms import Button, Label, CheckBox, TextBox, ComboBox, TabPage
    from pet_native_style import decorate_switch,decorate_label
    from pet_typography import rounded_font
    control.Font = rounded_font(control.Font.SizeInPoints,control.Font.Bold)
    control.ForeColor = color('ink')
    control.BackColor = color('surface' if isinstance(control, (TextBox, ComboBox, TabPage)) else 'bg')
    if isinstance(control, Button):style_button(control, scale)
    elif isinstance(control, CheckBox):decorate_switch(control, color, scale)
    elif isinstance(control, Label):
        control.ForeColor = color('ink' if control.Font.Bold else 'muted')
        control.UseCompatibleTextRendering = False
        decorate_label(control)
    for child in control.Controls:style_tree(child, scale)

def apply_window(host, form, title, subtitle):
    from System.Drawing import Font, FontStyle, Size
    from System.Windows.Forms import (TableLayoutPanel, RowStyle, SizeType, DockStyle, Panel,
        Label, Screen, Padding, FlowLayoutPanel, FlowDirection, Button, CheckBox, TextBox,
        TextRenderer, TextFormatFlags, AutoSizeMode)
    from pet_native_style import soften_frame,decorate_label
    from pet_typography import rounded_font
    if form.Name == 'companion-window':return
    roots = list(form.Controls)
    if len(roots) != 1:return
    scale = max(1, float(getattr(host, 'dpi_scale', 1)));px = lambda n:round(n*scale)
    form.SuspendLayout();form.Name = 'companion-window'
    form.Font = rounded_font(10.5)
    style_tree(form, scale)
    body = roots[0];form.Controls.Remove(body)
    body.BackColor = color('bg');body.Margin = Padding(0);body.Dock = DockStyle.Fill
    body.Padding = Padding(px(18),px(12),px(18),px(14))
    if isinstance(body, FlowLayoutPanel):body.AutoScroll = True
    layout = TableLayoutPanel();layout.Dock = DockStyle.Fill;layout.Margin = Padding(0)
    layout.Padding = Padding(0);layout.ColumnCount = 1;layout.RowCount = 3
    layout.RowStyles.Add(RowStyle(SizeType.Absolute, float(px(112))))
    layout.RowStyles.Add(RowStyle(SizeType.Percent,100.0))
    layout.RowStyles.Add(RowStyle(SizeType.Absolute, 0.0))
    layout.BackColor = color('bg')
    header = Panel();header.Dock = DockStyle.Fill;header.Margin = Padding(0);header.BackColor = color('surface')
    kicker = Label();kicker.Text = 'AGENT  /  COMPANION';kicker.Font = rounded_font(8.0)
    kicker.ForeColor = color('accent');kicker.BackColor = color('surface')
    heading = Label();heading.Text = title;heading.Font = rounded_font(15,True)
    heading.ForeColor = color('ink');heading.BackColor = color('surface')
    caption = Label();caption.Text = subtitle;caption.Font = rounded_font(9.5)
    caption.ForeColor = color('muted');caption.BackColor = color('surface')
    for item in (kicker,heading,caption):
        item.UseCompatibleTextRendering = False;header.Controls.Add(item);decorate_label(item)
    footer = FlowLayoutPanel();footer.Dock = DockStyle.Fill;footer.Margin = Padding(0)
    footer.Padding = Padding(px(18),px(10),px(18),px(8));footer.WrapContents = True
    footer.FlowDirection = FlowDirection.LeftToRight;footer.BackColor = color('surface')
    for control in list(body.Controls):
        if isinstance(control, Button) and str(control.Text).startswith(('保存','测试提醒','打开提醒收件箱')):
            body.Controls.Remove(control);footer.Controls.Add(control)
    for item, row in ((header,0),(body,1),(footer,2)):layout.Controls.Add(item,0,row)
    form.Controls.Add(layout)
    busy = [False];rerun = [False];queued = [False]
    flags = TextFormatFlags.WordBreak | TextFormatFlags.NoPadding
    def height(text, font, width):
        return TextRenderer.MeasureText(str(text or ' '),font,Size(max(1,int(width)),10000),flags).Height
    def fit(sender=None,args=None):
        if form.IsDisposed:return
        if busy[0]:rerun[0] = True;return
        busy[0] = True
        rerun[0] = False
        try:
            width = max(1,header.ClientSize.Width-px(36))
            kicker.SetBounds(px(19),px(11),width,px(15))
            heading.SetBounds(px(18),px(29),width,max(px(30),heading.Font.Height+px(5)))
            cap_height = max(px(24),height(caption.Text,caption.Font,width)+px(4))
            caption.SetBounds(px(19),px(64),width,cap_height)
            layout.RowStyles[0].Height = float(px(72)+cap_height)
            available = max(px(130),body.ClientSize.Width-body.Padding.Horizontal-px(18))
            body.SuspendLayout()
            for control in body.Controls:
                control.Margin = Padding(0,0,0,px(10));control.Width = available
                if isinstance(control,CheckBox):
                    control.AutoSize = False
                    control.Height = max(px(60),height(control.Text,control.Font,max(1,available-px(96)))+px(32))
                elif isinstance(control,Label):
                    control.AutoSize = False
                    control.Height = max(px(26),height(control.Text,control.Font,available-px(4))+px(12))
                elif isinstance(control,Button):control.Height = max(px(42),control.Font.Height+px(18))
                elif isinstance(control,FlowLayoutPanel):
                    control.WrapContents = True
                    if control.AutoSize:control.AutoSizeMode = AutoSizeMode.GrowAndShrink
                    for child in control.Controls:
                        if isinstance(child,Button):child.Height = max(px(38),child.Font.Height+px(14))
                        elif isinstance(child,FlowLayoutPanel):
                            child.Width = available
                            labels = [v for v in child.Controls if isinstance(v,Label)]
                            buttons = [v for v in child.Controls if isinstance(v,Button)]
                            if labels and buttons:
                                label_width = max(px(100),available-sum(v.Width+v.Margin.Horizontal for v in buttons)-px(20))
                                labels[0].Width = label_width
                                child.Height = max(px(64),height(labels[0].Text,labels[0].Font,label_width)+px(12))
                                labels[0].Height = child.Height
                        elif isinstance(child,Label):
                            child.Width = available;child.Height = height(child.Text,child.Font,available)+px(16)
                elif isinstance(control,TextBox):
                    if not control.Multiline:control.Height = max(px(34),control.Font.Height+px(12))
            body.ResumeLayout(True)
            footer_available = max(px(120),footer.ClientSize.Width-footer.Padding.Horizontal)
            used = 0;rows = 1
            for button in footer.Controls:
                button.Width = min(footer_available,max(px(94),TextRenderer.MeasureText(button.Text,button.Font).Width+px(24)))
                button.Height = max(px(40),button.Font.Height+px(16))
                button.Margin = Padding(0,0,px(10),px(8))
                if used and used+button.Width+px(10)>footer_available:rows+=1;used=0
                used += button.Width+px(10)
            layout.RowStyles[2].Height = float(rows*max(px(48),form.Font.Height+px(24))+px(22)) if footer.Controls.Count else 0.0
            footer.PerformLayout()
            layout.PerformLayout()
        finally:
            busy[0] = False
            if rerun[0] and not queued[0] and form.IsHandleCreated and not form.IsDisposed:
                from System import Action
                queued[0] = True
                form.BeginInvoke(Action(drain))
    def drain():
        queued[0] = False
        fit()
    form.Resize += fit;body.ClientSizeChanged += fit;header.Resize += fit;footer.Resize += fit
    for control in body.Controls:
        if isinstance(control,(Label,CheckBox)):control.TextChanged += fit
        elif isinstance(control,FlowLayoutPanel):
            control.ControlAdded += fit
            control.ControlRemoved += fit
    form.Shown += lambda s,e:(soften_frame(form),fit())
    area = Screen.FromControl(host.form).WorkingArea
    width,height_default = {'任务提醒设置':(400,480),'陪伴':(400,420),'勿扰':(420,460),
        '提醒收件箱':(420,480),'API 余额设置':(420,420)}.get(title,(420,460))
    form.ClientSize = Size(min(px(width),area.Width-px(32)),min(px(height_default),area.Height-px(48)))
    form.MinimumSize = Size(min(px(320),area.Width-px(32)),min(px(340),area.Height-px(48)))
    fit();form.ResumeLayout(True)

def theme_menu(menu, scale=1):
    from System.Drawing import Font
    from System.Windows.Forms import ToolStripSystemRenderer,Padding
    from pet_typography import rounded_font
    menu.Renderer = ToolStripSystemRenderer();menu.Font = rounded_font(10.5)
    menu.BackColor = color('surface');menu.ForeColor = color('ink');menu.ShowImageMargin = False
    menu.Padding = Padding(4)
    for item in menu.Items:
        item.ForeColor = color('ink');item.Padding = Padding(round(10*scale),round(3*scale),round(12*scale),round(3*scale))
