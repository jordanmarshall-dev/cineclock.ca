"""The Dunbar: one Veezi ticketing page listing every film and session.

The page shows sessions twice, by date and by film. We read the by-film half,
where each film block has its dates ("Friday 23, October") and times
("4:00 PM"), each time linking to its ticket page. Dates carry no year, so the
weekday picks it, as at the Park.
"""

import re
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from cineclock.dates import hour_24, month_number, resolve
from cineclock.models import Screening
from cineclock.scrapers import make_client
from cineclock.titles import clean_title, split_year

VENUE = "The Dunbar"
VENUES = (VENUE,)
ROOM = "dunbar-main"
SESSIONS_URL = "https://ticketing.uswest.veezi.com/sessions/?siteToken=sap55z6c6aj6b96yshhtj7vyw4"

# "Friday 23, October"
DATE = re.compile(r"(?P<weekday>[A-Za-z]+)\s+(?P<day>\d{1,2}),?\s+(?P<month>[A-Za-z]+)")
# "4:00 PM"
TIME = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>[AaPp][Mm])")


def parse_sessions(page: str, now: datetime) -> list[Screening]:
    soup = BeautifulSoup(page, "html.parser")
    container = soup.select_one("#sessionsByFilmConent") or soup
    screenings = []
    for film in container.select(".film"):
        heading = film.select_one(".title")
        if not heading:
            continue
        title, note = clean_title(heading.get_text(" ", strip=True))
        title, year = split_year(title)
        poster = film.select_one("img.poster")
        poster_url = urljoin(SESSIONS_URL, poster["src"]) if poster and poster.get("src") else None

        for day in film.select(".date-container"):
            date_tag = day.select_one(".date")
            date = DATE.search(date_tag.get_text(" ", strip=True)) if date_tag else None
            month = month_number(date["month"]) if date else None
            if not month:
                continue
            for link in day.select(".session-times a[href]"):
                time = TIME.search(link.get_text(" ", strip=True))
                if not time:
                    continue
                start = resolve(
                    month,
                    int(date["day"]),
                    hour_24(int(time["hour"]), time["ampm"]),
                    int(time["minute"]),
                    date["weekday"],
                    now,
                )
                if not start:
                    continue
                screenings.append(
                    Screening(
                        venue=VENUE,
                        room=ROOM,
                        title=title,
                        year=year,
                        note=note,
                        starts_at=start,
                        url=urljoin(SESSIONS_URL, link["href"]),
                        poster_url=poster_url,
                    )
                )
    return screenings


def scrape(client: httpx.Client, now: datetime | None = None) -> list[Screening]:
    now = now or datetime.now(UTC)
    response = client.get(SESSIONS_URL)
    response.raise_for_status()
    return [s for s in parse_sessions(response.text, now) if s.starts_at >= now]


if __name__ == "__main__":
    with make_client() as client:
        for s in scrape(client):
            print(s.local_start.strftime("%a %b %d %H:%M"), s.title, s.year or "", s.note or "")
