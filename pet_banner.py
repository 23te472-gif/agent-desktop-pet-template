"""Native right-click banner with stable hit targets and a softly raised ink finish."""
from pet_banner_model import PRIMARY, MORE, INTERACTIONS, banner_layout, clamp_popup, place_banner, more_popup_layout, orbit_layout, more_popup_bounds, surface_bounds, contains_surface
import pet_banner_style as style
from pet_agent_reminders import selected_unread
import time
from pet_banner_motion import Tween


def _smooth_label(graphics,text,font,brush,rectangle,fmt):
    """Supersample TrueType outlines; keep tiny Chinese glyphs off bitmap strikes."""
    from System.Drawing import Bitmap,Graphics,Color,RectangleF
    from System.Drawing.Drawing2D import InterpolationMode,PixelOffsetMode
    from pet_native_style import draw_text
    factor=3
    image=Bitmap(max(1,round(rectangle.Width*factor)),max(1,round(rectangle.Height*factor)))
    image.SetResolution(graphics.DpiX,graphics.DpiY)
    surface=Graphics.FromImage(image)
    try:
        surface.Clear(Color.Transparent)
        surface.ScaleTransform(float(factor),float(factor))
        draw_text(surface,text,font,brush,RectangleF(0.,0.,rectangle.Width,rectangle.Height),fmt)
        state=graphics.Save()
        try:
            graphics.InterpolationMode=InterpolationMode.HighQualityBicubic
            graphics.PixelOffsetMode=PixelOffsetMode.HighQuality
            graphics.DrawImage(image,rectangle)
        finally:graphics.Restore(state)
    finally:surface.Dispose();image.Dispose()


