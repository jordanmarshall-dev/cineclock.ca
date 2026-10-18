from datetime import UTC, datetime

import pytest

from cineclock.films import Film, match_key, normalize, search_queries, slugify

NOW = datetime(2026, 10, 18, tzinfo=UTC)


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Don’t Look Now", "dont look now"),
        ("Harold & Maude", "harold and maude"),
        ("Amélie", "amelie"),
        ("Dune: Part Three", "dune part three"),
        ("  (500) Days of Summer ", "500 days of summer"),
        ("M*A*S*H", "m a s h"),
    ],
)
def test_normalize(title, expected):
    assert normalize(title) == expected


def test_match_key_ignores_punctuation_but_keeps_year():
    assert match_key("The Thing", 1982) == match_key("the thing", 1982) == "the thing|1982"
    assert match_key("The Thing", 1982) != match_key("The Thing", 2011)
    assert match_key("SFMF Series 2", None) == "sfmf series 2|"


@pytest.mark.parametrize(
    "title, year, expected",
    [
        ("Pulse", 2001, ["Pulse"]),
        ("Ken Russell's 'The Devils'", 1971, ["Ken Russell's 'The Devils'", "The Devils"]),
        (
            "John Woo’s “A Better Tomorrow”",
            1986,
            ["John Woo’s “A Better Tomorrow”", "A Better Tomorrow"],
        ),
        (
            "Gremlins: In Conversation with Zach Galligan",
            1984,
            ["Gremlins: In Conversation with Zach Galligan", "Gremlins"],
        ),
        # Without a year, "Dune" alone could be any Dune
        ("Dune: Part Three", None, ["Dune: Part Three"]),
    ],
)
def test_search_queries(title, year, expected):
    assert search_queries(title, year) == expected


def test_links_for_a_matched_film():
    film = Film("the thing|1982", NOW, tmdb_id=1091, imdb_id="tt0084787", title="The Thing")
    assert film.matched
    assert film.letterboxd_link == "https://letterboxd.com/tmdb/1091/"
    assert film.imdb_link == "https://www.imdb.com/title/tt0084787/"
    assert film.rt_link == "https://www.rottentomatoes.com/search?search=The+Thing"


def test_letterboxd_page_wins_over_redirect_link():
    film = Film("x|", NOW, tmdb_id=1091, letterboxd_url="https://letterboxd.com/film/the-thing/")
    assert film.letterboxd_link == "https://letterboxd.com/film/the-thing/"


def test_unmatched_film_has_no_links():
    film = Film("sfmf series 2|", NOW)
    assert not film.matched
    assert film.letterboxd_link is film.imdb_link is film.rt_link is None


def test_slugify():
    assert slugify("Ken Russell's 'The Devils'") == "ken-russells-the-devils"
    assert slugify("???") == "film"
