import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import collector

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


class CollectorTests(unittest.TestCase):
    def test_relevance(self):
        self.assertEqual(collector.brand_for("Motorola Glance lock screen ads"), "Glance")
        self.assertEqual(collector.brand_for("Unity Aura recommends apps"), "Unity Aura")
        self.assertEqual(collector.brand_for("I took a glance at my watch"), None)
        self.assertEqual(collector.brand_for("lock screen ads are intrusive"), "Industry")

    def test_dates(self):
        self.assertEqual(collector.parse_date(1794441600).tzinfo, timezone.utc)
        self.assertIsNone(collector.parse_date("not a date"))

    def test_records_and_age_limit(self):
        item = collector.record("reddit:p:abc123", "Reddit", "Glance ads on Motorola",
                                "", "https://www.reddit.com/r/motorola/comments/abc123/",
                                NOW - timedelta(days=2), NOW)
        self.assertEqual(item["brand"], "Glance")
        self.assertEqual(item["kind"], "reaction")
        old = collector.record("old", "Reddit", "Glance lock screen", "",
                               "https://reddit.com/x", NOW-timedelta(days=40), NOW)
        self.assertIsNone(old)

    def test_reddit_scoped_queries(self):
        calls = []
        ts = int((NOW-timedelta(days=1)).timestamp())
        def fake_get(url, attempts=2):
            calls.append(url)
            params = parse_qs(urlparse(url).query)
            self.assertIn("subreddit", params)
            if "query" in params and params["subreddit"][0] == "motorola":
                raise HTTPError(url, 422, "timeout", {}, None)
            if "query" not in params and "body" not in params and params["subreddit"][0] == "motorola":
                return json.dumps({"data": [{"id": "abc123", "title": "Glance lock screen ads",
                                              "subreddit": "motorola", "created_utc": ts}]}).encode()
            return b'{"data":[]}'
        with patch("collector.get", side_effect=fake_get), patch("collector.time.sleep"):
            items, ok, errors = collector.collect_reddit(NOW)
        self.assertEqual(ok, 8)
        self.assertEqual([x["source"] for x in items], ["Reddit"])
        self.assertEqual(items[0]["id"], "reddit:p:abc123")
        self.assertTrue(any("fallback" in e for e in errors))
        self.assertTrue(all("subreddit=" in url for url in calls))

    def test_main_idempotent(self):
        example = collector.record("hn:123", "Hacker News", "Glance lock screen ads", "",
                                   "https://news.ycombinator.com/item?id=123",
                                   NOW-timedelta(days=1), NOW)
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "monitor.json"
            with patch("collector.DATA", file), patch("collector.now", return_value=NOW), \
                 patch("collector.collect_reddit", return_value=([example], 1, [])), \
                 patch("collector.collect_bluesky", return_value=([], 1, [])), \
                 patch("collector.collect_hn", return_value=([], 1, [])), \
                 patch("collector.collect_news", return_value=([], 1, [])):
                collector.main()
                collector.main()
            result = json.loads(file.read_text(encoding='utf-8'))
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["daily"][0]["new_reactions"], 1)
            self.assertEqual(len(result["runs"]), 2)


if __name__ == "__main__":
    unittest.main()
