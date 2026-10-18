from cineclock.scrapers import cinematheque, park, rio, viff
from cineclock.venues import BY_NAME, VENUES, order


def test_every_scraped_venue_is_registered():
    for scraper in (rio, park, cinematheque, viff):
        for name in scraper.VENUES:
            assert name in BY_NAME


def test_order_is_rio_park_cinematheque_viff():
    names = sorted(BY_NAME, key=order)
    assert names == ["The Rio", "The Park", "The Cinematheque", "VIFF Centre", "VIFF Lochmaddy"]


def test_unknown_venue_sorts_last():
    assert order("Somewhere New") == len(VENUES)


def test_slugs_are_unique_and_url_safe():
    slugs = [v.slug for v in VENUES]
    assert len(set(slugs)) == len(slugs)
    assert all(s.replace("-", "").isalnum() and s.islower() for s in slugs)


def test_only_rio_and_park_prefer_their_own_posters():
    assert {v.name for v in VENUES if v.own_posters} == {"The Rio", "The Park"}


def test_map_link_searches_the_address():
    assert BY_NAME["The Rio"].map_url.endswith(
        "query=1660+East+Broadway%2C+Vancouver%2C+BC+V5N+1W1"
    )


def test_every_venue_has_specs_and_a_neighbourhood():
    for v in VENUES:
        assert v.specs and v.neighbourhood and v.short


def test_monograms():
    assert BY_NAME["The Rio"].monogram == "R"
    assert BY_NAME["VIFF Lochmaddy"].monogram == "L"
    assert BY_NAME["VIFF Centre"].monogram == "VC"
