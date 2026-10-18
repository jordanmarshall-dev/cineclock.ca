"""VIFF Centre: listings come from the calendar API, details from each film page.

Since Aug 2026 the API wants a security token (a WordPress "nonce") that the
calendar page embeds and rotates about every 12 hours, so each run grabs a
fresh one before asking for listings.
"""

import json
import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from cineclock.models import VANCOUVER, Screening
from cineclock.scrapers import FilmDetails, add_details, make_client
from cineclock.titles import clean_title, split_year

VENUE = "VIFF Centre"
VENUES = (VENUE,)

# Each listing names its room explicitly in "resourceId". These map VIFF's IDs
# to ours. Anything else at the VIFF Centre is kept with no room rather than
# guessed; anything elsewhere (festival venues) isn't the VIFF Centre at all.
ROOMS = {
    "viff-centre-viff-cinema": "viff-main",
    "viff-centre-lochmaddy-studio-theatre": "viff-lochmaddy",
}
CENTRE_PREFIX = "viff-centre-"

log = logging.getLogger(__name__)
CALENDAR_URL = "https://viff.org/whats-on-calendar/"
INSTANCES_URL = "https://viff.org/wp-json/v1/attendable/calendar/instances"

API_SETTINGS = re.compile(r"wpApiSettings\s*=\s*(\{[^}]*\})")


def parse_nonce(page: str) -> str | None:
    match = API_SETTINGS.search(page)
    if not match:
        return None
    return json.loads(match.group(1)).get("nonce")


def parse_start(item: dict, card: BeautifulSoup) -> datetime:
    # The card's <time> tag has the UTC offset. The bare "start" field is local
    # Vancouver time without one, so it's only the fallback.
    tag = card.select_one("time[datetime]")
    if tag:
        return datetime.fromisoformat(tag["datetime"])
    return datetime.fromisoformat(item["start"]).replace(tzinfo=VANCOUVER)


def parse_instances(data: list[dict]) -> list[Screening]:
    screenings = []
    for item in data:
        # "VIFF Live" is concerts and cabaret, not films.
        if item.get("eventType") != "Film":
            continue
        resource = item.get("resourceId") or ""
        if resource in ROOMS:
            room = ROOMS[resource]
        elif resource.startswith(CENTRE_PREFIX):
            log.warning("VIFF Centre room %r isn't known; keeping it unassigned", resource)
            room = None
        else:
            log.info("Skipping a VIFF listing outside the VIFF Centre: %r", resource)
            continue
        card = BeautifulSoup(item["title"], "html.parser")
        heading = card.select_one(".c-calendar-instance__title")
        book = card.select_one("a.c-btn--primary")
        info = card.select_one("a.c-btn--ghost")
        if not heading or not (book or info):
            continue
        title, note = clean_title(heading.get_text(" ", strip=True))
        title, year = split_year(title)
        screenings.append(
            Screening(
                venue=VENUE,
                room=room,
                title=title,
                year=year,
                note=note,
                starts_at=parse_start(item, card),
                url=(book or info)["href"],
                info_url=info["href"] if info else None,
            )
        )
    return screenings


def parse_film_page(page: str) -> FilmDetails:
    soup = BeautifulSoup(page, "html.parser")
    year = None
    for label in soup.select(".c-event__details-title"):
        if label.get_text(strip=True) == "Year":
            value = label.find_next_sibling(class_="c-event__details-details")
            match = re.search(r"\b(18|19|20)\d{2}\b", value.get_text()) if value else None
            year = int(match.group(0)) if match else None
            break
    # VIFF's share image is a wide film still, not a poster.
    og_image = soup.find("meta", property="og:image")
    return FilmDetails(
        year=year, poster_url=(og_image.get("content") if og_image else None) or None
    )


def scrape(client: httpx.Client, now: datetime | None = None) -> list[Screening]:
    calendar = client.get(CALENDAR_URL)
    calendar.raise_for_status()
    nonce = parse_nonce(calendar.text)
    if not nonce:
        raise RuntimeError("VIFF calendar page has no API token; the site may have changed")

    response = client.get(INSTANCES_URL, headers={"X-WP-Nonce": nonce})
    response.raise_for_status()
    screenings = parse_instances(response.json())
    if now:
        screenings = [s for s in screenings if s.starts_at >= now]
    return add_details(client, screenings, parse_film_page)


if __name__ == "__main__":
    with make_client() as client:
        for s in scrape(client):
            print(s.local_start.strftime("%a %b %d %H:%M"), s.title, s.year or "", s.note or "")
