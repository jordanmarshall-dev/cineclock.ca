from datetime import UTC, date, datetime

from cineclock import personal
from cineclock.films import Film, match_key
from cineclock.listings import FilmPage
from cineclock.models import Screening
from cineclock.profiles import Profile

NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)

PROFILE = Profile(
    "me",
    watchlist={"jaws", "alien"},
    watched={"alien": 9, "heat": None, "jaws": None},
    diary={"heat": date(2026, 10, 9)},
    diary_since=date(2026, 8, 10),
)


def page(slug, lb_slug, *starts, runtime=None):
    film = Film(
        match_key(slug, None), NOW, tmdb_id=1, title=slug.title(), runtime=runtime,
        letterboxd_url=f"https://letterboxd.com/film/{lb_slug}/" if lb_slug else None,
    )  # fmt: skip
    shows = [Screening("The Rio", slug.title(), t, f"https://tix/{slug}/{t:%d%H}") for t in starts]
    return FilmPage(slug, slug.title(), None, film, shows)


def test_status_uses_short_keys():
    assert personal.status(PROFILE, "jaws") == {"w": 1, "s": 1, "old": 1}
    assert personal.status(PROFILE, "alien") == {"w": 1, "s": 1, "r": 9, "old": 1}
    assert personal.status(PROFILE, "heat") == {"s": 1, "d": "2026-10-09"}
    assert personal.status(PROFILE, "nope") is None


def test_profile_json_only_covers_films_playing():
    films = [page("jaws", "jaws"), page("musk", "musk"), page("mystery", None)]
    data = personal.profile_json(PROFILE, films, NOW)
    assert data["user"] == "me"
    assert data["films"] == {"jaws": {"w": 1, "s": 1, "old": 1}}
