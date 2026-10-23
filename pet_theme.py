"""Shared mint styling for native assistant windows; no timers or data access."""
PALETTE = dict(bg='#f3f8f6', surface='#ffffff', ink='#203e35', muted='#637b72',
               accent='#287863', hover='#e7f3ed', edge='#d9e7e1')
_renderer_type = None

def color(name):
    from System.Drawing import ColorTranslator
    return ColorTranslator.FromHtml(PALETTE.get(name, name))

def style_button(button):
    from System.Windows.Forms import FlatStyle, Cursors
    primary = str(button.Text).startswith(('保存', '确认', '确定', '应用'))
    button.FlatStyle = FlatStyle.Flat
    button.UseVisualStyleBackColor = False
    button.BackColor = color('accent' if primary else 'surface')
    button.ForeColor = color('surface' if primary else 'ink')
    button.FlatAppearance.BorderColor = color('accent' if primary else 'edge')
    button.FlatAppearance.BorderSize = 1
    button.FlatAppearance.MouseOverBackColor = color('#1e6553' if primary else 'hover')
    button.FlatAppearance.MouseDownBackColor = color('#194f42' if primary else '#d6ebe1')
    button.Cursor = Cursors.Hand

def style_tree(control):
    from System.Windows.Forms import Button, Label, CheckBox, TextBox, ComboBox, TabPage
    control.ForeColor = color('ink')
    if isinstance(control, Button):
        style_button(control)
    elif isinstance(control, (TextBox, ComboBox)):
        control.BackColor = color('surface')
    else:
        control.BackColor = color('surface' if isinstance(control, TabPage) else 'bg')
        if isinstance(control, Label):control.ForeColor = color('ink' if control.Font.Bold else 'muted')
    for child in control.Controls:style_tree(child)

def apply_window(host, form, title, subtitle):
    """Keep existing controls, events and scrolling; add a compact page heading."""
    from System.Drawing import Font, FontStyle, Size
    from System.Windows.Forms import (TableLayoutPanel, RowStyle, SizeType, DockStyle,
                                     Panel, Label, Screen, Padding, FlowLayoutPanel)
    if getattr(form, 'Name', '') == 'mint-window':return
    scale = max(1, float(getattr(host, 'dpi_scale', 1)))
    px = lambda value: round(value * scale)
    form.SuspendLayout()
    form.Name = 'mint-window'
    form.Font = Font('Microsoft YaHei UI', 10.5)
    style_tree(form)
    form.MaximizeBox = True
    roots = list(form.Controls)
    if len(roots) == 1:
        body = roots[0]
        form.Controls.Remove(body)
        layout = TableLayoutPanel()
        layout.Dock = DockStyle.Fill
        layout.RowCount = 2
        layout.ColumnCount = 1
        layout.Margin = Padding(0)
        layout.Padding = Padding(0)
        layout.BackColor = color('bg')
        layout.RowStyles.Add(RowStyle(SizeType.Absolute, float(px(92))))
        layout.RowStyles.Add(RowStyle(SizeType.Percent, 100.0))
        header = Panel()
        header.Dock = DockStyle.Fill
        header.Margin = Padding(0)
        header.BackColor = color('surface')
        heading = Label()
        heading.Text = title
        heading.Font = Font('Microsoft YaHei UI', 17, FontStyle.Bold)
        heading.ForeColor = color('ink')
        caption = Label()
        caption.Text = subtitle
        caption.Font = Font('Microsoft YaHei UI', 9.5)
        caption.ForeColor = color('muted')
        header.Controls.Add(heading)
        header.Controls.Add(caption)
        def fit(sender=None, args=None):
            width = max(px(150), header.ClientSize.Width - px(40))
            heading.SetBounds(px(20), px(13), width, px(36))
            caption.SetBounds(px(21), px(53), width, px(32))
        header.Resize += fit
        layout.Controls.Add(header, 0, 0)
        if isinstance(body, FlowLayoutPanel):body.AutoScroll = True
        body.Dock = DockStyle.Fill
        body.Margin = Padding(0)
        layout.Controls.Add(body, 0, 1)
        form.Controls.Add(layout)
        area = Screen.FromControl(host.form).WorkingArea
        form.ClientSize = Size(form.ClientSize.Width, min(form.ClientSize.Height + px(60), area.Height - px(48)))
        fit()
    form.ResumeLayout(True)

def theme_menu(menu, scale=1):
    """Use the built-in renderer: stable hover/keyboard behavior across Windows DPI."""
    from System.Drawing import Font
    from System.Windows.Forms import ToolStripSystemRenderer, Padding
    menu.Renderer = ToolStripSystemRenderer()
    menu.Font = Font('Microsoft YaHei UI', 10)
    menu.BackColor = color('surface')
    menu.ForeColor = color('ink')
    menu.ShowImageMargin = False
    menu.Padding = Padding(4)
    for item in menu.Items:
        item.ForeColor = color('ink')
        item.Padding = Padding(round(10 * scale), round(3 * scale), round(12 * scale), round(3 * scale))
