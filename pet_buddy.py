"""Local reminder inbox, temporary DND, and daily interaction goal.

Pure Python: no WinForms, network, chat text, clipboard, or credentials. The
store writes one bounded JSON file atomically; a corrupt file is preserved and
mutations refuse to overwrite it. A failed write leaves both memory and disk on
the previous state, and raises BuddyWriteError for the UI to show.
"""
from __future__ import annotations

from pet_agent_reminders import normalize_agent

import copy
import json
import math
import os
import random
import tempfile
import time
import uuid
from datetime import date, datetime
from pathlib import Path

MAX_ITEMS = 50
MAX_BYTES = 64 * 1024
DND_MINUTES = tuple(range(1, 61))
COOLDOWN_SECONDS = 60
GOAL_TARGET = 3
AFFINITY_MAX = 100
AFFINITY_PER_PAT = 15
KINDS = frozenset(("done", "waiting", "quota"))
SOURCES = frozenset(("live", "quiet", "hidden", "dnd", "other-thread"))
FEEDBACK_TEXTS = (
    "在呢，今天也一起加油。",
    "收到你的招呼啦。",
    "摸摸头，慢慢来就好。",
    "陪你一会儿。",
    "今天也辛苦啦。",
)


class BuddyWriteError(OSError):
    """Raised when the local buddy file cannot be written safely."""


def _fresh_state() -> dict:
    return {
        "version": 1,
        "inbox": [],
        "dnd": {"until": 0.0, "since": 0.0, "summary_due": False, "indefinite": False},
        "interaction": {
            "date": "",
            "today": 0,
            "affinity": 0,
            "total": 0,
            "active_days": 0,
            "last_count": 0.0,
            "feedback": True,
            "goal": True,
            "target": GOAL_TARGET,
        },
    }


def _number(value, default=0.0) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        return default
    return float(value)


