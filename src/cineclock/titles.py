import html
import re

# A bracketed tag at the very end, like "(4K Restoration)" or "(Rockytober!)".
# Five characters minimum so a trailing year like "(1986)" is left alone.
TRAILING_NOTE = re.compile(r"\s*\(([^()]{5,})\)$")

# "(Matt Johnson, 2026 / 106 mins / 14A)", sometimes without the comma:
# "(Wes Craven 1996 / 111 min / 14A)". The fields after the year come in
# any order, so match only up to the slash after the year.
CREDITS_YEAR = re.compile(r"\([^()]+?,?\s+((?:18|19|20)\d{2})\s*/")


def clean_title(raw: str) -> tuple[str, str | None]:
    """Split a venue's listing title into the film title and an optional note."""
    title = html.unescape(raw).strip()
    match = TRAILING_NOTE.search(title)
    if not match:
        return title, None
    return title[: match.start()].strip(), match.group(1).strip()


def credits_year(text: str) -> int | None:
    match = CREDITS_YEAR.search(text)
    return int(match.group(1)) if match else None
