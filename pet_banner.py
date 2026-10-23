"""Native right-click banner with stable hit targets and a soft ice-blue finish."""
from pet_banner_model import PRIMARY, MORE, banner_layout, clamp_popup, place_banner
import pet_banner_style as style
import time
from pet_banner_motion import Tween


class BannerMenu:
    def __init__(self, host):
        from System.Drawing import Font, FontStyle, Size, Point, ContentAlignment
        from System.Windows.Forms import (Form, FormBorderStyle, FormStartPosition,
            AutoScaleMode, Panel, Label, Button, FlatStyle, Padding, Cursors, ToolTip, Timer)
        self.host = host
        self.scale = max(1, float(getattr(host, 'dpi_scale', 1)))
        self.px = lambda n: round(n * self.scale)
        self.expanded = False
        self.anchor = (0, 0)
        self.pet_rect = None
        self.area = (0, 0, 1920, 1080)
        self.images = []
        self._resources_disposed = False
        self._hot = set()
        self._button_icons = {}
        self._motion = {}
        self._controls = {}
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
        self.menu.BackColor = style.color(style.BAR_EDGE)
        self.root = Panel()
        self.root.BackColor = style.color(style.BAR_BG)
        self.root.AutoScroll = True
        self.root.Margin = Padding(0)
        self.regular = Font('Microsoft YaHei UI', 9)
        self.bold = Font('Microsoft YaHei UI', 9, FontStyle.Bold)
        self.root.Font = self.regular
        self.title = Label()
        unread = host.buddy.unread_count()
        self.title.Text = 'Agent 助手' + ('  ·  %d 条未读' % unread if unread else '  ·  随手打开')
        if host.buddy.dnd_active():self.title.Text += '  ·  勿扰中'
        self.title.ForeColor = style.color(style.TITLE_FG)
        self.title.BackColor = style.color(style.BAR_BG)
        self.title.Font = self.regular
        self.title.Paint += self._paint_title
        self.root.Controls.Add(self.title)
        self.tip = ToolTip()
        self.tip.InitialDelay = 500
        self.tip.AutoPopDelay = 6000
        for key, label, glyph in PRIMARY:
            button = Button()
            button.Name = key
            button.AccessibleName = label
            button.Text = label
            button.Font = self.regular
            button.TextAlign = ContentAlignment.BottomCenter
            button.ImageAlign = ContentAlignment.TopCenter
            button.Padding = Padding(2, 0, 2, self.px(6))
            button.FlatStyle = FlatStyle.Flat
            button.UseVisualStyleBackColor = False
            button.FlatAppearance.BorderSize = 0
            button.FlatAppearance.BorderColor = style.color(style.CARD_EDGE)
            button.FlatAppearance.MouseOverBackColor = style.color(style.BAR_BG)
            button.FlatAppearance.MouseDownBackColor = style.color(style.BAR_BG)
            button.BackColor = style.color(style.BAR_BG)
            button.ForeColor = style.color(style.INK)
            button.Cursor = Cursors.Hand
            tone = style.icon_tone(key)
            normal = self._icon(glyph, False, tone)
            hot = self._icon(glyph, True, tone)
            # Custom paint is the sole image owner; native Button painting must
            # not contribute a second, differently positioned icon.
            button.Image = None
            self._button_icons[key] = (normal, hot)
            self._wire_button(button, key, normal, hot, danger=False)
            self.root.Controls.Add(button)
            self.buttons[key] = button
            self.tip.SetToolTip(button, dict(tools='常用工具', inbox='提醒收件箱', dnd='临时勿扰', buddy='陪伴小目标', quota='显示或隐藏额度消息卡', settings='桌宠设置', more='展开更多操作')[key])
        self.extra = []
        for key, label in MORE:
            button = Button()
            button.Name = key
            button.AccessibleName = label
            button.Text = label
            button.Font = self.regular
            button.TextAlign = ContentAlignment.MiddleCenter
            button.FlatStyle = FlatStyle.Flat
            button.UseVisualStyleBackColor = False
            button.FlatAppearance.BorderSize = 0
            button.FlatAppearance.BorderColor = style.color(style.CARD_EDGE)
            button.FlatAppearance.MouseOverBackColor = style.color(style.BAR_BG)
            button.FlatAppearance.MouseDownBackColor = style.color(style.BAR_BG)
            button.BackColor = style.color(style.BAR_BG)
            button.ForeColor = style.color(style.DANGER if key == 'quit' else style.INK)
            button.Cursor = Cursors.Hand
            button.AutoEllipsis = True
            self._button_icons[key] = (None, None)
            self._wire_button(button, key, None, None, danger=(key == 'quit'))
            button.Visible = False
            self.root.Controls.Add(button)
            self.extra.append(button)
        self.root.Location = Point(1,1)
        self.menu.Controls.Add(self.root)
        self.menu.Disposed += self._disposed
        self._owner_closed = lambda s,e:self.menu.Dispose()
        host.form.FormClosed += self._owner_closed

    def _wire_button(self, button, key, normal, hot, danger=False):
        """Keep native button behavior; custom paint supplies the rounded look."""
        style.enable_double_buffer(button)
        self._motion[key] = (Tween(), Tween())
        self._controls[key] = button

        def refresh():
            if self._resources_disposed or button.IsDisposed:return
            active = key in self._hot or button.Focused
            button.Font = self.regular
            button.BackColor = style.color(style.BAR_BG)
            if danger:
                button.ForeColor = style.color(style.DANGER_HOT if active else style.DANGER)
            else:
                button.ForeColor = style.color(style.INK_HOT if active else style.INK)
            self._motion[key][0].to(1 if active else 0,time.monotonic(),.24)
            self._animation_timer.Start()
            button.Invalidate()

        def set_hover(active):
            if self._resources_disposed or button.IsDisposed:return
            if active:
                self._hot.add(key)
            else:
                self._hot.discard(key)
                self._motion[key][1].to(0,time.monotonic(),.24)
            refresh()

        def press(down):
            if self._resources_disposed or button.IsDisposed:return
            self._motion[key][1].to(1 if down else 0,time.monotonic(),.16 if down else .26)
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
        style.fill_rect(g,0,0,sender.Width,sender.Height,style.BAR_BG)
        g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
        brush = SolidBrush(style.color(style.TITLE_FG))
        fmt = StringFormat()
        fmt.Trimming = StringTrimming.EllipsisCharacter
        fmt.FormatFlags = StringFormatFlags.NoWrap
        try:g.DrawString(str(sender.Text),self.regular,brush,RectangleF(0.,0.,float(sender.Width),float(sender.Height)),fmt)
        finally:fmt.Dispose();brush.Dispose()

    def _icon(self, glyph, hot, tone='blue'):
        from System.Drawing import Bitmap, Graphics, Font, GraphicsUnit, SolidBrush, Color, RectangleF, StringFormat, StringAlignment
        from System.Drawing.Text import TextRenderingHint
        image = Bitmap(self.px(44), self.px(32))
        graphics = Graphics.FromImage(image)
        graphics.Clear(Color.Transparent)
        graphics.TextRenderingHint = TextRenderingHint.AntiAliasGridFit
        font = Font('Segoe MDL2 Assets', float(self.px(20 if hot else 17)), GraphicsUnit.Pixel)
        brush = SolidBrush(style.icon_color(tone, hot))
        fmt = StringFormat()
        fmt.Alignment = StringAlignment.Center
        try:graphics.DrawString(glyph, font, brush, RectangleF(0.,float(self.px(2 if hot else 5)),float(image.Width),float(image.Height)),fmt)
        finally:
            fmt.Dispose();brush.Dispose();font.Dispose();graphics.Dispose()
        self.images.append(image)
        return image

    def _paint_button(self, sender, event, key):
        """Fully repaint one button: bar background, rounded card, icon and text."""
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
        style.fill_rect(graphics, 0, 0, bounds.Width, bounds.Height, style.BAR_BG)

        primary = key in self.buttons
        active = key in self._hot or button.Focused
        focused = button.Focused
        now = time.monotonic()
        amount, pressed = (t.value(now) for t in self._motion[key])
        inset = max(1, self.px(1))
        card_x = float(inset)
        card_y = float(inset)
        card_w = float(max(1, bounds.Width - 2 * inset))
        card_h = float(max(1, bounds.Height - 2 * inset))
        radius = min(self.px(16 if primary else 13), card_w / 2.0, card_h / 2.0)
        fill = style.mix(style.mix(style.CARD_BG,style.CARD_HOT_BG,amount),style.CARD_PRESSED_BG,pressed*.65)
        border = style.mix(style.CARD_EDGE,style.FOCUS if focused else style.CARD_HOT_EDGE,amount)
        border_width = 1.0 + (0.6 if focused else 0.4)*amount
        style.paint_round_card(graphics, card_x, card_y, card_w, card_h, radius,
                               fill, border, border_width)

        if primary:
            images = self._button_icons.get(key)
            image = images[1] if images else None
            if image is not None:
                # Transform one opaque glyph instead of cross-fading two
                # outlines. Every frame starts with the opaque background above.
                factor = .85 + .15*amount
                width, height = image.Width*factor, image.Height*factor
                ix = card_x + (card_w-width)/2.0
                iy = card_y + self.px(5)*(1-amount) + self.px(1)*pressed
                graphics.DrawImage(image,RectangleF(float(ix),float(iy),float(width),float(height)))

        text = str(button.Text or '')
        if not text:
            return
        if primary:
            text_x = card_x + self.px(2)
            text_y = card_y + card_h - self.px(18) - self.px(2)
            text_w = card_w - self.px(4)
            text_h = self.px(18)
        else:
            text_x = card_x + self.px(8)
            text_y = card_y + self.px(2)
            text_w = card_w - self.px(16)
            text_h = card_h - self.px(4)
        if key == 'quit':
            text_color = style.mix(style.DANGER,style.DANGER_HOT,amount)
        else:
            text_color = style.mix(style.INK,style.INK_HOT,amount)
        font = self.regular
        brush = SolidBrush(style.color(text_color))
        fmt = StringFormat()
        fmt.Alignment = StringAlignment.Center
        fmt.LineAlignment = StringAlignment.Center
        fmt.Trimming = StringTrimming.EllipsisCharacter
        fmt.FormatFlags = StringFormatFlags.NoWrap
        try:
            graphics.DrawString(text, font, brush,
                                RectangleF(float(text_x), float(text_y),
                                           float(max(1.0, text_w)), float(max(1.0, text_h))),
                                fmt)
        finally:
            fmt.Dispose();brush.Dispose()

    def _key(self, sender, event):
        from System.Windows.Forms import Keys
        keys = [self.buttons[k] for k,_,_ in PRIMARY] + (self.extra if self.expanded else [])
        if event.KeyCode in (Keys.Left, Keys.Right):
            index = keys.index(sender)
            keys[(index + (1 if event.KeyCode==Keys.Right else -1)) % len(keys)].Focus()
            event.Handled = True
            event.SuppressKeyPress = True
        elif event.KeyCode == Keys.Escape:
            self.menu.Close()
            event.Handled = True

    def _window_key(self, sender, event):
        from System.Windows.Forms import Keys
        if event.KeyCode == Keys.Escape:
            event.Handled = True
            event.SuppressKeyPress = True
            self.menu.Close()

    def show_at(self, x, y):
        from System.Drawing import Point
        from System.Windows.Forms import Screen
        self.anchor = (x,y)
        rect = getattr(self.host, 'char_rect', None)
        if rect and len(rect)==4 and rect[2]>0 and rect[3]>0:
            rx,ry,rw,rh = rect
            self.pet_rect = (self.host.form.Left+rx,self.host.form.Top+ry,
                             self.host.form.Left+rx+rw,self.host.form.Top+ry+rh)
        else:
            b = self.host.form.Bounds
            self.pet_rect = (b.Left,b.Top,b.Right,b.Bottom)
        center = Point(round((self.pet_rect[0]+self.pet_rect[2])/2),round((self.pet_rect[1]+self.pet_rect[3])/2))
        bounds = Screen.FromPoint(center).WorkingArea
        self.area = (bounds.Left,bounds.Top,bounds.Right,bounds.Bottom)
        self.layout()
        x,y = place_banner(self.pet_rect,self.menu.Width,self.menu.Height,self.area,self.px(10))
        self.menu.Location = Point(x,y)
        self.menu.Show(self.host.form)

    def layout(self):
        from System.Drawing import Size, Point
        data = banner_layout(self.scale,self.area,self.expanded)
        self.root.SuspendLayout()
        self.root.AutoScrollPosition = Point(0,0)
        self.root.Size = Size(data['width'],data['height'])
        self.menu.Size = Size(data['width']+2,data['height']+2)
        self.title.SetBounds(self.px(16),self.px(3),data['width']-self.px(30),self.px(20))
        for (key,_,_),rect in zip(PRIMARY,data['primary']):self.buttons[key].SetBounds(*rect)
        self.buttons['more'].Text = '收起' if self.expanded else '更多'
        for button in self.extra:button.Visible = self.expanded
        for button,rect in zip(self.extra,data['more']):button.SetBounds(*rect)
        self.root.AutoScrollMinSize = Size(0,data['content_height'])
        # Hidden More entries must not keep a stale hover state when collapsed.
        visible_keys = set(self.buttons)
        if self.expanded:
            visible_keys.update(key for key, _ in MORE)
        self._hot.intersection_update(visible_keys)
        now = time.monotonic()
        for key, tweens in self._motion.items():
            if key not in visible_keys:
                for tween in tweens:tween.to(0,now,.24)
        self.root.ResumeLayout(True)
        from System.Drawing import Region
        radius = min(self.px(26), self.menu.Height // 2)
        path = style.rounded_path(0, 0, self.menu.Width, self.menu.Height, radius)
        old_region = self.menu.Region
        self.menu.Region = Region(path)
        path.Dispose()
        if old_region is not None:old_region.Dispose()
        self.root.Invalidate(True)
        if self.menu.Visible:
            x,y = place_banner(self.pet_rect,self.menu.Width,self.menu.Height,self.area,self.px(10))
            self.menu.Location = Point(x,y)
            b = self.menu.Bounds
            self.host._menu_rect = (b.Left,b.Top,b.Right,b.Bottom)

    def activate(self, key):
        if key == 'more':
            self.expanded = not self.expanded
            self.layout()
            return
        h = self.host
        actions = dict(tools=lambda:h.open_assistant_panel('tools'),inbox=lambda:h.open_assistant_panel('inbox'),
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
        self._animation_timer.Stop()
        self._animation_timer.Tick -= self._animate
        self._animation_timer.Dispose()
        self.host.form.FormClosed -= self._owner_closed
        self.tip.Dispose()
        for image in self.images:image.Dispose()
        self._button_icons.clear()
        self._hot.clear()
        self._controls.clear()
        self._motion.clear()
        self.regular.Dispose();self.bold.Dispose()

