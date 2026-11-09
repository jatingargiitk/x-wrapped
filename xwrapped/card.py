"""Render stats as a 1200x675 SVG card (X's large-image aspect ratio)."""
from xml.sax.saxutils import escape

W, H = 1200, 675


def _fmt(n):
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 10_000:
        return "%.1fK" % (n / 1000)
    return "{:,}".format(n)


def _clip(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "\u2026"


def _hour(h):
    if h is None:
        return "-"
    suffix = "am" if h < 12 else "pm"
    return "%d%s" % ((h % 12) or 12, suffix)


def render_svg(s):
    who = "@" + s["handle"] if s["handle"] else "My X"
    tiles = [
        ("posts", _fmt(s["posts"])),
        ("replies", _fmt(s["replies"])),
        ("likes received", _fmt(s["likes_received"])),
        ("reposts received", _fmt(s["reposts_received"])),
        ("active days", "%d/%d" % (s["active_days"], s["days"])),
        ("longest streak", "%d day%s" % (s["longest_streak"], "" if s["longest_streak"] == 1 else "s")),
    ]
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#0f172a"/><stop offset="1" stop-color="#1e1b4b"/></linearGradient></defs>',
        '<rect width="100%" height="100%" fill="url(#bg)"/>',
        '<g font-family="Inter, Helvetica, Arial, sans-serif" fill="#f8fafc">',
        '<text x="60" y="95" font-size="44" font-weight="700">%s, wrapped</text>' % escape(who),
        '<text x="60" y="140" font-size="24" fill="#94a3b8">last %d days \u00b7 %s to %s</text>'
        % (s["days"], s["start"], s["end"]),
    ]
    for i, (label, value) in enumerate(tiles):
        col, row = i % 3, i // 3
        x, y = 60 + col * 370, 190 + row * 140
        out.append('<rect x="%d" y="%d" width="340" height="115" rx="18" fill="#ffffff" fill-opacity="0.07"/>' % (x, y))
        out.append('<text x="%d" y="%d" font-size="46" font-weight="700">%s</text>' % (x + 24, y + 62, escape(value)))
        out.append('<text x="%d" y="%d" font-size="20" fill="#94a3b8">%s</text>' % (x + 24, y + 96, escape(label)))

    y = 500
    if s["top_post"]:
        tp = s["top_post"]
        out.append('<text x="60" y="%d" font-size="20" fill="#a5b4fc">TOP POST \u00b7 %s likes \u00b7 %s</text>'
                   % (y, _fmt(tp["likes"]), tp["date"]))
        out.append('<text x="60" y="%d" font-size="26">\u201c%s\u201d</text>' % (y + 38, escape(_clip(tp["text"], 76))))
    facts = []
    if s["busiest_weekday"]:
        facts.append("most active: %ss around %s" % (s["busiest_weekday"], _hour(s["busiest_hour"])))
    if s["top_reply_targets"]:
        facts.append("most replied to: @%s" % s["top_reply_targets"][0]["name"])
    if s["top_hashtags"]:
        facts.append("#%s" % s["top_hashtags"][0]["name"])
    if facts:
        out.append('<text x="60" y="%d" font-size="22" fill="#cbd5e1">%s</text>' % (y + 95, escape(_clip("  \u00b7  ".join(facts), 95))))
    out.append('<text x="1140" y="645" font-size="16" fill="#64748b" text-anchor="end">made offline with x-wrapped</text>')
    out.append("</g></svg>")
    return "\n".join(out) + "\n"


def render_text(s):
    who = "@" + s["handle"] if s["handle"] else "your account"
    lines = [
        "%s, last %d days (%s to %s)" % (who, s["days"], s["start"], s["end"]),
        "  posts            %s" % _fmt(s["posts"]),
        "  replies          %s" % _fmt(s["replies"]),
        "  reposts          %s" % _fmt(s["reposts"]),
        "  likes received   %s" % _fmt(s["likes_received"]),
        "  reposts received %s" % _fmt(s["reposts_received"]),
        "  avg likes/post   %s" % s["avg_likes_per_post"],
        "  active days      %d/%d (longest streak %d)" % (s["active_days"], s["days"], s["longest_streak"]),
    ]
    if s["busiest_weekday"]:
        lines.append("  most active      %ss around %s" % (s["busiest_weekday"], _hour(s["busiest_hour"])))
    if s["top_post"]:
        tp = s["top_post"]
        lines.append("  top post         %s likes, %s: %s" % (_fmt(tp["likes"]), tp["date"], _clip(tp["text"], 60)))
    if s["top_reply_targets"]:
        lines.append("  most replied to  " + ", ".join("@%(name)s (%(count)d)" % kv for kv in s["top_reply_targets"]))
    if s["top_hashtags"]:
        lines.append("  top hashtags     " + ", ".join("#%(name)s (%(count)d)" % kv for kv in s["top_hashtags"]))
    if s["top_words"]:
        lines.append("  top words        " + ", ".join("%(name)s (%(count)d)" % kv for kv in s["top_words"]))
    return "\n".join(lines)
