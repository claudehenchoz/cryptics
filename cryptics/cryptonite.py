"""Import the Cryptonite dataset (Efrat et al., 2021).

Cryptonite is a research dataset of ~523k cryptic clues from The Times and The
Telegraph (https://github.com/aviaefrat/cryptonite). Clues are lowercased, and
there are no definitions or annotations. It is distributed for research
purposes (the Hugging Face dataset card lists CC BY-NC 4.0), so this data
should only be used non-commercially.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import zipfile
from datetime import datetime, timezone

import pandas as pd

from cryptics.config import SQLITE_DATABASE
from cryptics.seed import DOWNLOADS_DIR, download
from cryptics.utils import get_logger

CRYPTONITE_URL = "https://raw.githubusercontent.com/aviaefrat/cryptonite/main/data/cryptonite-official-split.zip"
CRYPTONITE_PATH = os.path.join(DOWNLOADS_DIR, "cryptonite-official-split.zip")


def parse_cryptonite_row(row: dict) -> dict:
    date = datetime.fromtimestamp(row["date"] / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d"
    )
    publisher = row["publisher"].lower()
    clue = row["clue"].strip()
    return {
        "source": f"cryptonite_{publisher}",
        # Cryptonite lowercases all clues; at least capitalize the first letter.
        "clue": clue[:1].upper() + clue[1:],
        "answer": row["answer"].strip().upper(),
        "definition": None,
        "annotation": None,
        "clue_number": f"{row['number']}{row['orientation'][0]}",
        "puzzle_date": date,
        "puzzle_name": f"{row.get('sub_publisher') or row['publisher']} {date}",
        "puzzle_url": None,
        "source_url": f"cryptonite:{publisher}:{date}",
    }


def import_cryptonite(logger: logging.Logger | None = None):
    if logger is None:
        logger = get_logger()

    with sqlite3.connect(SQLITE_DATABASE) as conn:
        (already_imported,) = conn.execute(
            "SELECT COUNT(*) FROM raw WHERE location = ?;", (CRYPTONITE_URL,)
        ).fetchone()
    if already_imported:
        logger.info("Cryptonite already imported, skipping")
        return

    download(CRYPTONITE_URL, CRYPTONITE_PATH, logger)
    rows: list[dict] = []
    with zipfile.ZipFile(CRYPTONITE_PATH) as z:
        for name in sorted(z.namelist()):
            if not name.endswith(".jsonl"):
                continue
            with z.open(name) as f:
                rows.extend(
                    parse_cryptonite_row(json.loads(line)) for line in f if line.strip()
                )

    data = pd.DataFrame(rows).sort_values(["source", "puzzle_date"], kind="stable")
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        data.to_sql("clues", conn, if_exists="append", index=False)
        conn.execute(
            "INSERT INTO raw (source, location, content_type, is_parsed, datetime_parsed) VALUES ('cryptonite', ?, 'seed', TRUE, datetime('now'));",
            (CRYPTONITE_URL,),
        )
        conn.commit()
    logger.info(f"Imported {len(data)} clues from Cryptonite")


if __name__ == "__main__":
    import_cryptonite()
