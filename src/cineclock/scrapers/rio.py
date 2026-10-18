"""The Rio Theatre: listings come from its WordPress API, details from each film page."""

from datetime import UTC, datetime, timedelta

import httpx
from bs4 import BeautifulSoup

from cineclock.models import Screening
from cineclock.scrapers import FilmDetails, add_details, make_client
from cineclock.titles import clean_title, credits_year, split_year

VENUE = "The Rio"
VENUES = (VENUE,)
ROOM = "rio-main"
LISTINGS_URL = "https://riotheatre.ca/wp-json/barker/v1/listings"


def parse_listings(data: list[dict]) -> list[Screening]:
    screenings = []
    for item in data:
        event = item["event"]
        # /event/ pages are live shows (burlesque, comedy, private bookings), not films.
        if "/movie/" not in event["link"]:
            continue
        title, note = clean_title(event["title"])
        title, year = split_year(title)
        screenings.append(
            Screening(
                venue=VENUE,
                room=ROOM,
                title=title,
                year=year,
                note=note,
                # The API includes the UTC offset, so this is already an exact moment.
                starts_at=datetime.fromisoformat(item["start_time"]),
                url=item["tickets_link"] or event["link"],
                info_url=event["link"],
            )
        )
    return screenings


def parse_film_page(page: str) -> FilmDetails:
    soup = BeautifulSoup(page, "html.parser")
    og_image = soup.find("meta", property="og:image")
    poster = og_image.get("content") if og_image else None
    return FilmDetails(year=credits_year(soup.get_text(" ")), poster_url=poster or None)


def scrape(client: httpx.Client, now: datetime | None = None) -> list[Screening]:
    now = now or datetime.now(UTC)
    params = {
        "status": "publish",
        "per_page": 500,
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=60)).isoformat(),
    }
    response = client.get(LISTINGS_URL, params=params)
    response.raise_for_status()
    return add_details(client, parse_listings(response.json()), parse_film_page)


if __name__ == "__main__":
    with make_client() as client:
        for s in scrape(client):
            print(s.local_start.strftime("%a %b %d %H:%M"), s.title, s.year or "", s.note or "")
