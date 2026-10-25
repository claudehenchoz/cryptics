"""Build or update the local cryptics database, end to end.

Usage:
    python -m cryptics.update all
    python -m cryptics.update blogs --sources timesforthetimes --limit 10
    python -m cryptics.update guardian
    python -m cryptics.update export

Steps:
    seed        Import the published cryptics.georgeho.org dataset (once).
    cryptonite  Import the Cryptonite research dataset (once).
    blogs       Scrape new blog posts and parse them into clues.
    guardian    Scrape new Guardian crosswords and parse them into clues.
    export      Write exports/clues.csv.gz and exports/clues-unique.csv.gz.
    all         All of the above, in order.

Every step is resumable: raw responses are saved before parsing, and already
scraped URLs are skipped.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from cryptics.config import BLOG_SOURCES
from cryptics.cryptonite import import_cryptonite
from cryptics.export import export
from cryptics.guardian import SERIES_GROUPS, parse_unparsed_guardian, scrape_guardian
from cryptics.main import parse_unparsed_html
from cryptics.scrape_blogs import scrape_blogs
from cryptics.seed import seed
from cryptics.utils import get_logger

STEPS = ["seed", "cryptonite", "blogs", "guardian", "export"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("steps", nargs="+", choices=STEPS + ["all"])
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=list(BLOG_SOURCES),
        # thenationcryptic posts only give answers and wordplay, not clue
        # text, so the parsers produce nothing useful from them.
        default=[source for source in BLOG_SOURCES if source != "thenationcryptic"],
        help="Blog sources to scrape (for the blogs step).",
    )
    parser.add_argument(
        "--guardian-groups",
        nargs="+",
        choices=list(SERIES_GROUPS),
        default=list(SERIES_GROUPS),
        help="Guardian series to scrape (for the guardian step).",
    )
    parser.add_argument("--sleep-interval", type=float, default=1)
    parser.add_argument(
        "--limit", type=int, default=None, help="Maximum new pages per source."
    )
    parser.add_argument(
        "--reparse-all",
        action="store_true",
        help="Retry parsing all unparsed blog posts, not just those scraped in this run.",
    )
    args = parser.parse_args()
    steps = STEPS if "all" in args.steps else args.steps

    logger = get_logger()
    # raw.datetime_requested is in UTC.
    started = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    if args.reparse_all:
        started = "1970-01-01"

    if "seed" in steps:
        seed(logger)
    if "cryptonite" in steps:
        import_cryptonite(logger)
    if "blogs" in steps:
        sources = {source: BLOG_SOURCES[source] for source in args.sources}
        scrape_blogs(sources, args.sleep_interval, args.limit, logger)  # type: ignore
        parse_unparsed_html(sources, datetime_requested=started, logger=logger)
    if "guardian" in steps:
        scrape_guardian(args.guardian_groups, args.sleep_interval, args.limit, logger)
        parse_unparsed_guardian(logger)
    if "export" in steps:
        export(logger)
