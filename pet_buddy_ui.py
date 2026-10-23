"""Small WinForms panels for the local buddy inbox, DND and interaction goal.

All controls are created/updated on the host UI thread. The module is imported
lazily by run.py so the pure state module stays testable without CLR.
"""
from __future__ import annotations

import time


_KIND_LABELS = {"done": "完成", "waiting": "待确认", "quota": "额度"}


def _existing(host, key):
    form = host.assistant_panels.get(key)
    if form is not None and not form.IsDisposed:
        refresh = getattr(host, "_buddy_refresh", None) if key == "buddy" else None
        if refresh is not None:refresh()
        form.Show()
        form.Activate()
        return form
    return None


def _attach(host, key, form, timer=None):
    def owner_closed(sender, args):
        if not form.IsDisposed:
            form.Close()

    def closed(sender, args):
        if timer is not None:
            try:
                timer.Stop()
                timer.Dispose()
            except Exception:
                pass
        host.unregister_aux_window(form)
        host.form.FormClosed -= owner_closed
        if key == "buddy":
            host._buddy_tabs = None
        if host.assistant_panels.get(key) is form:
            host.assistant_panels.pop(key, None)
            if key == "buddy":
                host._buddy_refresh = None
                host._buddy_tabs = None

    form.FormClosed += closed
    host.form.FormClosed += owner_closed
    host.assistant_panels[key] = form
    from pet_theme import apply_window
    apply_window(host, form, '提醒与陪伴' if key == 'buddy' else '临时勿扰',
                 '把消息收好，也给自己留一点安静。' if key == 'buddy' else '暂停打扰，重要消息稍后统一查看。')
    form.Show()
    host.register_aux_window(form)
    form.Activate()


def _status_text(host):
    buddy = host.buddy
    lines = ["未读 %d 条" % buddy.unread_count()]
    if buddy.dnd_active():
        minutes = max(1, (buddy.dnd_remaining() + 59) // 60)
        lines.append("勿扰剩余 %d 分钟" % minutes)
    else:
        lines.append("勿扰未开启")
    if buddy.error:
        lines.append("提醒历史损坏，原文件已保留：" + buddy.error)
    elif buddy.last_error:
        lines.append(buddy.last_error)
    return " · ".join(lines[:2]) + ("\n" + lines[2] if len(lines) > 2 else "")


def _stamp(value):
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(float(value)))
    except (OSError, ValueError, TypeError):
        return "--"


def _item_text(item):
    title = str(item.get("title") or "").strip()
    detail = str(item.get("detail") or "").strip()
    if not title:
        title = "任务标题已隐藏"
    if detail:
        title = title + "（" + detail + "）"
    return "%s  %s\n%s" % (_stamp(item.get("at")), _KIND_LABELS.get(item.get("kind"), "提醒"), title)


