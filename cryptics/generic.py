"""A generic, line-based parser for crossword blog posts.

Most cryptic crossword blogs (bigdave44, fifteensquared, Times for the Times,
The Hindu Crossword Corner, ...) follow the same basic shape, whether the post
is laid out as a table, as paragraphs or as divs:

    ACROSS
    1a  Clue text with an underlined definition (5)
        ANSWER - annotation explaining the wordplay
    ...
    DOWN
    ...

This module linearizes the post into lines of text and runs a small state
machine over them. Answers are only accepted if they are in uppercase and, when
the clue has an enumeration, their letter count matches the enumeration. This
keeps precision high at the cost of skipping the more exotic layouts (which
fall back to the legacy parsers in `cryptics.parse`).
"""
from __future__ import annotations

import re

import bs4
import pandas as pd

# Sentinels used to mark definitions (underlined text) within the linearized text.
DEF_OPEN = "⟦"
DEF_CLOSE = "⟧"

BLOCK_TAGS = {
    "p",
    "div",
    "li",
    "tr",
    "td",
    "th",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "details",
    "summary",
    "blockquote",
    "ul",
    "ol",
    "section",
    "article",
}

CONTENT_SELECTORS = [
    {"class_": re.compile(r"\bentry-content\b")},
    {"class_": re.compile(r"\bpost-body\b")},
    {"class_": re.compile(r"\bpost-content\b")},
    {"name": "article"},
]

MIN_CLUES = 6
MAX_CLUE_LENGTH = 300

WHITESPACE = re.compile(r"[\s  -​  　﻿]+")
DIRECTION = re.compile(r"^\W*(across|down)\b\W*(clues?)?\W*$", re.IGNORECASE)
NUMBER_ONLY = re.compile(r"^(\d{1,2})\s*(a|d|ac|dn|across|down)?\.?$", re.IGNORECASE)
CLUE_LINE = re.compile(
    r"^(?P<number>\d{1,2}(?:\s*[,/&]\s*\d{1,2}(?:a|d)?)*)\s*"
    r"(?P<direction>a|d|ac|dn|across|down)?\b[\s.:)\-–—*?]*"
    r"(?P<rest>\S.*)$",
    re.IGNORECASE,
)
ENUMERATION = re.compile(
    r"\((?P<enum>\d{1,2}(?:\s*[-,.\s]\s*\d{1,2})*)(?:[,\s]*(?:\w+\s*)?words?)?\)"
)
ANSWER_WORD = r"[A-Z][A-Z'’]*(?:-[A-Z'’]+)*"
ANSWER = re.compile(rf"^(?P<answer>{ANSWER_WORD}(?: {ANSWER_WORD})*)(?![a-z(\[{{])")
SKIP_LINE = re.compile(
    r"^(answer|solution|parsing|explanation|reveal|show|hint|click here!?|toggle)s?\W*$",
    re.IGNORECASE,
)


def _is_underlined(tag: bs4.Tag) -> bool:
    if tag.name == "u":
        return True
    style = (tag.get("style") or "").replace(" ", "").lower()
    if "text-decoration:underline" in style:
        return True
    classes = tag.get("class") or []
    # bigdave44 marks definitions with these classes.
    return any(c in ("dls", "tod") for c in classes)


def _is_bold_italic(tag: bs4.Tag) -> bool:
    # The Hindu Crossword Corner marks definitions in bold italics.
    if tag.name not in ("b", "strong"):
        return False
    children = [c for c in tag.children if not (isinstance(c, str) and not c.strip())]
    return len(children) == 1 and getattr(children[0], "name", None) in ("i", "em")


def find_content(soup: bs4.BeautifulSoup) -> bs4.Tag:
    for selector in CONTENT_SELECTORS:
        content = soup.find(**selector)
        if content is not None:
            return content
    return soup.body or soup


