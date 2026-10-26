"""A Letterboxd member's public watchlist, watched films and recent diary.

Letterboxd has no API, so we read the same public pages a browser would:
  /<user>/watchlist/page/N/  film slugs on the watchlist
  /<user>/films/page/N/      films they've marked watched, with their star rating
  /<user>/rss/               their latest diary entries, with the date watched

Letterboxd blocks the watched list past its first page (and the full diary),
so a synced profile knows the whole watchlist but only recent watches.

Films are identified by Letterboxd's own slug ("santa-sangre"), which the
site already stores for every matched film, so matching is exact rather than
a guess on title and year.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import date
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

BASE = "https://letterboxd.com"
# Members whose lists the site reads on each update. Letterboxd won't let a
# browser read profiles from another site, so these are the usernames that work.
SYNCED = ["yogzoth"]
MAX_PAGES = 60  # 60 pages of watched films is over 4,000; a safety stop, not a limit we expect
LB_NS = "{https://letterboxd.com}"


@dataclass
class Profile:
    user: str
    watchlist: set[str] = field(default_factory=set)
    # slug -> rating out of 10 (Letterboxd's half stars), or None if watched but unrated
    watched: dict[str, int | None] = field(default_factory=dict)
    # slug -> most recent date in the diary feed
    diary: dict[str, date] = field(default_factory=dict)
    # The oldest date the diary feed reaches back to. A watched film with no
    # entry after this was seen before it.
    diary_since: date | None = None


def slug_from_link(link: str) -> str | None:
    """/film/santa-sangre/ or https://letterboxd.com/you/film/santa-sangre/1/ -> santa-sangre"""
    match = re.search(r"/film/([^/]+)/", link)
    return match.group(1) if match else None


def parse_grid(page: str) -> tuple[dict[str, int | None], bool]:
    """Film slugs on one page of a poster grid, each with its rating if shown,
    and whether there's a next page."""
    soup = BeautifulSoup(page, "html.parser")
    films: dict[str, int | None] = {}
    for item in soup.select("li.griditem"):
        poster = item.select_one("[data-item-slug]")
        if not poster:
            continue
        rated = item.select_one(".poster-viewingdata [class*=rated-]")
        match = re.search(r"\brated-(\d+)\b", " ".join(rated["class"])) if rated else None
        films[poster["data-item-slug"]] = int(match.group(1)) if match else None
    return films, soup.select_one("a.next") is not None


def parse_rss(feed: str) -> dict[str, date]:
    """Diary entries in the RSS feed: film slug -> the latest date watched."""
    seen: dict[str, date] = {}
    for item in ElementTree.fromstring(feed).iter("item"):
        watched = item.findtext(f"{LB_NS}watchedDate")
        slug = slug_from_link(item.findtext("link") or "")
        if not watched or not slug:
            continue  # list updates and other non-diary items
        day = date.fromisoformat(watched)
        if slug not in seen or day > seen[slug]:
            seen[slug] = day
    return seen


def fetch_grid(client: httpx.Client, path: str, pause: float) -> dict[str, int | None]:
    films: dict[str, int | None] = {}
    for number in range(1, MAX_PAGES + 1):
        response = client.get(f"{BASE}/{path}/page/{number}/" if number > 1 else f"{BASE}/{path}/")
        if response.status_code == 403 and number > 1:
            # Letterboxd blocks deeper pages of some lists (the watched list past
            # page one). Keep what we have rather than lose the lot.
            print(f"Letterboxd {path}: stopped at page {number} (blocked)")
            break
        response.raise_for_status()
        page, more = parse_grid(response.text)
        films.update(page)
        if not more:
            break
        time.sleep(pause)  # be gentle; this runs once a day at most
    return films


def fetch(client: httpx.Client, user: str, pause: float = 1.0) -> Profile:
    profile = Profile(user)
    profile.watchlist = set(fetch_grid(client, f"{user}/watchlist", pause))
    profile.watched = fetch_grid(client, f"{user}/films", pause)
    response = client.get(f"{BASE}/{user}/rss/")
    response.raise_for_status()
    profile.diary = parse_rss(response.text)
    profile.diary_since = min(profile.diary.values(), default=None)
    # Films in the diary feed are watched even if the watched list didn't reach them.
    for slug in profile.diary:
        profile.watched.setdefault(slug, None)
    return profile
