from datetime import UTC, date, datetime

from cineclock import personal
from cineclock.films import Film, match_key
from cineclock.models import VANCOUVER, Screening
from cineclock.profiles import Profile
from cineclock.site import FilmPage, venue_for, when

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


def test_films_index_has_what_a_card_needs():
    show = datetime(2026, 10, 19, 19, 0, tzinfo=VANCOUVER)
    [entry] = personal.films_index([page("jaws", "jaws", show)], NOW, when)
    assert entry["lb"] == "jaws" and entry["next"] == "Tomorrow, 7:00 pm"
    assert entry["venues"][0]["src"] == "static/logos/rio-mark.png"


def test_watchlist_calendar_lists_each_screening():
    shows = [
        datetime(2026, 10, 19, 19, 0, tzinfo=VANCOUVER),
        datetime(2026, 10, 20, 21, 0, tzinfo=VANCOUVER),
    ]
    films = [page("jaws", "jaws", *shows, runtime=124), page("heat", "heat", shows[0])]
    feed = personal.watchlist_calendar(PROFILE, films, venue_for, NOW)
    assert feed.count("BEGIN:VEVENT") == 2  # heat is seen, not on the watchlist
    assert "DTSTART:20261020T020000Z" in feed  # 7 pm in Vancouver is 2 am UTC
    assert "DTEND:20261020T040400Z" in feed  # plus the 124-minute runtime
    assert "SUMMARY:Jaws at The Rio" in feed
    assert "LOCATION:1660 East Broadway\\, Vancouver\\, BC V5N 1W1" in feed
    assert all(len(line) <= 75 for line in feed.split("\r\n"))
    assert feed.endswith("END:VCALENDAR\r\n")