def open_panel(host, kind):
    key = "buddy"
    old = _existing(host, key)
    if old is not None:
        tabs = getattr(host, "_buddy_tabs", None)
        if tabs is not None:
            tabs.SelectedIndex = 1 if kind == "buddy" else 0
        return

    from System.Drawing import Color, Font, Size, ContentAlignment, FontStyle
    from System.Windows.Forms import (
        AutoScaleMode,
        AutoSizeMode,
        Button,
        CheckBox,
        DialogResult,
        DockStyle,
        FlowDirection,
        FlowLayoutPanel,
        Form,
        FormStartPosition,
        Label,
        MessageBox,
        MessageBoxButtons,
        Padding,
        Screen,
        TabControl,
        TabPage,
        Timer,
    )

    scale = max(1, float(getattr(host, "dpi_scale", 1)))
    px = lambda value: round(value * scale)
    form = Form()
    form.Text = "提醒收件箱与陪伴 · Agent 桌宠"
    form.AutoScaleMode = getattr(AutoScaleMode, "None")
    form.StartPosition = FormStartPosition.CenterScreen
    area = Screen.FromControl(host.form).WorkingArea
    form.ClientSize = Size(min(px(560), area.Width - 40), min(px(620), area.Height - 70))
    form.MinimumSize = Size(min(px(420), area.Width - 40), min(px(360), area.Height - 70))
    form.Font = Font("Microsoft YaHei UI", 11)
    form.BackColor = Color.FromArgb(248, 247, 241)
    form.TopMost = bool(host.settings.get("alwaysOnTop", True))
    form.ShowInTaskbar = True
    form.MinimizeBox = False

    tabs = TabControl()
    tabs.Dock = DockStyle.Fill
    form.Controls.Add(tabs)
    host._buddy_tabs = tabs
    inbox_page = TabPage("提醒")
    companion_page = TabPage("陪伴")
    tabs.TabPages.Add(inbox_page)
    tabs.TabPages.Add(companion_page)
    tabs.SelectedIndex = 1 if kind == "buddy" else 0

    def page_panel(page):
        panel = FlowLayoutPanel()
        panel.Dock = DockStyle.Fill
        panel.FlowDirection = FlowDirection.TopDown
        panel.WrapContents = False
        panel.AutoScroll = True
        panel.Padding = Padding(px(16))
        panel.BackColor = Color.FromArgb(248, 247, 241)
        page.Controls.Add(panel)
        return panel

    def add_label(panel, text="", height=30, color=None):
        item = Label()
        item.Text = text
        item.AutoSize = False
        item.Width = max(px(220), form.ClientSize.Width - px(72))
        item.Height = px(height)
        item.Margin = Padding(0, 0, 0, px(6))
        item.ForeColor = color or Color.FromArgb(65, 86, 74)
        panel.Controls.Add(item)
        return item

    def add_button(panel, text, handler, width=112):
        item = Button()
        item.Text = text
        item.Width = px(width)
        item.Height = max(px(30), form.Font.Height + px(8))
        item.Margin = Padding(0, 0, px(8), px(6))
        item.BackColor = Color.FromArgb(235, 241, 227)
        item.Click += lambda sender, args: handler()
        panel.Controls.Add(item)
        return item

    def clear(panel):
        while panel.Controls.Count:
            item = panel.Controls[0]
            panel.Controls.Remove(item)
            try:
                item.Dispose()
            except Exception:
                pass

    inbox = page_panel(inbox_page)
    status = add_label(inbox, "", 44)
    dnd_row = FlowLayoutPanel()
    dnd_row.FlowDirection = FlowDirection.LeftToRight
    dnd_row.WrapContents = True
    dnd_row.AutoSize = True
    dnd_row.Width = max(px(260), form.ClientSize.Width - px(72))
    dnd_row.Margin = Padding(0, 0, 0, px(4))
    inbox.Controls.Add(dnd_row)

    def refresh_status():
        status.Text = _status_text(host)
        dnd_row.Enabled = True

    def change_dnd(minutes):
        try:
            host.buddy.set_dnd(minutes)
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "勿扰未设置")
        refresh_status()

    def cancel_dnd():
        try:
            host.buddy.cancel_dnd()
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "勿扰未取消")
        refresh_status()

    for minutes in (15, 30, 60):
        add_button(dnd_row, "勿扰%d分" % minutes, lambda value=minutes: change_dnd(value), 92)
    add_button(dnd_row, "取消勿扰", cancel_dnd, 92)

    list_panel = FlowLayoutPanel()
    list_panel.FlowDirection = FlowDirection.TopDown
    list_panel.WrapContents = False
    list_panel.AutoSize = True
    list_panel.AutoSizeMode = AutoSizeMode.GrowAndShrink
    list_panel.Width = max(px(260), form.ClientSize.Width - px(72))
    list_panel.Margin = Padding(0, 0, 0, px(8))
    inbox.Controls.Add(list_panel)

    action_row = FlowLayoutPanel()
    action_row.FlowDirection = FlowDirection.LeftToRight
    action_row.WrapContents = True
    action_row.AutoSize = True
    action_row.Width = max(px(260), form.ClientSize.Width - px(72))
    inbox.Controls.Add(action_row)

    def mark_read(item_id):
        try:
            host.buddy.mark_read(item_id)
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "已读状态未保存")
        rebuild_inbox()

    def mark_all():
        try:
            host.buddy.mark_all_read()
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "已读状态未保存")
        rebuild_inbox()

    def clear_history():
        if MessageBox.Show(form, "清空本机提醒历史？此操作不会影响 Agent 会话。", "清空提醒收件箱",
                           MessageBoxButtons.YesNo) != DialogResult.Yes:
            return
        try:
            host.buddy.clear_inbox()
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "历史未清空")
        rebuild_inbox()

    add_button(action_row, "全部已读", mark_all, 96)
    add_button(action_row, "清空历史", clear_history, 96)

    def row_width():
        width = list_panel.ClientSize.Width
        if width <= 0:
            width = form.ClientSize.Width - px(72)
        return max(px(260), width - px(8))

    def add_item_row(item):
        width = row_width()
        row = FlowLayoutPanel()
        row.FlowDirection = FlowDirection.LeftToRight
        row.WrapContents = False
        row.AutoSize = False
        row.Width = width
        row.Height = max(px(48), form.Font.Height + px(22))
        row.Margin = Padding(0, 0, 0, px(4))
        text = Label()
        text.Text = _item_text(item)
        text.AutoSize = False
        text.Width = max(px(170), width - px(86))
        text.Height = row.Height
        text.TextAlign = ContentAlignment.MiddleLeft
        text.AutoEllipsis = True
        read = Button()
        read.Text = "已读"
        read.Width = px(68)
        read.Height = max(px(28), form.Font.Height + px(4))
        read.Enabled = not bool(item.get("read"))
        read.Click += lambda sender, args, value=item.get("id"): mark_read(value)
        row.Controls.Add(text)
        row.Controls.Add(read)
        from pet_theme import style_tree, color
        style_tree(row)
        row.BackColor = color('surface')
        text.BackColor = row.BackColor
        text.ForeColor = color('ink')
        list_panel.Controls.Add(row)

    rendered = {"items": None}
    def rebuild_inbox():
        items = host.buddy.snapshot()["inbox"]
        if items != rendered["items"]:
            rendered["items"] = items
            clear(list_panel)
            if not items:
                empty = Label()
                empty.Text = "暂时没有新提醒。\n任务完成、需要回复或额度不足时，会记录在这里。"
                empty.Width = row_width()
                empty.Height = px(74)
                empty.ForeColor = Color.FromArgb(99, 123, 114)
                empty.Padding = Padding(px(10))
                list_panel.Controls.Add(empty)
            for item in reversed(items):
                add_item_row(item)
        refresh_status()

    refresh_status()
    rebuild_inbox()

    companion = page_panel(companion_page)
    progress = add_label(companion, "", 46)
    progress.Font = Font("Microsoft YaHei UI", 18, FontStyle.Bold)
    stats = add_label(companion, "", 34)
    hint = add_label(companion, "每 60 秒最多计 1 次，每天最多 3 次；没有后台在线奖励。", 40)
    feedback_box = CheckBox()
    feedback_box.Text = "显示互动短反馈"
    feedback_box.AutoSize = True
    feedback_box.Margin = Padding(0, 0, 0, px(8))
    companion.Controls.Add(feedback_box)
    goal_box = CheckBox()
    goal_box.Text = "开启每日小目标"
    goal_box.AutoSize = True
    goal_box.Margin = Padding(0, 0, 0, px(8))
    companion.Controls.Add(goal_box)
    companion_status = add_label(companion, "", 34)
    guard = {"updating": False}

    def refresh_companion():
        data = host.buddy.interaction_snapshot()
        progress.Text = "今日互动：%d / %d" % (data["today"], data["target"])
        stats.Text = "累计 %d 天 · %d 次互动" % (data["active_days"], data["total"])
        guard["updating"] = True
        feedback_box.Checked = bool(data["feedback"])
        goal_box.Checked = bool(data["goal"])
        guard["updating"] = False
        companion_status.Text = "目标已完成。" if data["completed"] else "慢慢来，不着急。"
        if host.buddy.last_error:
            companion_status.Text = host.buddy.last_error

    def toggle_feedback():
        if guard["updating"]:
            return
        try:
            host.buddy.set_feedback(bool(feedback_box.Checked))
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "反馈设置未保存")
        refresh_companion()

    def toggle_goal():
        if guard["updating"]:
            return
        try:
            host.buddy.set_goal(bool(goal_box.Checked))
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "目标设置未保存")
        refresh_companion()

    feedback_box.CheckedChanged += lambda sender, args: toggle_feedback()
    goal_box.CheckedChanged += lambda sender, args: toggle_goal()
    refresh_companion()

    def resize(sender, args):
        width = max(px(220), form.ClientSize.Width - px(72))
        for panel in (inbox, companion):
            for control in panel.Controls:
                if isinstance(control, Label) or isinstance(control, FlowLayoutPanel):
                    if control is dnd_row:
                        control.Width = width
                    elif control is list_panel or control is action_row:
                        control.Width = width
                    elif isinstance(control, Label):
                        control.Width = width
        for row in list_panel.Controls:
            row.Width = row_width()
            if row.Controls.Count:
                row.Controls[0].Width = max(px(170), row.Width - px(86))

    form.Resize += resize

    timer = Timer()
    timer.Interval = 2000

    def refresh_all():
        rebuild_inbox()
        refresh_companion()

    host._buddy_refresh = refresh_all

    def tick(sender, args):
        refresh_all()

    timer.Tick += tick
    timer.Start()

    _attach(host, key, form, timer)


