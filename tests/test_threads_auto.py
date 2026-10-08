import json
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from threads_auto import analytics, publish
from threads_auto.config import load_settings
from threads_auto.discord_ingest import ingest_channel
from threads_auto.store import Store, write_json
from threads_auto.threads_api import ThreadsClient, parse_insights
from threads_auto.validate import validate_queue

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 1, 8, 0, tzinfo=JST)


class FakeThreads:
    """Threads API の最小フェイク。呼び出しを記録する。"""

    def __init__(self, recent=None, views=None, fail_publish=False, fail_replies=False):
        self.calls = []
        self.recent = recent or []
        self.views = views or {}
        self.fail_publish = fail_publish
        self.fail_replies = fail_replies
        self.counter = 0

    def __call__(self, method, url, body, headers):
        parsed = urllib.parse.urlparse(url)
        params = dict(urllib.parse.parse_qsl(parsed.query or (body or b"").decode()))
        path = parsed.path
        self.calls.append((method, path, params))
        if path.endswith("/threads") and method == "POST":
            if self.fail_replies and params.get("reply_to_id"):
                return 403, {"error": {"message": "Application does not have permission for this action"}}
            self.counter += 1
            return 200, {"id": f"c{self.counter}"}
        if path.endswith("/threads_publish"):
            if self.fail_publish:
                return 400, {"error": {"message": "boom"}}
            return 200, {"id": "m" + params["creation_id"][1:]}
        if method == "GET" and params.get("fields", "").startswith("status"):
            return 200, {"status": "FINISHED"}
        if path.endswith("/threads") and method == "GET":
            return 200, {"data": self.recent}
        if path.endswith("/threads_insights"):
            return 200, {"data": [{"name": "followers_count", "total_value": {"value": 42}}]}
        if path.endswith("/insights"):
            mid = path.split("/")[-2]
            return 200, {"data": [{"name": "views", "values": [{"value": self.views.get(mid, 0)}]}, {"name": "likes", "total_value": {"value": 3}}]}
        mid = path.split("/")[-1]
        return 200, {"id": mid, "permalink": f"https://www.threads.com/@me/post/{mid}", "timestamp": NOW.isoformat()}


def queue_item(text="本文です", minutes_ago=5, **kw):
    item = {
        "text": text,
        "format_id": "F01",
        "tags": ["研修設計"],
        "scheduled_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "status": "queued",
        "review": {"status": "approved", "score": 85, "human_approved": True},
    }
    item.update(kw)
    return item


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        write_json(self.root / "formats.json", [{"id": "F01"}, {"id": "F02"}])
        self.store = Store(self.root)
        self.settings = load_settings(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, fake):
        return ThreadsClient("tok", transport=fake, sleep=lambda s: None)

    def enqueue(self, name, item):
        write_json(self.root / "queue" / f"{name}.json", item)