class BannerMenu:
    def __init__(self, host):
        from System.Drawing import Font, Size, Point, ContentAlignment
        from System.Windows.Forms import (Form, FormBorderStyle, FormStartPosition,
            AutoScaleMode, Panel, Label, Button, FlatStyle, Padding, Cursors, ToolTip, Timer)
        self.host = host
        settings = getattr(host, 'settings', {})
        theme = settings.get('settingsTheme') if hasattr(settings, 'get') else None
        self.style = style.for_theme(theme)
        self.scale = max(1, float(getattr(host, 'dpi_scale', 1)))
        self.px = lambda n: round(n * self.scale)
        self.expanded = False
        self.expanded_group = None
        self.anchor = (0, 0)
        self.pet_rect = None
        self.area = (0, 0, 1920, 1080)
        self.images = []
        self._bar_screen = None
        self._hit_surfaces = ()
        self._base_surfaces = ()
        self._orbit_data = None
        self._layout_busy = False
        self._label_key = None
        self._resources_disposed = False
        self._hot = set()
        self._button_icons = {}
        self._motion = {}
        self._controls = {}
        self._group_separators = []
        self._animation_timer = Timer()
        self._animation_timer.Interval = 20
        self._animation_timer.Tick += self._animate
        self.buttons = {}
        # A ToolStripDropDown can be demoted when the foreground app is maximized.
        # Use an ordinary topmost tool window, like the pet's working auxiliary UI.
        self.menu = Form()
        self.menu.Tag = 'banner'
        self.menu.Name = 'pet-banner'
        self.menu.Text = 'Agent 桌宠 · 快捷工具栏'
        self.menu.AutoSize = False
        self.menu.AutoScaleMode = getattr(AutoScaleMode, 'None')
        self.menu.FormBorderStyle = getattr(FormBorderStyle, 'None')
        self.menu.StartPosition = FormStartPosition.Manual
        self.menu.ShowInTaskbar = False
        self.menu.TopMost = True
        self.menu.MinimizeBox = False
        self.menu.MaximizeBox = False
        self.menu.KeyPreview = True
        self.menu.KeyDown += self._window_key
        self.menu.Deactivate += lambda s,e:self.menu.Close() if self.menu.Visible else None
        self.menu.Padding = Padding(1)
        self.menu.BackColor = self.style.color(self.style.BAR_EDGE)
        self.root = Panel()
        self.root.BackColor = self.style.color(self.style.BAR_BG)
        self.root.AutoScroll = True
        self.root.Margin = Padding(0)
        self.root.Paint += self._paint_root
        self.regular = Font('Microsoft YaHei UI', 9.0)
        self.small = Font('Microsoft YaHei UI', 8.0)
        self.root.Font = self.regular
        self.title = Label()
        unread = selected_unread(host)
        self.title.Text = 'Agent 助手' + ('  ·  %d 条未读' % unread if unread else '  ·  随手打开')
        if host.buddy.dnd_active():self.title.Text += '  ·  勿扰中'
        self.title.ForeColor = self.style.color(self.style.TITLE_FG)
        self.title.BackColor = self.style.color(self.style.BAR_BG)
        self.title.Font = self.regular
        self.title.Paint += self._paint_title
        self.title.Visible = False
        self.root.Controls.Add(self.title)
        self.tip = ToolTip()
        self.tip.InitialDelay = 500
        self.tip.AutoPopDelay = 6000
        for key, label, glyph in PRIMARY:
            button = Button()
            button.Name = key
            button.AccessibleName = label
            button.Text = label
            button.Font = self.small if key in ('quota', 'settings', 'more') else self.regular
            button.TextAlign = ContentAlignment.BottomCenter
            button.ImageAlign = ContentAlignment.TopCenter
            button.Padding = Padding(2, 0, 2, self.px(6))
            button.FlatStyle = FlatStyle.Flat
            button.UseVisualStyleBackColor = False
            button.FlatAppearance.BorderSize = 0
            button.FlatAppearance.BorderColor = self.style.color(self.style.CARD_EDGE)
            button.FlatAppearance.MouseOverBackColor = self.style.color(self.style.BAR_BG)
            button.FlatAppearance.MouseDownBackColor = self.style.color(self.style.BAR_BG)
            button.BackColor = self.style.color(self.style.BAR_BG)
            button.ForeColor = self.style.color(self.style.INK)
            button.Cursor = Cursors.Hand
            # Custom paint owns one opaque icon per button. Never layer a
            # normal and hot image here: the old second glyph can leave a
            # faint edge behind while the hover tween settles.
            button.Image = None
            self._button_icons[key] = self._icon(key, self.style.icon_tone(key))
            self._wire_button(button, key, danger=False)
            self.root.Controls.Add(button)
            self.buttons[key] = button
            self.tip.SetToolTip(button, dict(tools='打开工具中心', interaction='摸头、换表情和随机动作', console='提醒、收件箱、勿扰与陪伴', quota='显示或隐藏额度消息卡', settings='桌宠设置', more='展开更多操作')[key])
        self.more_panel = Panel()
        self.more_panel.Name = 'pet-more-popup'
        self.more_panel.AccessibleName = '更多操作'
        self.more_panel.BackColor = self.style.color(self.style.BAR_BG)
        self.more_panel.AutoScroll = True
        self.more_panel.Visible = False
        self.more_panel.Paint += self._paint_more
        self.style.enable_double_buffer(self.more_panel)
        self.menu.Controls.Add(self.more_panel)
        self.orbit_label = Button()
        self.orbit_label.Name = 'pet-orbit-label'
        self.orbit_label.FlatStyle = FlatStyle.Flat
        self.orbit_label.FlatAppearance.BorderSize = 0
        self.orbit_label.BackColor = self.style.color(self.style.BAR_BG)
        self.orbit_label.ForeColor = self.style.color(self.style.INK)
        self.orbit_label.Font = self.small
        self.orbit_label.TabStop = False
        self.orbit_label.Cursor = Cursors.Hand
        self.orbit_label.Visible = False
        self.orbit_label.Paint += self._paint_orbit_label
        self.orbit_label.Click += lambda s,e:self.activate(self._label_key) if self._label_key else None
        self.menu.Controls.Add(self.orbit_label)
        self.extra = []
        for key, label in INTERACTIONS + MORE:
            button = Button()
            button.Name = key
            button.AccessibleName = label
            button.Text = label
            button.Font = self.small
            button.TextAlign = ContentAlignment.MiddleCenter
            button.FlatStyle = FlatStyle.Flat
            button.UseVisualStyleBackColor = False
            button.FlatAppearance.BorderSize = 0
            button.FlatAppearance.BorderColor = self.style.color(self.style.CARD_EDGE)
            button.FlatAppearance.MouseOverBackColor = self.style.color(self.style.BAR_BG)
            button.FlatAppearance.MouseDownBackColor = self.style.color(self.style.BAR_BG)
            button.BackColor = self.style.color(self.style.BAR_BG)
            button.ForeColor = self.style.color(self.style.DANGER if key == 'quit' else self.style.INK)
            button.Cursor = Cursors.Hand
            button.AutoEllipsis = True
            self._wire_button(button, key, danger=(key == 'quit'))
            button.Visible = False
            if key in dict(INTERACTIONS):
                self.menu.Controls.Add(button)
                if key == 'pat': self._button_icons[key] = self._icon('buddy', 'mint')
            else:
                self.more_panel.Controls.Add(button)
            self.extra.append(button)
        for index,button in enumerate(list(self.buttons.values())+self.extra):
            button.TabIndex = index
        self.root.Location = Point(1,1)
        self.menu.Controls.Add(self.root)
        self.menu.Disposed += self._disposed
        self._owner_closed = lambda s,e:self.menu.Dispose()
        host.form.FormClosed += self._owner_closed
        from pet_edge import EdgeHalo
        self._edge=EdgeHalo(self.menu,scale=self.scale,provider=self._edge_surfaces,fill=self.style.color(self.style.BAR_BG))

    def _wire_button(self, button, key, danger=False):
        """Keep native button behavior; custom paint supplies the rounded look."""
        self.style.enable_double_buffer(button)
        self._motion[key] = (Tween(), Tween())
        self._controls[key] = button

        def refresh():
            if self._resources_disposed or button.IsDisposed:return
            active = key in self._hot or button.Focused
            button.BackColor = self.style.color(self.style.BAR_BG)
            if danger:
                button.ForeColor = self.style.color(self.style.DANGER_HOT if active else self.style.DANGER)
            else:
                button.ForeColor = self.style.color(self.style.INK_HOT if active else self.style.INK)
            # Deliberately slower than the old banner: a calm fade instead of
            # a quick flicker while the cursor crosses the grouped bar.
            self._motion[key][0].to(1 if active else 0,time.monotonic(),.32)
            self._animation_timer.Start()
            button.Invalidate()
            if key in dict(INTERACTIONS): self._refresh_orbit_label()

        def set_hover(active):
            if self._resources_disposed or button.IsDisposed:return
            if active:
                self._hot.add(key)
            else:
                self._hot.discard(key)
                self._motion[key][1].to(0,time.monotonic(),.32)
            refresh()

        def press(down):
            if self._resources_disposed or button.IsDisposed:return
            self._motion[key][1].to(1 if down else 0,time.monotonic(),.22 if down else .34)
            self._animation_timer.Start()

        button.MouseEnter += lambda s,e:set_hover(True)
        button.MouseLeave += lambda s,e:set_hover(False)
        button.GotFocus += lambda s,e:refresh()
        button.LostFocus += lambda s,e:refresh()
        button.MouseDown += lambda s,e:press(True)
        button.MouseUp += lambda s,e:press(False)
        button.Paint += lambda s,e,k=key:self._paint_button(s,e,k)
        button.Click += lambda s,e,k=key:self.activate(k)
        button.KeyDown += self._key

    def _animate(self, sender, args):
        if self._resources_disposed:return
        now = time.monotonic()
        moving = False
        for key, tweens in self._motion.items():
            button = self._controls[key]
            if button.IsDisposed or not button.Visible:continue
            # Include the settling frame so the last painted value is exact.
            button.Invalidate()
            moving = moving or any(t.moving(now) for t in tweens)
        if not moving:self._animation_timer.Stop()

    def _paint_title(self, sender, event):
        from System.Drawing import RectangleF, SolidBrush, StringFormat, StringTrimming, StringFormatFlags
        from System.Drawing.Text import TextRenderingHint
        if self._resources_disposed:return
        g = event.Graphics
        self.style.fill_rect(g,0,0,sender.Width,sender.Height,self.style.BAR_BG)
        g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
        brush = SolidBrush(self.style.color(self.style.TITLE_FG))
        fmt = StringFormat()
        fmt.Trimming = StringTrimming.EllipsisCharacter
        fmt.FormatFlags = StringFormatFlags.NoWrap
        from pet_native_style import draw_text
        try:draw_text(g,str(sender.Text),self.regular,brush,RectangleF(0.,0.,float(sender.Width),float(sender.Height)),fmt)
        finally:fmt.Dispose();brush.Dispose()

    def _icon(self, key, tone='mint'):
        """Use the approved PNG silhouette; ice tints it once without editing the file."""
        from pathlib import Path
        from System.Drawing import Bitmap, Graphics, Color, Rectangle, RectangleF, GraphicsUnit
        from System.Drawing.Drawing2D import InterpolationMode, PixelOffsetMode
        image = Bitmap(self.px(40), self.px(26))
        graphics = Graphics.FromImage(image)
        graphics.Clear(Color.Transparent)
        graphics.InterpolationMode = InterpolationMode.HighQualityBicubic
        graphics.PixelOffsetMode = PixelOffsetMode.HighQuality
        source = None
        attributes = None
        try:
            icon_key = {'interaction': 'buddy', 'console': 'inbox'}.get(key, key)
            source = Bitmap(str(Path(__file__).resolve().parent / 'web' / 'banner-icons' / (icon_key + '.png')))
            size = self.px(18)
            if getattr(self.style, 'TINT_ICONS', False):
                from System.Drawing.Imaging import ImageAttributes, ColorMatrix
                target = self.style.icon_tint(tone)
                matrix = ColorMatrix()
                matrix.Matrix00 = 0.0
                matrix.Matrix11 = 0.0
                matrix.Matrix22 = 0.0
                matrix.Matrix33 = 1.0
                matrix.Matrix40 = target.R / 255.0
                matrix.Matrix41 = target.G / 255.0
                matrix.Matrix42 = target.B / 255.0
                matrix.Matrix44 = 1.0
                attributes = ImageAttributes()
                attributes.SetColorMatrix(matrix)
                graphics.DrawImage(source,
                    Rectangle(round((image.Width - size) / 2), round(self.px(2)), round(size), round(size)),
                    0, 0, source.Width, source.Height, GraphicsUnit.Pixel, attributes)
            else:
                graphics.DrawImage(source, RectangleF(float((image.Width-size)/2), float(self.px(2)), float(size), float(size)))
        except Exception:
            image.Dispose()
            raise
        finally:
            if attributes is not None: attributes.Dispose()
            if source is not None: source.Dispose()
            graphics.Dispose()
        self.images.append(image)
        return image

    def _paint_root(self, sender, event):
        """Paint the bar wash, its thin rim, and the quiet group separators."""
        if self._resources_disposed:
            return
        from System.Drawing import Pen
        graphics = event.Graphics
        self.style.paint_vertical_gradient(graphics, 0, 0, sender.Width, sender.Height,
                                           self.style.BAR_TOP_BG, self.style.BAR_BOTTOM_BG)
        line_width = max(1.0, self.scale * 0.65)
        top_pen = Pen(self.style.color(self.style.BAR_TOP_LIGHT), line_width)
        bottom_pen = Pen(self.style.color(self.style.BAR_BOTTOM_SHADE), max(1.0, self.scale * 0.8))
        separator_pen = Pen(self.style.color(self.style.DIVIDER), max(1.0, self.scale * 0.65))
        try:
            inset = self.px(11)
            graphics.DrawLine(top_pen, float(inset), float(self.px(1)),
                              float(sender.Width - inset), float(self.px(1)))
            graphics.DrawLine(bottom_pen, float(inset), float(sender.Height - self.px(2)),
                              float(sender.Width - inset), float(sender.Height - self.px(2)))
            for x in self._group_separators:
                graphics.DrawLine(separator_pen, float(x), float(self.px(21)),
                                  float(x), float(self.px(45)))
        finally:
            top_pen.Dispose()
            bottom_pen.Dispose()
            separator_pen.Dispose()

    def _paint_button(self, sender, event, key):
        """Fully repaint one button: bar background, soft card, one icon and text."""
        if self._resources_disposed:
            return
        from System.Drawing import RectangleF, SolidBrush, StringFormat, StringAlignment, StringTrimming, StringFormatFlags
        from System.Drawing.Drawing2D import SmoothingMode, InterpolationMode, PixelOffsetMode
        from System.Drawing.Text import TextRenderingHint
        button = sender
        bounds = button.ClientRectangle
        if bounds.Width <= 0 or bounds.Height <= 0:
            return
        graphics = event.Graphics
        graphics.SmoothingMode = SmoothingMode.AntiAlias
        graphics.InterpolationMode = InterpolationMode.HighQualityBicubic
        graphics.PixelOffsetMode = PixelOffsetMode.HighQuality
        graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit

        # Repaint the whole client area so the native flat-button text/image
        # underneath never peeks through the rounded corners.
        self.style.fill_rect(graphics, 0, 0, bounds.Width, bounds.Height, self.style.BAR_BG)

        if key in dict(INTERACTIONS):
            self._paint_orbit_button(sender,event,key)
            return
        if key in dict(MORE):
            self._paint_more_button(sender,event,key)
            return
        primary = key in self.buttons
        focused = button.Focused
        now = time.monotonic()
        amount, pressed = (t.value(now) for t in self._motion[key])
        unit = float(max(1, self.px(1)))
        card_x = unit
        card_w = float(max(1, bounds.Width - 2 * unit))
        card_h = float(max(1, bounds.Height - 4 * unit))
        card_y = unit - amount * unit + pressed * unit * 2.0
        card_y = max(0.0, min(float(bounds.Height) - card_h - unit * 0.5, card_y))
        radius = min(self.px(14 if key == 'tools' else 12 if primary else 9),
                     card_w / 2.0, card_h / 2.0)

        if primary and key == 'tools':
            base_top, base_bottom = self.style.TOOL_TOP_BG, self.style.TOOL_BOTTOM_BG
        elif primary and key == self.expanded_group:
            base_top, base_bottom = self.style.CARD_HOT_TOP_BG, self.style.CARD_HOT_BOTTOM_BG
        else:
            base_top, base_bottom = self.style.CARD_TOP_BG, self.style.CARD_BOTTOM_BG
        top = self.style.mix(base_top, self.style.CARD_HOT_TOP_BG, amount)
        bottom = self.style.mix(base_bottom, self.style.CARD_HOT_BOTTOM_BG, amount)
        top = self.style.mix(top, self.style.CARD_PRESSED_TOP_BG, pressed * .8)
        bottom = self.style.mix(bottom, self.style.CARD_PRESSED_BOTTOM_BG, pressed * .8)
        border = self.style.mix(self.style.CARD_EDGE, self.style.CARD_HOT_EDGE, amount)
        border = self.style.mix(border, self.style.CARD_EDGE, pressed * .55)
        if focused:
            border = self.style.FOCUS
        top_light = self.style.mix(self.style.CARD_TOP_LIGHT, self.style.CARD_HOT_TOP_LIGHT, amount)
        top_light = self.style.mix(top_light, self.style.CARD_PRESSED_TOP_LIGHT, pressed * .7)
        border_width = max(1.0, self.scale * 0.7)
        shadow_offset = unit * 1.2 + amount * unit * .9 - pressed * unit * .8
        shadow_offset = max(0.0, min(shadow_offset,
                                     bounds.Height - card_y - card_h - unit * .2))
        self.style.paint_depth_card(graphics, card_x, card_y, card_w, card_h, radius,
                                    top, bottom, border, border_width, top_light,
                                    border_width, self.style.CARD_SHADOW, shadow_offset)

        if primary:
            image = self._button_icons.get(key)
            if image is not None:
                # One opaque PNG glyph; the raised card, not a second icon,
                # carries the hover and pressed feedback.
                factor = .95 + .05 * amount
                width, height = image.Width * factor, image.Height * factor
                ix = card_x + (card_w - width) / 2.0
                iy = card_y + self.px(4)
                graphics.DrawImage(image, RectangleF(float(ix), float(iy), float(width), float(height)))

        text = str(button.Text or '')
        if not text:
            return
        if primary:
            text_x = card_x + self.px(2)
            text_y = card_y + card_h - self.px(15) - self.px(2)
            text_w = card_w - self.px(4)
            text_h = self.px(15)
            font = self.small if key in ('quota', 'settings', 'more') else self.regular
        else:
            text_x = card_x + self.px(8)
            text_y = card_y + self.px(2)
            text_w = card_w - self.px(16)
            text_h = card_h - self.px(4)
            font = self.small
        if key == 'quit':
            text_color = self.style.mix(self.style.DANGER, self.style.DANGER_HOT, amount)
        else:
            text_color = self.style.mix(self.style.INK, self.style.INK_HOT, amount)
        brush = SolidBrush(self.style.color(text_color))
        fmt = StringFormat()
        fmt.Alignment = StringAlignment.Center
        fmt.LineAlignment = StringAlignment.Center
        fmt.Trimming = StringTrimming.EllipsisCharacter
        fmt.FormatFlags = StringFormatFlags.NoWrap
        try:
            _smooth_label(graphics, text, font, brush,
                      RectangleF(float(text_x), float(text_y),
                                 float(max(1.0, text_w)), float(max(1.0, text_h))),
                      fmt)
        finally:
            fmt.Dispose(); brush.Dispose()

        try:
            flagged = False
            if key == 'console':
                flagged = selected_unread(self.host) > 0 or bool(self.host.buddy.dnd_active())
            elif key == self.expanded_group:
                flagged = True
            if flagged:
                self.style.draw_dot(graphics, card_x + card_w - self.px(8),
                                    card_y + self.px(8), max(2.0, self.px(2)),
                                    self.style.ICON_MINT)
        except Exception:
            # Indicator paint must never break the native toolbar.
            pass

    def _text(self, graphics, text, rectangle, color=None, align=None):
        from System.Drawing import RectangleF, SolidBrush, StringFormat, StringAlignment, StringTrimming, StringFormatFlags
        brush=SolidBrush(self.style.color(color or self.style.INK))
        fmt=StringFormat()
        fmt.Alignment=StringAlignment.Center if align is None else align
        fmt.LineAlignment=StringAlignment.Center
        fmt.Trimming=StringTrimming.EllipsisCharacter
        fmt.FormatFlags=StringFormatFlags.NoWrap
        try:_smooth_label(graphics,text,self.small,brush,RectangleF(*map(float,rectangle)),fmt)
        finally:fmt.Dispose();brush.Dispose()

    def _paint_more(self, sender, event):
        if self._resources_disposed:return
        from System.Drawing import Pen, StringAlignment
        from System.Drawing.Drawing2D import SmoothingMode
        g=event.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias
        if self.style.name == 'ice':
            # Rows share one quiet surface instead of pale rectangular patches
            # interrupting a stronger blue gradient behind them.
            self.style.fill_rect(g,0,0,sender.Width,sender.Height,self.style.BAR_BG)
            self.style.paint_round_card(g,0,0,sender.Width-1,sender.Height-1,self.px(14),self.style.BAR_BG,self.style.CARD_EDGE,max(1.,self.scale*.6))
        else:
            self.style.paint_vertical_gradient(g,0,0,sender.Width,sender.Height,self.style.BAR_TOP_BG,self.style.BAR_BOTTOM_BG)
        data=more_popup_layout(self.scale,self.area)
        offset=sender.AutoScrollPosition.Y
        for text,(x,y,w,h) in data['headings']:
            self._text(g,text,(x,y+offset,w,h),self.style.TITLE_FG,StringAlignment.Near)
        pen=Pen(self.style.color(self.style.DIVIDER),max(1.,self.scale*.6))
        try:
            for y in data['dividers']:
                g.DrawLine(pen,float(self.px(10)),float(y+offset),float(sender.ClientSize.Width-self.px(10)),float(y+offset))
        finally:pen.Dispose()

    def _paint_more_button(self, sender, event, key):
        if self._resources_disposed:return
        from System.Drawing import StringAlignment
        from System.Drawing.Drawing2D import SmoothingMode
        g=event.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias
        # Opaque repaint ensures hovered rows never leave glyph/shadow residue.
        self.style.fill_rect(g,0,0,sender.Width,sender.Height,self.style.BAR_BG)
        amount,pressed=(t.value(time.monotonic()) for t in self._motion[key])
        top=self.style.mix(self.style.BAR_BG,self.style.CARD_HOT_TOP_BG,amount)
        bottom=self.style.mix(self.style.BAR_BG,self.style.CARD_HOT_BOTTOM_BG,amount)
        edge=self.style.FOCUS if sender.Focused else self.style.mix(self.style.BAR_BG,self.style.CARD_HOT_EDGE,amount)
        self.style.paint_depth_card(g,1.,1.+pressed,max(1.,sender.Width-2.),max(1.,sender.Height-3.),self.px(8),top,bottom,edge,max(1.,self.scale*.6))
        color=self.style.DANGER if key=='quit' else self.style.INK
        self._text(g,str(sender.Text),(self.px(6),0,max(1,sender.Width-self.px(10)),sender.Height),color,StringAlignment.Near)

    def _paint_orbit_button(self, sender, event, key):
        if self._resources_disposed:return
        from System.Drawing import Pen, RectangleF
        from System.Drawing.Drawing2D import SmoothingMode, PixelOffsetMode, InterpolationMode
        g=event.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias;g.PixelOffsetMode=PixelOffsetMode.HighQuality
        g.InterpolationMode=InterpolationMode.HighQualityBicubic
        amount,pressed=(t.value(time.monotonic()) for t in self._motion[key])
        self.style.fill_rect(g,0,0,sender.Width,sender.Height,self.style.BAR_BG)
        top=self.style.mix(self.style.CARD_TOP_BG,self.style.CARD_HOT_TOP_BG,amount)
        bottom=self.style.mix(self.style.CARD_BOTTOM_BG,self.style.CARD_HOT_BOTTOM_BG,amount)
        edge=self.style.FOCUS if sender.Focused else self.style.mix(self.style.CARD_EDGE,self.style.CARD_HOT_EDGE,amount)
        self.style.paint_depth_card(g,1.,1.,sender.Width-2.,sender.Height-2.,sender.Width/2.,top,bottom,edge,max(1.,self.scale*.7),self.style.CARD_TOP_LIGHT)
        cx,cy=sender.Width/2.,sender.Height/2.+pressed*self.scale
        if key=='pat':
            image=self._button_icons.get('pat')
            if image is not None:
                g.DrawImage(image,RectangleF(float(cx-image.Width/2.),float(cy-image.Height/2.),float(image.Width),float(image.Height)))
            return
        pen=Pen(self.style.color(self.style.ICON_MINT),max(1.3,self.scale*1.35))
        radius=self.px(8)
        try:
            if key=='expression':
                g.DrawEllipse(pen,float(cx-radius),float(cy-radius),float(2*radius),float(2*radius))
                for dx in (-3,3):
                    self.style.draw_dot(g,cx+self.px(abs(dx))*(1 if dx>0 else -1),cy-self.px(2),max(.8,self.scale*.9),self.style.ICON_MINT)
                g.DrawArc(pen,float(cx-self.px(4)),float(cy-self.px(2)),float(self.px(8)),float(self.px(7)),0.,180.)
            else:
                points=((0,-9),(2.8,-2.8),(9,0),(2.8,2.8),(0,9),(-2.8,2.8),(-9,0),(-2.8,-2.8),(0,-9))
                for (x,y),(xx,yy) in zip(points,points[1:]):
                    g.DrawLine(pen,float(cx+x*self.scale),float(cy+y*self.scale),float(cx+xx*self.scale),float(cy+yy*self.scale))
        finally:pen.Dispose()

    def _paint_orbit_label(self, sender, event):
        if self._resources_disposed:return
        from System.Drawing.Drawing2D import SmoothingMode
        g=event.Graphics;g.SmoothingMode=SmoothingMode.AntiAlias
        self.style.fill_rect(g,0,0,sender.Width,sender.Height,self.style.BAR_BG)
        self.style.paint_round_card(g,0,0,sender.Width-1,sender.Height-1,self.px(8),self.style.CARD_TOP_BG,self.style.CARD_EDGE)
        self._text(g,str(sender.Text),(0,0,sender.Width,sender.Height))

    def _refresh_orbit_label(self):
        if self._layout_busy or self._resources_disposed:return
        key=None
        if self.expanded_group=='interaction':
            key=next((k for k,_ in INTERACTIONS if k in self._hot),None)
            if key is None:key=next((k for k,_ in INTERACTIONS if self._controls[k].Focused),None)
        if key!=self._label_key:
            self._label_key=key
            self._update_orbit_label()

    def _edge_surfaces(self):
        left,top=self.menu.Left,self.menu.Top
        return tuple(((x-left,y-top,w,h),r) for (x,y,w,h),r in self._hit_surfaces)

    def _update_orbit_label(self):
        """Update only the label and hit mask; never move the window or circles.

        Moving/resizing a shaped top-level window during MouseEnter/Leave can
        invalidate the very edge under the cursor and retrigger the transition.
        Its bounding box already reserves every possible label at group-open.
        Reserved blank space remains outside the actual native Region.
        """
        if self._resources_disposed:return
        orbit=self._orbit_data if self.expanded_group=='interaction' else None
        valid=bool(orbit and self._label_key in orbit['labels'])
        surfaces=list(self._base_surfaces)
        if valid:
            x,y,w,h=orbit['labels'][self._label_key]
            self.orbit_label.SetBounds(x-self.menu.Left,y-self.menu.Top,w,h)
            self.orbit_label.Text=dict(INTERACTIONS)[self._label_key]
            self.orbit_label.AccessibleName=self.orbit_label.Text
            self._set_region(self.orbit_label,[((0,0,w,h),self.px(8))])
            surfaces.append(((x,y,w,h),self.px(8)))
        self.orbit_label.Visible=valid
        if valid:self.orbit_label.BringToFront()
        left,top=self.menu.Left,self.menu.Top
        self._set_region(self.menu,[((x-left,y-top,w,h),r) for (x,y,w,h),r in surfaces])
        self._hit_surfaces=tuple(surfaces)
        self.orbit_label.Invalidate()
        edge=getattr(self,'_edge',None)
        if edge is not None:edge.refresh()

    def _key(self, sender, event):
        from System.Windows.Forms import Keys
        key=str(sender.Name)
        primary=[self.buttons[k] for k,_,_ in PRIMARY]
        active=[self._controls[k] for k,_ in (MORE if self.expanded_group=='more' else INTERACTIONS) if self._controls[k].Visible] if self.expanded else []
        if key in ('more','interaction') and self.expanded_group==key and active and event.KeyCode in (Keys.Down,Keys.Up):
            active[0 if event.KeyCode==Keys.Down else -1].Focus()
        elif event.KeyCode in (Keys.Left,Keys.Right,Keys.Up,Keys.Down,Keys.Home,Keys.End):
            keys=primary if key in self.buttons else active
            if not keys:return
            i=keys.index(sender)
            if event.KeyCode==Keys.Home:i=0
            elif event.KeyCode==Keys.End:i=len(keys)-1
            else:i=(i+(1 if event.KeyCode in (Keys.Right,Keys.Down) else -1))%len(keys)
            keys[i].Focus()
        else:return
        event.Handled=True;event.SuppressKeyPress=True

    def _window_key(self, sender, event):
        from System.Windows.Forms import Keys
        if event.KeyCode==Keys.Escape:
            event.Handled=True;event.SuppressKeyPress=True
            if self.expanded:
                key=self.expanded_group
                self.expanded=False;self.expanded_group=None;self._label_key=None
                self.layout();self.buttons[key].Focus()
            else:self.menu.Close()

    def show_at(self, x, y):
        from System.Drawing import Point
        from System.Windows.Forms import Screen
        self.anchor=(x,y)
        rect=getattr(self.host,'char_rect',None)
        if rect and len(rect)==4 and rect[2]>0 and rect[3]>0:
            rx,ry,rw,rh=rect
            self.pet_rect=(self.host.form.Left+rx,self.host.form.Top+ry,self.host.form.Left+rx+rw,self.host.form.Top+ry+rh)
        else:
            b=self.host.form.Bounds;self.pet_rect=(b.Left,b.Top,b.Right,b.Bottom)
        center=Point(round((self.pet_rect[0]+self.pet_rect[2])/2),round((self.pet_rect[1]+self.pet_rect[3])/2))
        b=Screen.FromPoint(center).WorkingArea
        self.area=(b.Left,b.Top,b.Right,b.Bottom)
        self._bar_screen=None
        self.layout()
        self.menu.Show(self.host.form)

    def contains_screen_point(self, point):
        # Immutable screen-coordinate snapshot: safe for the global input hook.
        return not self._resources_disposed and contains_surface(point,self._hit_surfaces)

    def layout(self):
        from System.Drawing import Size, Point, Region
        if self._layout_busy or self._resources_disposed:return
        self._layout_busy=True
        self.menu.SuspendLayout();self.root.SuspendLayout();self.more_panel.SuspendLayout()
        try:
            data=banner_layout(self.scale,self.area)
            bw,bh=data['width']+2,data['height']+2
            if self._bar_screen is None:
                x,y=place_banner(self.pet_rect,bw,bh,self.area,self.px(10))
                self._bar_screen=(x,y,x+bw,y+bh)
            bar=self._bar_screen
            bar_surface=((bar[0],bar[1],bw,bh),min(self.px(20),bh/2))
            surfaces=[bar_surface]
            more=None;orbit=None
            if self.expanded_group=='more':
                more=more_popup_layout(self.scale,self.area)
                bounds=more_popup_bounds(self.pet_rect,bar,(more['width'],more['height']),self.area,self.px(10))
                if bounds:
                    mx,my,_,more['visible_height']=bounds
                    surfaces.append((bounds,self.px(14)))
                else:
                    more=None
                    self.tip.SetToolTip(self.buttons['more'],'当前屏幕空间不足，请移动桌宠或减小界面缩放后再试')
            elif self.expanded_group=='interaction':
                orbit=orbit_layout(self.pet_rect,self.area,self.scale,bar=bar)
                if not orbit['entries']:
                    self.tip.SetToolTip(self.buttons['interaction'],'当前屏幕空间不足，请移动桌宠或减小界面缩放后再试')
                surfaces.extend((rect,rect[2]/2.) for key,rect in orbit['entries'])
            # Reserve all label extents once, without making their empty pixels
            # hittable. Hover only changes the Region, not HWND/child geometry.
            reserved=surfaces+([(rect,self.px(8)) for rect in orbit['labels'].values()] if orbit else [])
            left,top,right,bottom=surface_bounds(reserved)
            self.menu.SetBounds(left,top,right-left,bottom-top)
            self.root.SetBounds(bar[0]-left+1,bar[1]-top+1,data['width'],data['height'])
            self.root.AutoScrollMinSize=Size(0,data['content_height'])
            self._group_separators=list(data.get('separators',[]))
            self.title.Visible=False
            for (key,_,_),rect in zip(PRIMARY,data['primary']):self.buttons[key].SetBounds(*rect)
            self.buttons['more'].Text='更多'
            self.buttons['more'].AccessibleDescription='收起更多' if self.expanded_group=='more' else '展开更多'
            self.buttons['interaction'].AccessibleDescription='收起互动' if self.expanded_group=='interaction' else '展开互动'
            active={key for key,_ in (orbit['entries'] if orbit else more['entries'] if more else ())}
            # Do not hide/re-show a focused circle when its label is updated.
            # WinForms transfers focus as soon as Visible becomes False.
            for button in self.extra:button.Visible=str(button.Name) in active
            self.more_panel.Visible=more is not None
            if more is not None:
                self.more_panel.SetBounds(mx-left,my-top,more['width'],more['visible_height'])
                self.more_panel.AutoScrollPosition=Point(0,0)
                for key,rect in more['entries']:
                    self._controls[key].SetBounds(*rect);self._controls[key].Visible=True
                self.more_panel.AutoScrollMinSize=Size(0,more['height'])
                self._set_region(self.more_panel,[( (0,0,more['width'],more['visible_height']),self.px(14))])
            if orbit is not None:
                for key,(x,y,w,h) in orbit['entries']:
                    button=self._controls[key]
                    button.SetBounds(x-left,y-top,w,h)
                    self._set_region(button,[((0,0,w,h),w/2.)])
                    button.Visible=True
            self._orbit_data=orbit
            self._base_surfaces=tuple(surfaces)
            self._update_orbit_label()
            self.host._menu_rect=(left,top,right,bottom)
            visible=set(self.buttons)|{str(b.Name) for b in self.extra if b.Visible}
            self._hot.intersection_update(visible)
            for key,tweens in self._motion.items():
                if key not in visible:
                    for t in tweens:t.to(0,time.monotonic(),.32)
        finally:
            self.more_panel.ResumeLayout(True);self.root.ResumeLayout(True);self.menu.ResumeLayout(True)
            self._layout_busy=False
        self.menu.Invalidate(True)

    def _set_region(self, control, surfaces):
        from System.Drawing import Region
        region=Region();region.MakeEmpty()
        try:
            for (x,y,w,h),radius in surfaces:
                path=self.style.rounded_path(x,y,w,h,radius)
                try:region.Union(path)
                finally:path.Dispose()
            old=control.Region;control.Region=region
            if old is not None:old.Dispose()
        except Exception:
            region.Dispose();raise

    def activate(self, key):
        if key in ('more', 'interaction'):
            self.expanded_group = None if self.expanded_group == key else key
            self.expanded = self.expanded_group is not None
            self._label_key = None
            self.layout()
            return
        h = self.host
        actions = dict(tools=lambda:h.open_assistant_panel('tools'),console=lambda:h.open_assistant_panel('control'),inbox=lambda:h.open_assistant_panel('inbox'),
            dnd=h.open_buddy_dnd,buddy=lambda:h.open_assistant_panel('buddy'),quota=h.toggle_metric_card,
            settings=h.show_settings,progress=h.toggle_card,refresh=h.refresh_card_now,
            pat=lambda:h.user_interaction('pat'),expression=lambda:h.post({'t':'cycle-expression'}),
            motion=lambda:h.post({'t':'react','kind':'motion'}),reminders=lambda:h.open_assistant_panel('reminders'),
            quiet=h.open_companion_panel,focus_agent=h.focus_agent_window,agent=h.open_agent_picker,
            reload=h.reload_page,repaint=h.repaint_now,hide=h.hide_to_tray,quit=h.form.Close)
        action = actions.get(key)
        if action is None:raise ValueError('未知工具栏操作')
        h._menu_close_reason = '点选了工具栏入口'
        self.menu.Close()
        action()

    def _disposed(self, sender, args):
        if self._resources_disposed:return
        self._resources_disposed = True
        edge=getattr(self,'_edge',None)
        if edge is not None:edge.dispose()
        self._animation_timer.Stop()
        self._animation_timer.Tick -= self._animate
        self._animation_timer.Dispose()
        self.host.form.FormClosed -= self._owner_closed
        try:self.root.Paint -= self._paint_root
        except Exception:pass
        self.tip.Dispose()
        for image in self.images:image.Dispose()
        self._hit_surfaces = ()
        self._base_surfaces = ()
        self._button_icons.clear()
        self._hot.clear()
        self._controls.clear()
        self._motion.clear()
        self.regular.Dispose();self.small.Dispose()

