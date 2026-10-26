"""Small native GDI+ treatments; no timers, binary dependencies or data access."""

def draw_text(graphics, text, font, brush, rectangle, fmt=None):
    """Render TrueType outlines, avoiding small embedded bitmap glyphs."""
    from System.Drawing import StringFormat
    from System.Drawing.Drawing2D import GraphicsPath,SmoothingMode,PixelOffsetMode
    path=GraphicsPath();owned=fmt is None
    if owned:fmt=StringFormat()
    try:
        graphics.SmoothingMode=SmoothingMode.AntiAlias
        graphics.PixelOffsetMode=PixelOffsetMode.HighQuality
        path.AddString(str(text),font.FontFamily,int(font.Style),
            float(font.SizeInPoints*graphics.DpiY/72.0),rectangle,fmt)
        if font.Bold:
            from System.Drawing import Pen
            from System.Drawing.Drawing2D import LineJoin
            pen=Pen(brush.Color,float(.3*graphics.DpiY/96.0));pen.LineJoin=LineJoin.Round
            try:graphics.DrawPath(pen,path)
            finally:pen.Dispose()
        graphics.FillPath(brush,path)
    finally:
        path.Dispose()
        if owned:fmt.Dispose()

def decorate_label(control):
    from System.Drawing import SolidBrush,RectangleF,StringFormat,StringAlignment,StringTrimming,StringFormatFlags
    if str(control.Tag or '')=='pet-smooth-label':return
    control.Tag='pet-smooth-label';_buffer(control)
    def paint(sender,event):
        g=event.Graphics
        g.Clear(control.BackColor if control.BackColor.A==255 else control.Parent.BackColor)
        if not control.Text:return
        pad=control.Padding
        rectangle=RectangleF(float(pad.Left),float(pad.Top),float(max(1,control.Width-pad.Horizontal)),float(max(1,control.Height-pad.Vertical)))
        fmt=StringFormat();alignment=str(control.TextAlign)
        fmt.Alignment=StringAlignment.Center if alignment.endswith('Center') else StringAlignment.Far if alignment.endswith('Right') else StringAlignment.Near
        fmt.LineAlignment=StringAlignment.Center if alignment.startswith('Middle') else StringAlignment.Far if alignment.startswith('Bottom') else StringAlignment.Near
        if control.AutoEllipsis:
            fmt.Trimming=StringTrimming.EllipsisCharacter
            if '\n' not in control.Text:fmt.FormatFlags=StringFormatFlags.NoWrap
        brush=SolidBrush(control.ForeColor)
        try:draw_text(g,control.Text,control.Font,brush,rectangle,fmt)
        finally:brush.Dispose();fmt.Dispose()
    control.Paint+=paint

def rounded_path(x, y, width, height, radius):
    from System.Drawing.Drawing2D import GraphicsPath
    path = GraphicsPath()
    diameter = max(1, min(radius * 2, width, height))
    for left, top, angle in ((x, y, 180), (x+width-diameter, y, 270),
                             (x+width-diameter, y+height-diameter, 0), (x, y+height-diameter, 90)):
        path.AddArc(float(left), float(top), float(diameter), float(diameter), float(angle), 90.0)
    path.CloseFigure()
    return path


def shape(graphics, bounds, radius, fill, edge=None):
    from System.Drawing import SolidBrush, Pen
    path = rounded_path(*bounds, radius)
    brush = SolidBrush(fill)
    try:
        graphics.FillPath(brush, path)
        if edge is not None:
            pen = Pen(edge, 1.0)
            try:graphics.DrawPath(pen, path)
            finally:pen.Dispose()
    finally:brush.Dispose();path.Dispose()


def _buffer(control):
    from System.Reflection import BindingFlags
    prop = control.GetType().GetProperty('DoubleBuffered', BindingFlags.Instance | BindingFlags.NonPublic)
    if prop is not None:prop.SetValue(control, True, None)


