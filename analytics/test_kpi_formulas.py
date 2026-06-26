import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mongo_kpi_analysis import (
    classify_freshness,
    diff_ms,
    latency_breakdown,
    stats,
    success_rate,
)


class KpiFormulaTests(unittest.TestCase):
    def setUp(self):
        base = dt.datetime(2026, 6, 26, 9, 0, 0, tzinfo=dt.timezone.utc)
        self.flat = {
            "timestamps.ui_triggered_at": base,
            "timestamps.backend_received_at": base + dt.timedelta(milliseconds=100),
            "timestamps.bridge_received_at": base + dt.timedelta(milliseconds=250),
            "timestamps.robot_action_started_at": base + dt.timedelta(milliseconds=500),
            "timestamps.robot_action_completed_at": base + dt.timedelta(milliseconds=2500),
            "timestamps.mongodb_logged_at": base + dt.timedelta(milliseconds=2800),
            "timestamps.dashboard_updated_at": base + dt.timedelta(milliseconds=3200),
        }

    def test_pairwise_diff_ms(self):
        self.assertEqual(
            diff_ms(self.flat["timestamps.backend_received_at"], self.flat["timestamps.ui_triggered_at"]),
            100,
        )

    def test_latency_breakdown(self):
        latencies = latency_breakdown(self.flat)
        self.assertEqual(latencies["ui_to_backend"], 100)
        self.assertEqual(latencies["backend_to_bridge"], 150)
        self.assertEqual(latencies["bridge_to_robot_start"], 250)
        self.assertEqual(latencies["robot_action_duration"], 2000)
        self.assertEqual(latencies["robot_to_mongodb"], 300)
        self.assertEqual(latencies["mongodb_to_dashboard"], 400)
        self.assertEqual(latencies["end_to_end"], 3200)

    def test_stored_latency_precedence(self):
        flat = dict(self.flat)
        flat["latency_ms.end_to_end"] = 1234
        self.assertEqual(latency_breakdown(flat)["end_to_end"], 1234)

    def test_success_rate(self):
        result = success_rate(["completed", "success", "failed", "pending", "unknown"])
        self.assertEqual(result["success"], 2)
        self.assertEqual(result["failure"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["terminal_events"], 3)
        self.assertEqual(result["success_rate_percent"], 66.67)

    def test_stats(self):
        result = stats([10, 20, 30, 40, 50])
        self.assertEqual(result["latest"], 50)
        self.assertEqual(result["average"], 30)
        self.assertEqual(result["minimum"], 10)
        self.assertEqual(result["maximum"], 50)
        self.assertEqual(result["p50"], 30)
        self.assertEqual(result["p95"], 48)
        self.assertEqual(result["p99"], 49.6)

    def test_collection_freshness(self):
        now = dt.datetime(2026, 6, 26, 10, 0, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(classify_freshness(None, now=now, count=0), "empty")
        self.assertEqual(classify_freshness(now - dt.timedelta(minutes=2), now=now, count=1), "active")
        self.assertEqual(classify_freshness(now - dt.timedelta(minutes=20), now=now, count=1), "delayed")
        self.assertEqual(classify_freshness(now - dt.timedelta(minutes=31), now=now, count=1), "stale")
        self.assertEqual(classify_freshness(None, now=now, count=1), "unknown")


if __name__ == "__main__":
    unittest.main()
