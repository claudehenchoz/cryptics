"""Scrape and parse cryptic crosswords from The Guardian.

The Guardian serves every crossword (including solutions, once they are
available) as JSON at https://www.theguardian.com/crosswords/<series>/<n>.json.
Unlike the blog sources, there is no need to parse HTML: clues and answers are
structured data. There are no definitions or annotations, though.

The cryptic and prize series share the same numbering, so for each number in
that range we try the cryptic first, and then the prize.
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from cryptics.config import SQLITE_DATABASE
from cryptics.generic import ENUMERATION
from cryptics.scrape_blogs import get_session
from cryptics.utils import get_logger

BASE_URL = "https://www.theguardian.com/crosswords"

# Groups of series sharing a numbering scheme, and the first number to try.
# The Guardian's online archive of cryptics starts at No 21,620 (January 1999).
# The Everyman archive goes back to No 1 (1945), with many gaps.
SERIES_GROUPS: dict[str, tuple[list[str], int]] = {
    "cryptic": (["cryptic", "prize"], 21620),
    "quiptic": (["quiptic"], 1),
    "everyman": (["everyman"], 1),
}


def puzzle_url(series: str, number: int) -> str:
    return f"{BASE_URL}/{series}/{number}"


def get_latest_number(session, series: list[str]) -> int:
    latest = 0
    for s in series:
        response = session.get(f"{BASE_URL}/series/{s}", timeout=60)
        response.raise_for_status()
        numbers = [int(n) for n in re.findall(rf"/crosswords/{s}/(\d+)", response.text)]
        latest = max([latest] + numbers)
    return latest


def get_known_numbers(series: list[str]) -> set[int]:
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        cursor = conn.cursor()
        known: set[int] = set()
        for s in series:
            cursor.execute(
                "SELECT location FROM raw WHERE location LIKE ?;",
                (f"{BASE_URL}/{s}/%",),
            )
            known.update(int(url.rsplit("/", 1)[-1]) for url, in cursor.fetchall())
    return known


def insert_raw(source: str, location: str, content_type: str, content: str | None):
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO raw (source, location, content_type, content, is_parsed) VALUES (?, ?, ?, ?, ?)",
            (source, location, content_type, content, content is None),
        )
        conn.commit()


def scrape_guardian(
    groups: list[str] | None = None,
    sleep_interval: float = 1,
    limit: int | None = None,
    logger: logging.Logger | None = None,
):
    if logger is None:
        logger = get_logger()
    session = get_session()

    for group in groups or list(SERIES_GROUPS):
        series, first_number = SERIES_GROUPS[group]
        latest = get_latest_number(session, series)
        known = get_known_numbers(series)
        numbers = [n for n in range(latest, first_number - 1, -1) if n not in known]
        if limit is not None:
            numbers = numbers[:limit]
        logger.info(f"Scraping guardian {group}: {len(numbers)} puzzles to try")

        for i, number in enumerate(numbers):
            found = False
            for s in series:
                url = puzzle_url(s, number)
                try:
                    response = session.get(url + ".json", timeout=60)
                except Exception:
                    logger.error(f"Error requesting: {url}", exc_info=True)
                    found = True  # Don't record as missing; retry next time.
                    break
                time.sleep(sleep_interval)
                if response.status_code == 404:
                    continue
                if not response.ok:
                    logger.error(f"Response not OK ({response.status_code}): {url}")
                    found = True
                    break
                crossword = response.json().get("crossword")
                if crossword is None:
                    continue
                found = True
                # Prize puzzles' solutions are only published after the
                # closing date: skip them, so they're retried next time.
                if not any("solution" in entry for entry in crossword["entries"]):
                    logger.info(f"No solutions available yet: {url}")
                    break
                logger.info(f"Requested {i}/{len(numbers)}: {url}")
                insert_raw(f"guardian_{s}", url, "guardian_json", json.dumps(crossword))
                break
            if not found:
                # Record misses, so we don't request them again.
                insert_raw(f"guardian_{group}", puzzle_url(series[0], number), "missing", None)


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def format_answer(letters: str, clue: str, separators: dict[str, list[int]]) -> str:
    """Format an answer with spaces and hyphens, using the clue's enumeration
    if possible, or else the entry's separator locations."""
    enumerations = list(ENUMERATION.finditer(clue))
    if enumerations:
        enumeration = enumerations[-1].group("enum")
        lengths = [int(n) for n in re.findall(r"\d+", enumeration)]
        if sum(lengths) == len(letters):
            joiners = re.findall(r"\d+\s*([-,.\s])?", enumeration)
            answer, position = "", 0
            for length, joiner in zip(lengths, joiners):
                answer += letters[position : position + length]
                position += length
                if position < len(letters):
                    answer += "-" if joiner.strip() == "-" else " "
            return answer
    positions = sorted(
        [(p, "-" if separator == "-" else " ") for separator, ps in separators.items() for p in ps],
        reverse=True,
    )
    for position, joiner in positions:
        if 0 < position < len(letters):
            letters = letters[:position] + joiner + letters[position:]
    return letters