class PublishTests(Base):
    def test_publishes_due_post_with_replies_chain(self):
        self.enqueue("a", queue_item(replies=["続き1", "続き2"]))
        fake = FakeThreads()
        log = publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertTrue(any(l.startswith("POSTED") for l in log), log)
        posted = json.loads((self.root / "posted" / "a.json").read_text())
        self.assertEqual(posted["media_id"], "m1")
        self.assertEqual(posted["reply_media_ids"], ["m2", "m3"])
        creates = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/threads")]
        self.assertNotIn("reply_to_id", creates[0][2])
        self.assertEqual(creates[1][2]["reply_to_id"], "m1")
        self.assertEqual(creates[2][2]["reply_to_id"], "m2")
        self.assertFalse((self.root / "queue" / "a.json").exists())

    def test_requires_human_approval_by_default(self):
        self.enqueue("a", queue_item(review={"status": "approved"}))
        fake = FakeThreads()
        publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertFalse(fake.calls)

    def test_future_and_unapproved_are_skipped(self):
        self.enqueue("future", queue_item(minutes_ago=-30))
        self.enqueue("pending", queue_item(review={"status": "pending"}))
        fake = FakeThreads()
        publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertFalse(fake.calls)

    def test_expired_is_not_published(self):
        self.enqueue("old", queue_item(minutes_ago=60 * 30))
        fake = FakeThreads()
        publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertEqual(json.loads((self.root / "queue" / "old.json").read_text())["status"], "expired")
        self.assertFalse(fake.calls)

    def test_max_posts_per_run(self):
        self.enqueue("a", queue_item("一本目", minutes_ago=20))
        self.enqueue("b", queue_item("二本目", minutes_ago=10))
        publish.publish_due(self.client(FakeThreads()), self.store, self.settings, NOW)
        self.assertTrue((self.root / "posted" / "a.json").exists())
        self.assertTrue((self.root / "queue" / "b.json").exists())

    def test_min_interval(self):
        write_json(self.root / "posted" / "p.json", {"text": "前の投稿", "published_at": (NOW - timedelta(minutes=10)).isoformat()})
        self.enqueue("a", queue_item())
        fake = FakeThreads()
        log = publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertTrue(any(l.startswith("WAIT") for l in log))
        self.assertFalse(fake.calls)

    def test_recovers_already_published_without_reposting(self):
        self.enqueue("a", queue_item("同じ 本文"))
        fake = FakeThreads(recent=[{"id": "m99", "text": "同じ本文"}])
        publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertFalse([c for c in fake.calls if c[0] == "POST"])
        self.assertEqual(json.loads((self.root / "posted" / "a.json").read_text())["media_id"], "m99")

    def test_recovered_post_does_not_repost_replies(self):
        self.enqueue("a", queue_item("同じ 本文", replies=["返信"]))
        fake = FakeThreads(recent=[{"id": "m99", "text": "同じ本文"}])
        publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertFalse([c for c in fake.calls if c[0] == "POST"])
        self.assertTrue(json.loads((self.root / "posted" / "a.json").read_text())["replies_unverified"])

    def test_reply_failure_keeps_main_post_and_retries_only_replies(self):
        self.enqueue("a", queue_item("本文", replies=["返信1", "返信2"]))
        fake = FakeThreads(fail_replies=True)
        publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        item = json.loads((self.root / "queue" / "a.json").read_text())
        self.assertEqual(item["media_id"], "m1")
        self.assertEqual(item["attempts"], 1)
        # 次の実行: 本文は直近の投稿にあるが、返信だけを本文にぶら下げて投稿する
        fake2 = FakeThreads(recent=[{"id": "m1", "text": "本文"}])
        publish.publish_due(self.client(fake2), self.store, self.settings, NOW + timedelta(hours=2))
        creates = [c for c in fake2.calls if c[0] == "POST" and c[1].endswith("/threads")]
        self.assertEqual(len(creates), 2)
        self.assertEqual(creates[0][2]["reply_to_id"], "m1")
        posted = json.loads((self.root / "posted" / "a.json").read_text())
        self.assertEqual(posted["media_id"], "m1")
        self.assertEqual(len(posted["reply_media_ids"]), 2)

    def test_publishes_image_post_and_waits_for_container(self):
        self.enqueue("img", queue_item("画像つき", image_url="https://example.com/a.png", replies=["返信"]))
        fake = FakeThreads()
        log = publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertTrue(any(l.startswith("POSTED") for l in log), log)
        creates = [c for c in fake.calls if c[0] == "POST" and c[1].endswith("/threads")]
        self.assertEqual(creates[0][2]["media_type"], "IMAGE")
        self.assertEqual(creates[0][2]["image_url"], "https://example.com/a.png")
        self.assertEqual(creates[1][2]["media_type"], "TEXT")
        self.assertTrue(any(c[0] == "GET" and c[2].get("fields", "").startswith("status") for c in fake.calls))

    def test_failure_increments_attempts_then_fails(self):
        self.enqueue("a", queue_item())
        fake = FakeThreads(fail_publish=True)
        for _ in range(3):
            publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        item = json.loads((self.root / "queue" / "a.json").read_text())
        self.assertEqual(item["attempts"], 3)
        self.assertEqual(item["status"], "failed")

    def test_validation_error_blocks_publish(self):
        self.enqueue("a", queue_item("あ" * 501))
        fake = FakeThreads()
        log = publish.publish_due(self.client(fake), self.store, self.settings, NOW)
        self.assertTrue(any(l.startswith("SKIP") for l in log))
        self.assertFalse(fake.calls)

    def test_client_factory_not_called_when_nothing_due(self):
        def factory():
            raise AssertionError("トークン不要のはず")

        log = publish.publish_due(factory, self.store, self.settings, NOW)
        self.assertEqual(log, ["公開対象なし"])

    def test_client_factory_called_when_due(self):
        self.enqueue("a", queue_item())
        fake = FakeThreads()
        publish.publish_due(lambda: self.client(fake), self.store, self.settings, NOW)
        self.assertTrue((self.root / "posted" / "a.json").exists())

    def test_next_free_slots_skips_taken(self):
        self.enqueue("a", queue_item(scheduled_at="2026-10-01T12:15:00+09:00"))
        slots = publish.next_free_slots(self.store, self.settings, NOW, 3)
        self.assertEqual([s.strftime("%m-%d %H:%M") for s in slots], ["10-01 20:30", "10-02 07:30", "10-02 12:15"])


