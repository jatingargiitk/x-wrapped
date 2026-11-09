"""Compute wrapped-style stats over a time window."""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_URL = re.compile(r"https?://\S+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")
STOPWORDS = set("""
the and for that this with you your are was were have has had not but they them their
from what when will would just like about into out more can all one get got its it's
than then there here been being also our ours his her she him who how why which some
any very really amp i'm don't can't i've i'll you're we're that's it’s
""".split())


def parse_tz(s):
    """'+05:30' / '-0800' / 'UTC' -> tzinfo."""
    if not s or s.upper() in ("UTC", "Z"):
        return timezone.utc
    m = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})?", s.strip())
    if not m:
        raise ValueError("bad --tz %r, use e.g. +05:30 or -08:00" % s)
    sign = 1 if m.group(1) == "+" else -1
    delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
    return timezone(sign * delta)


def window(tweets, days, until=None):
    """Tweets with until-days < created_at <= until. `until` defaults to now (UTC)."""
    until = until or datetime.now(timezone.utc)
    start = until - timedelta(days=days)
    return [t for t in tweets if start < t["created_at"] <= until], start, until


def longest_streak(dates):
    days = sorted(set(dates))
    best = cur = 0
    prev = None
    for d in days:
        cur = cur + 1 if prev is not None and (d - prev).days == 1 else 1
        best = max(best, cur)
        prev = d
    return best


def top_words(texts, n=5):
    c = Counter()
    for text in texts:
        text = _URL.sub(" ", text)
        for w in _WORD.findall(text):
            lw = w.lower()
            if lw not in STOPWORDS and not lw.startswith("@"):
                c[lw] += 1
    return c.most_common(n)


def _named(pairs):
    return [{"name": k, "count": v} for k, v in pairs]


def compute(tweets, days=30, until=None, tz=timezone.utc, handle=None):
    win, start, until = window(tweets, days, until)
    own = [t for t in win if not t["is_repost"]]
    def is_self_thread(t):
        return bool(handle) and t["reply_to"].lower() == handle.lower()

    # Replies to yourself are thread continuations, so they count as posts.
    originals = [t for t in own if not t["reply_to"] or is_self_thread(t)]
    replies = [t for t in own if t["reply_to"] and not is_self_thread(t)]
    local = [t["created_at"].astimezone(tz) for t in win]

    hours = Counter(d.hour for d in local)
    weekdays = Counter(d.weekday() for d in local)
    top = max(own, key=lambda t: (t["likes"], t["reposts"], t["created_at"]), default=None)
    reply_targets = Counter(
        t["reply_to"] for t in replies if t["reply_to"]
    )
    hashtags = Counter(h.lower() for t in own for h in t["hashtags"])
    active_days = len(set(d.date() for d in local))

    return {
        "handle": handle,
        "days": days,
        "start": (start + timedelta(seconds=1)).astimezone(tz).strftime("%Y-%m-%d"),
        "end": until.astimezone(tz).strftime("%Y-%m-%d"),
        "posts": len(originals),
        "replies": len(replies),
        "reposts": len(win) - len(own),
        "total": len(win),
        "likes_received": sum(t["likes"] for t in own),
        "reposts_received": sum(t["reposts"] for t in own),
        "avg_likes_per_post": round(sum(t["likes"] for t in originals) / len(originals), 1) if originals else 0,
        "active_days": active_days,
        "longest_streak": longest_streak(d.date() for d in local),
        "busiest_hour": hours.most_common(1)[0][0] if hours else None,
        "busiest_weekday": WEEKDAYS[weekdays.most_common(1)[0][0]] if weekdays else None,
        "top_post": None if top is None else {
            "id": top["id"],
            "text": top["text"],
            "likes": top["likes"],
            "reposts": top["reposts"],
            "date": top["created_at"].astimezone(tz).strftime("%Y-%m-%d"),
            "url": ("https://x.com/%s/status/%s" % (handle or "i/web", top["id"])) if top["id"] else None,
        },
        "top_reply_targets": _named(reply_targets.most_common(3)),
        "top_hashtags": _named(hashtags.most_common(3)),
        "top_words": _named(top_words([t["text"] for t in originals])),
    }
