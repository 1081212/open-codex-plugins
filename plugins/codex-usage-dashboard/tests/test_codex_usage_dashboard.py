import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_usage_dashboard import (
    Cost,
    FileCursor,
    UsageStore,
    channel_label,
    find_codex_executable,
)


def record(timestamp, item_type, payload):
    return json.dumps(
        {"timestamp": timestamp, "type": item_type, "payload": payload},
        ensure_ascii=False,
    ) + "\n"


class UsageStoreTest(unittest.TestCase):
    def setUp(self):
        self.rate_limit_patch = patch(
            "codex_usage_dashboard.read_codex_weekly_rate_limit",
            return_value={"available": False, "reason": "test"},
        )
        self.rate_limit_patch.start()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.lark_home = self.root / "lark-channel"
        self.rollout = self.root / "2026" / "08" / "18" / "rollout.jsonl"
        self.rollout.parent.mkdir(parents=True)
        self.rollout.write_text(
            record(
                "2026-08-18T15:58:00Z",
                "session_meta",
                {
                    "id": "session-1",
                    "cwd": "/work/payment-service",
                    "source": "vscode",
                },
            )
            + record(
                "2026-08-18T15:58:30Z",
                "event_msg",
                {
                    "type": "thread_settings_applied",
                    "thread_settings": {
                        "model": "gpt-5.6-sol",
                        "service_tier": "default",
                    },
                },
            )
            + record(
                "2026-08-18T15:59:00Z",
                "turn_context",
                {"model": "gpt-5.6-sol", "turn_id": "turn-1"},
            )
            + record(
                "2026-08-18T16:01:00Z",
                "event_msg",
                {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 60,
                            "output_tokens": 20,
                            "reasoning_output_tokens": 5,
                            "total_tokens": 120,
                        }
                    },
                },
            )
        )

    def tearDown(self):
        self.temp.cleanup()
        self.rate_limit_patch.stop()

    def make_store(self):
        return UsageStore(
            self.root,
            timezone_name="Asia/Shanghai",
            lark_channel_home=self.lark_home,
        )

    def test_timezone_and_usage_breakdown(self):
        store = self.make_store()
        store.refresh(force_full=True)
        data = store.snapshot(7)
        row = next(r for r in data["daily"] if r["date"] == "2026-08-19")
        self.assertEqual(row["total_tokens"], 120)
        self.assertEqual(row["cached_input_tokens"], 60)
        self.assertEqual(row["uncached_input_tokens"], 40)
        self.assertEqual(row["output_tokens"], 20)
        self.assertEqual(row["sessions"], 1)
        self.assertEqual(data["models"][0]["name"], "gpt-5.6-sol")
        self.assertEqual(row["priced_cost_usd"], 0.00083)
        self.assertEqual(data["projects"][0]["name"], "payment-service")
        self.assertEqual(data["projects"][0]["priced_cost_usd"], 0.00083)
        self.assertEqual(data["channels"][0]["name"], "VS Code")

    def test_incremental_append_and_partial_line(self):
        store = self.make_store()
        store.refresh(force_full=True)
        partial = json.dumps(
            {
                "timestamp": "2026-08-19T01:00:00Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"last_token_usage": {"total_tokens": 55}},
                },
            }
        )
        with self.rollout.open("a") as stream:
            stream.write(partial)
        store.refresh()
        self.assertEqual(store.snapshot(7)["summary"]["total_tokens"], 120)
        with self.rollout.open("a") as stream:
            stream.write("\n")
        store.refresh()
        summary = store.snapshot(7)["summary"]
        self.assertEqual(summary["total_tokens"], 175)
        self.assertEqual(summary["unattributed_tokens"], 55)

    def test_duplicate_session_event_is_deduplicated(self):
        duplicate = self.root / "duplicate.jsonl"
        duplicate.write_text(self.rollout.read_text())
        store = self.make_store()
        store.refresh(force_full=True)
        self.assertEqual(store.snapshot(7)["summary"]["total_tokens"], 120)

    def test_official_price_components_are_separate(self):
        cost = Cost()
        cost.add(
            {
                "input_tokens": 100_000,
                "cached_input_tokens": 60_000,
                "output_tokens": 10_000,
                "reasoning_output_tokens": 2_000,
                "total_tokens": 110_000,
            },
            "gpt-5.6-sol",
            "default",
        )
        result = cost.as_dict()
        self.assertEqual(result["input_cost_usd"], 0.2)
        self.assertEqual(result["cached_input_cost_usd"], 0.03)
        self.assertEqual(result["output_cost_usd"], 0.3)
        self.assertEqual(result["priced_cost_usd"], 0.53)
        self.assertEqual(result["unpriced_tokens"], 0)

    def test_unknown_model_is_not_guessed(self):
        cost = Cost()
        cost.add(
            {
                "input_tokens": 100,
                "cached_input_tokens": 50,
                "output_tokens": 20,
                "reasoning_output_tokens": 0,
                "total_tokens": 120,
            },
            "codex-auto-review",
            "priority",
        )
        result = cost.as_dict()
        self.assertEqual(result["priced_cost_usd"], 0)
        self.assertEqual(result["unpriced_tokens"], 120)
        self.assertEqual(result["unpriced_models"], ["codex-auto-review"])

    def test_missing_tier_falls_back_to_official_standard(self):
        cost = Cost()
        values = {
            "input_tokens": 100_000,
            "cached_input_tokens": 60_000,
            "output_tokens": 10_000,
            "reasoning_output_tokens": 0,
            "total_tokens": 110_000,
        }
        cost.add(values, "gpt-5.6-sol", "")
        result = cost.as_dict()
        self.assertEqual(result["priced_cost_usd"], 0.53)
        self.assertEqual(result["standard_fallback_tokens"], 110_000)
        self.assertEqual(result["standard_fallback_events"], 1)
        self.assertEqual(result["unpriced_tokens"], 0)

    def test_codex_executable_can_be_resolved(self):
        self.assertIsNotNone(find_codex_executable())

    def test_lark_exec_session_is_classified_by_thread_id(self):
        profile = self.lark_home / "profiles" / "codex"
        profile.mkdir(parents=True)
        (profile / "sessions.json.catalog.json").write_text(
            json.dumps([{"threadId": "lark-session"}])
        )
        lark_rollout = self.rollout.parent / "lark.jsonl"
        lark_rollout.write_text(
            record(
                "2026-08-19T02:00:00Z",
                "session_meta",
                {
                    "id": "lark-session",
                    "cwd": "/work/lark-task",
                    "source": "exec",
                    "originator": "codex_exec",
                },
            )
            + record(
                "2026-08-19T02:00:01Z",
                "turn_context",
                {"model": "gpt-5.6-sol", "turn_id": "lark-turn"},
            )
            + record(
                "2026-08-19T02:00:02Z",
                "event_msg",
                {
                    "type": "token_count",
                    "info": {"last_token_usage": {"total_tokens": 50}},
                },
            )
        )
        store = self.make_store()
        store.refresh(force_full=True)
        channels = {row["name"]: row for row in store.snapshot(7)["channels"]}
        self.assertEqual(channels["飞书"]["total_tokens"], 50)
        self.assertEqual(channels["VS Code"]["total_tokens"], 120)

    def test_non_lark_codex_exec_remains_exec(self):
        cursor = FileCursor(
            session_id="manual-exec",
            source="exec",
            originator="codex_exec",
        )
        self.assertEqual(channel_label(cursor, set()), "Exec")

    def test_failed_quota_refresh_keeps_last_success(self):
        store = self.make_store()
        with patch(
            "codex_usage_dashboard.read_codex_weekly_rate_limit",
            return_value={
                "available": True,
                "used_percent": 67.0,
                "remaining_percent": 33.0,
                "window_duration_mins": 10_080,
            },
        ):
            store.refresh(force_full=True)
        with patch(
            "codex_usage_dashboard.read_codex_weekly_rate_limit",
            return_value={"available": False, "reason": "CLI 初始化未完成"},
        ):
            store.refresh()
        quota = store.snapshot(7)["weekly_rate_limit"]
        self.assertTrue(quota["available"])
        self.assertTrue(quota["stale"])
        self.assertEqual(quota["used_percent"], 67.0)
        self.assertEqual(quota["last_error"], "CLI 初始化未完成")


if __name__ == "__main__":
    unittest.main()
