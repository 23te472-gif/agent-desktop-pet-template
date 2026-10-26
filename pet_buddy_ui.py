"""Small WinForms panels for the local buddy inbox, DND and interaction goal.

All controls are created/updated on the host UI thread. The module is imported
lazily by run.py so the pure state module stays testable without CLR.
"""
from __future__ import annotations

import time
from pet_agent_reminders import selected_agent,selected_items,selected_unread,validate_scope


_KIND_LABELS = {"done": "完成", "waiting": "待确认", "quota": "额度"}


def _existing(host, key):
    form = host.assistant_panels.get(key)
    if form is not None and not form.IsDisposed:
        refresh = getattr(host, "_pet_panel_refresh", {}).get(key)
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
        if host.assistant_panels.get(key) is form:
            host.assistant_panels.pop(key, None)
            getattr(host, "_pet_panel_refresh", {}).pop(key, None)

    form.FormClosed += closed
    host.form.FormClosed += owner_closed
    host.assistant_panels[key] = form
    from pet_theme import apply_window
    titles = {'inbox': ('提醒收件箱', '任务与额度消息，留在这里慢慢看。'),
              'buddy': ('陪伴', '摸摸头、换个表情，陪你歇一会儿。'),
              'buddy-dnd': ('勿扰', '手动安静与游戏安静，各自生效、各自恢复。')}
    apply_window(host, form, *titles[key])
    form.Show()
    host.register_aux_window(form)
    form.Activate()


def _status_text(host):
    buddy = host.buddy
    lines = ["未读 %d 条" % selected_unread(host)]
    if buddy.error:
        lines.append("提醒历史损坏，原文件已保留：" + buddy.error)
    elif buddy.last_error:
        lines.append(buddy.last_error)
    return "\n".join(lines)


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


def open_panel(host,kind):
    if callable(getattr(host,'create_props',None)):
        from pet_desktop_panels import open_desktop_panel
        try:return open_desktop_panel(host,'companion' if kind=='buddy' else 'inbox')
        except Exception:pass
    return _open_native_panel(host,kind)

def _open_native_panel(host, kind):
    if kind not in ('inbox', 'buddy'):raise ValueError('未知面板')
    key = kind
    if _existing(host, key) is not None:return

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
        Timer,
    )

    scale = max(1, float(getattr(host, "dpi_scale", 1)))
    px = lambda value: round(value * scale)
    form = Form()
    form.Text = ("陪伴" if kind == "buddy" else "提醒收件箱") + " · Agent 桌宠"
    form.AutoScaleMode = getattr(AutoScaleMode, "None")
    form.StartPosition = FormStartPosition.CenterScreen
    area = Screen.FromControl(host.form).WorkingArea
    form.ClientSize = Size(min(px(560), area.Width - 40), min(px(450 if kind == "buddy" else 620), area.Height - 70))
    form.MinimumSize = Size(min(px(420), area.Width - 40), min(px(360), area.Height - 70))
    form.Font = Font("Microsoft YaHei UI", 11)
    form.BackColor = Color.FromArgb(248, 247, 241)
    form.TopMost = bool(host.settings.get("alwaysOnTop", True))
    form.ShowInTaskbar = True
    form.MinimizeBox = False

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

    if kind == 'inbox':
        inbox = page_panel(form)
        status = add_label(inbox, "", 56)
        def refresh_status():status.Text = _status_text(host)
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
                host.buddy.mark_read(item_id,agent=validate_scope(host,dict(agent=rendered["agent"])))
            except Exception as exc:  # noqa: BLE001
                MessageBox.Show(form, str(exc), "已读状态未保存")
            rebuild_inbox()

        def mark_all():
            try:
                host.buddy.mark_all_read(agent=validate_scope(host,dict(agent=rendered["agent"])))
            except Exception as exc:  # noqa: BLE001
                MessageBox.Show(form, str(exc), "已读状态未保存")
            rebuild_inbox()

        def clear_history():
            agent=rendered["agent"]
            try:validate_scope(host,dict(agent=agent))
            except ValueError:
                rebuild_inbox();return
            if MessageBox.Show(form, "清空当前 Agent 的提醒历史？其他 Agent 的消息将保留。", "清空提醒收件箱",
                               MessageBoxButtons.YesNo) != DialogResult.Yes:
                return
            try:
                validate_scope(host,dict(agent=agent))
                host.buddy.clear_inbox(agent=agent)
            except Exception as exc:  # noqa: BLE001
                MessageBox.Show(form, str(exc), "历史未清空")
            rebuild_inbox()

        add_button(action_row, "全部已读", mark_all, 96)
        add_button(action_row, "清空历史", clear_history, 96)
        add_button(action_row, "通知设置…", lambda: host.open_assistant_panel("reminders"), 112)

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

        rendered = {"items": None,"agent":selected_agent(host)}
        def rebuild_inbox():
            agent=selected_agent(host)
            items = selected_items(host,agent=agent)
            if items != rendered["items"] or agent!=rendered["agent"]:
                rendered["items"] = items
                rendered["agent"] = agent
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

    else:
        companion = page_panel(form)
        progress = add_label(companion, "", 46)
        progress.Font = Font("Microsoft YaHei UI", 18, FontStyle.Bold)
        stats = add_label(companion, "", 34)
        hint = add_label(companion, "每 60 秒最多计 1 次，每天最多 3 次；没有后台在线奖励。", 40)
        feedback_box = CheckBox()
        feedback_box.Text = "互动时显示短句"
        feedback_box.AutoSize = True
        feedback_box.Margin = Padding(0, 0, 0, px(8))
        companion.Controls.Add(feedback_box)
        goal_box = CheckBox()
        goal_box.Text = "开启每日小目标"
        goal_box.AutoSize = True
        goal_box.Margin = Padding(0, 0, 0, px(8))
        companion.Controls.Add(goal_box)
        action_row = FlowLayoutPanel()
        action_row.FlowDirection = FlowDirection.LeftToRight
        action_row.WrapContents = True
        action_row.AutoSize = True
        action_row.Width = max(px(220), form.ClientSize.Width - px(72))
        companion.Controls.Add(action_row)
        add_button(action_row, '摸摸头', lambda: host.user_interaction('pat'), 96)
        add_button(action_row, '换个表情', lambda: host.post({'t': 'cycle-expression'}), 96)
        add_button(action_row, '随机动作', lambda: host.post({'t': 'react', 'kind': 'motion'}), 96)
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
        panel = inbox if kind == 'inbox' else companion
        for control in panel.Controls:
            if isinstance(control, (Label, FlowLayoutPanel)):control.Width = width
        if kind == 'inbox':
            for row in list_panel.Controls:
                row.Width = row_width()
                if row.Controls.Count:row.Controls[0].Width = max(px(170), row.Width - px(86))
    form.Resize += resize
    timer = Timer()
    timer.Interval = 2000
    refresh_all = rebuild_inbox if kind == 'inbox' else refresh_companion
    if not hasattr(host, '_pet_panel_refresh'):host._pet_panel_refresh = {}
    host._pet_panel_refresh[key] = refresh_all
    timer.Tick += lambda sender, args: refresh_all()
    timer.Start()
    _attach(host, key, form, timer)


