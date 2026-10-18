import httpx
import pytest

from cineclock.enrich import letterboxd, omdb


def test_letterboxd_page(fixture_text):
    url, rating = letterboxd.parse_film_page(fixture_text("enrich/letterboxd_the_thing.html"))
    assert url == "https://letterboxd.com/film/the-thing/"
    assert rating == 4.24


def test_letterboxd_page_without_rating():
    # Films with too few ratings have no average yet.
    page = '<meta property="og:url" content="https://letterboxd.com/film/obscure/">'
    assert letterboxd.parse_film_page(page) == ("https://letterboxd.com/film/obscure/", None)


def test_letterboxd_lookup_follows_the_redirect(fixture_text):
    def handler(request):
        if request.url.path == "/tmdb/1091/":
            return httpx.Response(
                302, headers={"Location": "https://letterboxd.com/film/the-thing/"}
            )
        return httpx.Response(200, text=fixture_text("enrich/letterboxd_the_thing.html"))

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        assert letterboxd.lookup(client, 1091) == ("https://letterboxd.com/film/the-thing/", 4.24)


def test_letterboxd_blocked_raises():
    def handler(request):
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            letterboxd.lookup(client, 1091)


def test_omdb(fixture_json):
    assert omdb.parse(fixture_json("enrich/omdb_tt0084787.json")) == (8.2, 84)


@pytest.mark.parametrize(
    "data, expected",
    [
        ({"Response": "False", "Error": "Incorrect IMDb ID."}, (None, None)),
        ({"Response": "True", "imdbRating": "N/A", "Ratings": []}, (None, None)),
        ({"Response": "True", "imdbRating": "6.1"}, (6.1, None)),
        (
            {
                "Response": "True",
                "imdbRating": "N/A",
                "Ratings": [{"Source": "Rotten Tomatoes", "Value": "100%"}],
            },
            (None, 100),
        ),
    ],
)
def test_omdb_partial(data, expected):
    assert omdb.parse(data) == expected


def test_omdb_lookup_sends_id_and_key(fixture_json):
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=fixture_json("enrich/omdb_tt0084787.json"))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert omdb.lookup(client, "key", "tt0084787") == (8.2, 84)
    assert seen == {"i": "tt0084787", "apikey": "key"}
