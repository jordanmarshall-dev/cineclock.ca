"""What we know about a film beyond its showtimes, and how venue titles map to it."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Film:
    """Details for one venue title and year, looked up from TMDB, Letterboxd and OMDb."""

    match_key: str
    fetched_at: datetime
    tmdb_id: int | None = None
    imdb_id: str | None = None
    title: str | None = None
    year: int | None = None
    director: str | None = None
    runtime: int | None = None
    overview: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None
    letterboxd_url: str | None = None
    letterboxd_rating: float | None = None
    imdb_rating: float | None = None
    rt_score: int | None = None

    @property
    def matched(self) -> bool:
        return self.tmdb_id is not None

    @property
    def letterboxd_link(self) -> str | None:
        # letterboxd.com/tmdb/<id>/ redirects to the film, so it works even
        # when we couldn't read the page ourselves.
        if self.letterboxd_url:
            return self.letterboxd_url
        return f"https://letterboxd.com/tmdb/{self.tmdb_id}/" if self.tmdb_id else None

    @property
    def imdb_link(self) -> str | None:
        return f"https://www.imdb.com/title/{self.imdb_id}/" if self.imdb_id else None

    @property
    def rt_link(self) -> str | None:
        # No API gives Rotten Tomatoes page addresses, so link to its search.
        if not self.title:
            return None
        return f"https://www.rottentomatoes.com/search?search={quote_plus(self.title)}"


def normalize(title: str) -> str:
    """Lowercase, no accents or punctuation: "Don’t Look Now" -> "dont look now"."""
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"['’‘`]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def match_key(title: str, year: int | None) -> str:
    return f"{normalize(title)}|{year or ''}"


# "Ken Russell's 'The Devils'" or "John Woo’s “A Better Tomorrow”"
POSSESSIVE = re.compile(r"^[\w .\-]+?['’]s\s+['‘’\"“”](?P<title>.+?)['‘’\"“”]$")


def search_queries(title: str, year: int | None) -> list[str]:
    """Titles to try on TMDB, best first."""
    queries = [title]
    possessive = POSSESSIVE.match(title)
    if possessive:
        queries.append(possessive["title"])
    # "Gremlins: In Conversation with Zach Galligan" -> "Gremlins", but only with
    # a year to check against; alone, "Dune" would match the wrong Dune.
    if year and ":" in title:
        queries.append(title.split(":", 1)[0].strip())
    return list(dict.fromkeys(q for q in queries if q))


def slugify(text: str) -> str:
    return normalize(text).replace(" ", "-") or "film"
