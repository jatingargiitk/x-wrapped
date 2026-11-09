import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

from xwrapped.archive import ArchiveError, load_archive, parse_ytd
from xwrapped.card import render_svg
from xwrapped.cli import main
from xwrapped.stats import compute, longest_streak, parse_tz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "examples", "sample-archive")


def tw(i, when, text="hello world", likes=0, rts=0, reply_to=None, tags=()):
    return {"tweet": {
        "id_str": str(i), "created_at": when.strftime("%a %b %d %H:%M:%S +0000 %Y"),
        "full_text": text, "favorite_count": str(likes), "retweet_count": str(rts),
        "in_reply_to_screen_name": reply_to,
        "entities": {"hashtags": [{"text": t} for t in tags], "user_mentions": []},
    }}


def write_archive(d, items, username="me", fname="tweets.js", var="tweets"):
    os.makedirs(os.path.join(d, "data"), exist_ok=True)
    with open(os.path.join(d, "data", fname), "w") as f:
        f.write("window.YTD.%s.part0 = %s" % (var, json.dumps(items)))
    with open(os.path.join(d, "data", "account.js"), "w") as f:
        f.write("window.YTD.account.part0 = " + json.dumps([{"account": {"username": username}}]))


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


class TestArchive(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_parse_ytd_wrapper(self):
        self.assertEqual(parse_ytd('window.YTD.tweets.part0 = [{"a": 1}];'), [{"a": 1}])

    def test_folder_zip_and_old_filename(self):
        base = datetime(2026, 10, 1, tzinfo=timezone.utc)
        write_archive(self.d, [tw(1, base), tw(2, base + timedelta(days=1))], fname="tweet.js", var="tweet")
        acct, tweets = load_archive(self.d)
        self.assertEqual(acct["username"], "me")
        self.assertEqual([t["id"] for t in tweets], ["1", "2"])
        z = os.path.join(self.d, "a.zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.write(os.path.join(self.d, "data", "tweet.js"), "twitter-2026/data/tweet.js")
            zf.write(os.path.join(self.d, "data", "account.js"), "twitter-2026/data/account.js")
        self.assertEqual(len(load_archive(z)[1]), 2)

    def test_multi_part_and_deleted_ignored(self):
        base = datetime(2026, 10, 1, tzinfo=timezone.utc)
        write_archive(self.d, [tw(1, base)])
        with open(os.path.join(self.d, "data", "tweets-part1.js"), "w") as f:
            f.write("window.YTD.tweets.part1 = " + json.dumps([tw(2, base)]))
        with open(os.path.join(self.d, "data", "deleted-tweets.js"), "w") as f:
            f.write("window.YTD.deleted_tweets.part0 = " + json.dumps([tw(3, base)]))
        self.assertEqual(sorted(t["id"] for t in load_archive(self.d)[1]), ["1", "2"])

    def test_not_an_archive(self):
        with self.assertRaises(ArchiveError):
            load_archive(self.d)


class TestStats(unittest.TestCase):
    def test_window_kinds_and_self_thread(self):
        until = datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc)
        items = [
            tw(1, until - timedelta(days=40), likes=999),               # outside window
            tw(2, until - timedelta(days=3), likes=10, rts=2, tags=["AI"]),
            tw(3, until - timedelta(days=3, minutes=-1), likes=4, reply_to="me"),  # self thread = post
            tw(4, until - timedelta(days=2), likes=1, reply_to="bob"),
            tw(5, until - timedelta(days=1), text="RT @x: hi"),
        ]
        from xwrapped.archive import normalize
        s = compute([normalize(i) for i in items], days=30, until=until, handle="me")
        self.assertEqual((s["posts"], s["replies"], s["reposts"], s["total"]), (2, 1, 1, 4))
        self.assertEqual(s["likes_received"], 15)
        self.assertEqual(s["top_post"]["id"], "2")
        self.assertEqual(s["top_reply_targets"], [{"name": "bob", "count": 1}])
        self.assertEqual(s["top_hashtags"], [{"name": "ai", "count": 1}])
        self.assertEqual(s["longest_streak"], 3)
        self.assertEqual(s["start"], "2026-10-02")

    def test_tz_shifts_hour_and_day(self):
        from xwrapped.archive import normalize
        t = normalize(tw(1, datetime(2026, 10, 10, 20, 0, tzinfo=timezone.utc)))
        until = datetime(2026, 10, 31, tzinfo=timezone.utc)
        self.assertEqual(compute([t], until=until)["busiest_hour"], 20)
        s = compute([t], until=until, tz=parse_tz("+05:30"))
        self.assertEqual((s["busiest_hour"], s["busiest_weekday"]), (1, "Sunday"))

    def test_streak_and_tz_parse(self):
        d = datetime(2026, 1, 1).date()
        self.assertEqual(longest_streak([d, d + timedelta(1), d + timedelta(3)]), 2)
        self.assertEqual(parse_tz("-0800").utcoffset(None), timedelta(hours=-8))
        with self.assertRaises(ValueError):
            parse_tz("IST")


class TestCli(unittest.TestCase):
    def test_sample_text_json_svg(self):
        d = tempfile.mkdtemp()
        try:
            svg = os.path.join(d, "card.svg")
            rc, out, err = run([SAMPLE, "--until", "2026-10-31", "--tz", "+05:30", "-o", svg])
            self.assertEqual(rc, 0)
            self.assertIn("@sample_dev, last 30 days (2026-10-02 to 2026-10-31)", out)
            with open(svg) as fh:
                body = fh.read()
            self.assertTrue(body.startswith("<svg"))
            self.assertIn("@sample_dev, wrapped", body)
            rc, out, _ = run([SAMPLE, "--until", "2026-10-31", "--days", "90", "--json"])
            s = json.loads(out)
            self.assertEqual(s["top_post"]["likes"], 412)
            self.assertEqual(s["total"], s["posts"] + s["replies"] + s["reposts"])
        finally:
            shutil.rmtree(d)

    def test_png(self):
        try:
            import cairosvg  # noqa: F401
        except ImportError:
            self.skipTest("cairosvg not installed")
        d = tempfile.mkdtemp()
        try:
            png = os.path.join(d, "card.png")
            rc, _, _ = run([SAMPLE, "--until", "2026-10-31", "--png", png])
            self.assertEqual(rc, 0)
            with open(png, "rb") as fh:
                self.assertEqual(fh.read(8), b"\x89PNG\r\n\x1a\n")
        finally:
            shutil.rmtree(d)

    def test_empty_window_exit_1(self):
        rc, _, err = run([SAMPLE, "--until", "2020-01-01"])
        self.assertEqual(rc, 1)
        self.assertIn("no posts", err)

    def test_bad_path_exit_2(self):
        rc, _, err = run(["/nonexistent/archive"])
        self.assertEqual(rc, 2)

    def test_svg_escapes_text(self):
        from xwrapped.archive import normalize
        until = datetime(2026, 10, 31, tzinfo=timezone.utc)
        t = normalize(tw(1, until - timedelta(days=1), text="<script>&\"x\"", likes=5))
        svg = render_svg(compute([t], until=until, handle="a&b"))
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;script&gt;", svg)
        import xml.dom.minidom
        xml.dom.minidom.parseString(svg)  # well-formed


if __name__ == "__main__":
    unittest.main()