def parse_guardian(crossword: dict, url: str) -> pd.DataFrame | None:
    if not crossword.get("solutionAvailable", True):
        return None
    entries = {entry["id"]: entry for entry in crossword["entries"]}
    rows = []
    for entry in crossword["entries"]:
        group = entry.get("group") or [entry["id"]]
        # Clues spanning several entries are given on the first entry only.
        if group[0] != entry["id"]:
            continue
        if any("solution" not in entries.get(id_, {}) for id_ in group):
            return None
        clue = strip_html(entry["clue"])
        letters = "".join(entries[id_]["solution"] for id_ in group)
        separators = entry.get("separatorLocations", {}) if len(group) == 1 else {}
        rows.append(
            {
                "clue_number": entry["humanNumber"].replace(" ", "")
                + entry["direction"][0],
                "clue": clue,
                "answer": format_answer(letters.upper(), clue, separators),
                "definition": None,
                "annotation": None,
            }
        )
    if not rows:
        return None
    data = pd.DataFrame(rows)
    data["puzzle_name"] = crossword.get("name")
    # Not datetime.fromtimestamp: it fails for pre-1970 dates on Windows.
    data["puzzle_date"] = (
        datetime(1970, 1, 1, tzinfo=timezone.utc)
        + timedelta(milliseconds=crossword["date"])
    ).strftime("%Y-%m-%d")
    data["puzzle_url"] = url
    data["source_url"] = url
    return data


def parse_unparsed_guardian(logger: logging.Logger | None = None):
    if logger is None:
        logger = get_logger()

    with sqlite3.connect(SQLITE_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT location FROM raw WHERE content_type = 'guardian_json' AND NOT is_parsed;"
        )
        urls = [url for url, in cursor.fetchall()]

    for i, url in enumerate(urls):
        with sqlite3.connect(SQLITE_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content, source FROM raw WHERE location = ?;", (url,))
            content, source = cursor.fetchone()

        try:
            data = parse_guardian(json.loads(content), url)
        except Exception:
            logger.error(f"Failed to parse: {url}", exc_info=True)
            continue
        if data is None:
            logger.warning(f"No solutions available: {url}")
            continue

        data["source"] = source
        with sqlite3.connect(SQLITE_DATABASE) as conn:
            data.to_sql("clues", conn, if_exists="append", index=False)
            conn.execute(
                "UPDATE raw SET is_parsed = TRUE, datetime_parsed = datetime('now') WHERE location = ?;",
                (url,),
            )
        logger.info(f"Parsed {i}/{len(urls)}: {url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape", dest="scrape", action="store_true")
    parser.add_argument("--no-scrape", dest="scrape", action="store_false")
    parser.set_defaults(scrape=True)
    parser.add_argument(
        "--groups", nargs="+", choices=list(SERIES_GROUPS), default=list(SERIES_GROUPS)
    )
    parser.add_argument("--sleep-interval", type=float, default=1)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.scrape:
        scrape_guardian(args.groups, args.sleep_interval, args.limit)
    parse_unparsed_guardian()
