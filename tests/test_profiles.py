from datetime import date

import httpx

from cineclock import profiles
from cineclock.profiles import parse_grid, parse_rss, slug_from_link


def test_watchlist_page_lists_film_slugs(fixture_text):
    films, more = parse_grid(fixture_text("letterboxd_user/watchlist_page1.html"))
    assert len(films) == 28 and more
    assert "santa-sangre" in films
    assert all(rating is None for rating in films.values())


def test_watched_page_has_ratings_out_of_ten(fixture_text):
    films, more = parse_grid(fixture_text("letterboxd_user/films_page1.html"))
    assert len(films) == 72 and more
    assert films["gasmask"] == 8  # four stars
    assert films["pre-parenting"] is None  # watched, not rated


def test_diary_feed_keeps_the_latest_watch_and_skips_lists(fixture_text):
    diary = parse_rss(fixture_text("letterboxd_user/rss.xml"))
    assert diary["you-can-see-everything"] == date(2026, 10, 17)
    assert min(diary.values()) == date(2026, 8, 10)
    assert not any(slug.startswith("viff-2026") for slug in diary)


def test_slug_from_link():
    assert slug_from_link("/film/santa-sangre/") == "santa-sangre"
    assert slug_from_link("https://letterboxd.com/yogzoth/film/jaws/1/") == "jaws"
    assert slug_from_link("https://letterboxd.com/yogzoth/list/canadian-horror/") is None


def test_fetch_follows_pages_until_there_is_no_next(fixture_text):
    last = '<ul><li class="griditem"><div data-item-slug="jaws"></div></li></ul>'
    pages = {
        "/yogzoth/watchlist/": fixture_text("letterboxd_user/watchlist_page1.html"),
        "/yogzoth/watchlist/page/2/": last,
        "/yogzoth/films/": last,
        "/yogzoth/rss/": fixture_text("letterboxd_user/rss.xml"),
    }
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, text=pages[request.url.path])

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        profile = profiles.fetch(client, "yogzoth", pause=0)
    assert len(profile.watchlist) == 29
    assert profile.watched["jaws"] is None
    # Diary films count as watched even when the watched list stops early
    assert "you-can-see-everything" in profile.watched
    assert profile.diary_since == date(2026, 8, 10)
    assert seen.count("/yogzoth/watchlist/page/2/") == 1


def test_blocked_later_pages_keep_what_was_read(fixture_text):
    def handler(request):
        if request.url.path == "/me/films/page/2/":
            return httpx.Response(403)
        return httpx.Response(200, text=fixture_text("letterboxd_user/films_page1.html"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert len(profiles.fetch_grid(client, "me/films", pause=0)) == 72
