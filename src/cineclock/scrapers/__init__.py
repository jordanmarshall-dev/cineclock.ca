from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

import httpx

from cineclock.models import Screening

USER_AGENT = "cineclock (+https://github.com/yogzoth/cineclock)"


@dataclass(frozen=True)
class FilmDetails:
    year: int | None = None
    poster_url: str | None = None
    film_format: str | None = None
    series: str | None = None


def make_client() -> httpx.Client:
    headers = {
        "User-Agent": USER_AGENT,
        # Some venue sites refuse requests that don't say they accept HTML.
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }
    return httpx.Client(headers=headers, timeout=30, follow_redirects=True)


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
            film_format=details[s.info_url].film_format or s.film_format,
            series=details[s.info_url].series or s.series,
        )
        if s.info_url
        else s
        for s in screenings
    ]