def linearize(content: bs4.Tag) -> list[str]:
    """Convert HTML into a list of non-empty lines of text, with definitions
    wrapped in DEF_OPEN and DEF_CLOSE."""
    for tag in content.find_all(["script", "style", "noscript", "img", "s", "strike"]):
        tag.decompose()
    for tag in content.find_all(True):
        if (_is_underlined(tag) or _is_bold_italic(tag)) and tag.get_text(strip=True):
            # Avoid nesting markers when definitions are doubly marked up.
            if not tag.find_parent(lambda t: t.get("data-def") == "1"):
                tag["data-def"] = "1"
                tag.insert(0, DEF_OPEN)
                tag.append(DEF_CLOSE)
    for br in content.find_all("br"):
        br.replace_with("\n")
    for tag in content.find_all(BLOCK_TAGS):
        tag.insert_before("\n")
        tag.insert_after("\n")

    lines = []
    for line in content.get_text().split("\n"):
        line = WHITESPACE.sub(" ", line).strip()
        # Drop markers wrapping nothing but whitespace.
        line = line.replace(DEF_OPEN + DEF_CLOSE, "")
        if line:
            lines.append(line)
    return lines


def _merge_number_lines(lines: list[str]) -> list[str]:
    """Merge lines consisting only of a clue number (e.g. a table cell) into
    the following line."""
    merged: list[str] = []
    i = 0
    while i < len(lines):
        if NUMBER_ONLY.match(lines[i]) and i + 1 < len(lines):
            merged.append(lines[i] + " " + lines[i + 1])
            i += 2
        else:
            merged.append(lines[i])
            i += 1
    return merged


def strip_markers(s: str) -> str:
    return WHITESPACE.sub(" ", s.replace(DEF_OPEN, "").replace(DEF_CLOSE, "")).strip()


def extract_definitions(clue: str) -> str | None:
    definitions = [
        strip_markers(d).strip(" ,.;:!?")
        for d in re.findall(f"{DEF_OPEN}(.*?){DEF_CLOSE}", clue)
    ]
    definitions = [d for d in definitions if d]
    return "/".join(definitions) if definitions else None


def enumeration_length(enumeration: str) -> int:
    return sum(int(n) for n in re.findall(r"\d+", enumeration))


def match_answer(text: str, target_length: int | None) -> tuple[str, str] | None:
    """Find an uppercase answer at the start of `text`, returning (answer,
    remaining text). If target_length is given, the answer's letter count must
    match it exactly."""
    text = strip_markers(text).lstrip(" :–—-*•")
    m = ANSWER.match(text)
    if not m:
        return None
    words = m.group("answer").split(" ")
    if target_length is None:
        answer = " ".join(words)
        letters = len(re.sub(r"[^A-Z]", "", answer))
        # Without an enumeration, we're more conservative.
        if letters < 3:
            return None
        return answer, text[len(answer) :].strip()
    for n in range(1, len(words) + 1):
        answer = " ".join(words[:n])
        letters = len(re.sub(r"[^A-Z]", "", answer))
        if letters == target_length:
            return answer, text[len(answer) :].strip()
        if letters > target_length:
            break
    return None


def looks_like_clue(clue: str) -> bool:
    """Clues are prose: mostly lowercase and not too long. This rejects, e.g.,
    annotated answers such as "ACCUS(TO M)ED"."""
    letters = [c for c in ENUMERATION.sub("", clue) if c.isalpha()]
    if len(letters) < 3 or len(clue) > MAX_CLUE_LENGTH:
        return False
    return sum(c.islower() for c in letters) / len(letters) >= 0.5


def _clean_annotation(s: str) -> str | None:
    s = strip_markers(s).lstrip(" :–—-*•").strip()
    return s or None


