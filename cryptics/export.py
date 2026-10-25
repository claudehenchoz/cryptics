"""Export the clues table to compressed CSVs.

Two files are written:

- `exports/clues.csv.gz`: every clue, from every source.
- `exports/clues-unique.csv.gz`: one row per distinct (clue, answer) pair.
  Sources overlap (e.g. fifteensquared blogs The Guardian's puzzles, and
  Cryptonite overlaps with bigdave44 and Times for the Times), so when the same
  clue appears more than once, we keep the row with a definition and
  annotation if possible, and otherwise the earliest row.
"""
from __future__ import annotations

import logging
import os
import sqlite3

import pandas as pd

from cryptics.config import PROJECT_DIR, SQLITE_DATABASE
from cryptics.utils import get_logger

EXPORTS_DIR = os.path.join(PROJECT_DIR, "exports")
COLUMNS = [
    "source",
    "clue",
    "answer",
    "definition",
    "annotation",
    "clue_number",
    "puzzle_date",
    "puzzle_name",
    "puzzle_url",
    "source_url",
]


def normalize(series: pd.Series) -> pd.Series:
    return series.fillna("").str.lower().str.replace(r"[^a-z0-9]", "", regex=True)


def deduplicate(data: pd.DataFrame) -> pd.DataFrame:
    key = normalize(data["clue"]) + "|" + normalize(data["answer"])
    preference = data["definition"].isna().astype(int) + data["annotation"].isna().astype(int)
    order = pd.DataFrame({"key": key, "preference": preference, "order": data.index})
    keep = order.sort_values(["preference", "order"]).drop_duplicates("key").index
    return data.loc[sorted(keep)]


def export(logger: logging.Logger | None = None):
    if logger is None:
        logger = get_logger()

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    with sqlite3.connect(SQLITE_DATABASE) as conn:
        data = pd.read_sql(
            f"SELECT rowid, {', '.join(COLUMNS)} FROM clues WHERE clue IS NOT NULL AND clue != '' AND answer IS NOT NULL AND answer != '';",
            conn,
            index_col="rowid",
        )

    path = os.path.join(EXPORTS_DIR, "clues.csv.gz")
    data.to_csv(path, index=False)
    logger.info(f"Exported {len(data)} clues to {path}")

    unique = deduplicate(data)
    path = os.path.join(EXPORTS_DIR, "clues-unique.csv.gz")
    unique.to_csv(path, index=False)
    logger.info(f"Exported {len(unique)} unique clues to {path}")

    counts = pd.DataFrame(
        {
            "clues": data["source"].value_counts(),
            "unique_clues": unique["source"].value_counts(),
            # Some sources (e.g. nytimes) have no puzzle dates at all.
            "latest_puzzle_date": data.dropna(subset=["puzzle_date"])
            .groupby("source")["puzzle_date"]
            .max(),
        }
    ).fillna({"clues": 0, "unique_clues": 0, "latest_puzzle_date": ""})
    logger.info(f"Clues by source:\n{counts.to_string()}")


if __name__ == "__main__":
    export()
