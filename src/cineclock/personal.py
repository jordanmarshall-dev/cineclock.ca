"""What a Letterboxd member's lists mean for what's playing.

The site is plain files, so personal touches happen in the visitor's browser
(static/me.js). For each synced member the build publishes me/<user>.json:
their status for every film playing. films.json carries each film's card so
the browser can draw a member's films the same way as everywhere else.
"""

import re
from datetime import datetime

from cineclock.profiles import Profile


def letterboxd_slug(url: str | None) -> str | None:
    match = re.search(r"/film/([^/]+)/", url or "")
    return match.group(1) if match else None


def status(profile: Profile, slug: str) -> dict | None:
    """A film's place in the member's lists, in short keys to keep the file small:
    w on watchlist, r rating out of 10, s seen, d last diary date, old seen before
    the diary feed reaches back (so a while ago)."""
    found: dict = {}
    if slug in profile.watchlist:
        found["w"] = 1
    if slug in profile.watched:
        found["s"] = 1
        if profile.watched[slug] is not None:
            found["r"] = profile.watched[slug]
        if slug in profile.diary:
            found["d"] = profile.diary[slug].isoformat()
        elif profile.diary_since:
            found["old"] = 1
    return found or None


def profile_json(profile: Profile, film_list, now: datetime) -> dict:
    films = {}
    for page in film_list:
        slug = letterboxd_slug(page.film.letterboxd_url) if page.film else None
        found = status(profile, slug) if slug else None
        if found:
            films[page.slug] = found
    return {"user": profile.user, "updated": now.isoformat(), "films": films}