class CarouselTests(Base):
    def test_carousel_post(self):
        self.enqueue("c", queue_item("写真と図解", image_urls=["https://e.com/a.jpg", "https://e.com/b.png"]))
        fake = FakeThreads()
        publish.publish_due(lambda: self.client(fake), self.store, self.settings, NOW)
        posts = [p for m, path, p in fake.calls if m == "POST" and path.endswith("/threads")]
        self.assertEqual([p.get("is_carousel_item") for p in posts[:2]], ["true", "true"])
        self.assertEqual(posts[2]["media_type"], "CAROUSEL")
        self.assertEqual(posts[2]["children"], "c1,c2")
        self.assertTrue((self.root / "posted" / "c.json").exists())


class ValidateTests(Base):
    def test_rules(self):
        (self.root / "config").mkdir()
        (self.root / "config" / "ng_words.txt").write_text("# comment\n社外秘\n", encoding="utf-8")
        write_json(self.root / "posted" / "p.json", {"text": "公開済み"})
        self.enqueue("ng", queue_item("これは社外秘です"))
        self.enqueue("dup", queue_item("公開済み"))
        self.enqueue("tz", queue_item("ok", scheduled_at="2026-10-01T08:00:00"))
        self.enqueue("fmt", queue_item("ok2", format_id="F99"))
        res = validate_queue(self.store)
        self.assertTrue(any("NGワード" in e for e in res["ng.json"][0]))
        self.assertTrue(any("公開済み" in e for e in res["dup.json"][0]))
        self.assertTrue(any("scheduled_at" in e for e in res["tz.json"][0]))
        self.assertEqual(res["fmt.json"][0], [])
        self.assertTrue(any("F99" in w for w in res["fmt.json"][1]))

    def test_identity_terms_and_pr_notice(self):
        (self.root / "config").mkdir()
        (self.root / "config" / "identity_terms.txt").write_text(
            "# comment\nFA営業: FA|ファクトリーオートメーション\n人材開発: 人材開発|研修(担当|企画)\n", encoding="utf-8"
        )
        self.enqueue("one", queue_item("FA営業で身につく力", replies=["顧客は工場です"]))
        self.enqueue("two", queue_item("FA営業の話", replies=["今は研修企画をしています"]))
        self.enqueue("link", queue_item("おすすめの本", replies=["https://example.com"]))
        self.enqueue("pr", queue_item("PR おすすめの本", replies=["https://example.com"]))
        res = validate_queue(self.store)
        self.assertEqual(res["one.json"][0], [])
        self.assertTrue(any("身バレ" in e for e in res["two.json"][0]))
        self.assertTrue(any("PR" in w for w in res["link.json"][1]))
        self.assertFalse(any("PR" in w for w in res["pr.json"][1]))

    def test_evidence_ids_must_point_to_usable_facts(self):
        write_json(
            self.root / "knowledge" / "facts" / "light.json",
            [{"id": "K-light-001", "status": "verified"}, {"id": "K-light-002", "status": "myth"}],
        )
        self.enqueue("ok", queue_item("電球色は2600〜3250K", evidence_ids=["K-light-001"]))
        self.enqueue("myth", queue_item("電球色は暗い", evidence_ids=["K-light-002"]))
        self.enqueue("missing", queue_item("60形は810lm", evidence_ids=["K-light-999"]))
        self.enqueue("noev", queue_item("60形は810lm以上"))
        res = validate_queue(self.store)
        self.assertEqual(res["ok.json"][0], [])
        self.assertTrue(any("myth" in e for e in res["myth.json"][0]))
        self.assertTrue(any("ありません" in e for e in res["missing.json"][0]))
        self.assertTrue(any("evidence_ids" in w for w in res["noev.json"][1]))

    def test_two_second_rule_warnings(self):
        self.enqueue("long", queue_item("電球色なのに、ウォルナットや料理がくすんで見える照明は「Ra」が低いです。"))
        self.enqueue("short", queue_item("料理がまずそうに見える照明、ある。\n差は箱の小さな数字ひとつ。"))
        res = validate_queue(self.store)
        self.assertTrue(any("1行目" in w for w in res["long.json"][1]))
        self.assertTrue(any("専門用語" in w for w in res["long.json"][1]))
        self.assertFalse(any("1行目" in w or "専門用語" in w or "本文が" in w for w in res["short.json"][1]))

    def test_image_url_must_be_https(self):
        self.enqueue("img", queue_item("画像", image_url="http://example.com/a.png"))
        res = validate_queue(self.store)
        self.assertTrue(any("image_url" in e for e in res["img.json"][0]))


