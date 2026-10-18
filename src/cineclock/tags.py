"""Tags on a screening: film format, special events and previews.

Venues say these in different ways ("Presented in 70mm", "Filmmakers in
Attendance for Q&A", a "35mm" format field), so each tag is a pattern matched
against everything the venue told us about that one showing. A tag only
appears when the listing says so: a theatre that can run 70mm doesn't make
every screening there 70mm.
"""

import re

# How the film is shown.
FORMATS = {
    "70mm": r"\b70\s?mm\b",
    "35mm": r"\b35\s?mm\b",
    "16mm": r"\b16\s?mm\b",
    "IMAX": r"\bimax\b",
    # "4K restoration" describes the restoration, not the projection, so only
    # an explicit 4K presentation counts.
    "4K": r"\b(presented|projected|screening|screened|shown) in 4k\b",
    "Dolby Atmos": r"\bdolby atmos\b",
    "3D": r"\bin 3-?d\b|\b3-?d (screening|presentation)\b",
}

# What makes the showing more than a screening. Checked in this order.
EVENTS = {
    "Filmmaker Q&A": r"(filmmaker|director|cast|creator)s?\b.{0,60}\b(q\s?&\s?a|q and a)"
    r"|(q\s?&\s?a|q and a)\b.{0,40}\b(filmmaker|director|cast)",
    "Q&A": r"\bq\s?&\s?a\b|\bq and a\b|talkback|in conversation",
    "Introduction": r"introduc|\bintro\b",
    "Live accompaniment": r"live (score|music|accompaniment|soundtrack)"
    r"|accompanied by|\bperforms\b",
    "Festival": r"\bfestival\b|\bfest\b",
    "Shorts programme": r"\bshorts\b|short films",
    "Special presentation": r"special (presentation|screening|event)",
    "Guests": r"\bguests?\b|in attendance|\bpanel\b",
}
PREVIEW = r"advance screening|insider screening|sneak preview|preview screening"

RARE = ["One screening", "One day only"]
ORDER = RARE + list(FORMATS) + list(EVENTS) + ["Preview"]
ON_FILM = {"70mm", "35mm", "16mm"}


def screening_tags(title: str, note: str | None, film_format: str | None) -> list[str]:
    text = " ".join(filter(None, [title, note, film_format])).lower()
    tags = [name for name, pattern in FORMATS.items() if re.search(pattern, text)]
    tags += [name for name, pattern in EVENTS.items() if re.search(pattern, text)]
    if "Filmmaker Q&A" in tags and "Q&A" in tags:
        tags.remove("Q&A")
    if "Filmmaker Q&A" in tags and "Guests" in tags:
        tags.remove("Guests")
    if re.search(PREVIEW, text):
        tags.append("Preview")
    return tags


def kind(tag: str) -> str:
    """Which family a tag belongs to, so each family can look different."""
    if tag in RARE:
        return "rare"
    if tag in FORMATS:
        return "format"
    return "event"


def is_event(tags) -> bool:
    return any(t in EVENTS for t in tags)


def sort_tags(tags) -> list[str]:
    return sorted(set(tags), key=lambda t: ORDER.index(t) if t in ORDER else len(ORDER))


def slug(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def filter_slugs(tags) -> list[str]:
    """Tag slugs for the filters, plus "on-film" and "event" for any film format or event."""
    slugs = [slug(t) for t in tags]
    if ON_FILM & set(tags):
        slugs.append("on-film")
    if is_event(tags):
        slugs.append("event")
    return slugs
