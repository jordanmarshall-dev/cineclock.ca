"""OMDb: IMDb, Rotten Tomatoes and Metacritic scores by IMDb ID (free key, 1,000 a day)."""

from dataclasses import dataclass

import httpx

API = "https://www.omdbapi.com/"


@dataclass(frozen=True)
class Scores:
    imdb: float | None = None
    rt: int | None = None
    metacritic: int | None = None


def parse(data: dict) -> Scores:
    """{"imdbRating": "7.8", "Ratings": [{"Source": "Rotten Tomatoes", "Value": "92%"}, ...]}"""
    if data.get("Response") != "True":
        return Scores()
    try:
        imdb = float(data.get("imdbRating", ""))
    except ValueError:
        imdb = None
    rt = metacritic = None
    for rating in data.get("Ratings", []):
        source, value = rating.get("Source"), rating.get("Value", "")
        if source == "Rotten Tomatoes" and value[:-1].isdigit() and value.endswith("%"):
            rt = int(value[:-1])
        if source == "Metacritic" and value.split("/")[0].isdigit():
            metacritic = int(value.split("/")[0])
    return Scores(imdb, rt, metacritic)


def lookup(client: httpx.Client, key: str, imdb_id: str) -> Scores:
    response = client.get(API, params={"i": imdb_id, "apikey": key})
    response.raise_for_status()
    return parse(response.json())