class SlotTests(Base):
    def test_weekend_slots(self):
        self.settings.values["posting_slots"] = ["07:15", "12:05", "21:00"]
        self.settings.values["posting_slots_weekend"] = ["09:45", "13:00", "21:00"]
        tz = self.settings.tz
        friday_night = datetime(2026, 10, 9, 22, 0, tzinfo=tz)  # 金曜22時
        slots = publish.next_free_slots(self.store, self.settings, friday_night, 4)
        self.assertEqual([s.strftime("%a %H:%M") for s in slots], ["Sat 09:45", "Sat 13:00", "Sat 21:00", "Sun 09:45"])
        monday = publish.next_free_slots(self.store, self.settings, datetime(2026, 10, 12, 6, 0, tzinfo=tz), 1)
        self.assertEqual(monday[0].strftime("%a %H:%M"), "Mon 07:15")


class AnalyticsTests(Base):
    def test_parse_insights_both_shapes(self):
        res = {"data": [{"name": "views", "values": [{"value": 10}]}, {"name": "likes", "total_value": {"value": 2}}]}
        self.assertEqual(parse_insights(res), {"views": 10, "likes": 2})

    def test_fetch_and_score_loop(self):
        specs = [("F01", ["A"], 1000), ("F01", ["A"], 800), ("F01", ["B"], 900), ("F02", ["B"], 100), ("F02", ["B"], 200)]
        views = {}
        for i, (fmt, tags, v) in enumerate(specs):
            mid = f"m{i}"
            views[mid] = v
            write_json(
                self.root / "posted" / f"p{i}.json",
                {"text": f"t{i}", "media_id": mid, "format_id": fmt, "tags": tags, "published_at": (NOW - timedelta(days=3)).isoformat()},
            )
        write_json(self.root / "posted" / "young.json", {"text": "y", "media_id": "my", "format_id": "F02", "published_at": (NOW - timedelta(hours=5)).isoformat()})
        write_json(self.root / "ideas.json", [{"id": "I1", "tags": ["A"], "status": "unused"}, {"id": "I2", "tags": ["B"], "status": "unused"}])

        analytics.fetch_insights(self.client(FakeThreads(views=views)), self.store, self.settings, NOW)
        self.assertEqual(json.loads((self.root / "posted" / "p0.json").read_text())["metrics"]["views"], 1000)
        self.assertTrue((self.root / "metrics" / "history.jsonl").exists())

        w = analytics.update_weights(self.store, self.settings, NOW)
        self.assertEqual(w["sample_size"], 5)  # young は経過時間不足で除外
        self.assertEqual(w["formats"]["F01"]["rank"], 1)
        self.assertLess(w["formats"]["F02"]["score"], 1.0)
        fmts = {f["id"]: f for f in json.loads((self.root / "formats.json").read_text())}
        self.assertEqual(fmts["F01"]["rank"], 1)
        ideas = {i["id"]: i for i in json.loads((self.root / "ideas.json").read_text())}
        self.assertGreater(ideas["I1"]["weight"], ideas["I2"]["weight"])
        self.assertTrue(Path(w["report_path"]).read_text().startswith("# Threads 週次レポート"))
        learning = json.loads((self.root / "learning.json").read_text())
        self.assertEqual(learning["sample_size"], 5)
        self.assertEqual(learning["features"]["pillar"]["A"]["n"], 2)
        self.assertEqual(learning["features"]["pillar"]["A"]["decision"], "検証中")
        self.assertEqual(learning["followers"]["followers"], 42)
        self.assertIn("特徴別の傾向", Path(w["report_path"]).read_text())

    def test_eval_snapshot_at_24h(self):
        published = NOW - timedelta(hours=30)
        write_json(
            self.root / "posted" / "p.json",
            {"text": "t", "media_id": "m", "format_id": "F01", "published_at": published.isoformat(),
             "metrics": {"views": 100, "likes": 2, "age_hours": 6.0}},
        )
        analytics.fetch_insights(self.client(FakeThreads(views={"m": 500})), self.store, self.settings, NOW)
        item = json.loads((self.root / "posted" / "p.json").read_text())
        # 6h で100、30h で500 → 24h 時点は 100 + 400 × 18/24 = 400
        self.assertEqual(item["eval_metrics"]["views"], 400)
        self.assertEqual(item["eval_metrics"]["method"], "interpolated")
        # 一度決まった 24h 時点の値は、その後の取得で変わらない
        analytics.fetch_insights(self.client(FakeThreads(views={"m": 900})), self.store, self.settings, NOW + timedelta(days=1))
        item = json.loads((self.root / "posted" / "p.json").read_text())
        self.assertEqual(item["eval_metrics"]["views"], 400)
        self.assertEqual(item["metrics"]["views"], 900)

    def test_empty_report(self):
        w = analytics.update_weights(self.store, self.settings, NOW)
        self.assertEqual(w["sample_size"], 0)


class DiscordTests(Base):
    def test_incremental_ingest(self):
        pages = [
            [{"id": "3", "content": "メモ3", "author": {"username": "u"}}, {"id": "2", "content": "メモ2", "author": {"username": "u"}}, {"id": "1", "content": "bot", "author": {"bot": True}}],
            [],
        ]
        seen = []

        def fake(method, url, body, headers):
            seen.append(url)
            self.assertEqual(headers["Authorization"], "Bot tok")
            return 200, pages.pop(0) if pages else []

        self.assertEqual(ingest_channel(self.store, "tok", "c1", transport=fake), 2)
        self.assertIn("after=0", seen[0])
        self.assertEqual(json.loads((self.root / "knowledge" / "discord_state.json").read_text())["c1"], "3")


if __name__ == "__main__":
    unittest.main()
