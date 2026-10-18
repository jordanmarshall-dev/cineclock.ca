"""OMDb: IMDb and Rotten Tomatoes ratings by IMDb ID (free key, 1,000 lookups a day)."""

import httpx

API = "https://www.omdbapi.com/"


def parse(data: dict) -> tuple[float | None, int | None]:
    """{"imdbRating": "7.8", "Ratings": [{"Source": "Rotten Tomatoes", "Value": "92%"}]}"""
    if data.get("Response") != "True":
        return None, None
    try:
        imdb = float(data.get("imdbRating", ""))
    except ValueError:
        imdb = None
    rt = None
    for rating in data.get("Ratings", []):
        value = rating.get("Value", "")
        if rating.get("Source") == "Rotten Tomatoes" and value.endswith("%"):
            rt = int(value[:-1]) if value[:-1].isdigit() else None
    return imdb, rt


def lookup(client: httpx.Client, key: str, imdb_id: str) -> tuple[float | None, int | None]:
    response = client.get(API, params={"i": imdb_id, "apikey": key})
    response.raise_for_status()
    return parse(response.json())
