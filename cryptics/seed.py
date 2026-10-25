"""Seed the local database with the published cryptics.georgeho.org dataset.

The published dataset (last updated July 2023) contains ~660k clues, but no raw
HTML. We copy its clues into the local `clues` table, and record each source
URL in the `raw` table (with `content_type = 'seed'`) so that the scrapers know
not to scrape those blog posts again.
"""
from __future__ import annotations

import logging
import os
import sqlite3

import requests

from cryptics.config import HEADERS, INITIALIZE_DB_SQL, PROJECT_DIR, SQLITE_DATABASE
from cryptics.utils import get_logger

BASELINE_URL = "https://cryptics.georgeho.org/data.db"
DOWNLOADS_DIR = os.path.join(PROJECT_DIR, "downloads")
BASELINE_PATH = os.path.join(DOWNLOADS_DIR, "georgeho-data.db")
BASELINE_COLUMNS = [
    "clue",
    "answer",
    "definition",
    "clue_number",
    "puzzle_date",
    "puzzle_name",
    "source_url",
    "source",
]


def download(url: str, path: str, logger: logging.Logger):
    if os.path.exists(path):
        logger.info(f"Already downloaded: {path}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    logger.info(f"Downloading {url} to {path}")
    with requests.get(url, headers=HEADERS, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(path + ".part", "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    os.replace(path + ".part", path)


def initialize_db():
    with open(INITIALIZE_DB_SQL) as f:
        sql = f.read()
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        conn.executescript(sql)
        # Write-ahead logging allows scraping several sources in parallel.
        conn.execute("PRAGMA journal_mode=WAL;")


def seed(logger: logging.Logger | None = None):
    if logger is None:
        logger = get_logger()

    initialize_db()
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        (num_seeded,) = conn.execute(
            "SELECT COUNT(*) FROM raw WHERE content_type = 'seed';"
        ).fetchone()
    if num_seeded:
        logger.info(f"Database already seeded ({num_seeded} source URLs), skipping")
        return

    download(BASELINE_URL, BASELINE_PATH, logger)

    columns = ", ".join(BASELINE_COLUMNS)
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        conn.execute("ATTACH DATABASE ? AS baseline;", (BASELINE_PATH,))
        conn.execute(
            f"INSERT INTO clues ({columns}) SELECT {columns} FROM baseline.clues ORDER BY rowid;"
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO raw (source, location, content_type, is_parsed, datetime_parsed)
            SELECT source, source_url, 'seed', TRUE, datetime('now')
            FROM baseline.clues
            GROUP BY source, source_url;
            """
        )
        conn.commit()
        (num_clues,) = conn.execute("SELECT COUNT(*) FROM clues;").fetchone()
    logger.info(f"Seeded database with baseline dataset: {num_clues} clues")


if __name__ == "__main__":
    seed()
