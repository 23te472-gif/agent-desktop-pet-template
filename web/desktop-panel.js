(function () {
  "use strict";

  var VIEWS = ["reminder", "inbox", "dnd", "companion"];
  var bridge = window.chrome && window.chrome.webview ? window.chrome.webview : null;
  var state = {
    connected: false,
    readySent: false,
    booted: false,
    hasState: false,
    view: "reminder",
    agent: "codex",
    latestServerSettings: null,
    dirty: false,
    savePending: false,
    pendingSave: null
  };
  var savedTimer = 0;
  var selectedMinutes = 30;
  var resizeDrag = null;

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }
  function $$(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }
  function asInt(value, fallback) {
    var number = Number(value);
    return isFinite(number) ? Math.max(0, Math.trunc(number)) : fallback;
  }
  function isRecord(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }
  function pad2(value) {
    return value < 10 ? "0" + value : String(value);
  }
  function formatStamp(value) {
    var number = Number(value);
    if (!isFinite(number) || number <= 0) return "--";
    var date = new Date(number * 1000);
    if (isNaN(date.getTime())) return "--";
    return pad2(date.getMonth() + 1) + "-" + pad2(date.getDate()) + " " + pad2(date.getHours()) + ":" + pad2(date.getMinutes());
  }
  function formatRemaining(value) {
    var seconds = asInt(value, 0);
    var hours = Math.floor(seconds / 3600);
    var minutes = Math.floor((seconds % 3600) / 60);
    var rest = seconds % 60;
    if (hours > 0) return hours + " 小时 " + pad2(minutes) + " 分";
    if (minutes > 0) return minutes + " 分 " + pad2(rest) + " 秒";
    return rest + " 秒";
  }
  function kindLabel(kind) {
    return { done: "完成", waiting: "待确认", quota: "额度" }[kind] || "提醒";
  }
  function itemTitle(item) {
    return String((item && item.title) || "任务标题已隐藏");
  }

  var panelHeader = $("#panelHeader");
  var appKicker = $(".app-kicker");
  var closePanel = $("#closePanel");
  var tabBar = $("#tabBar");
  var tabs = $$(".tab");
  var panelMain = $("#panelMain");
  var views = {
    reminder: $("#view-reminder"),
    inbox: $("#view-inbox"),
    dnd: $("#view-dnd"),
    companion: $("#view-companion")
  };
  var connectionState = $("#connectionState");
  var connectionTitle = $("#connectionTitle");
  var connectionDetail = $("#connectionDetail");
  var statusLine = $("#statusLine");
  var saveButton = $("#saveButton");
  var stateError = $("#stateError");
  var tabUnread = $("#tabUnread");
  var reminderUnread = $("#reminderUnread");
  var recentList = $("#recentList");
  var recentEmpty = $("#recentEmpty");
  var viewInboxButton = $("#viewInbox");
  var testButton = $("#testButton");
  var inboxList = $("#inboxList");
  var inboxEmpty = $("#inboxEmpty");
  var inboxSummary = $("#inboxSummary");
  var readAllButton = $("#readAllButton");
  var clearButton = $("#clearButton");
  var dndCard = $("#dndCard");
  var dndStateText = $("#dndState");
  var dndDetail = $("#dndDetail");
  var dndPill = $("#dndPill");
  var dndSwitch = $("#dndSwitch");
  var gameSwitch = $("#gameSwitch");
  var gameActiveChip = $("#gameActiveChip");
  var rootsText = $("#rootsText");
  var folderButton = $("#folderButton");
  var durationPicker = $("#durationPicker");
  var minuteWheel = $("#minuteWheel");
  var minuteValue = $("#minuteValue");
  var minuteGhosts = $$(".minute-ghost");
  var minutePlus = $("#minutePlus");
  var minuteMinus = $("#minuteMinus");
  var dndStartButton = $("#dndStartButton");
  var minuteAnnounce = $("#minuteAnnounce");
  var feedbackSwitch = $("#feedbackSwitch");
  var goalSwitch = $("#goalSwitch");
  var goalCount = $("#goalCount");
  var goalProgress = $("#goalProgress");
  var goalNote = $("#goalNote");
  var interactionStats = $("#interactionStats");
  var goalCard = $(".goal-card");
  var affinityValue = $("#affinityValue");
  var affinityMax = $("#affinityMax");
  var affinityProgress = $("#affinityProgress");
  var petButtons = $$(".pet-action");
  var recentTemplate = $("#recentTemplate");
  var inboxTemplate = $("#inboxTemplate");
  var resizeLayer = $("#resizeLayer");
  var resizeEdges = $$(".resize-edge");
  var reminderSwitches = [$("#switchDone"), $("#switchWaiting"), $("#switchSound"), $("#switchShowTitle")];

  function controlsReady() {
    return state.connected && state.hasState;
  }

  function clampMinutes(value) {
    var number = Number(value);
    if (!isFinite(number)) return selectedMinutes;
    return Math.max(1, Math.min(60, Math.trunc(number)));
  }

  function updateMinutePicker(announce) {
    var minutes = clampMinutes(selectedMinutes);
    selectedMinutes = minutes;
    minuteValue.textContent = String(minutes);
    minuteWheel.setAttribute("aria-valuenow", String(minutes));
    minuteWheel.setAttribute("aria-valuetext", minutes + " 分钟");
    dndStartButton.setAttribute("aria-label", "开始安静，" + minutes + " 分钟");
    minuteGhosts.forEach(function (ghost) {
      var step = Number(ghost.getAttribute("data-step"));
      var value = minutes + step;
      var visible = value >= 1 && value <= 60;
      ghost.textContent = visible ? String(value) : "";
      ghost.classList.toggle("is-empty", !visible);
    });
    var ready = controlsReady();
    minutePlus.disabled = !ready || minutes >= 60;
    minuteMinus.disabled = !ready || minutes <= 1;
    if (announce) minuteAnnounce.textContent = "已选择 " + minutes + " 分钟。";
  }

  function setSelectedMinutes(value, announce) {
    var next = clampMinutes(value);
    var changed = next !== selectedMinutes;
    selectedMinutes = next;
    updateMinutePicker(Boolean(announce && changed));
  }

  function submitDndSelection() {
    if (!controlsReady()) return;
    updateMinutePicker(false);
    setStatus("正在开始 " + selectedMinutes + " 分钟安静…", "info");
    post({ action: "dnd", minutes: selectedMinutes });
  }

  function updateAffinity(interaction) {
    var data = isRecord(interaction) ? interaction : {};
    var affinity = Number(data.affinity);
    var maximum = Number(data.affinity_max);
    var valid = Number.isInteger(affinity) && Number.isInteger(maximum)
      && affinity >= 0 && maximum > 0 && affinity <= maximum;
    if (!valid) {
      affinityValue.textContent = "—";
      affinityMax.textContent = "—";
      affinityProgress.hidden = true;
      affinityProgress.removeAttribute("aria-valuetext");
      return;
    }
    affinityValue.textContent = String(affinity);
    affinityMax.textContent = String(maximum);
    affinityProgress.max = maximum;
    affinityProgress.value = affinity;
    affinityProgress.setAttribute("aria-valuetext", affinity + " / " + maximum);
    affinityProgress.hidden = false;
  }

  function sendResizeMove(drag) {
    if (!drag) return;
    if (drag.lastDx === drag.sentDx && drag.lastDy === drag.sentDy) return;
    drag.sentDx = drag.lastDx;
    drag.sentDy = drag.lastDy;
    post({ action: "resize", phase: "move", dx: drag.lastDx, dy: drag.lastDy });
  }

  function scheduleResizeMove(drag) {
    if (!drag || drag.frame) return;
    drag.frame = window.requestAnimationFrame(function () {
      if (resizeDrag !== drag) return;
      drag.frame = 0;
      sendResizeMove(drag);
    });
  }

  function handleResizeMove(event) {
    var drag = resizeDrag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    drag.lastDx = (event.screenX - drag.startX) * drag.dpr;
    drag.lastDy = (event.screenY - drag.startY) * drag.dpr;
    scheduleResizeMove(drag);
  }

  function releaseResizeCapture(drag) {
    if (!drag) return;
    try {
      if (drag.edge.hasPointerCapture && drag.edge.hasPointerCapture(drag.pointerId)) {
        drag.edge.releasePointerCapture(drag.pointerId);
      }
    } catch (error) {
      // Capture may already be gone after a cancel or a lost-capture event.
    }
  }

  function finishResizeDrag(event) {
    var drag = resizeDrag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    event.preventDefault();
    event.stopPropagation();
    if (drag.frame) {
      window.cancelAnimationFrame(drag.frame);
      drag.frame = 0;
    }
    // Flush the last coalesced displacement before ending the native resize.
    sendResizeMove(drag);
    post({ action: "resize", phase: "end" });
    resizeDrag = null;
    // Nulling first makes the automatic lostpointercapture event a no-op.
    releaseResizeCapture(drag);
  }

  function beginResize(event, edge) {
    if (event.button !== 0 || !state.connected || resizeDrag) return;
    event.preventDefault();
    event.stopPropagation();
    var dpr = Number(window.devicePixelRatio);
    if (!isFinite(dpr) || dpr <= 0) dpr = 1;
    var drag = {
      pointerId: event.pointerId,
      edge: edge,
      startX: event.screenX,
      startY: event.screenY,
      dpr: dpr,
      lastDx: 0,
      lastDy: 0,
      sentDx: 0,
      sentDy: 0,
      frame: 0
    };
    try {
      edge.setPointerCapture(event.pointerId);
    } catch (error) {
      setStatus("无法开始调整窗口大小。", "error");
      return;
    }
    resizeDrag = drag;
    if (!post({ action: "resize", phase: "start", edge: edge.getAttribute("data-resize-edge") })) {
      resizeDrag = null;
      releaseResizeCapture(drag);
    }
  }

  function setStatus(text, kind) {
    var value = String(text || "").trim() || "操作未完成。";
    statusLine.textContent = value;
    statusLine.className = "footer-status" + (kind ? " status--" + kind : "");
    statusLine.title = value;
  }

  function setStateError(text) {
    var value = String(text || "").trim();
    if (value) {
      stateError.textContent = value;
      stateError.hidden = false;
    } else {
      stateError.textContent = "";
      stateError.hidden = true;
    }
  }

  function post(message) {
    if (!bridge || typeof bridge.postMessage !== "function") {
      setStatus("未连接桌宠，无法执行操作。", "error");
      return false;
    }
    try {
      bridge.postMessage(message);
      return true;
    } catch (error) {
      setStatus("消息发送失败：" + String(error && error.message ? error.message : error), "error");
      return false;
    }
  }

  function showDisconnected(title, detail) {
    state.connected = false;
    connectionState.hidden = false;
    tabBar.hidden = true;
    panelMain.hidden = true;
    resizeLayer.hidden = true;
    saveButton.hidden = true;
    closePanel.disabled = true;
    minuteWheel.tabIndex = -1;
    minuteWheel.setAttribute("aria-disabled", "true");
    connectionTitle.textContent = title || "未连接桌宠";
    connectionDetail.textContent = detail || "请从桌宠内重新打开这个面板；浏览器直接打开时不会读取或保存本机数据。";
    setStatus("未连接桌宠。", "error");
  }

  function showConnectedOnce() {
    if (state.hasState) return false;
    state.hasState = true;
    connectionState.hidden = true;
    tabBar.hidden = false;
    panelMain.hidden = false;
    $$("[data-needs-state]").forEach(function (element) { element.disabled = false; });
    minuteWheel.tabIndex = 0;
    minuteWheel.setAttribute("aria-disabled", "false");
    updateMinutePicker(false);
    closePanel.disabled = false;
    return true;
  }

  function normalizeView(view) {
    return VIEWS.indexOf(view) >= 0 ? view : null;
  }

  function selectView(view, notifyHost) {
    var next = normalizeView(view);
    if (!next) return;
    var changed = state.view !== next;
    state.view = next;
    tabs.forEach(function (tab) {
      var selected = tab.getAttribute("data-view") === next;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    VIEWS.forEach(function (name) {
      views[name].hidden = name !== next;
    });
    if (changed) panelMain.scrollTop = 0;
    saveButton.hidden = !(state.hasState && next === "reminder");
    updateSaveButton();
    if (notifyHost && state.connected) post({ action: "view", view: next });
  }

  function clearSavedFeedback() {
    if (savedTimer) {
      window.clearTimeout(savedTimer);
      savedTimer = 0;
    }
    saveButton.classList.remove("is-saved");
  }

  function updateSaveButton() {
    var visible = state.hasState && state.view === "reminder";
    saveButton.hidden = !visible;
    saveButton.disabled = !visible || !state.connected || state.savePending || !state.dirty;
    if (state.savePending) {
      saveButton.textContent = "正在保存…";
    } else if (!savedTimer) {
      saveButton.textContent = "保存设置";
    }
  }

  function readSettings(raw) {
    if (!isRecord(raw)) return null;
    var keys = ["done", "waiting", "sound", "showTitle"];
    for (var index = 0; index < keys.length; index += 1) {
      if (typeof raw[keys[index]] !== "boolean") return null;
    }
    return { done: raw.done, waiting: raw.waiting, sound: raw.sound, showTitle: raw.showTitle };
  }

  function applySettings(settings) {
    if (!settings) return;
    var mapping = {
      done: $("#switchDone"),
      waiting: $("#switchWaiting"),
      sound: $("#switchSound"),
      showTitle: $("#switchShowTitle")
    };
    Object.keys(mapping).forEach(function (key) {
      mapping[key].setAttribute("aria-checked", String(Boolean(settings[key])));
    });
  }

  function collectSettings() {
    return {
      done: $("#switchDone").getAttribute("aria-checked") === "true",
      waiting: $("#switchWaiting").getAttribute("aria-checked") === "true",
      sound: $("#switchSound").getAttribute("aria-checked") === "true",
      showTitle: $("#switchShowTitle").getAttribute("aria-checked") === "true"
    };
  }

  function settingsEqual(first, second) {
    return Boolean(first && second && first.done === second.done && first.waiting === second.waiting && first.sound === second.sound && first.showTitle === second.showTitle);
  }

  function setReminderBusy(busy) {
    state.savePending = Boolean(busy);
    reminderSwitches.forEach(function (button) {
      button.disabled = Boolean(busy) || !state.hasState;
    });
    updateSaveButton();
  }

  function refreshDirty() {
    if (state.savePending) return;
    var draft = collectSettings();
    state.dirty = !settingsEqual(draft, state.latestServerSettings);
    updateSaveButton();
    if (state.dirty) {
      setStatus("有未保存的提醒设置。", "dirty");
    } else {
      setStatus("提醒设置已与桌宠一致。", "info");
    }
  }

  function bindEvents() {
    closePanel.addEventListener("click", function () {
      if (state.connected) post({ action: "close" });
    });

    panelHeader.addEventListener("pointerdown", function (event) {
      if (event.button !== 0 || !state.connected) return;
      if (event.target.closest("button, input, a, select, textarea, label")) return;
      event.preventDefault();
      post({ action: "drag" });
    });

    resizeEdges.forEach(function (edge) {
      edge.addEventListener("pointerdown", function (event) {
        beginResize(event, edge);
      });
    });
    window.addEventListener("pointermove", handleResizeMove, true);
    window.addEventListener("pointerup", finishResizeDrag, true);
    window.addEventListener("pointercancel", finishResizeDrag, true);
    window.addEventListener("lostpointercapture", finishResizeDrag, true);

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && state.connected) {
        event.preventDefault();
        post({ action: "close" });
      }
    });

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        selectView(tab.getAttribute("data-view"), true);
      });
    });
    tabBar.addEventListener("keydown", function (event) {
      var keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
      if (keys.indexOf(event.key) < 0) return;
      var index = tabs.indexOf(document.activeElement);
      if (index < 0) return;
      var next = index;
      if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = tabs.length - 1;
      event.preventDefault();
      selectView(tabs[next].getAttribute("data-view"), true);
      tabs[next].focus();
    });

    reminderSwitches.forEach(function (button) {
      button.addEventListener("click", function () {
        if (state.savePending) return;
        button.setAttribute("aria-checked", String(button.getAttribute("aria-checked") !== "true"));
        clearSavedFeedback();
        refreshDirty();
      });
    });

    saveButton.addEventListener("click", function () {
      if (!state.hasState || state.view !== "reminder" || !state.dirty || state.savePending || !state.connected) return;
      var settings = collectSettings();
      clearSavedFeedback();
      state.pendingSave = settings;
      setReminderBusy(true);
      setStatus("正在保存提醒设置…", "info");
      if (!post({ action: "save", settings: settings })) {
        state.pendingSave = null;
        setReminderBusy(false);
        setStatus("保存请求未能发送，草稿已保留。", "error");
      }
    });

    testButton.addEventListener("click", function () {
      setStatus("正在生成本机测试提醒…", "info");
      post({ action: "test" });
    });
    viewInboxButton.addEventListener("click", function () {
      selectView("inbox", true);
    });
    readAllButton.addEventListener("click", function () {
      setStatus("正在标记全部已读…", "info");
      post({ action: "read-all", agent: state.agent });
    });
    clearButton.addEventListener("click", function () {
      setStatus("等待本机确认清空提醒…", "info");
      post({ action: "clear", agent: state.agent });
    });
    inboxList.addEventListener("click", function (event) {
      var button = event.target.closest("button[data-read-id]");
      if (!button) return;
      setStatus("正在标记这条提醒为已读…", "info");
      post({ action: "read", id: button.getAttribute("data-read-id"), agent: state.agent });
    });

    dndSwitch.addEventListener("click", function () {
      if (dndSwitch.getAttribute("aria-checked") === "true") {
        setStatus("正在取消勿扰…", "info");
        post({ action: "cancel-dnd" });
      } else {
        submitDndSelection();
      }
    });
    minuteGhosts.forEach(function (ghost) {
      ghost.addEventListener("click", function () {
        if (!controlsReady()) return;
        var step = Number(ghost.getAttribute("data-step"));
        if (!isFinite(step) || step === 0) return;
        minuteWheel.focus();
        setSelectedMinutes(selectedMinutes + step, true);
      });
    });
    minuteWheel.addEventListener("pointerdown", function () {
      if (controlsReady()) minuteWheel.focus();
    });
    minuteWheel.addEventListener("keydown", function (event) {
      if (!controlsReady()) return;
      var next = selectedMinutes;
      if (event.key === "ArrowUp") next += 1;
      else if (event.key === "ArrowDown") next -= 1;
      else if (event.key === "Home") next = 1;
      else if (event.key === "End") next = 60;
      else return;
      event.preventDefault();
      event.stopPropagation();
      setSelectedMinutes(next, true);
    });
    minutePlus.addEventListener("click", function () {
      if (controlsReady()) setSelectedMinutes(selectedMinutes + 1, true);
    });
    minuteMinus.addEventListener("click", function () {
      if (controlsReady()) setSelectedMinutes(selectedMinutes - 1, true);
    });
    dndStartButton.addEventListener("click", submitDndSelection);
    durationPicker.addEventListener("wheel", function (event) {
      if (!controlsReady()) return;
      event.preventDefault();
      event.stopPropagation();
      var delta = Number(event.deltaY);
      if (!isFinite(delta) || delta === 0) return;
      setSelectedMinutes(selectedMinutes + (delta < 0 ? 1 : -1), true);
    }, { passive: false });
    gameSwitch.addEventListener("click", function () {
      var enabled = gameSwitch.getAttribute("aria-checked") !== "true";
      setStatus("正在更新游戏自动安静…", "info");
      post({ action: "game", enabled: enabled });
    });
    folderButton.addEventListener("click", function () {
      setStatus("请选择要添加的游戏目录…", "info");
      post({ action: "folder" });
    });

    petButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        setStatus("正在把互动交给桌宠…", "info");
        post({ action: "pet", kind: button.getAttribute("data-pet") });
      });
    });
    feedbackSwitch.addEventListener("click", function () {
      var enabled = feedbackSwitch.getAttribute("aria-checked") !== "true";
      setStatus("正在保存互动短句设置…", "info");
      post({ action: "feedback", enabled: enabled });
    });
    goalSwitch.addEventListener("click", function () {
      var enabled = goalSwitch.getAttribute("aria-checked") !== "true";
      setStatus("正在保存每日小目标设置…", "info");
      post({ action: "goal", enabled: enabled });
    });
  }

  function renderRecent(inbox) {
    var items = inbox.slice().reverse().slice(0, 3);
    recentList.textContent = "";
    recentEmpty.hidden = items.length > 0;
    items.forEach(function (item) {
      var node = recentTemplate.content.firstElementChild.cloneNode(true);
      var dot = node.querySelector(".recent-dot");
      dot.setAttribute("data-read", String(Boolean(item.read)));
      node.querySelector(".recent-title").textContent = itemTitle(item);
      node.querySelector(".recent-meta").textContent = kindLabel(item.kind) + (item.read ? " · 已读" : " · 未读");
      node.querySelector(".recent-time").textContent = formatStamp(item.at);
      recentList.appendChild(node);
    });
  }

  var renderedInboxSignature = null;
  function renderInbox(inbox, unread) {
    // DND countdown updates do not change the inbox. Keep its action nodes so
    // periodic state messages cannot steal focus or interrupt an in-flight click.
    var signature = JSON.stringify([inbox, unread]);
    if (signature === renderedInboxSignature) return;
    renderedInboxSignature = signature;
    inboxList.textContent = "";
    inboxEmpty.hidden = inbox.length > 0;
    var items = inbox.slice().reverse();
    items.forEach(function (item) {
      var node = inboxTemplate.content.firstElementChild.cloneNode(true);
      var read = Boolean(item.read);
      node.classList.toggle("is-read", read);
      node.querySelector(".kind-chip").textContent = kindLabel(item.kind);
      node.querySelector(".inbox-time").textContent = formatStamp(item.at);
      node.querySelector(".inbox-title").textContent = itemTitle(item);
      node.querySelector(".read-chip").hidden = !read;
      var readButton = node.querySelector(".mini-action");
      readButton.hidden = read;
      if (!read) {
        readButton.setAttribute("data-read-id", String(item.id));
        readButton.setAttribute("aria-label", "标为已读：" + itemTitle(item));
      }
      inboxList.appendChild(node);
    });

    var maxBadge = unread > 99 ? "99+" : String(unread);
    tabUnread.textContent = maxBadge;
    tabUnread.hidden = unread <= 0;
    reminderUnread.textContent = unread > 0 ? unread + " 条未读" : "";
    reminderUnread.hidden = unread <= 0;
    inboxSummary.textContent = inbox.length ? (unread > 0 ? unread + " 条未读 · 共 " + inbox.length + " 条" : "全部已读 · 共 " + inbox.length + " 条") : "本机提醒会保存在这里";
    readAllButton.disabled = !state.hasState || unread <= 0;
    clearButton.disabled = !state.hasState || inbox.length <= 0;
  }

  function renderDnd(data) {
    var on = data.dnd === true;
    var remaining = data.remaining;
    var infinite = on && remaining === null;
    dndSwitch.setAttribute("aria-checked", String(on));
    dndCard.classList.toggle("is-on", on);
    dndPill.setAttribute("data-on", String(on));
    dndPill.textContent = on ? "安静中" : "未开启";
    dndStateText.textContent = on ? "安静中" : "未开启";
    if (on) {
      dndDetail.textContent = infinite ? "会保持到手动关闭。" : "剩余 " + formatRemaining(remaining) + "。";
    } else {
      dndDetail.textContent = "手动勿扰未开启。";
    }

    // The minute wheel is a local choice for the next start. Incoming
    // countdown states must never reset a value the user is scrolling.

    var game = data.game === true;
    gameSwitch.setAttribute("aria-checked", String(game));
    var gameActive = data.gameActive === true;
    gameActiveChip.hidden = !gameActive;
    var roots = asInt(data.roots, 0);
    rootsText.textContent = roots > 0 ? "已添加 " + roots + " 个游戏目录" : "尚未添加额外游戏目录";
  }

  function renderCompanion(interaction) {
    var data = isRecord(interaction) ? interaction : {};
    var target = asInt(data.target, 0);
    var today = asInt(data.today, 0);
    var total = asInt(data.total, 0);
    var activeDays = asInt(data.active_days, 0);
    var goalEnabled = data.goal === true;
    var completed = data.completed === true;
    goalCount.textContent = target > 0 ? today + " / " + target : "— / —";
    goalProgress.hidden = target <= 0;
    if (target > 0) {
      goalProgress.max = target;
      goalProgress.value = Math.min(today, target);
    }
    goalCard.classList.toggle("is-goal-off", !goalEnabled);
    if (!goalEnabled) {
      goalNote.textContent = "每日小目标当前关闭。";
    } else if (completed) {
      goalNote.textContent = "今天的小目标完成。";
    } else if (target > 0) {
      goalNote.textContent = "一点点来，今天还差 " + Math.max(0, target - today) + " 次互动。";
    } else {
      goalNote.textContent = "等待桌宠同步每日目标。";
    }
    interactionStats.textContent = "累计 " + activeDays + " 天 · " + total + " 次互动";
    feedbackSwitch.setAttribute("aria-checked", String(data.feedback === true));
    goalSwitch.setAttribute("aria-checked", String(goalEnabled));
    updateAffinity(data);
  }

  function applyState(message) {
    var data = message && message.data;
    if (!isRecord(data)) {
      setStatus("收到的状态数据不完整。", "error");
      return;
    }
    document.documentElement.dataset.settingsTheme = data.settingsTheme === "ice" ? "ice" : "paper";
    var rawAgent = data.agent;
    var hasValidAgent = typeof rawAgent === "string" && /^[a-z0-9_-]{1,40}$/.test(rawAgent);
    var agent = hasValidAgent ? rawAgent : "codex";
    var rawName = typeof data.agentName === "string" ? data.agentName.trim().replace(/\s+/g, " ") : "";
    var agentName = hasValidAgent && rawName ? rawName.slice(0, 80) : "";
    if (!agentName) agentName = agent === "codex" ? "Codex" : agent;
    state.agent = agent;
    if (appKicker) appKicker.textContent = "轻桌宠 · " + agentName;
    var first = showConnectedOnce();
    var incomingView = normalizeView(message.view);
    if (incomingView) selectView(incomingView, false);

    var settings = readSettings(data.settings);
    if (settings) {
      state.latestServerSettings = settings;
      if (!state.dirty && !state.savePending) applySettings(settings);
    } else {
      setStateError("提醒设置数据不完整，已保留当前显示。");
    }

    var inbox = Array.isArray(data.inbox) ? data.inbox.filter(isRecord).slice(0, 100) : [];
    var unread = asInt(data.unread, inbox.filter(function (item) { return !item.read; }).length);
    renderRecent(inbox);
    renderInbox(inbox, unread);
    renderDnd(data);
    renderCompanion(data.interaction);
    setStateError(typeof data.error === "string" ? data.error : "");
    updateSaveButton();

    if (first) {
      setStatus("已连接桌宠，状态已同步。", "info");
    }
  }

  function applyResult(message) {
    var action = String(message.action || "");
    var ok = message.ok === true;
    var text = String(message.text || "").trim();
    if (!text) text = ok ? "操作已完成。" : "操作未完成。";

    if (action === "save") {
      var submitted = state.pendingSave;
      state.pendingSave = null;
      setReminderBusy(false);
      if (ok) {
        state.dirty = false;
        if (submitted) {
          applySettings(submitted);
          state.latestServerSettings = submitted;
        }
        clearSavedFeedback();
        saveButton.classList.add("is-saved");
        saveButton.textContent = "已保存";
        savedTimer = window.setTimeout(function () {
          savedTimer = 0;
          saveButton.classList.remove("is-saved");
          updateSaveButton();
        }, 1400);
        setStatus(text, "ok");
      } else {
        clearSavedFeedback();
        setStatus(text + " 草稿已保留。", "error");
      }
      updateSaveButton();
      return;
    }

    setStatus(text, ok ? "ok" : "error");
    if (action === "pet" && ok) {
      $("#petLine").textContent = "互动已发送，进度以桌宠同步为准。";
    }
  }

  function handleBridgeMessage(event) {
    var message = event && event.data;
    if (typeof message === "string") {
      try { message = JSON.parse(message); } catch (error) { return; }
    }
    if (!isRecord(message)) return;
    if (message.t === "state") applyState(message);
    else if (message.t === "result") applyResult(message);
  }

  function initBridge() {
    if (!bridge || typeof bridge.postMessage !== "function" || typeof bridge.addEventListener !== "function") {
      showDisconnected("未连接桌宠", "请从桌宠内重新打开这个面板；浏览器直接打开时不会读取或保存本机数据。");
      return;
    }
    bridge.addEventListener("message", handleBridgeMessage);
    state.connected = true;
    resizeLayer.hidden = false;
    closePanel.disabled = false;
    connectionTitle.textContent = "正在等待桌宠状态…";
    connectionDetail.textContent = "连接已建立，正在同步本机提醒、勿扰和陪伴数据。";
    setStatus("正在等待桌宠状态…", "info");
    if (post({ action: "ready" })) state.readySent = true;
  }

  function cssReady() {
    try {
      return window.getComputedStyle(document.documentElement).getPropertyValue("--desktop-panel-ready").trim() === "ready";
    } catch (error) {
      return false;
    }
  }

  function boot() {
    if (state.booted || !cssReady()) return;
    state.booted = true;
    bindEvents();
    initBridge();
  }

  function start() {
    var stylesheet = document.getElementById("panelStyles");
    if (stylesheet) {
      stylesheet.addEventListener("load", function () {
        if (cssReady()) boot();
      });
      stylesheet.addEventListener("error", function () {
        state.booted = true;
        showDisconnected("界面样式加载失败", "面板样式未能加载，已停止连接与保存。");
      });
    }
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", boot, { once: true });
    } else {
      boot();
    }
  }

  updateMinutePicker(false);
  start();
})();
