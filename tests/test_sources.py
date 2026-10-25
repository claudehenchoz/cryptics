from __future__ import annotations

import pytest

from cryptics import cryptonite, guardian, utils

GUARDIAN_CROSSWORD = {
    "name": "Cryptic crossword No 29,000",
    "date": 1677024000000,
    "solutionAvailable": True,
    "entries": [
        {
            "id": "1-across",
            "humanNumber": "1",
            "clue": "Page with dotty portraits lacking an introduction to Roy Lichtenstein? (3,6)",
            "direction": "across",
            "group": ["1-across"],
            "separatorLocations": {",": [3]},
            "solution": "POPARTIST",
        },
        {
            "id": "5-across",
            "humanNumber": "5,6",
            "clue": "<i>Dead</i> animals reported in small bag? (5-2,4)",
            "direction": "across",
            "group": ["5-across", "6-down"],
            "separatorLocations": {"-": [5]},
            "solution": "CARRY",
        },
        {
            "id": "6-down",
            "humanNumber": "6",
            "clue": "See 5",
            "direction": "down",
            "group": ["5-across", "6-down"],
            "separatorLocations": {},
            "solution": "ONBAGS",
        },
    ],
}


@pytest.mark.parametrize(
    "url, expected",
    [
        ["http://bigdave44.com/2021/01/01/dt-1/", "bigdave44.com/2021/01/01/dt-1"],
        ["https://www.fifteensquared.net/2021/x/", "fifteensquared.net/2021/x"],
        ["https://WWW.Example.com/Path", "example.com/Path"],
        ["cru-cryptics/Cryptic196.pdf", "cru-cryptics/Cryptic196.pdf"],
    ],
)
def test_normalize_url(url: str, expected: str):
    assert utils.normalize_url(url) == expected


def test_parse_guardian():
    url = "https://www.theguardian.com/crosswords/cryptic/29000"
    data = guardian.parse_guardian(GUARDIAN_CROSSWORD, url)
    assert data is not None
    assert data["clue_number"].tolist() == ["1a", "5,6a"]
    assert data["answer"].tolist() == ["POP ARTIST", "CARRY-ON BAGS"]
    assert data["clue"].tolist()[1] == "Dead animals reported in small bag? (5-2,4)"
    assert set(data["puzzle_date"]) == {"2023-02-22"}
    assert set(data["source_url"]) == {url}


def test_parse_guardian_without_solutions():
    crossword = {
        **GUARDIAN_CROSSWORD,
        "entries": [
            {k: v for k, v in e.items() if k != "solution"}
            for e in GUARDIAN_CROSSWORD["entries"]
        ],
    }
    assert guardian.parse_guardian(crossword, "url") is None


@pytest.mark.parametrize(
    "letters, clue, separators, expected",
    [
        ["POPARTIST", "Clue (3,6)", {}, "POP ARTIST"],
        ["CARRYON", "Clue (5-2)", {}, "CARRY-ON"],
        ["CARRYON", "Clue without enumeration", {"-": [5]}, "CARRY-ON"],
        ["ABC", "Clue (4)", {}, "ABC"],
    ],
)
def test_format_answer(letters: str, clue: str, separators: dict, expected: str):
    assert guardian.format_answer(letters, clue, separators) == expected


def test_parse_cryptonite_row():
    row = {
        "publisher": "Times",
        "date": 971654400000,
        "number": 1,
        "orientation": "across",
        "clue": "solution woman had found is a turning point (9)",
        "answer": "watershed",
        "sub_publisher": "The Times",
    }
    assert cryptonite.parse_cryptonite_row(row) == {
        "source": "cryptonite_times",
        "clue": "Solution woman had found is a turning point (9)",
        "answer": "WATERSHED",
        "definition": None,
        "annotation": None,
        "clue_number": "1a",
        "puzzle_date": "2000-10-16",
        "puzzle_name": "The Times 2000-10-16",
        "puzzle_url": None,
        "source_url": "cryptonite:times:2000-10-16",
    }
