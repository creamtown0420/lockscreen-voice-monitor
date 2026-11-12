import unittest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
import backfill
import collector
import sentiment


class SentimentAndHistoryTests(unittest.TestCase):
    def test_negative_by_uninstall(self):
        r=sentiment.classify("I hate these annoying Glance ads. I can't disable the lock screen.")
        self.assertEqual(r["sentiment"],"negative")
        self.assertEqual(r["topic"],"停止・削除")
    def test_positive(self):
        r=sentiment.classify("I love the useful Glance lock screen news.")
        self.assertEqual(r["sentiment"],"positive")
    def test_unscored_description(self):
        r=sentiment.classify("Is this Glance on my Motorola lock screen?")
        self.assertIn(r["sentiment"],["neutral","unclear"])
    def test_explicitly_unscored(self):
        self.assertEqual(sentiment.classify("")["sentiment"],"unclear")
    def test_historical_records_kept(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        then=now-timedelta(days=1000)
        self.assertIsNone(collector.record("1","Reddit","Glance ads on Motorola","",
                          "https://www.reddit.com",then,now))
        r=collector.record("1","Reddit","Glance ads on Motorola","",
                          "https://www.reddit.com",then,now,historical=True)
        self.assertIsNotNone(r)
        self.assertEqual(r["published_at"][:4],"2024")
    def test_historical_keyword_timeout_uses_bounded_fallback(self):
        observed=datetime(2026,11,12,tzinfo=timezone.utc)
        task=("2022-01/posts/motorola/title/Glance",2022,1,"posts","motorola","title","Glance")
        seen=[]
        def fetch(url,attempts=1):
            seen.append(url)
            p=parse_qs(urlparse(url).query)
            if "title" in p:
                raise HTTPError(url,422,"timeout",{},None)
            return json.dumps({"data":[{"id":"abc123","subreddit":"motorola",
                "title":"Glance lock screen ads","created_utc":1641023472}]}).encode()
        with patch("backfill.collector.get",side_effect=fetch):
            items,saturated=backfill.get_reddit(task,observed)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["published_at"][:4],"2022")
        self.assertFalse(saturated)
        self.assertEqual(len(seen),2)

    def test_first_backfill_batch_covers_multiple_years(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        jobs=backfill.tasks_for(now)
        self.assertIn("2022-01/posts/motorola/title/Glance", {j[0] for j in jobs})
        self.assertIn("2026-11/posts/motorola/title/Glance", {j[0] for j in jobs})
        self.assertTrue(any(j[1]==2022 for j in jobs[:20]))
        self.assertTrue(any(j[1]==2025 for j in jobs[:20]))


if __name__=="__main__":
    unittest.main()
