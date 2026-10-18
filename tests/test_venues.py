from cineclock.scrapers import cinematheque, dunbar, park, rio, viff
from cineclock.venues import BY_NAME, SPEC_FIELDS, VENUES, order, room_label, shown_specs


def test_every_scraped_venue_is_registered():
    for scraper in (rio, park, cinematheque, viff, dunbar):
        for name in scraper.VENUES:
            assert name in BY_NAME


def test_order_is_rio_park_cinematheque_viff_dunbar():
    names = sorted(BY_NAME, key=order)
    assert names == ["The Rio", "The Park", "The Cinematheque", "VIFF Centre", "The Dunbar"]


def test_every_scraper_room_exists_at_its_venue():
    for scraper in (rio, park, cinematheque, dunbar):
        assert BY_NAME[scraper.VENUE].room(scraper.ROOM)
    for room in viff.ROOMS.values():
        assert BY_NAME[viff.VENUE].room(room)


def test_room_ids_are_unique():
    ids = [r.id for v in VENUES for r in v.rooms]
    assert len(set(ids)) == len(ids)


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


def test_every_venue_has_rooms_and_a_neighbourhood():
    for v in VENUES:
        assert v.rooms and v.neighbourhood and v.short


def test_specs_are_known_fields_with_a_source():
    for v in VENUES:
        for room in v.rooms:
            assert set(room.specs) <= set(SPEC_FIELDS), room.id
            assert room.sources, room.id


def test_only_specs_every_room_has_are_shown():
    assert shown_specs() == ["Seats"]


def test_room_label_only_for_rooms_other_than_the_main_one():
    assert room_label("VIFF Centre", "viff-lochmaddy") == "Lochmaddy"
    assert room_label("VIFF Centre", "viff-main") is None
    assert room_label("VIFF Centre", None) is None
    assert room_label("Somewhere New", "x") is None


def test_monograms():
    assert BY_NAME["The Rio"].monogram == "R"
    assert BY_NAME["The Dunbar"].monogram == "D"
    assert BY_NAME["VIFF Centre"].monogram == "V"
