#!/usr/bin/env python3
"""Local-only Codex token usage dashboard.

Reads only structured token_count events from Codex rollout JSONL files. It
does not collect or expose prompts, responses, tool inputs, or credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import signal
import subprocess
import threading
import time
import webbrowser
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47831
DEFAULT_REFRESH_SECONDS = 300
DEFAULT_TIMEZONE = "UTC"
DEFAULT_LARK_PROFILE = "codex"
TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
    "total_tokens",
)

PRICING_SOURCE = "https://developers.openai.com/api/docs/pricing"
PRICING_AS_OF = "2026-08-19"
LONG_CONTEXT_THRESHOLD = 272_000

# Official USD prices per 1M tokens. Only exact model IDs and the service tier
# recorded by Codex are priced. Unknown aliases are intentionally not guessed.
MODEL_PRICING_USD_PER_MILLION: Dict[str, Dict[str, Dict[str, Tuple[float, float, float]]]] = {
    "gpt-5.6-sol": {
        "standard": {"short": (5.00, 0.50, 30.00), "long": (10.00, 1.00, 45.00)},
        "fast": {"short": (10.00, 1.00, 60.00), "long": (20.00, 2.00, 90.00)},
        "flex": {"short": (2.50, 0.25, 15.00), "long": (5.00, 0.50, 22.50)},
    },
    "gpt-5.6-luna": {
        "standard": {"short": (0.20, 0.02, 1.20), "long": (0.40, 0.04, 1.80)},
        "fast": {"short": (0.40, 0.04, 2.40), "long": (0.80, 0.08, 3.60)},
        "flex": {"short": (0.10, 0.01, 0.60), "long": (0.20, 0.02, 0.90)},
    },
    "gpt-5.5": {
        "standard": {"short": (5.00, 0.50, 30.00), "long": (10.00, 1.00, 45.00)},
        "fast": {"short": (12.50, 1.25, 75.00)},
        "flex": {"short": (2.50, 0.25, 15.00), "long": (5.00, 0.50, 22.50)},
    },
    "gpt-5.4": {
        "standard": {"short": (2.50, 0.25, 15.00), "long": (5.00, 0.50, 22.50)},
        "fast": {"short": (5.00, 0.50, 30.00)},
        "flex": {"short": (1.25, 0.13, 7.50), "long": (2.50, 0.25, 11.25)},
    },
}

SERVICE_TIER_NAMES = {
    "default": "standard",
    "standard": "standard",
    "priority": "fast",
    "fast": "fast",
    "flex": "flex",
}


def pricing_metadata() -> Dict[str, Any]:
    models = []
    for model, tiers in MODEL_PRICING_USD_PER_MILLION.items():
        for tier, contexts in tiers.items():
            for context, rates in contexts.items():
                models.append({
                    "model": model,
                    "tier": tier,
                    "context": context,
                    "input": rates[0],
                    "cached_input": rates[1],
                    "output": rates[2],
                })
    return {
        "currency": "USD",
        "unit_tokens": 1_000_000,
        "source": PRICING_SOURCE,
        "as_of": PRICING_AS_OF,
        "long_context_threshold": LONG_CONTEXT_THRESHOLD,
        "models": models,
        "notes": [
            "按日志记录的模型、CLI service tier 和单次输入 Token 选择官方价档。",
            "模型有官方价格但日志缺少 service tier 时，按该模型 Standard 价回退并单独标记。",
            "非缓存输入按普通输入价计算；日志没有 cache-write Token，未计缓存写入附加价。",
            "这是标准 API 单价的等价成本，不是 ChatGPT/Codex 订阅账单。",
        ],
    }


def find_codex_executable() -> Optional[str]:
    configured = os.getenv("CODEX_CLI_PATH")
    if configured and Path(configured).is_file():
        return configured
    on_path = shutil.which("codex")
    if on_path:
        return on_path
    candidates = list((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/codex"))
    candidates.extend([Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex")])
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return None
    return str(max(existing, key=lambda path: path.stat().st_mtime))


def read_codex_weekly_rate_limit(timeout_seconds: float = 15.0) -> Dict[str, Any]:
    """Read the exact seven-day ChatGPT quota window from Codex app-server."""
    initialize = json.dumps({
            "method": "initialize",
            "id": 1,
            "params": {"clientInfo": {
                "name": "codex_usage_dashboard",
                "title": "Codex Usage Dashboard",
                "version": "1.0.0",
            }},
        })
    codex_executable = find_codex_executable()
    if not codex_executable:
        return {"available": False, "reason": "后台进程找不到 Codex CLI"}
    try:
        process = subprocess.Popen(
            [codex_executable, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(initialize + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + timeout_seconds

        def read_response(response_id: int) -> Optional[Dict[str, Any]]:
            while time.monotonic() < deadline:
                ready, _, _ = select.select(
                    [process.stdout], [], [], max(0.0, deadline - time.monotonic())
                )
                if not ready:
                    break
                line = process.stdout.readline()
                if not line:
                    break
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get("id") == response_id:
                    return message
            return None

        if read_response(1) is None:
            return {"available": False, "reason": "CLI 初始化未完成"}
        process.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
        process.stdin.write(json.dumps({"method": "account/rateLimits/read", "id": 2}) + "\n")
        process.stdin.flush()
        response = read_response(2)
    except OSError as error:
        return {"available": False, "reason": f"CLI 额度读取失败：{type(error).__name__}"}
    finally:
        if "process" in locals():
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
    if response is None:
        return {"available": False, "reason": "CLI 未返回额度数据"}
    if response.get("error"):
        return {"available": False, "reason": "CLI 拒绝读取额度"}

    result = response.get("result") or {}
    candidates: List[Tuple[str, str, Dict[str, Any]]] = []
    buckets = result.get("rateLimitsByLimitId") or {}
    if isinstance(buckets, dict):
        for limit_id, bucket in buckets.items():
            if not isinstance(bucket, dict):
                continue
            for window_name in ("primary", "secondary"):
                window = bucket.get(window_name)
                if isinstance(window, dict):
                    candidates.append((str(limit_id), window_name, window))
    legacy = result.get("rateLimits")
    if isinstance(legacy, dict):
        for window_name in ("primary", "secondary"):
            window = legacy.get(window_name)
            if isinstance(window, dict):
                candidates.append((str(legacy.get("limitId") or "codex"), window_name, window))

    weekly = [item for item in candidates if safe_int(item[2].get("windowDurationMins")) == 10_080]
    if not weekly:
        return {"available": False, "reason": "CLI 当前未返回精确的 7 天额度窗口"}
    weekly.sort(key=lambda item: (item[0] != "codex", item[1] != "secondary"))
    limit_id, window_name, window = weekly[0]
    try:
        used_percent = float(window.get("usedPercent"))
    except (TypeError, ValueError):
        return {"available": False, "reason": "7 天额度缺少 usedPercent"}
    used_percent = min(100.0, max(0.0, used_percent))
    return {
        "available": True,
        "limit_id": limit_id,
        "window": window_name,
        "window_duration_mins": 10_080,
        "used_percent": used_percent,
        "remaining_percent": 100.0 - used_percent,
        "resets_at": safe_int(window.get("resetsAt")) or None,
    }


def safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def parse_timestamp(value: str, tz: ZoneInfo) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(tz)


def project_label(cwd: str) -> str:
    if not cwd:
        return "未知项目"
    path = Path(cwd)
    return path.name or str(path)


def read_lark_thread_ids(home: Path, profile: str = DEFAULT_LARK_PROFILE) -> Set[str]:
    """Read only Codex thread IDs recorded by the local Lark bridge."""
    profile_root = home.expanduser() / "profiles" / profile
    thread_ids: Set[str] = set()
    catalog = profile_root / "sessions.json.catalog.json"
    try:
        rows = json.loads(catalog.read_text())
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get("threadId"):
                    thread_ids.add(str(row["threadId"]))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass

    logs_root = profile_root / "logs"
    for path in sorted(logs_root.glob("bridge-*.jsonl")):
        try:
            with path.open("rb") as stream:
                for raw in stream:
                    if b'"threadId"' not in raw:
                        continue
                    try:
                        item = json.loads(raw)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if item.get("event") not in {"resume", "set-thread"}:
                        continue
                    thread_id = item.get("threadId")
                    if thread_id:
                        thread_ids.add(str(thread_id))
        except OSError:
            continue
    return thread_ids


def session_source_label(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and "subagent" in value:
        return "subagent"
    return ""


def channel_label(cursor: "FileCursor", lark_thread_ids: Set[str]) -> str:
    if cursor.session_id in lark_thread_ids:
        return "飞书"
    source = cursor.source.lower()
    originator = cursor.originator.lower()
    if source == "vscode" or originator == "codex_vscode":
        return "VS Code"
    if source == "cli" or originator == "codex-tui":
        return "Codex CLI"
    if source == "exec" or originator == "codex_exec":
        return "Exec"
    if source == "subagent" or "subagent" in originator:
        return "子代理"
    return cursor.source or cursor.originator or "未知渠道"


@dataclass
class Usage:
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0
    events: int = 0

    def add(self, values: Dict[str, int]) -> None:
        self.input_tokens += values["input_tokens"]
        self.cached_input_tokens += values["cached_input_tokens"]
        self.output_tokens += values["output_tokens"]
        self.reasoning_output_tokens += values["reasoning_output_tokens"]
        self.total_tokens += values["total_tokens"]
        self.events += 1

    def merge(self, other: "Usage") -> None:
        for name in TOKEN_FIELDS:
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.events += other.events

    def as_dict(self) -> Dict[str, int]:
        uncached = max(0, self.input_tokens - self.cached_input_tokens)
        attributed = self.input_tokens + self.output_tokens
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "uncached_input_tokens": uncached,
            "output_tokens": self.output_tokens,
            "reasoning_output_tokens": self.reasoning_output_tokens,
            "total_tokens": self.total_tokens,
            "unattributed_tokens": max(0, self.total_tokens - attributed),
            "events": self.events,
        }


@dataclass
class Cost:
    input_cost_usd: float = 0.0
    cached_input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    priced_tokens: int = 0
    unpriced_tokens: int = 0
    unpriced_events: int = 0
    unpriced_models: Set[str] = field(default_factory=set)
    standard_fallback_tokens: int = 0
    standard_fallback_events: int = 0

    def add(self, values: Dict[str, int], model: str, service_tier: str) -> None:
        input_tokens = values["input_tokens"]
        cached_tokens = min(input_tokens, values["cached_input_tokens"])
        uncached_tokens = max(0, input_tokens - cached_tokens)
        output_tokens = values["output_tokens"]
        attributable = input_tokens + output_tokens
        unattributed = max(0, values["total_tokens"] - attributable)
        tier = SERVICE_TIER_NAMES.get(service_tier)
        used_standard_fallback = tier is None and model in MODEL_PRICING_USD_PER_MILLION
        if used_standard_fallback:
            tier = "standard"
        context = "long" if input_tokens > LONG_CONTEXT_THRESHOLD else "short"
        rates = MODEL_PRICING_USD_PER_MILLION.get(model, {}).get(tier or "", {}).get(context)
        if rates is None:
            self.unpriced_tokens += values["total_tokens"]
            self.unpriced_events += 1
            self.unpriced_models.add(model or "未知模型")
            return
        input_rate, cached_rate, output_rate = rates
        self.input_cost_usd += uncached_tokens * input_rate / 1_000_000
        self.cached_input_cost_usd += cached_tokens * cached_rate / 1_000_000
        self.output_cost_usd += output_tokens * output_rate / 1_000_000
        self.priced_tokens += attributable
        if used_standard_fallback:
            self.standard_fallback_tokens += attributable
            self.standard_fallback_events += 1
        if unattributed:
            self.unpriced_tokens += unattributed

    def merge(self, other: "Cost") -> None:
        self.input_cost_usd += other.input_cost_usd
        self.cached_input_cost_usd += other.cached_input_cost_usd
        self.output_cost_usd += other.output_cost_usd
        self.priced_tokens += other.priced_tokens
        self.unpriced_tokens += other.unpriced_tokens
        self.unpriced_events += other.unpriced_events
        self.unpriced_models.update(other.unpriced_models)
        self.standard_fallback_tokens += other.standard_fallback_tokens
        self.standard_fallback_events += other.standard_fallback_events

    def as_dict(self) -> Dict[str, Any]:
        total = self.input_cost_usd + self.cached_input_cost_usd + self.output_cost_usd
        return {
            "priced_cost_usd": round(total, 8),
            "input_cost_usd": round(self.input_cost_usd, 8),
            "cached_input_cost_usd": round(self.cached_input_cost_usd, 8),
            "output_cost_usd": round(self.output_cost_usd, 8),
            "priced_tokens": self.priced_tokens,
            "unpriced_tokens": self.unpriced_tokens,
            "unpriced_events": self.unpriced_events,
            "unpriced_models": sorted(self.unpriced_models),
            "standard_fallback_tokens": self.standard_fallback_tokens,
            "standard_fallback_events": self.standard_fallback_events,
        }


@dataclass
class DayUsage:
    usage: Usage = field(default_factory=Usage)
    cost: Cost = field(default_factory=Cost)
    sessions: Set[str] = field(default_factory=set)
    by_model: DefaultDict[str, Usage] = field(
        default_factory=lambda: defaultdict(Usage)
    )
    by_model_cost: DefaultDict[str, Cost] = field(
        default_factory=lambda: defaultdict(Cost)
    )
    by_project: DefaultDict[str, Usage] = field(
        default_factory=lambda: defaultdict(Usage)
    )
    by_project_cost: DefaultDict[str, Cost] = field(
        default_factory=lambda: defaultdict(Cost)
    )
    by_channel: DefaultDict[str, Usage] = field(
        default_factory=lambda: defaultdict(Usage)
    )
    by_channel_cost: DefaultDict[str, Cost] = field(
        default_factory=lambda: defaultdict(Cost)
    )


@dataclass
class FileCursor:
    offset: int = 0
    inode: int = 0
    session_id: str = ""
    cwd: str = ""
    source: str = ""
    originator: str = ""
    model: str = "未知模型"
    service_tier: str = ""
    turn_id: str = ""


class UsageStore:
    def __init__(
        self,
        sessions_root: Path,
        timezone_name: str = DEFAULT_TIMEZONE,
        lark_channel_home: Optional[Path] = None,
        lark_profile: str = DEFAULT_LARK_PROFILE,
    ):
        self.sessions_root = sessions_root.expanduser().resolve()
        self.lark_channel_home = (
            lark_channel_home
            or Path(os.getenv("LARK_CHANNEL_HOME", "~/.lark-channel"))
        ).expanduser().resolve()
        self.lark_profile = lark_profile
        self.timezone_name = timezone_name
        # UTC works even on Windows Python installations without the optional
        # IANA tzdata package. Named local zones still use the system database.
        self.tz = timezone.utc if timezone_name.upper() == "UTC" else ZoneInfo(timezone_name)
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._days: DefaultDict[str, DayUsage] = defaultdict(DayUsage)
        self._files: Dict[Path, FileCursor] = {}
        self._seen_events: Set[Tuple[Any, ...]] = set()
        self._lark_thread_ids: Set[str] = set()
        self._last_refresh: Optional[datetime] = None
        self._last_duration_ms = 0
        self._parse_errors = 0
        self._is_refreshing = False
        self._rate_limits: Dict[str, Any] = {
            "available": False,
            "reason": "尚未读取 CLI 额度",
        }

    @property
    def is_refreshing(self) -> bool:
        with self._lock:
            return self._is_refreshing

    def _rollout_files(self) -> List[Path]:
        if not self.sessions_root.exists():
            return []
        return sorted(self.sessions_root.rglob("*.jsonl"))

    def refresh(self, force_full: bool = False) -> Dict[str, Any]:
        if not self._refresh_lock.acquire(blocking=False):
            return self.snapshot(30)

        started = time.monotonic()
        try:
            with self._lock:
                self._is_refreshing = True

            files = self._rollout_files()
            lark_thread_ids = read_lark_thread_ids(
                self.lark_channel_home, self.lark_profile
            )
            current = set(files)
            known = set(self._files)
            requires_rebuild = (
                force_full
                or bool(known - current)
                or lark_thread_ids != self._lark_thread_ids
            )
            self._lark_thread_ids = lark_thread_ids

            if not requires_rebuild:
                for path in files:
                    cursor = self._files.get(path)
                    if cursor is None:
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        requires_rebuild = True
                        break
                    if stat.st_ino != cursor.inode or stat.st_size < cursor.offset:
                        requires_rebuild = True
                        break

            if requires_rebuild:
                with self._lock:
                    self._days = defaultdict(DayUsage)
                    self._files = {}
                    self._seen_events = set()
                    self._parse_errors = 0

            for path in files:
                self._consume_file(path)

            rate_limits = read_codex_weekly_rate_limit()
            if not rate_limits.get("available") and rate_limits.get("reason") in {
                "CLI 初始化未完成",
                "CLI 未返回额度数据",
                "CLI 拒绝读取额度",
            }:
                rate_limits = read_codex_weekly_rate_limit()

            finished = datetime.now(self.tz)
            with self._lock:
                self._last_refresh = finished
                self._last_duration_ms = int((time.monotonic() - started) * 1000)
                checked_at = finished.isoformat()
                if rate_limits.get("available"):
                    rate_limits.update({
                        "stale": False,
                        "last_checked": checked_at,
                        "last_success": checked_at,
                    })
                    self._rate_limits = rate_limits
                elif self._rate_limits.get("available"):
                    retained = dict(self._rate_limits)
                    retained.update({
                        "stale": True,
                        "last_checked": checked_at,
                        "last_error": rate_limits.get("reason") or "CLI 额度刷新失败",
                    })
                    self._rate_limits = retained
                else:
                    rate_limits["last_checked"] = checked_at
                    self._rate_limits = rate_limits
        finally:
            with self._lock:
                self._is_refreshing = False
            self._refresh_lock.release()

        return self.snapshot(30)

    def _consume_file(self, path: Path) -> None:
        try:
            stat = path.stat()
        except OSError:
            with self._lock:
                self._parse_errors += 1
            return

        with self._lock:
            cursor = self._files.get(path)
            if cursor is None:
                cursor = FileCursor(inode=stat.st_ino)
                self._files[path] = cursor
            start_offset = cursor.offset

        if stat.st_size <= start_offset:
            return

        try:
            with path.open("rb") as stream:
                stream.seek(start_offset)
                while True:
                    line_start = stream.tell()
                    raw = stream.readline()
                    if not raw:
                        break
                    if not raw.endswith(b"\n"):
                        stream.seek(line_start)
                        break
                    if not any(
                        marker in raw
                        for marker in (b'"token_count"', b'"session_meta"', b'"turn_context"', b'"thread_settings_applied"')
                    ):
                        continue
                    try:
                        item = json.loads(raw)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        with self._lock:
                            self._parse_errors += 1
                        continue
                    self._consume_item(path, cursor, item)
                new_offset = stream.tell()
        except OSError:
            with self._lock:
                self._parse_errors += 1
            return

        with self._lock:
            cursor.offset = new_offset
            cursor.inode = stat.st_ino

    def _consume_item(
        self, path: Path, cursor: FileCursor, item: Dict[str, Any]
    ) -> None:
        payload = item.get("payload") or {}
        item_type = item.get("type")

        if item_type == "session_meta":
            cursor.session_id = str(
                payload.get("id") or payload.get("session_id") or path.stem
            )
            cursor.cwd = str(payload.get("cwd") or cursor.cwd)
            cursor.source = session_source_label(payload.get("source")) or cursor.source
            cursor.originator = str(payload.get("originator") or cursor.originator)
            return

        if item_type == "turn_context":
            cursor.model = str(payload.get("model") or cursor.model or "未知模型")
            cursor.cwd = str(payload.get("cwd") or cursor.cwd)
            cursor.turn_id = str(payload.get("turn_id") or cursor.turn_id)
            return

        if item_type == "event_msg" and payload.get("type") == "thread_settings_applied":
            settings = payload.get("thread_settings") or {}
            cursor.model = str(settings.get("model") or cursor.model or "未知模型")
            cursor.service_tier = str(settings.get("service_tier") or cursor.service_tier)
            cursor.cwd = str(settings.get("cwd") or cursor.cwd)
            return

        if item_type != "event_msg" or payload.get("type") != "token_count":
            return

        info = payload.get("info") or {}
        usage = info.get("last_token_usage") or {}
        if not usage:
            return

        timestamp = str(item.get("timestamp") or "")
        try:
            local_time = parse_timestamp(timestamp, self.tz)
        except (TypeError, ValueError):
            with self._lock:
                self._parse_errors += 1
            return

        values = {name: safe_int(usage.get(name)) for name in TOKEN_FIELDS}
        if values["total_tokens"] == 0:
            values["total_tokens"] = (
                values["input_tokens"] + values["output_tokens"]
            )
        if values["total_tokens"] == 0:
            return

        session_id = cursor.session_id or path.stem
        event_key = (
            session_id,
            timestamp,
            cursor.turn_id,
            *(values[name] for name in TOKEN_FIELDS),
        )
        day_key = local_time.date().isoformat()
        model = cursor.model or "未知模型"
        project = project_label(cursor.cwd)
        channel = channel_label(cursor, self._lark_thread_ids)

        with self._lock:
            if event_key in self._seen_events:
                return
            self._seen_events.add(event_key)
            day = self._days[day_key]
            day.usage.add(values)
            day.cost.add(values, model, cursor.service_tier)
            day.sessions.add(session_id)
            day.by_model[model].add(values)
            day.by_model_cost[model].add(values, model, cursor.service_tier)
            day.by_project[project].add(values)
            day.by_project_cost[project].add(
                values, model, cursor.service_tier
            )
            day.by_channel[channel].add(values)
            day.by_channel_cost[channel].add(
                values, model, cursor.service_tier
            )

    def snapshot(self, days: int = 30) -> Dict[str, Any]:
        with self._lock:
            today = datetime.now(self.tz).date()
            available = sorted(self._days)
            if days <= 0:
                if available:
                    start = date.fromisoformat(available[0])
                else:
                    start = today
            else:
                start = today - timedelta(days=days - 1)

            selected_dates: List[date] = []
            current = start
            while current <= today:
                selected_dates.append(current)
                current += timedelta(days=1)

            total = Usage()
            total_cost = Cost()
            session_ids: Set[str] = set()
            by_model: DefaultDict[str, Usage] = defaultdict(Usage)
            by_model_cost: DefaultDict[str, Cost] = defaultdict(Cost)
            by_project: DefaultDict[str, Usage] = defaultdict(Usage)
            by_project_cost: DefaultDict[str, Cost] = defaultdict(Cost)
            by_channel: DefaultDict[str, Usage] = defaultdict(Usage)
            by_channel_cost: DefaultDict[str, Cost] = defaultdict(Cost)
            daily: List[Dict[str, Any]] = []

            for day_date in selected_dates:
                key = day_date.isoformat()
                day = self._days.get(key)
                if day is None:
                    daily.append({
                        "date": key,
                        **Usage().as_dict(),
                        **Cost().as_dict(),
                        "sessions": 0,
                    })
                    continue
                total.merge(day.usage)
                total_cost.merge(day.cost)
                session_ids.update(day.sessions)
                for name, usage in day.by_model.items():
                    by_model[name].merge(usage)
                for name, cost in day.by_model_cost.items():
                    by_model_cost[name].merge(cost)
                for name, usage in day.by_project.items():
                    by_project[name].merge(usage)
                for name, cost in day.by_project_cost.items():
                    by_project_cost[name].merge(cost)
                for name, usage in day.by_channel.items():
                    by_channel[name].merge(usage)
                for name, cost in day.by_channel_cost.items():
                    by_channel_cost[name].merge(cost)
                daily.append({
                    "date": key,
                    **day.usage.as_dict(),
                    **day.cost.as_dict(),
                    "sessions": len(day.sessions),
                })

            def ranking(
                values: Dict[str, Usage], costs: Optional[Dict[str, Cost]] = None
            ) -> List[Dict[str, Any]]:
                ranked = sorted(
                    values.items(),
                    key=lambda pair: pair[1].total_tokens,
                    reverse=True,
                )
                rows = []
                for name, usage in ranked[:10]:
                    row = {"name": name, **usage.as_dict()}
                    if costs is not None:
                        row.update(costs[name].as_dict())
                    rows.append(row)
                return rows

            return {
                "timezone": self.timezone_name,
                "range": {
                    "days": days,
                    "start": selected_dates[0].isoformat(),
                    "end": selected_dates[-1].isoformat(),
                },
                "summary": {
                    **total.as_dict(),
                    **total_cost.as_dict(),
                    "sessions": len(session_ids),
                    "cache_rate": (
                        total.cached_input_tokens / total.input_tokens
                        if total.input_tokens
                        else 0.0
                    ),
                },
                "daily": daily,
                "models": ranking(by_model, by_model_cost),
                "projects": ranking(by_project, by_project_cost),
                "channels": ranking(by_channel, by_channel_cost),
                "pricing": pricing_metadata(),
                "weekly_rate_limit": dict(self._rate_limits),
                "meta": {
                    "files": len(self._files),
                    "events": len(self._seen_events),
                    "parse_errors": self._parse_errors,
                    "last_refresh": (
                        self._last_refresh.isoformat() if self._last_refresh else None
                    ),
                    "last_duration_ms": self._last_duration_ms,
                    "refreshing": self._is_refreshing,
                    "sessions_root": str(self.sessions_root),
                    "lark_threads": len(self._lark_thread_ids),
                },
            }


class DashboardHandler(BaseHTTPRequestHandler):
    store: UsageStore
    index_html: bytes

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_bytes(
                HTTPStatus.OK,
                self.index_html,
                "text/html; charset=utf-8",
            )
            return

        if parsed.path == "/api/usage":
            params = parse_qs(parsed.query)
            try:
                days = int(params.get("days", ["30"])[0])
            except ValueError:
                days = 30
            days = 0 if days == 0 else min(max(days, 1), 3660)
            self._send_json(HTTPStatus.OK, self.store.snapshot(days))
            return

        if parsed.path == "/healthz":
            snapshot = self.store.snapshot(1)
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "last_refresh": snapshot["meta"]["last_refresh"],
                    "files": snapshot["meta"]["files"],
                },
            )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/refresh":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        params = parse_qs(parsed.query)
        force_full = params.get("full", ["0"])[0] == "1"
        data = self.store.refresh(force_full=force_full)
        self._send_json(HTTPStatus.OK, data)

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(
        self, status: HTTPStatus, body: bytes, content_type: str
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        message = fmt % args
        print(f"{datetime.now().isoformat(timespec='seconds')} {self.client_address[0]} {message}", flush=True)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def background_refresh(
    store: UsageStore, interval_seconds: int, stop_event: threading.Event
) -> None:
    while not stop_event.wait(max(10, interval_seconds)):
        store.refresh()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("CODEX_USAGE_HOST", DEFAULT_HOST))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CODEX_USAGE_PORT", str(DEFAULT_PORT))),
    )
    parser.add_argument(
        "--sessions-root",
        type=Path,
        default=Path(
            os.getenv(
                "CODEX_USAGE_SESSIONS_ROOT",
                str(Path(os.getenv("CODEX_HOME", "~/.codex")).expanduser() / "sessions"),
            )
        ),
    )
    parser.add_argument(
        "--timezone",
        default=os.getenv("CODEX_USAGE_TIMEZONE", DEFAULT_TIMEZONE),
    )
    parser.add_argument(
        "--refresh-seconds",
        type=int,
        default=int(
            os.getenv("CODEX_USAGE_REFRESH_SECONDS", str(DEFAULT_REFRESH_SECONDS))
        ),
    )
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--once", action="store_true", help="Print JSON and exit")
    parser.add_argument("--days", type=int, default=30, help="Range for --once")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    store = UsageStore(args.sessions_root, args.timezone)

    if args.once:
        store.refresh(force_full=True)
        print(json.dumps(store.snapshot(args.days), ensure_ascii=False, indent=2))
        return 0

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing to bind beyond localhost")

    index_path = Path(__file__).with_name("index.html")
    DashboardHandler.store = store
    DashboardHandler.index_html = index_path.read_bytes()

    server = ReusableThreadingHTTPServer((args.host, args.port), DashboardHandler)
    stop_event = threading.Event()
    initializer = threading.Thread(
        target=store.refresh,
        kwargs={"force_full": True},
        name="codex-usage-initial-scan",
        daemon=True,
    )
    initializer.start()
    refresher = threading.Thread(
        target=background_refresh,
        args=(store, args.refresh_seconds, stop_event),
        name="codex-usage-refresh",
        daemon=True,
    )
    refresher.start()

    def stop_server(_signum: int, _frame: Any) -> None:
        stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)

    url = f"http://{args.host}:{args.port}/"
    print(f"Codex usage dashboard: {url}", flush=True)
    if args.open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        stop_event.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
