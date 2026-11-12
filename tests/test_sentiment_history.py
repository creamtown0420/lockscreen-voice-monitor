import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
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
    def test_first_backfill_batch_covers_multiple_years(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        jobs=backfill.tasks_for(now)
        self.assertIn("2022-01/posts/motorola/title/Glance", {j[0] for j in jobs})
        self.assertIn("2026-11/posts/motorola/title/Glance", {j[0] for j in jobs})
        self.assertTrue(any(j[1]==2022 for j in jobs[:20]))
        self.assertTrue(any(j[1]==2025 for j in jobs[:20]))


if __name__=="__main__":
    unittest.main()
