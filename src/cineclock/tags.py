"""Tags on a screening: film format, special events and previews.

Venues say these in different ways ("Presented in 70mm", "Filmmakers in
Attendance for Q&A", a "35mm" format field), so each tag is a list of
patterns matched against everything the venue told us about the showing.
"""

import re

FORMATS = {
    "70mm": r"\b70\s?mm\b",
    "35mm": r"\b35\s?mm\b",
    "16mm": r"\b16\s?mm\b",
    "IMAX": r"\bimax\b",
}

EVENT = "|".join([
    r"q\s?&\s?a", r"\bq and a\b", r"in conversation", r"introduc", r"\bintro\b",
    r"guest", r"panel", r"in attendance", r"talkback", r"\blive\b", r"performs",
])  # fmt: skip
PREVIEW = r"advance screening|insider screening|sneak preview|preview screening"

ORDER = ["One screening", "One day only", "70mm", "35mm", "16mm", "IMAX", "Event", "Preview"]


def screening_tags(title: str, note: str | None, film_format: str | None) -> list[str]:
    text = " ".join(filter(None, [title, note, film_format])).lower()
    tags = [name for name, pattern in FORMATS.items() if re.search(pattern, text)]
    if re.search(EVENT, text):
        tags.append("Event")
    if re.search(PREVIEW, text):
        tags.append("Preview")
    return tags


def sort_tags(tags) -> list[str]:
    return sorted(set(tags), key=lambda t: ORDER.index(t) if t in ORDER else len(ORDER))


def slug(tag: str) -> str:
    return tag.lower().replace(" ", "-")
