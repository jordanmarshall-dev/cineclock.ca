"""Look up details for every film that's showing: poster, synopsis, links and ratings.

TMDB finds the film. Letterboxd gives its page and rating. OMDb gives the IMDb
and Rotten Tomatoes ratings. Results are cached for a week per film, and a
film that couldn't be found isn't searched again until then either.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from cineclock import db
from cineclock.enrich import letterboxd, omdb, tmdb
from cineclock.films import Film, match_key

REFRESH_MATCHED = timedelta(days=30)
RETRY_UNMATCHED = timedelta(days=7)


@dataclass(frozen=True)
class EnrichResult:
    looked_up: int
    matched: int
    failed: int


def needs_backfill(film: Film) -> bool:
    """Films saved before rating counts were collected get one early refresh."""
    return film.letterboxd_rating is not None and film.letterboxd_count is None


def lookup_film(
    client: httpx.Client,
    title: str,
    year: int | None,
    now: datetime,
    tmdb_key: str,
    omdb_key: str | None,
    pause: float,
) -> Film:
    found = tmdb.find(client, tmdb_key, title, year)
    if not found:
        return Film(match_key=match_key(title, year), fetched_at=now)

    lb, imdb_rating, rt_score = letterboxd.LetterboxdFilm(), None, None
    # Letterboxd and OMDb are extras: if either is down, keep the TMDB match.
    try:
        time.sleep(pause)  # Be gentle with Letterboxd, which has no API.
        lb = letterboxd.lookup(client, found["tmdb_id"])
    except httpx.HTTPError:
        pass
    if omdb_key and found["imdb_id"]:
        try:
            imdb_rating, rt_score = omdb.lookup(client, omdb_key, found["imdb_id"])
        except httpx.HTTPError:
            pass

    return Film(
        match_key=match_key(title, year),
        fetched_at=now,
        letterboxd_url=lb.url,
        letterboxd_rating=lb.rating,
        letterboxd_count=lb.rating_count,
        imdb_rating=imdb_rating,
        rt_score=rt_score,
        **found,
    )


def enrich(
    conn,
    client: httpx.Client,
    now: datetime,
    tmdb_key: str | None,
    omdb_key: str | None = None,
    pause: float = 0.5,
) -> EnrichResult:
    if not tmdb_key:
        return EnrichResult(looked_up=0, matched=0, failed=0)

    wanted = {(s.title, s.year) for s in db.upcoming(conn, now)}
    looked_up = matched = failed = 0
    for title, year in sorted(wanted, key=lambda item: (item[0], item[1] or 0)):
        cached = db.get_film(conn, match_key(title, year))
        if cached and not needs_backfill(cached):
            wait = REFRESH_MATCHED if cached.matched else RETRY_UNMATCHED
            if now - cached.fetched_at < wait:
                continue
        try:
            film = lookup_film(client, title, year, now, tmdb_key, omdb_key, pause)
        except httpx.HTTPError:
            # Not saved, so it's retried on the next run.
            failed += 1
            continue
        db.save_film(conn, film)
        looked_up += 1
        matched += film.matched
    return EnrichResult(looked_up=looked_up, matched=matched, failed=failed)