def decorate_button(button, color, scale=1):
    from System.Windows.Forms import FlatStyle, Cursors
    from System.Drawing import RectangleF, SolidBrush, StringFormat, StringAlignment
    from System.Drawing.Drawing2D import SmoothingMode
    from System.Drawing.Text import TextRenderingHint
    if str(button.Tag or '') == 'pet-rounded':return
    button.Tag = 'pet-rounded';_buffer(button)
    button.FlatStyle = FlatStyle.Flat;button.UseVisualStyleBackColor = False
    button.FlatAppearance.BorderSize = 0;button.Cursor = Cursors.Hand
    button.BackColor = color('surface');button.ForeColor = color('ink')
    state = {'hover': False, 'down': False}
    def update(key, value):state[key] = value;button.Invalidate()
    button.MouseEnter += lambda s,e:update('hover', True)
    button.MouseLeave += lambda s,e:(update('hover', False), update('down', False))
    button.MouseDown += lambda s,e:update('down', True)
    button.MouseUp += lambda s,e:update('down', False)
    button.GotFocus += lambda s,e:button.Invalidate()
    button.LostFocus += lambda s,e:button.Invalidate()
    def paint(sender, event):
        g = event.Graphics;g.Clear(button.Parent.BackColor if button.Parent is not None else color('bg'))
        g.SmoothingMode = SmoothingMode.AntiAlias;g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit
        primary = str(button.Text).startswith(('保存', '确认', '确定', '应用'))
        fill = color('accent' if primary else 'surface')
        if state['hover']:fill = color('accentStrong' if primary else 'hover')
        if state['down']:fill = color('accentStrong' if primary else 'pressed')
        if not button.Enabled:fill = color('edge')
        shape(g, (1, 1, max(1, button.Width-3), max(1, button.Height-3)), 10*scale, fill,
              color('focus' if button.Focused else 'accent' if primary else 'edge'))
        brush = SolidBrush(color('surface' if primary else 'ink' if button.Enabled else 'muted'))
        fmt = StringFormat();fmt.Alignment = StringAlignment.Center;fmt.LineAlignment = StringAlignment.Center
        try:draw_text(g,button.Text, button.Font, brush, RectangleF(7, 2, max(1, button.Width-14), max(1, button.Height-4)), fmt)
        finally:brush.Dispose();fmt.Dispose()
    button.Paint += paint


def decorate_switch(control, color, scale=1):
    from System.Windows.Forms import Appearance, FlatStyle, Cursors
    from System.Drawing import RectangleF, SolidBrush
    from System.Drawing.Drawing2D import SmoothingMode
    from System.Drawing.Text import TextRenderingHint
    if str(control.Tag or '') == 'pet-switch':return
    control.Tag = 'pet-switch';_buffer(control)
    control.Appearance = Appearance.Button;control.FlatStyle = FlatStyle.Flat
    control.FlatAppearance.BorderSize = 0;control.AutoSize = False
    control.UseVisualStyleBackColor = False;control.Cursor = Cursors.Hand
    control.AccessibleName = str(control.Text).split('\n')[0]
    hot = [False]
    def hover(value):hot[0] = value;control.Invalidate()
    control.MouseEnter += lambda s,e:hover(True)
    control.MouseLeave += lambda s,e:hover(False)
    control.CheckedChanged += lambda s,e:control.Invalidate()
    control.GotFocus += lambda s,e:control.Invalidate()
    control.LostFocus += lambda s,e:control.Invalidate()
    def paint(sender, event):
        g = event.Graphics;g.Clear(control.Parent.BackColor if control.Parent is not None else color('bg'))
        g.SmoothingMode = SmoothingMode.AntiAlias;g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit
        shape(g, (1, 1, max(1, control.Width-3), max(1, control.Height-3)), 14*scale,
              color('hover' if hot[0] else 'surface'), color('focus' if control.Focused else 'edge'))
        inset = 16*scale;track_width = 38*scale;track_height = 22*scale
        x = control.Width-inset-track_width;y = (control.Height-track_height)/2
        shape(g, (x, y, track_width, track_height), track_height/2,
              color('accent' if control.Checked else 'toggleOff'))
        knob = 16*scale
        shape(g, (x+track_width-knob-3*scale if control.Checked else x+3*scale, y+3*scale, knob, knob), knob/2, color('surface'))
        text = str(control.Text);title, _, detail = text.partition('\n')
        text_width = max(1, control.Width-inset*2-track_width-14*scale)
        brush = SolidBrush(color('ink'))
        try:
            if detail:
                # Allocate half the available row to each line group; layout measures
                # the entire text before assigning this control's height.
                from System.Windows.Forms import TextRenderer, TextFormatFlags
                from System.Drawing import Size
                title_height = TextRenderer.MeasureText(title, control.Font, Size(int(text_width), 10000),
                    TextFormatFlags.WordBreak | TextFormatFlags.NoPadding).Height + 4*scale
                draw_text(g,title, control.Font, brush, RectangleF(inset, 12*scale, text_width, title_height))
                brush.Color = color('muted')
                draw_text(g,detail, control.Font, brush, RectangleF(inset, 12*scale+title_height, text_width, max(1,control.Height-title_height-20*scale)))
            else:
                from System.Drawing import StringFormat, StringAlignment
                fmt = StringFormat();fmt.LineAlignment = StringAlignment.Center
                try:draw_text(g,title, control.Font, brush, RectangleF(inset, 8*scale, text_width, max(1,control.Height-16*scale)), fmt)
                finally:fmt.Dispose()
        finally:brush.Dispose()
    control.Paint += paint


def soften_frame(form):
    """Ask DWM for OS-managed corners and a matching caption; unsupported OS is OK."""
    import ctypes
    from ctypes import wintypes
    try:
        api = ctypes.WinDLL('dwmapi').DwmSetWindowAttribute
        api.argtypes = [wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
        for attribute, value in ((33, 2), (35, 0x00FEFAF7), (36, 0x00655343)):
            arg = ctypes.c_int(value)
            api(wintypes.HWND(int(form.Handle.ToInt64())), attribute, ctypes.byref(arg), ctypes.sizeof(arg))
    except (OSError, AttributeError):pass
