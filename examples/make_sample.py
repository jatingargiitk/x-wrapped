"""Generate examples/sample-archive: a small, synthetic X archive in the official file format.

All posts and accounts here are made up. Run: python examples/make_sample.py
"""
import json
import os
import random
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample-archive", "data")

TEXTS = [
    "Shipped a tiny CLI today that diffs agent sessions #buildinpublic",
    "Hot take: most agent evals measure the harness, not the model",
    "Wrote tests first, let the agent fill in the code. Tests caught two bugs",
    "Spent the morning reading git worktree docs. Parallel agents need them",
    "New post: why your coding agent keeps reading .env files #security",
    "Python packaging is fine once you stop fighting setuptools",
    "Agent memory is just a cache with opinions",
    "Benchmarks without error bars are vibes #ai",
]
REPLY_TARGETS = ["alice_codes", "bob_builds", "alice_codes", "carol_ml"]


def tweet(i, when, text, likes, rts, reply_to=None, hashtags=(), mentions=()):
    return {"tweet": {
        "id_str": str(1850000000000000000 + i),
        "created_at": when.strftime("%a %b %d %H:%M:%S +0000 %Y"),
        "full_text": text,
        "favorite_count": str(likes),
        "retweet_count": str(rts),
        "in_reply_to_screen_name": reply_to,
        "entities": {
            "hashtags": [{"text": h} for h in hashtags],
            "user_mentions": [{"screen_name": m} for m in mentions],
        },
    }}


def build():
    rng = random.Random(7)
    start = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)
    items = []
    i = 0
    for day in range(92):
        if rng.random() < 0.35:
            continue
        for _ in range(rng.randint(1, 3)):
            when = start + timedelta(days=day, hours=rng.randint(0, 14), minutes=rng.randint(0, 59))
            kind = rng.random()
            if kind < 0.55:
                text = rng.choice(TEXTS)
                tags = [w[1:] for w in text.split() if w.startswith("#")]
                items.append(tweet(i, when, text, rng.randint(0, 40), rng.randint(0, 6), hashtags=tags))
            elif kind < 0.85:
                who = rng.choice(REPLY_TARGETS)
                items.append(tweet(i, when, "@%s agreed, the tests are the spec" % who,
                                   rng.randint(0, 5), 0, reply_to=who, mentions=[who]))
            else:
                items.append(tweet(i, when, "RT @carol_ml: Calibration plots or it didn't happen", 0, 0,
                                   mentions=["carol_ml"]))
            i += 1
    # One clear standout post, plus a self-reply thread continuation.
    best = start + timedelta(days=80, hours=5)
    items.append(tweet(i, best, "I let an agent run for 6 hours and diffed my laptop before/after. Thread:",
                       412, 57))
    items.append(tweet(i + 1, best + timedelta(minutes=2), "It touched 14 files outside the repo.",
                       88, 9, reply_to="sample_dev"))
    return items


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "tweets.js"), "w") as f:
        f.write("window.YTD.tweets.part0 = " + json.dumps(build(), indent=2))
    with open(os.path.join(OUT, "account.js"), "w") as f:
        f.write("window.YTD.account.part0 = " + json.dumps(
            [{"account": {"username": "sample_dev", "accountDisplayName": "Sample Dev"}}], indent=2))


if __name__ == "__main__":
    main()