class BuddyStore:
    """Bounded inbox + DND + interaction state, persisted transactionally."""

    def __init__(self, base, clock=time.time, date_for=None, choice=random.choice):
        self.path = Path(base) / "pet_buddy.json"
        self.clock = clock
        self.date_for = date_for or (lambda stamp: datetime.fromtimestamp(stamp).date())
        self.choice = choice or random.choice
        self.error = ""
        self.last_error = ""
        self.state = self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> dict:
        self.error = ""
        try:
            if not self.path.exists():
                return _fresh_state()
            if self.path.stat().st_size > MAX_BYTES:
                raise ValueError("提醒历史文件过大")
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, dict) or raw.get("version") != 1:
                raise ValueError("提醒历史格式错误")
            return self._clean(raw)
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            self.error = str(exc) or "提醒历史文件损坏"
            return _fresh_state()

    def _clean(self, raw: dict) -> dict:
        state = _fresh_state()
        items = []
        source = raw.get("inbox")
        if isinstance(source, list):
            for value in source:
                if not isinstance(value, dict):
                    continue
                kind = value.get("kind")
                at = _number(value.get("at"), -1)
                if kind not in KINDS or at < 0:
                    continue
                title = value.get("title") if isinstance(value.get("title"), str) else ""
                detail = value.get("detail") if isinstance(value.get("detail"), str) else ""
                key = value.get("key") if isinstance(value.get("key"), str) else ""
                item_source = value.get("source")
                items.append(
                    {
                        "id": str(value.get("id") or uuid.uuid4().hex[:12])[:64],
                        "kind": kind,
                        "title": title[:80],
                        "at": at,
                        "read": bool(value.get("read", False)),
                        "source": item_source if item_source in SOURCES else "live",
                        "agent": normalize_agent(value.get("agent")),
                        "key": key[:160],
                        "detail": detail[:120],
                    }
                )
        items.sort(key=lambda item: item["at"])
        state["inbox"] = items[-MAX_ITEMS:]

        dnd = raw.get("dnd")
        if isinstance(dnd, dict):
            until = max(0.0, _number(dnd.get("until")))
            since = max(0.0, _number(dnd.get("since")))
            indefinite = dnd.get("indefinite") is True
            if until <= 0 and not indefinite:
                since = 0.0
            state["dnd"] = {
                "until": until,
                "since": since,
                "summary_due": bool(dnd.get("summary_due", False)),
                "indefinite": indefinite,
            }

        interaction = raw.get("interaction")
        if isinstance(interaction, dict):
            target = interaction.get("target")
            target = target if type(target) is int and 1 <= target <= 10 else GOAL_TARGET
            state["interaction"] = {
                "date": str(interaction.get("date") or "")[:10],
                "today": max(0, min(target, int(_number(interaction.get("today"))))),
                "affinity": max(0, min(AFFINITY_MAX, int(_number(interaction.get("affinity"))))),
                "total": max(0, int(_number(interaction.get("total")))),
                "active_days": max(0, int(_number(interaction.get("active_days")))),
                "last_count": max(0.0, _number(interaction.get("last_count"))),
                "feedback": bool(interaction.get("feedback", True)),
                "goal": bool(interaction.get("goal", True)),
                "target": target,
            }
        return state

    def _save(self, candidate: dict) -> None:
        if self.error:
            raise BuddyWriteError("原提醒历史未读取，文件已保留；请先备份并修复：" + self.error)
        payload = json.dumps(candidate, ensure_ascii=False, indent=2)
        if len(payload.encode("utf-8")) > MAX_BYTES:
            raise BuddyWriteError("提醒历史超过本地大小上限，未写入。")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = None
        name = ""
        try:
            fd, name = tempfile.mkstemp(prefix=".pet-buddy-", dir=self.path.parent)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                handle = stream
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            self.last_error = ""
        except OSError as exc:
            self.last_error = "提醒历史保存失败：" + str(exc)
            raise BuddyWriteError(self.last_error) from exc
        finally:
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
            if name:
                try:
                    Path(name).unlink(missing_ok=True)
                except OSError:
                    pass

    def _commit(self, candidate: dict) -> None:
        self._save(candidate)
        self.state = candidate

    # -- small helpers ----------------------------------------------------
    def _now(self, now=None) -> float:
        value = self.clock() if now is None else now
        value = _number(value, -1)
        if value < 0:
            raise ValueError("时间无效")
        return value

    def _today(self, now: float) -> str:
        value = self.date_for(now)
        if isinstance(value, datetime):
            value = value.date()
        if not isinstance(value, date):
            raise ValueError("日期无效")
        return value.isoformat()

    def snapshot(self) -> dict:
        now = self._now()
        state = copy.deepcopy(self.state)
        interaction = state["interaction"]
        if interaction["date"] != self._today(now):
            interaction["today"] = 0
        interaction["completed"] = interaction["today"] >= interaction["target"]
        state["unread"] = sum(1 for item in state["inbox"] if not item["read"])
        return state

    # -- inbox ------------------------------------------------------------
    def add_reminder(
        self,
        kind,
        title="",
        source="live",
        now=None,
        key="",
        detail="",
        show_title=True,
        agent="codex",
    ) -> dict:
        if kind not in KINDS:
            raise ValueError("提醒类型无效")
        source = source if source in SOURCES else "live"
        now = self._now(now)
        agent = normalize_agent(agent)
        key = str(key or "")[:160]
        if key:
            for item in self.state["inbox"]:
                if item["key"] == key and normalize_agent(item.get("agent")) == agent:
                    return copy.deepcopy(item)
        title = " ".join(str(title or "").split())[:80] if show_title else ""
        detail = " ".join(str(detail or "").split())[:120] if show_title else ""
        item = {
            "id": uuid.uuid4().hex[:12],
            "kind": kind,
            "title": title,
            "at": now,
            "read": False,
            "source": source,
            "agent": agent,
            "key": key,
            "detail": detail,
        }
        candidate = copy.deepcopy(self.state)
        candidate["inbox"].append(item)
        candidate["inbox"].sort(key=lambda value: value["at"])
        candidate["inbox"] = candidate["inbox"][-MAX_ITEMS:]
        self._commit(candidate)
        return copy.deepcopy(item)

    def mark_read(self, item_id, agent=None) -> bool:
        changed = False
        candidate = copy.deepcopy(self.state)
        for item in candidate["inbox"]:
            if item["id"] == item_id and not item["read"] and (agent is None or normalize_agent(item.get("agent"))==normalize_agent(agent)):
                item["read"] = True
                changed = True
        if changed:
            self._commit(candidate)
        return changed

    def mark_all_read(self, agent=None) -> int:
        changed = 0
        candidate = copy.deepcopy(self.state)
        for item in candidate["inbox"]:
            if not item["read"] and (agent is None or normalize_agent(item.get("agent"))==normalize_agent(agent)):
                item["read"] = True
                changed += 1
        if changed:
            self._commit(candidate)
        return changed

    def clear_inbox(self, agent=None) -> int:
        count = sum(1 for x in self.state["inbox"] if agent is None or normalize_agent(x.get("agent"))==normalize_agent(agent))
        if count:
            candidate = copy.deepcopy(self.state)
            candidate["inbox"] = [x for x in candidate["inbox"] if agent is not None and normalize_agent(x.get("agent"))!=normalize_agent(agent)]
            self._commit(candidate)
        return count

    def hide_titles(self) -> int:
        """Retroactively scrub task names after the user turns showTitle off."""
        changed = 0
        candidate = copy.deepcopy(self.state)
        for item in candidate["inbox"]:
            if item["title"] or item["detail"]:
                item["title"] = ""
                item["detail"] = ""
                changed += 1
        if changed:
            self._commit(candidate)
        return changed

    def unread_count(self, agent=None) -> int:
        return sum(1 for item in self.state["inbox"] if not item["read"] and (agent is None or normalize_agent(item.get("agent"))==normalize_agent(agent)))

    # -- DND --------------------------------------------------------------
    def dnd_active(self, now=None) -> bool:
        dnd = self.state["dnd"]
        return bool(dnd["indefinite"] or dnd["until"] > self._now(now))

    def dnd_remaining(self, now=None) -> int | None:
        dnd = self.state["dnd"]
        if dnd["indefinite"]:return None
        return max(0, int(math.ceil(dnd["until"] - self._now(now))))

    def dnd_pending(self, now=None) -> bool:
        dnd = self.state["dnd"]
        return bool(not dnd["indefinite"] and dnd["until"] and dnd["summary_due"] and self._now(now) >= dnd["until"])

    def set_dnd(self, minutes, now=None) -> int | None:
        if minutes is not None and (type(minutes) is not int or minutes not in DND_MINUTES):
            raise ValueError("勿扰时长无效")
        now = self._now(now)
        current = self.state["dnd"]
        since = current["since"] if self.dnd_active(now) else now
        candidate = copy.deepcopy(self.state)
        candidate["dnd"] = {
            "until": now + minutes * 60 if minutes is not None else 0.0,
            "since": since,
            "summary_due": True,
            "indefinite": minutes is None,
        }
        self._commit(candidate)
        return self.dnd_remaining(now)

    def cancel_dnd(self, now=None) -> None:
        now = self._now(now)
        current = self.state["dnd"]
        if not current["indefinite"] and current["until"] <= now and not current["summary_due"]:
            return
        candidate = copy.deepcopy(self.state)
        candidate["dnd"] = {
            "until": now,
            "since": current["since"],
            "summary_due": True,
            "indefinite": False,
        }
        self._commit(candidate)

    def _summary(self, prefix: str, items: list[dict]) -> dict:
        return {
            "count": len(items),
            "items": copy.deepcopy(items),
            "text": prefix + "收到 %d 条提醒，可在“提醒收件箱”查看。" % len(items),
        }

    def summary_since(self, since, now=None) -> dict:
        since = self._now(since)
        items = [
            item
            for item in self.state["inbox"]
            if not item["read"] and item["at"] >= since
        ]
        return self._summary("安静期间", items)

    def expire_dnd(self, now=None):
        now = self._now(now)
        dnd = self.state["dnd"]
        if dnd["indefinite"] or not dnd["summary_due"] or now < dnd["until"]:
            return None
        since = dnd["since"]
        items = [
            item
            for item in self.state["inbox"]
            if not item["read"] and item["at"] >= since
        ]
        candidate = copy.deepcopy(self.state)
        candidate["dnd"] = {"until": 0.0, "since": 0.0, "summary_due": False, "indefinite": False}
        self._commit(candidate)
        if not items:
            return None
        return self._summary("勿扰结束：期间", items)

    # -- interaction goal -------------------------------------------------
    def interaction_snapshot(self, now=None) -> dict:
        now = self._now(now)
        interaction = self.state["interaction"]
        same_day = interaction["date"] == self._today(now)
        today = interaction["today"] if same_day else 0
        return {
            "today": today,
            "affinity": interaction.get("affinity", 0) if same_day else 0,
            "affinity_max": AFFINITY_MAX,
            "target": interaction["target"],
            "total": interaction["total"],
            "active_days": interaction["active_days"],
            "completed": today >= interaction["target"],
            "goal": interaction["goal"],
            "feedback": interaction["feedback"],
        }

    def record_interaction(self, kind, now=None) -> dict:
        if kind not in ("pat", "poke"):
            raise ValueError("互动类型无效")
        now = self._now(now)
        today = self._today(now)
        candidate = copy.deepcopy(self.state)
        interaction = candidate["interaction"]
        changed = False
        if interaction["date"] != today:
            interaction["date"] = today
            interaction["today"] = 0
            interaction["affinity"] = 0
            changed = True

        if kind == "pat" and interaction.get("affinity", 0) < AFFINITY_MAX:
            interaction["affinity"] = min(AFFINITY_MAX, interaction.get("affinity", 0) + AFFINITY_PER_PAT)
            changed = True

        counted = False
        just_completed = False
        if (
            interaction["goal"]
            and interaction["today"] < interaction["target"]
            and (interaction["last_count"] <= 0 or now - interaction["last_count"] >= COOLDOWN_SECONDS)
        ):
            if interaction["today"] == 0:
                interaction["active_days"] += 1
            interaction["today"] += 1
            interaction["total"] += 1
            interaction["last_count"] = now
            counted = True
            just_completed = interaction["today"] >= interaction["target"]
            changed = True

        feedback = ""
        if interaction["feedback"]:
            feedback = "今天的小目标完成啦！" if just_completed else self.choice(FEEDBACK_TEXTS)
        if changed:
            self._commit(candidate)
        return {
            "counted": counted,
            "today": interaction["today"],
            "affinity": interaction.get("affinity", 0),
            "affinity_max": AFFINITY_MAX,
            "target": interaction["target"],
            "total": interaction["total"],
            "active_days": interaction["active_days"],
            "completed": interaction["today"] >= interaction["target"],
            "just_completed": just_completed,
            "goal": interaction["goal"],
            "feedback": feedback,
        }

    def set_feedback(self, enabled) -> None:
        enabled = bool(enabled)
        if self.state["interaction"]["feedback"] == enabled:
            return
        candidate = copy.deepcopy(self.state)
        candidate["interaction"]["feedback"] = enabled
        self._commit(candidate)

    def set_goal(self, enabled) -> None:
        enabled = bool(enabled)
        if self.state["interaction"]["goal"] == enabled:
            return
        candidate = copy.deepcopy(self.state)
        candidate["interaction"]["goal"] = enabled
        self._commit(candidate)
