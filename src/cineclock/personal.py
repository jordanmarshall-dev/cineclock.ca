"""What a Letterboxd member's lists mean for what's playing.

The site is plain files, so personal touches happen in the visitor's browser
(static/me.js). The build publishes what the browser needs:

  films.json                  every film playing, for matching an uploaded export
  me/<user>.json              a synced member's status for each film playing
  me/<user>/watchlist.ics     a calendar feed of every screening on their watchlist
"""

import re
from datetime import UTC, datetime, timedelta

from cineclock.models import Screening
from cineclock.profiles import Profile
from cineclock.render import logo_size
from cineclock.timefmt import clock


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


def films_index(film_list, now: datetime, when) -> list[dict]:
    """Enough about each film playing to match an export and draw a shelf card."""
    index = []
    for page in film_list:
        logos = []
        for v in page.venues:
            if v.mark:
                w, h = logo_size(f"logos/{v.mark}", 900 * v.mark_scale**2, 12 * v.mark_scale)
                logos.append({"name": v.name, "src": f"static/logos/{v.mark}", "w": w, "h": h})
        index.append(
            {
                "slug": page.slug,
                "title": page.title,
                "year": page.year,
                "alt": page.film.title if page.film and page.film.title else None,
                "lb": letterboxd_slug(page.film.letterboxd_url) if page.film else None,
                "poster": page.poster_url,
                "next": when(page.next_showing, now),
                "venues": logos,
            }
        )
    return index


def _ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """Calendar lines over 75 characters continue on the next line after a space."""
    out = [line[:75]]
    rest = line[75:]
    while rest:
        out.append(" " + rest[:74])
        rest = rest[74:]
    return out


def calendar(name: str, events: list[tuple[Screening, str, str, int | None]], now: datetime) -> str:
    """An iCalendar feed. Each event is (screening, title, venue address, runtime)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//cineclock//showtimes//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_ics_text(name)}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT4H",
    ]
    utc = "%Y%m%dT%H%M%SZ"
    stamp = now.astimezone(UTC).strftime(utc)
    for s, title, address, runtime in events:
        start = s.starts_at.astimezone(UTC)
        end = start + timedelta(minutes=runtime or 120)
        uid = re.sub(r"[^A-Za-z0-9]+", "-", f"{s.venue}-{s.title}-{start:%Y%m%d%H%M}").strip("-")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@cineclock",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{start.strftime(utc)}",
            f"DTEND:{end.strftime(utc)}",
            f"SUMMARY:{_ics_text(f'{title} at {s.venue}')}",
            f"LOCATION:{_ics_text(address)}",
            f"URL:{s.url}",
            f"DESCRIPTION:{_ics_text(f'{clock(s.starts_at)}. Tickets: {s.url}')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"


def watchlist_calendar(profile: Profile, film_list, venue_for, now: datetime) -> str:
    events = []
    for page in film_list:
        slug = letterboxd_slug(page.film.letterboxd_url) if page.film else None
        if slug not in profile.watchlist:
            continue
        runtime = page.film.runtime if page.film else None
        for s in page.screenings:
            events.append((s, page.title, venue_for(s.venue).address, runtime))
    events.sort(key=lambda e: e[0].starts_at)
    return calendar(f"cineclock: {profile.user}'s watchlist", events, now)
