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
    def test_specific_reinstallation_topic(self):
        self.assertEqual(sentiment.classify("The Glance app reinstalls itself after each update.")["topic"],"勝手に有効化")
    def test_spamware_topic(self):
        self.assertEqual(sentiment.classify("Glance is spamware and fills my lock screen with junk.")["topic"],"広告への不満")
    def test_unremovable_topic(self):
        self.assertEqual(sentiment.classify("The Glance ads are unremovable.")["topic"],"停止・削除")
    def test_positive(self):
        r=sentiment.classify("I love the useful Glance lock screen news.")
        self.assertEqual(r["sentiment"],"positive")
    def test_at_a_glance_ordinary_english_not_product(self):
        self.assertIsNone(collector.brand_for("At a glance I saw annoying Facebook ads on Motorola news."))
        self.assertIsNone(collector.brand_for("An Apple lock screen timer works at a glance without ads."))
        self.assertEqual(collector.brand_for("Remove Glance app lock screen ads from Motorola"),"Glance")
    def test_glance_on_android_removal_is_relevant(self):
        self.assertEqual(collector.brand_for("I disabled Glance on Android to avoid ads"), "Glance")
        self.assertEqual(collector.brand_for("I uninstalled glance because it was annoying my phone"), "Glance")
        self.assertIsNone(collector.brand_for("People read ads in a glance, even on Android devices"))
    def test_relevant_excerpt_preserves_late_product_context(self):
        text = "Normal description. " * 25 + "I disabled Glance on my Android lock screen."
        excerpt = collector.relevant_excerpt(text, "Glance")
        self.assertIn("Glance", excerpt)
        self.assertTrue(excerpt.startswith("…"))
    def test_phone_praise_is_not_glance_praise(self):
        r=sentiment.classify("My Motorola phone is really good after I removed Glance.", brand="Glance")
        self.assertNotEqual(r["sentiment"],"positive")
    def test_explicit_glance_praise_is_positive(self):
        r=sentiment.classify("I love Glance on the lock screen. It's very useful.", brand="Glance")
        self.assertEqual(r["sentiment"],"positive")
    def test_unscored_description(self):
        r=sentiment.classify("Is this Glance on my Motorola lock screen?")
        self.assertIn(r["sentiment"],["neutral","unclear"])
    def test_helpful_settings_instruction_is_neutral(self):
        r=sentiment.classify("Which phone do you have? Go to Settings and turn it off. Glance for Mi.")
        self.assertEqual(r["sentiment"],"neutral")
    def test_support_boilerplate_is_not_a_user_review(self):
        r=sentiment.classify("Hello u/Person! We truly empathize with your frustration with Glance lock screen ads.")
        self.assertEqual(r["sentiment"],"neutral")
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
            items,has_more,cursor=backfill.get_reddit(task,observed)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]["published_at"][:4],"2022")
        self.assertFalse(has_more)
        self.assertEqual(cursor["mode"],"unfiltered")
        self.assertEqual(len(seen),2)

    def test_backfill_checkpoint_resumes_after_full_page(self):
        observed=datetime(2026,11,12,tzinfo=timezone.utc)
        task=("2022-01/posts/motorola/title/Glance",2022,1,"posts","motorola","title","Glance")
        calls=[]
        def fake_request(typ,params):
            calls.append(params.get("after"))
            if len(calls)==1:
                return [{"id":format(100000+i,"x"),"subreddit":"motorola",
                    "title":"Glance ads on Motorola","created_utc":1641023472+i}
                    for i in range(50)]
            return [{"id":"abc999","subreddit":"motorola",
                "title":"Glance ads on Motorola","created_utc":1641023530}]
        with patch("backfill.request",side_effect=fake_request):
            first,more,cursor=backfill.get_reddit(task,observed)
            second,more2,_=backfill.get_reddit(task,observed,cursor)
        self.assertTrue(more)
        self.assertEqual(cursor["after"],1641023522)
        self.assertEqual(len(first),50)
        self.assertFalse(more2)
        self.assertEqual(len(second),1)
        self.assertEqual(calls[1],1641023522)

    def test_first_backfill_batch_covers_multiple_years(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc)
        jobs=backfill.tasks_for(now)
        self.assertIn("2022-01/posts/motorola/title/Glance", {j[0] for j in jobs})
        self.assertIn("2026-11/posts/motorola/title/Glance", {j[0] for j in jobs})
        self.assertTrue(any(j[1]==2022 for j in jobs[:20]))
        self.assertTrue(any(j[1]==2025 for j in jobs[:20]))


if __name__=="__main__":
    unittest.main()
