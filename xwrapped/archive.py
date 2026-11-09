"""Read tweets and account info from an official X data archive (folder or .zip)."""
import json
import os
import re
import zipfile
from datetime import datetime

_PREFIX = re.compile(r"^\s*window\.YTD\.[A-Za-z0-9_]+\.part\d+\s*=\s*", re.S)
_TWEET_FILE = re.compile(r"(^|/)data/(tweets?|tweet)(-part\d+)?\.js$")
_ACCOUNT_FILE = re.compile(r"(^|/)data/account\.js$")


class ArchiveError(Exception):
    pass


def parse_ytd(text):
    """Parse the `window.YTD.<name>.partN = [...]` JS wrapper used by archive files."""
    body = _PREFIX.sub("", text, count=1).strip()
    if body.endswith(";"):
        body = body[:-1]
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise ArchiveError("could not parse archive file: %s" % e)
    if not isinstance(data, list):
        raise ArchiveError("archive file is not a list")
    return data


def _iter_files(path):
    """Yield (relative_name, text) for every file under a folder or inside a zip."""
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, path).replace(os.sep, "/")
                if rel.endswith(".js"):
                    with open(full, encoding="utf-8") as fh:
                        yield rel, fh.read()
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith(".js"):
                    yield name, z.read(name).decode("utf-8")
    else:
        raise ArchiveError("not a folder or zip archive: %s" % path)


def parse_created_at(s):
    # e.g. "Wed Oct 10 20:19:24 +0000 2018"
    return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def normalize(raw):
    t = raw.get("tweet", raw)
    text = t.get("full_text") or t.get("text") or ""
    ents = t.get("entities") or {}
    return {
        "id": str(t.get("id_str") or t.get("id") or ""),
        "created_at": parse_created_at(t["created_at"]),
        "text": text,
        "likes": _int(t.get("favorite_count")),
        "reposts": _int(t.get("retweet_count")),
        "reply_to": t.get("in_reply_to_screen_name") or None,
        "is_repost": text.startswith("RT @"),
        "hashtags": [h.get("text", "") for h in ents.get("hashtags", []) if h.get("text")],
        "mentions": [m.get("screen_name", "") for m in ents.get("user_mentions", []) if m.get("screen_name")],
    }


def load_archive(path):
    """Return (account_dict, list_of_normalized_tweets)."""
    account = {}
    tweets = []
    seen_tweet_file = False
    for name, text in _iter_files(path):
        if _TWEET_FILE.search(name):
            seen_tweet_file = True
            for item in parse_ytd(text):
                if "created_at" in item.get("tweet", item):
                    tweets.append(normalize(item))
        elif _ACCOUNT_FILE.search(name):
            items = parse_ytd(text)
            if items:
                account = items[0].get("account", items[0])
    if not seen_tweet_file:
        raise ArchiveError("no data/tweets.js found in %s (is this an X data archive?)" % path)
    tweets.sort(key=lambda t: t["created_at"])
    return account, tweets