def open_dnd(host):
    if callable(getattr(host,'create_props',None)):
        from pet_desktop_panels import open_desktop_panel
        try:return open_desktop_panel(host,'dnd')
        except Exception:pass
    return _open_native_dnd(host)

def _open_native_dnd(host):
    key = 'buddy-dnd'
    if _existing(host, key) is not None:return
    from System.Windows.Forms import CheckBox, FolderBrowserDialog, DialogResult, MessageBox, Timer
    from pet_companion_ui import _settings
    from pet_quiet import steam_roots
    form, add, label, button = _settings(host, '勿扰', 540)
    status = label('', 96)
    label('手动勿扰', 28)
    def refresh():
        remaining = host.buddy.dnd_remaining()
        if host.buddy.dnd_active():
            manual = '直到手动关闭' if remaining is None else '剩余约 %d 分钟' % max(1, (remaining + 59) // 60)
        else:manual = '未开启'
        game = '正在安静' if host.quiet_state.active else ('已开启自动识别' if host.companion_config['quietEnabled'] else '未开启')
        status.Text = '手动勿扰：' + manual + '\n游戏安静：' + game + '\n暂停通知和声音；你主动互动时仍可回应。'
    def set_minutes(minutes):
        try:host.buddy.set_dnd(minutes)
        except (OSError, ValueError) as exc:MessageBox.Show(form, str(exc), '勿扰未设置')
        refresh()
    def cancel():
        try:
            host.buddy.cancel_dnd()
            host.on_buddy_timer()
        except (OSError, ValueError) as exc:MessageBox.Show(form, str(exc), '勿扰未取消')
        refresh()
    # Compact rows wrap naturally at larger text scales.
    from System.Windows.Forms import FlowLayoutPanel, FlowDirection, Button, Padding
    scale = max(1, float(getattr(host, 'dpi_scale', 1)))
    px = lambda n:round(n * scale)
    row = FlowLayoutPanel();row.FlowDirection = FlowDirection.LeftToRight
    row.WrapContents = True;row.AutoSize = True;add(row, 88)
    for text, action in [('15 分钟', lambda:set_minutes(15)), ('30 分钟', lambda:set_minutes(30)),
                         ('60 分钟', lambda:set_minutes(60)), ('直到手动关闭', lambda:set_minutes(None)),
                         ('结束手动勿扰', cancel)]:
        item = Button();item.Text = text;item.Width = px(126);item.Height = px(36)
        item.Margin = Padding(0, 0, px(8), px(6));item.Click += lambda sender, args, fn=action:fn()
        row.Controls.Add(item)
    label('游戏自动安静', 28)
    quiet = CheckBox();quiet.Text = '全屏游戏时隐藏桌宠并暂停动画'
    quiet.Checked = bool(host.companion_config['quietEnabled']);add(quiet, 40)
    extra = list(host.companion_config['gameRoots'])
    roots = label('自动识别 Steam 游戏库；额外目录 %d 个。' % len(extra), 40)
    def folder():
        dialog = FolderBrowserDialog()
        try:
            if dialog.ShowDialog(form) == DialogResult.OK and dialog.SelectedPath not in extra:
                extra.append(str(dialog.SelectedPath))
                roots.Text = '额外目录 %d 个，保存后生效。' % len(extra)
        finally:dialog.Dispose()
    button('添加其他游戏目录…', folder)
    def save():
        try:
            clean = host.companion_store.save(dict(host.companion_config, quietEnabled=bool(quiet.Checked), gameRoots=list(extra)))
            host.companion_config = clean;host.metric_service.config = clean
            host.game_detector.roots = steam_roots(clean['gameRoots'])
            host.update_game_quiet();refresh()
            roots.Text = '已保存。游戏结束恢复显示，手动勿扰保持原状态。'
        except (OSError, ValueError) as exc:MessageBox.Show(form, str(exc), '游戏设置未保存')
    button('保存游戏设置', save)
    label('安静结束后只汇总一次未读数量，不补播旧提醒。', 42)
    refresh()
    if not hasattr(host, '_pet_panel_refresh'):host._pet_panel_refresh = {}
    host._pet_panel_refresh[key] = refresh
    timer = Timer();timer.Interval = 2000;timer.Tick += lambda sender, args:refresh();timer.Start()
    _attach(host, key, form, timer)