def parse_lines(lines: list[str]) -> list[dict]:
    lines = _merge_number_lines(lines)
    clues: list[dict] = []
    direction = None
    # Some posts have no ACROSS/DOWN headers: then assume clues are listed
    # across first, and switch to down once the clue numbers reset.
    has_headers = any(DIRECTION.match(strip_markers(line)) for line in lines)
    if not has_headers:
        direction = "across"
    last_number = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if DIRECTION.match(strip_markers(line)):
            direction = DIRECTION.match(strip_markers(line)).group(1).lower()  # type: ignore
            i += 1
            continue

        # Match the marked-up line, so that `rest` keeps its definition markers.
        m = CLUE_LINE.match(line)
        if m is None or direction is None:
            i += 1
            continue

        number = m.group("number").replace(" ", "")
        explicit_direction = (m.group("direction") or "").lower()
        rest = m.group("rest")

        clue = answer = annotation = None
        consumed = 1

        enums = list(ENUMERATION.finditer(rest))
        if enums:
            enum = enums[-1]
            clue = rest[: enum.end()]
            target: int | None = enumeration_length(enum.group("enum"))
            trailing = rest[enum.end() :]
            found = match_answer(trailing, target) if strip_markers(trailing) else None
            if found:
                answer, annotation = found
            else:
                # Look ahead for the answer on the following lines.
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = strip_markers(lines[j])
                    if SKIP_LINE.match(candidate):
                        continue
                    if CLUE_LINE.match(candidate) and not match_answer(candidate, target):
                        break
                    found = match_answer(lines[j], target)
                    if found:
                        answer, annotation = found
                        consumed = j - i + 1
                    break
        else:
            # Answer-first layouts: "1 ANSWER" followed by "Clue text (5)".
            found = match_answer(rest, None)
            if (
                found
                and not found[1]
                and i + 1 < len(lines)
                and not CLUE_LINE.match(strip_markers(lines[i + 1]))
                and looks_like_clue(strip_markers(lines[i + 1]))
            ):
                candidate_clue = lines[i + 1]
                enums = list(ENUMERATION.finditer(candidate_clue))
                if not enums:
                    answer, clue = found[0], candidate_clue
                elif len(re.sub(r"[^A-Z]", "", found[0])) == enumeration_length(
                    enums[-1].group("enum")
                ):
                    answer, clue = found[0], candidate_clue[: enums[-1].end()]
                if answer:
                    consumed = 2
                    if i + 2 < len(lines) and not CLUE_LINE.match(
                        strip_markers(lines[i + 2])
                    ):
                        annotation = lines[i + 2]
                        consumed = 3
            else:
                # No enumeration (e.g. some Times for the Times posts): the
                # answer must be on the next line.
                clue = rest
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = strip_markers(lines[j])
                    if SKIP_LINE.match(candidate):
                        continue
                    if CLUE_LINE.match(candidate) or DIRECTION.match(candidate):
                        break
                    found = match_answer(lines[j], None)
                    if found:
                        answer, annotation = found
                        consumed = j - i + 1
                    break

        if clue and answer and looks_like_clue(strip_markers(clue)):
            first_number = int(re.match(r"\d+", number).group())  # type: ignore
            if not has_headers and first_number < last_number:
                direction = "down"
            last_number = first_number
            if explicit_direction:
                suffix = "a" if explicit_direction.startswith("a") else "d"
            else:
                suffix = direction[0]
            clues.append(
                {
                    "clue_number": re.sub(r"\b0+(\d)", r"\1", number.rstrip("ad"))
                    + suffix,
                    # Bloggers often split double definitions with slashes.
                    "clue": re.sub(r"\s/{1,2}\s", " ", strip_markers(clue)),
                    "answer": answer.strip(),
                    "definition": extract_definitions(clue),
                    "annotation": _clean_annotation(annotation or ""),
                }
            )
            i += consumed
        else:
            i += 1

    # Remove exact duplicates (some posts repeat the clue list).
    seen = set()
    unique = []
    for c in clues:
        key = (c["clue_number"], c["clue"], c["answer"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def parse_generic(html: str) -> pd.DataFrame | None:
    soup = bs4.BeautifulSoup(html, "lxml")
    lines = linearize(find_content(soup))
    clues = parse_lines(lines)
    if len(clues) < MIN_CLUES:
        return None
    return pd.DataFrame(
        clues, columns=["clue_number", "clue", "answer", "definition", "annotation"]
    )


def is_parsable_generic(html: str) -> bool:
    return parse_generic(html) is not None
