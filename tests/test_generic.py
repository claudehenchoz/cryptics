from __future__ import annotations

import pytest

from cryptics import generic


def _wrap(body: str) -> str:
    return f'<html><body><div class="entry-content">{body}</div></body></html>'


def _clues(n: int, template: str) -> str:
    return "".join(template.format(i=i) for i in range(1, n + 1))


# Times for the Times style: a table with the clue on one row, and the answer
# and annotation on the next.
TABLE_ROW = (
    '<tr><td>{i}</td><td><span style="color:blue"><u>Face</u> pressure entering a cult (6)</span></td></tr>'
    "<tr><td></td><td><b>ASPECT</b> - A, S(P)ECT.</td></tr>"
)
TABLE_HTML = _wrap(
    "<table><tr><td><strong>Across</strong></td></tr>"
    + _clues(4, TABLE_ROW)
    + "<tr><td><strong>Down</strong></td></tr>"
    + _clues(4, TABLE_ROW)
    + "</table>"
)

# bigdave44 style: paragraphs with the answer on the line after the clue.
PARAGRAPH_ROW = (
    "<p>{i}a&nbsp;&nbsp; A wader's swimming <u>away from the shore</u> (7)<br/>"
    "<span>SEAWARD</span>: An anagram (swimming) of A WADERS</p>"
)
PARAGRAPH_HTML = _wrap(
    "<p><strong>Across</strong></p>" + _clues(7, PARAGRAPH_ROW)
)

# The Hindu Crossword Corner style: the answer follows the enumeration.
INLINE_ROW = "<div>{i} <b><i>Inventor </i></b>is done? Is in trouble? (6) <b>EDISON</b>*</div>"
INLINE_HTML = _wrap("<div><b><u>DOWN</u></b></div>" + _clues(7, INLINE_ROW))

# fifteensquared "fts" tables: the answer comes before the clue.
ANSWER_FIRST_ROW = (
    "<tr><td>{i}</td><td><span>TAPESTRIES</span></td>"
    "<td><div>Striptease represented in <u>wall-hung art</u> (10)</div></td></tr>"
    "<tr><td colspan='2'></td><td>Anagram (represented) of STRIPTEASE</td></tr>"
)
ANSWER_FIRST_HTML = _wrap(
    "<table><tr><td colspan='3'>ACROSS</td></tr>"
    + _clues(7, ANSWER_FIRST_ROW)
    + "</table>"
)


@pytest.mark.parametrize(
    "html, expected",
    [
        [
            TABLE_HTML,
            dict(
                n=8,
                clue_number="1a",
                clue="Face pressure entering a cult (6)",
                answer="ASPECT",
                definition="Face",
                annotation="A, S(P)ECT.",
            ),
        ],
        [
            PARAGRAPH_HTML,
            dict(
                n=7,
                clue_number="1a",
                clue="A wader's swimming away from the shore (7)",
                answer="SEAWARD",
                definition="away from the shore",
                annotation="An anagram (swimming) of A WADERS",
            ),
        ],
        [
            INLINE_HTML,
            dict(
                n=7,
                clue_number="1d",
                clue="Inventor is done? Is in trouble? (6)",
                answer="EDISON",
                definition="Inventor",
                annotation=None,
            ),
        ],
        [
            ANSWER_FIRST_HTML,
            dict(
                n=7,
                clue_number="1a",
                clue="Striptease represented in wall-hung art (10)",
                answer="TAPESTRIES",
                definition="wall-hung art",
                annotation="Anagram (represented) of STRIPTEASE",
            ),
        ],
    ],
)
def test_parse_generic(html: str, expected: dict):
    data = generic.parse_generic(html)
    assert data is not None
    assert len(data) == expected.pop("n")
    first = data.iloc[0].to_dict()
    for key, value in expected.items():
        assert first[key] == value


def test_parse_generic_requires_matching_enumeration():
    # The answer has the wrong number of letters for the enumeration.
    html = _wrap(
        "<p>Across</p>"
        + _clues(7, "<p>{i} Some clue text here (5)<br/>WRONGLENGTH - nope</p>")
    )
    assert generic.parse_generic(html) is None


def test_parse_generic_rejects_annotated_answers():
    # thenationcryptic "solution" posts list annotated answers, not clues.
    html = _wrap(
        "<p>Across</p>"
        + _clues(7, "<p>{i} ACCUS(TO M)ED<br/>ACCUSED (charged) containing TO</p>")
    )
    assert generic.parse_generic(html) is None


def test_parse_generic_needs_enough_clues():
    assert generic.parse_generic(_wrap("<p>Across</p>" + _clues(2, PARAGRAPH_ROW))) is None


@pytest.mark.parametrize(
    "text, target_length, expected",
    [
        ["ROCK OF GIBRALTAR: An anagram", 15, ("ROCK OF GIBRALTAR", ": An anagram")],
        ["PSEUDOCIDE PSEUD [(DUPES)*]", 10, ("PSEUDOCIDE", "PSEUD [(DUPES)*]")],
        ["CARRY-ON - homophone", 7, ("CARRY-ON", "- homophone")],
        ["ASPECT - A, S(P)ECT.", None, ("ASPECT", "- A, S(P)ECT.")],
        ["Not an answer", 3, None],
        ["AB", None, None],
    ],
)
def test_match_answer(text: str, target_length: int | None, expected):
    assert generic.match_answer(text, target_length) == expected


@pytest.mark.parametrize(
    "clue, expected",
    [
        ["Labourers going around spotted tools (8)", True],
        ["ACCUS(TO M)ED", False],
        ["x" * 400, False],
    ],
)
def test_looks_like_clue(clue: str, expected: bool):
    assert generic.looks_like_clue(clue) == expected
