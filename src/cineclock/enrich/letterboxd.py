"""Letterboxd: the film's page and its average rating.

There's no public API, but letterboxd.com/tmdb/<id>/ redirects to the film's
page, and that page states the average rating in its share tags.
"""

import re

import httpx
from bs4 import BeautifulSoup


def tmdb_url(tmdb_id: int) -> str:
    return f"https://letterboxd.com/tmdb/{tmdb_id}/"


def parse_film_page(page: str) -> tuple[str | None, float | None]:
    soup = BeautifulSoup(page, "html.parser")
    og_url = soup.find("meta", property="og:url")
    url = og_url.get("content") if og_url else None
    # <meta name="twitter:data2" content="3.85 out of 5">
    data = soup.find("meta", attrs={"name": "twitter:data2"})
    match = re.match(r"\s*(\d(?:\.\d+)?) out of 5", data.get("content", "")) if data else None
    return url or None, round(float(match.group(1)), 2) if match else None


def lookup(client: httpx.Client, tmdb_id: int) -> tuple[str | None, float | None]:
    response = client.get(tmdb_url(tmdb_id))
    response.raise_for_status()
    url, rating = parse_film_page(response.text)
    return url or str(response.url), rating
