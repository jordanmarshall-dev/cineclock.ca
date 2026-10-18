from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

import httpx

from cineclock.models import Screening

USER_AGENT = "cineclock (+https://github.com/yogzoth/cineclock)"


@dataclass(frozen=True)
class FilmDetails:
    year: int | None = None
    poster_url: str | None = None


def make_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)


def add_details(
    client: httpx.Client,
    screenings: Iterable[Screening],
    parse_page: Callable[[str], FilmDetails],
) -> list[Screening]:
    """Fill in year and poster from each film's page, fetching every page only once."""
    screenings = list(screenings)
    details = {}
    for url in {s.info_url for s in screenings if s.info_url}:
        try:
            page = client.get(url)
            page.raise_for_status()
            details[url] = parse_page(page.text)
        except httpx.HTTPError:
            # A missing year or poster is fine; the screening still shows.
            details[url] = FilmDetails()

    return [
        replace(
            s,
            year=details[s.info_url].year or s.year,
            poster_url=details[s.info_url].poster_url or s.poster_url,
        )
        if s.info_url
        else s
        for s in screenings
    ]