def open_dnd(host):
    key = "buddy-dnd"
    old = _existing(host, key)
    if old is not None:
        return

    from System.Drawing import Color, Font, Size, ContentAlignment, FontStyle
    from System.Windows.Forms import AutoScaleMode, Button, DockStyle, FlowDirection, FlowLayoutPanel, Form, FormStartPosition, Label, MessageBox, Padding, Screen, Timer

    scale = max(1, float(getattr(host, "dpi_scale", 1)))
    px = lambda value: round(value * scale)
    form = Form()
    form.Text = "临时勿扰 · Agent 桌宠"
    form.AutoScaleMode = getattr(AutoScaleMode, "None")
    form.StartPosition = FormStartPosition.CenterScreen
    area = Screen.FromControl(host.form).WorkingArea
    form.ClientSize = Size(min(px(390), area.Width - 40), min(px(230), area.Height - 70))
    form.Font = Font("Microsoft YaHei UI", 11)
    form.BackColor = Color.FromArgb(248, 247, 241)
    form.TopMost = bool(host.settings.get("alwaysOnTop", True))
    form.ShowInTaskbar = True
    form.MinimizeBox = False
    panel = FlowLayoutPanel()
    panel.Dock = DockStyle.Fill
    panel.FlowDirection = FlowDirection.TopDown
    panel.WrapContents = False
    panel.Padding = Padding(px(16))
    form.Controls.Add(panel)
    status = Label()
    status.AutoSize = False
    status.Width = form.ClientSize.Width - px(48)
    status.Height = px(44)
    status.ForeColor = Color.FromArgb(65, 86, 74)
    panel.Controls.Add(status)
    row = FlowLayoutPanel()
    row.FlowDirection = FlowDirection.LeftToRight
    row.WrapContents = True
    row.AutoSize = True
    row.Width = form.ClientSize.Width - px(48)
    panel.Controls.Add(row)

    def refresh():
        if host.buddy.dnd_active():
            minutes = max(1, (host.buddy.dnd_remaining() + 59) // 60)
            status.Text = "勿扰中，剩余约 %d 分钟。期间只记录，不弹窗、不响铃。" % minutes
        else:
            status.Text = "当前未开启勿扰。到期只汇总一次，不重播旧提醒。"

    def set_minutes(minutes):
        try:
            host.buddy.set_dnd(minutes)
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "勿扰未设置")
        refresh()

    def cancel():
        try:
            host.buddy.cancel_dnd()
        except Exception as exc:  # noqa: BLE001
            MessageBox.Show(form, str(exc), "勿扰未取消")
        refresh()

    for minutes in (15, 30, 60):
        item = Button()
        item.Text = "勿扰 %d 分钟" % minutes
        item.Width = px(100)
        item.Height = max(px(30), form.Font.Height + px(8))
        item.Margin = Padding(0, 0, px(8), px(6))
        item.BackColor = Color.FromArgb(235, 241, 227)
        item.Click += lambda sender, args, value=minutes: set_minutes(value)
        row.Controls.Add(item)
    cancel_button = Button()
    cancel_button.Text = "取消勿扰"
    cancel_button.Width = px(100)
    cancel_button.Height = max(px(30), form.Font.Height + px(8))
    cancel_button.Margin = Padding(0, 0, px(8), px(6))
    cancel_button.BackColor = Color.FromArgb(241, 235, 227)
    cancel_button.Click += lambda sender, args: cancel()
    row.Controls.Add(cancel_button)
    refresh()
    timer = Timer()
    timer.Interval = 15000
    timer.Tick += lambda sender, args: refresh()
    timer.Start()
    _attach(host, key, form, timer)
