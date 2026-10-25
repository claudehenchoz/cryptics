from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Callable, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from cryptics.config import BLOG_SOURCES, HEADERS, SQLITE_DATABASE
from cryptics.utils import get_logger, normalize_url


def get_session() -> requests.Session:
    """A requests session that politely retries on transient errors."""
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=5,
        backoff_factor=5,
        status_forcelist=[429, 500, 502, 503, 504],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def get_known_urls(source: str) -> set[str]:
    """Normalized URLs that we've already scraped (or seeded) for a source."""
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT location FROM raw WHERE source = ? AND content_type IN ('html', 'seed');",
            (source,),
        )
        known_urls = {normalize_url(url) for url, in cursor.fetchall()}
        # Clues from the published baseline dataset have no raw HTML, so also
        # consider their source URLs as known.
        cursor.execute("SELECT DISTINCT source_url FROM clues WHERE source = ?;", (source,))
        known_urls.update(normalize_url(url) for url, in cursor.fetchall() if url)
    return known_urls


def scrape_blogs(
    sources: dict[str, Callable[[set[str]], Iterable[str]]],
    sleep_interval: float = 20,
    limit: int | None = None,
    logger: logging.Logger | None = None,
):
    if logger is None:
        logger = get_logger()

    session = get_session()
    for source, get_new_urls_func in sources.items():
        # Get new URLs from the blog
        logger.info(f"Scraping {source}")
        try:
            new_urls = sorted(get_new_urls_func(get_known_urls(source)), reverse=True)
        except Exception:
            logger.error(f"Failed to get new urls from {source}", exc_info=True)
            continue
        logger.info(f"Found {len(new_urls)} new urls from {source}")
        if limit is not None:
            new_urls = new_urls[:limit]

        # Request new URLs
        for i, url in enumerate(new_urls):
            logger.info(f"Requesting {i}/{len(new_urls)}: {url}")
            try:
                response = session.get(url, timeout=60)
                if not response.ok:
                    logger.error(f"Response not OK ({response.status_code}): {url}")
                    continue

                with sqlite3.connect(SQLITE_DATABASE) as conn:
                    cursor = conn.cursor()
                    sql = "INSERT OR IGNORE INTO raw (source, location, content_type, content) VALUES (?, ?, 'html', ?)"
                    cursor.execute(sql, (source, url, response.text))
                    conn.commit()
            except Exception:
                logger.error(f"Error requesting or inserting: {url}", exc_info=True)

            time.sleep(sleep_interval)


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    scrape_blogs(sources=BLOG_SOURCES, sleep_interval=1, logger=logger)
