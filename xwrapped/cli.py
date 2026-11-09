import argparse
import json
import sys
from datetime import datetime, time

from . import __version__
from .archive import ArchiveError, load_archive
from .card import render_svg, render_text
from .stats import compute, parse_tz


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="x-wrapped",
        description="Turn your X data archive (folder or .zip) into a shareable stats card. Runs offline.",
    )
    p.add_argument("archive", help="path to your X archive .zip or its unzipped folder")
    p.add_argument("--days", type=int, default=30, help="window length in days (default 30)")
    p.add_argument("--until", help="end date YYYY-MM-DD, inclusive (default: now)")
    p.add_argument("--tz", default="UTC", help="timezone offset for hours/days, e.g. +05:30 (default UTC)")
    p.add_argument("--handle", help="your handle without @ (default: read from data/account.js)")
    p.add_argument("-o", "--out", help="write the SVG card here, e.g. wrapped.svg")
    p.add_argument("--png", help="also write a PNG (needs: pip install 'x-wrapped[png]')")
    p.add_argument("--json", action="store_true", help="print stats as JSON instead of text")
    p.add_argument("--version", action="version", version="x-wrapped " + __version__)
    a = p.parse_args(argv)

    if a.days < 1:
        p.error("--days must be at least 1")
    try:
        tz = parse_tz(a.tz)
    except ValueError as e:
        p.error(str(e))
    until = None
    if a.until:
        try:
            d = datetime.strptime(a.until, "%Y-%m-%d").date()
        except ValueError:
            p.error("--until must be YYYY-MM-DD")
        until = datetime.combine(d, time(23, 59, 59), tzinfo=tz)

    try:
        account, tweets = load_archive(a.archive)
    except (ArchiveError, OSError) as e:
        print("x-wrapped: error: %s" % e, file=sys.stderr)
        return 2

    handle = a.handle or account.get("username")
    s = compute(tweets, days=a.days, until=until, tz=tz, handle=handle)
    if s["total"] == 0:
        print("x-wrapped: no posts in the last %d days ending %s (archive has %d posts total)"
              % (a.days, s["end"], len(tweets)), file=sys.stderr)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(render_svg(s))
    if a.png:
        try:
            import cairosvg
        except ImportError:
            print("x-wrapped: error: --png needs cairosvg: pip install 'x-wrapped[png]'", file=sys.stderr)
            return 2
        cairosvg.svg2png(bytestring=render_svg(s).encode("utf-8"), write_to=a.png)
        print("wrote %s" % a.png, file=sys.stderr)
    print(json.dumps(s, indent=2, ensure_ascii=False) if a.json else render_text(s))
    if a.out:
        print("wrote %s" % a.out, file=sys.stderr)
    return 0 if s["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
