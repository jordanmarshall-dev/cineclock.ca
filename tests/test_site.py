import re
from datetime import UTC, date, datetime, timedelta

import pytest

from cineclock import db
from cineclock.films import Film, match_key
from cineclock.models import VANCOUVER, Screening
from cineclock.site import choose_poster, compact, film_pages, group_days, pages, rails, stats
from cineclock.timefmt import clock, day_label, short_day
from cineclock.venues import VENUES, shown_specs

NOW = datetime(2026, 10, 18, 8, 0, tzinfo=UTC)  # 1am Oct 18 in Vancouver


def at(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=VANCOUVER)


def show(title, starts, venue="The Rio", year=None, note=None, poster=None, info=None, room=None):
    return Screening(
        venue, title, starts, f"https://tix/{venue}/{title}/{starts:%d%H%M}",
        info_url=info, year=year, note=note, poster_url=poster, room=room,
    )  # fmt: skip


def plain(html):
    """Page HTML without inline icons, so tests can match the text around them."""
    return re.sub(r"<svg.*?</svg>", "", html, flags=re.S)


def film(title, year, tmdb_id=None, **extra):
    return Film(match_key(title, year), NOW, tmdb_id=tmdb_id, title=title, year=year, **extra)


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def save(conn, *screenings):
    for venue in {s.venue for s in screenings}:
        db.sync_venue(conn, venue, [s for s in screenings if s.venue == venue], NOW)


# Time formatting


@pytest.mark.parametrize(
    "hour, minute, expected",
    [(0, 0, "12:00 am"), (9, 5, "9:05 am"), (12, 0, "12:00 pm"), (23, 45, "11:45 pm")],
)
def test_clock(hour, minute, expected):
    assert clock(at(18, hour, minute)) == expected


def test_day_labels():
    today = date(2026, 10, 18)
    assert day_label(today, today) == "Today, Oct 18"
    assert day_label(date(2026, 10, 19), today) == "Tomorrow, Oct 19"
    assert day_label(date(2026, 11, 6), today) == "Friday, Nov 6"
    assert short_day(date(2026, 10, 20), today) == "Tue 20"


# Posters


def test_rio_and_park_keep_their_own_posters():
    tmdb = film("Tony", 2026, 1, poster_url="https://tmdb/tony.jpg")
    assert choose_poster(
        show("Tony", at(18, 13), "The Park", poster="https://park/tony.jpg"), tmdb
    ) == ("https://park/tony.jpg")


def test_other_venues_use_tmdb_posters_over_stills():
    tmdb = film("Pulse", 2001, 2, poster_url="https://tmdb/pulse.jpg")
    still = show("Pulse", at(18, 20), "The Cinematheque", poster="https://cin/still.jpg")
    assert choose_poster(still, tmdb) == "https://tmdb/pulse.jpg"
    assert choose_poster(still, None) == "https://cin/still.jpg"


def test_rio_falls_back_to_tmdb_without_its_own_poster():
    tmdb = film("Musk", 2026, 3, poster_url="https://tmdb/musk.jpg")
    assert choose_poster(show("Musk", at(18, 12)), tmdb) == "https://tmdb/musk.jpg"


# Film pages


def test_matched_film_shares_one_page_across_venues():
    devils = film("The Devils", 1971, 31767)
    films = {
        match_key("Ken Russell's 'The Devils'", 1971): devils,
        match_key("The Devils", 1971): devils,
    }
    a = show("Ken Russell's 'The Devils'", at(18, 16), "The Park", year=1971)
    b = show("The Devils", at(20, 19), "VIFF Centre", year=1971)
    page_of = film_pages([a, b], films)
    assert page_of[id(a)] is page_of[id(b)]
    assert page_of[id(a)].slug == "the-devils-1971"
    assert page_of[id(a)].title == "The Devils"


def test_unmatched_titles_get_their_own_pages():
    a, b = show("SFMF Series 2", at(18, 13)), show("SFMF Series 3", at(18, 16))
    page_of = film_pages([a, b], {})
    assert page_of[id(a)].slug == "sfmf-series-2"
    assert page_of[id(b)].slug == "sfmf-series-3"


def test_same_title_different_films_get_different_slugs():
    films = {
        match_key("Pulse", 2001): film("Pulse", 2001, 1),
        match_key("Pulse", 2006): film("Pulse", 2006, 2),
        match_key("Pulse", None): film("Pulse", None, 3),
    }
    shows = [show("Pulse", at(18, 20), year=2001), show("Pulse", at(19, 20), year=2006)]
    shows.append(show("Pulse", at(20, 20)))
    slugs = [film_pages(shows, films)[id(s)].slug for s in shows]
    assert slugs == ["pulse-2001", "pulse-2006", "pulse"]


# Grouping by day


def test_late_show_stays_on_its_local_day():
    s = show("Rocky Horror", at(23, 23, 45))
    [day] = group_days([s], film_pages([s], {}), {}, NOW)
    assert day.date == date(2026, 10, 23)


def test_venues_follow_the_set_order():
    shows = [
        show("Mirror", at(18, 19), "The Dunbar"),
        show("Mirror", at(18, 18), "VIFF Centre"),
        show("Pulse", at(18, 20), "The Cinematheque"),
        show("Tony", at(18, 13), "The Park"),
        show("Musk", at(18, 12), "The Rio"),
    ]
    [day] = group_days(shows, film_pages(shows, {}), {}, NOW)
    assert [g.venue.name for g in day.groups] == [
        "The Rio", "The Park", "The Cinematheque", "VIFF Centre", "The Dunbar",
    ]  # fmt: skip


def test_same_film_twice_a_day_shares_a_row_unless_labelled_differently():
    shows = [
        show("Dune: Part Three", at(18, 15), "The Park", note="Presented in 70mm"),
        show("Dune: Part Three", at(18, 18), "The Park", note="Presented in 70mm"),
        show("Dune: Part Three", at(18, 21), "The Park", note="Advance Screening"),
    ]
    [day] = group_days(shows, film_pages(shows, {}), {}, NOW)
    rows = day.groups[0].rows
    assert [(r.note, len(r.showtimes)) for r in rows] == [
        ("Presented in 70mm", 2),
        ("Advance Screening", 1),
    ]


# Whole site


def test_pages_cover_home_films_and_every_venue(conn):
    save(conn, show("Musk", at(18, 12)), show("Pulse", at(18, 20), "The Cinematheque", year=2001))
    built = pages(conn, NOW)
    assert "index.html" in built
    assert "showtimes/index.html" in built
    assert "films/index.html" in built
    assert "theatres/index.html" in built
    assert "films/musk/index.html" in built
    assert "films/pulse-2001/index.html" in built
    for slug in ("rio", "park", "cinematheque", "viff-centre", "dunbar"):
        assert f"theatres/{slug}/index.html" in built


def test_links_are_relative_to_each_page(conn):
    save(conn, show("Musk", at(18, 12)))
    built = pages(conn, NOW)
    assert 'href="films/musk/"' in built["index.html"]
    assert 'href="static/site.css?v=' in built["index.html"]
    assert 'href="../../static/site.css?v=' in built["films/musk/index.html"]
    assert 'href="../../theatres/rio/"' in built["films/musk/index.html"]


def test_film_page_shows_details_ratings_and_links(conn):
    s = show("The Thing", at(31, 17, 40), "VIFF Centre", year=1982, info="https://viff/thing")
    save(conn, s)
    db.save_film(
        conn,
        film(
            "The Thing", 1982, 1091,
            imdb_id="tt0084787", director="John Carpenter", runtime=109,
            overview="A research team in Antarctica.", poster_url="https://tmdb/p.jpg",
            backdrop_url="https://tmdb/b.jpg", letterboxd_url="https://letterboxd.com/film/the-thing/",
            letterboxd_rating=4.35, imdb_rating=8.2, rt_score=85,
        ),
    )  # fmt: skip
    page = pages(conn, NOW)["films/the-thing-1982/index.html"]
    for expected in [
        "Directed by </span><b>John Carpenter</b>",
        "1h 49m",
        "A research team in Antarctica.",
        ">4.3<",
        ">8.2<",
        ">85%<",
        'href="https://letterboxd.com/film/the-thing/"',
        'href="https://www.imdb.com/title/tt0084787/"',
        "rottentomatoes.com/search?search=The+Thing",
        'href="https://tix/VIFF Centre/The Thing/311740"',
        'src="https://tmdb/b.jpg"',
        "has-backdrop",
    ]:
        assert expected in page, expected


def test_film_page_links_go_through_score_tiles(conn):
    save(conn, show("The Thing", at(31, 17, 40), "VIFF Centre", year=1982, info="https://viff/x"))
    db.save_film(conn, film("The Thing", 1982, 1091, imdb_id="tt0084787", letterboxd_rating=4.35))
    page = pages(conn, NOW)["films/the-thing-1982/index.html"]
    assert 'href="https://letterboxd.com/tmdb/1091/"' in page
    assert 'class="links"' not in page
    assert "https://viff/x" not in page
    assert 'href="../../theatres/viff-centre/">' in page


def test_film_page_hides_ratings_it_does_not_have(conn):
    save(conn, show("The Thing", at(31, 17, 40), year=1982))
    db.save_film(conn, film("The Thing", 1982, 1091, imdb_id="tt0084787", imdb_rating=8.2))
    page = pages(conn, NOW)["films/the-thing-1982/index.html"]
    assert "rating-imdb" in page
    for missing in ("rating-letterboxd", "rating-rt", "rating-metacritic", "–<"):
        assert missing not in page.split("<main>")[1].split("</main>")[0], missing


def test_film_page_without_any_ratings_has_no_score_row(conn):
    save(conn, show("The Thing", at(31, 17, 40), year=1982))
    db.save_film(conn, film("The Thing", 1982, 1091))
    assert 'class="scores"' not in pages(conn, NOW)["films/the-thing-1982/index.html"]


def test_unmatched_film_page_still_has_showtimes(conn):
    save(conn, show("SFMF Series 2", at(18, 13), "The Cinematheque"))
    page = pages(conn, NOW)["films/sfmf-series-2/index.html"]
    assert "1:00 pm" in page
    assert "Letterboxd</a>" not in page


def test_venue_page_lists_only_its_shows(conn):
    save(conn, show("Musk", at(18, 12)), show("Pulse", at(18, 20), "The Cinematheque"))
    page = pages(conn, NOW)["theatres/rio/index.html"]
    main = page.split("<main>")[1]
    assert "Musk" in main and "Pulse" not in main
    assert "1660 East Broadway" in page
    assert 'aria-current="page"' in page


def test_empty_venue_page_points_to_its_website(conn):
    page = pages(conn, NOW)["theatres/dunbar/index.html"]
    assert "Nothing listed here right now" in page


def test_titles_are_escaped(conn):
    save(conn, show("<script>alert(1)</script>", at(18, 12)))
    built = pages(conn, NOW)
    assert all("<script>alert(1)</script>" not in html for html in built.values())


def test_stats(conn):
    save(conn, show("The Thing", at(31, 17), "VIFF Centre", year=1982), show("SFMF", at(18, 13)))
    db.save_film(conn, film("The Thing", 1982, 1091, letterboxd_rating=4.35))
    summary = stats(conn, NOW)
    assert summary["screenings"] == 2
    assert summary["per_venue"] == {"The Rio": 1, "VIFF Centre": 1}
    assert (summary["matched"], summary["with_letterboxd_rating"]) == (1, 1)
    assert summary["unmatched"] == ["sfmf|"]


def test_past_screenings_are_left_out(conn):
    save(conn, show("Gone", NOW - timedelta(hours=1)), show("Musk", at(18, 12)))
    assert "Gone" not in pages(conn, NOW)["index.html"]


# Home page rails


def rail_titles(conn, now=NOW):
    screenings = db.upcoming(conn, now)
    page_of = film_pages(screenings, db.films_by_key(conn))
    return {r.title: r for r in rails(list({id(p): p for p in page_of.values()}.values()), now)}


@pytest.mark.parametrize(
    "n, expected",
    [(999, "999"), (1_000, "1K"), (12_345, "12K"), (1_476_132, "1.5M"), (2_000_000, "2M")],
)
def test_compact(n, expected):
    assert compact(n) == expected


def test_on_today_lists_todays_films_by_time(conn):
    save(conn, show("Late", at(18, 21)), show("Early", at(18, 13)), show("Tomorrow", at(19, 13)))
    today = rail_titles(conn)["On today"]
    assert [(c.page.title, c.next_label, c.why) for c in today.cards] == [
        ("Early", "Today, 1:00 pm", None),
        ("Late", "Today, 9:00 pm", None),
    ]
    assert today.more == "showtimes/#d20261018"


def test_just_added_skips_the_first_run(conn):
    save(conn, show("Old", at(20, 19)))
    assert "Just added" not in rail_titles(conn)
    later = NOW + timedelta(days=2)
    db.sync_venue(conn, "The Rio", [show("Old", at(20, 19)), show("New", at(22, 19))], later)
    assert [c.page.title for c in rail_titles(conn, later)["Just added"].cards] == ["New"]


def test_highly_rated_needs_enough_ratings(conn):
    save(conn, show("Classic", at(18, 19), year=1970), show("Obscure", at(18, 20), year=2020))
    db.save_film(conn, film("Classic", 1970, 1, letterboxd_rating=4.1, letterboxd_count=50_000))
    db.save_film(conn, film("Obscure", 2020, 2, letterboxd_rating=4.9, letterboxd_count=12))
    found = rail_titles(conn)
    assert [c.page.title for c in found["Highly rated"].cards] == ["Classic"]
    assert found["Highly rated"].cards[0].why == "4.1 on Letterboxd"
    assert found["Highly rated"].cards[0].next_label == "Today, 7:00 pm"
    assert found["Highly rated"].more == "films/?sort=rated"
    assert [c.page.title for c in found["Popular"].cards] == ["Classic", "Obscure"]
    assert found["Popular"].cards[0].why == "50K Letterboxd ratings"


def test_most_screenings(conn):
    save(conn, show("Once", at(19, 19)), *[show("Lots", at(d, 19)) for d in (18, 19, 20)])
    cards = rail_titles(conn)["Most screenings"].cards
    assert [(c.page.title, c.why) for c in cards] == [("Lots", "3 screenings")]


def test_on_film_rail(conn):
    save(
        conn,
        show("Dune: Part Three", at(18, 19), "The Park", note="Presented in 70mm"),
        Screening("The Cinematheque", "Vertigo", at(19, 19), "https://x", film_format="35mm"),
        show("Musk", at(18, 12)),
    )
    on_film = rail_titles(conn)["On film"]
    assert [(c.page.title, c.why) for c in on_film.cards] == [
        ("Dune: Part Three", "70mm"),
        ("Vertigo", "35mm"),
    ]
    assert on_film.more == "films/?tag=on-film"


def test_empty_rails_are_left_out(conn):
    save(conn, show("Musk", at(30, 12)))
    assert set(rail_titles(conn)) == {"Coming up"}


def test_leaving_soon_lists_films_whose_last_showing_is_this_week(conn):
    save(
        conn,
        show("Stays", at(19, 19)),
        show("Stays", at(30, 19)),
        show("Goes Later", at(19, 19)),
        show("Goes Later", at(23, 19)),
        show("Goes", at(20, 19)),
    )
    rail = rail_titles(conn)["Leaving soon"]
    assert [c.page.title for c in rail.cards] == ["Goes", "Goes Later"]
    assert rail.cards[0].why == "Last showing Tue Oct 20"
    assert rail.more == "films/?sort=leaving"


def test_coming_up_skips_what_is_on_today(conn):
    save(conn, show("Today", at(18, 19)), show("Later", at(25, 19)), show("Soon", at(19, 19)))
    assert [c.page.title for c in rail_titles(conn)["Coming up"].cards] == ["Soon", "Later"]


# Tags and filters


def test_rows_carry_tags_and_filter_data(conn):
    save(conn, show("Dune: Part Three", at(18, 19), "The Park", note="Presented in 70mm"))
    page = pages(conn, NOW)["showtimes/index.html"]
    assert 'data-venues="park"' in page
    assert 'data-tags="one-screening 70mm on-film"' in page
    assert 'class="tag tag-format tag-70mm">70mm<' in plain(page)
    assert 'data-value="on-film"' in page


def test_one_screening_tag_only_when_it_plays_once(conn):
    save(conn, show("Twice", at(18, 19)), show("Twice", at(19, 19)), show("Once", at(18, 21)))
    page = pages(conn, NOW)["showtimes/index.html"]
    assert page.count("tag-one-screening") == 1


def test_film_page_shows_tags(conn):
    save(
        conn, Screening("The Cinematheque", "Vertigo", at(19, 19), "https://x", film_format="35mm")
    )
    page = pages(conn, NOW)["films/vertigo/index.html"]
    assert ">35mm<" in page and ">One screening<" in page


def test_every_rail_has_a_see_all_link(conn):
    save(conn, show("Lots", at(18, 19)), show("Lots", at(19, 19)), show("Soon", at(20, 19)))
    for rail in rail_titles(conn).values():
        assert rail.more.startswith(("films/", "showtimes/")), rail.title


def test_next_label_for_later_days(conn):
    save(conn, show("Later", at(24, 20, 15)))
    [card] = rail_titles(conn)["Coming up"].cards
    assert card.next_label == "Oct 24, 8:15 pm"


def test_home_cards_show_year_reason_next_showing_and_theatres(conn):
    save(
        conn,
        show("Classic", at(18, 19), year=1970),
        show("Classic", at(20, 19), "The Cinematheque", year=1970),
    )
    db.save_film(conn, film("Classic", 1970, 1, letterboxd_rating=4.1, letterboxd_count=50_000))
    home = pages(conn, NOW)["index.html"]
    assert '<span class="year">1970</span>' in home
    assert '<span class="card-why">4.1 on Letterboxd</span>' in home
    assert '<span class="card-next">Today, 7:00 pm</span>' in plain(home)
    assert 'title="The Rio"' in home and 'title="The Cinematheque"' in home


def test_films_page_lists_each_film_once_with_dates(conn):
    save(conn, show("Musk", at(18, 12)), show("Musk", at(25, 12)), show("Pulse", at(19, 20)))
    page = pages(conn, NOW)["films/index.html"]
    assert page.count('class="film-item"') == 2
    assert "Oct 18 to Oct 25" in page
    assert "Oct 19 only" in page
    assert 'data-sort-screenings="2"' in page


def test_films_page_genre_filter_data(conn):
    save(conn, show("The Thing", at(18, 20), year=1982))
    db.save_film(conn, film("The Thing", 1982, 1091, genres="Horror, Science Fiction"))
    page = pages(conn, NOW)["films/index.html"]
    assert 'data-genres="horror science-fiction"' in page
    assert 'data-value="science-fiction"' in page


def test_theatres_page_lists_every_venue(conn):
    page = pages(conn, NOW)["theatres/index.html"]
    for name in ("The Rio", "The Park", "The Cinematheque", "VIFF Centre", "The Dunbar"):
        assert name in page


def test_theatre_page_has_specs_and_about(conn):
    page = pages(conn, NOW)["theatres/cinematheque/index.html"]
    assert "<dt>Seats</dt><dd>153</dd>" in plain(page)
    assert "Pacific Cinémathèque Pacifique Society" in page


def test_badge_falls_back_to_initials_without_a_logo(conn, monkeypatch, tmp_path):
    import shutil

    import cineclock.render as render

    # A static folder with the stylesheet but no logo files
    for name in ("site.css", "filters.js"):
        shutil.copy(render.STATIC / name, tmp_path / name)
    monkeypatch.setattr(render, "STATIC", tmp_path)
    save(conn, show("Musk", at(18, 12)))
    page = pages(conn, NOW)["index.html"]
    assert '<span class="monogram" role="img" aria-label="The Rio">R</span>' in page


def test_ratings_show_on_listings_without_toggles(conn):
    save(conn, show("The Thing", at(18, 20), year=1982))
    db.save_film(conn, film("The Thing", 1982, 1091, imdb_rating=8.2, metacritic=57))
    page = pages(conn, NOW)["showtimes/index.html"]
    assert 'class="rating rating-imdb"' in page and 'class="rating rating-metacritic"' in page
    assert "rating-letterboxd" not in page
    assert "rating-switches" not in page


def test_viff_rooms_share_one_venue_and_label_each_room(conn):
    save(
        conn,
        show("NAZA", at(19, 16), "VIFF Centre", room="viff-main"),
        show("NAZA", at(20, 16), "VIFF Centre", room="viff-lochmaddy"),
    )
    [p] = {id(x): x for x in film_pages(db.upcoming(conn, NOW), {}).values()}.values()
    assert [v.name for v in p.venues] == ["VIFF Centre"]
    page = pages(conn, NOW)["films/naza/index.html"]
    assert page.count("<small>Lochmaddy</small>") == 1
    assert page.count("<small>VIFF Cinema</small>") == 1


def test_every_theatre_page_shows_the_same_spec_fields(conn):
    built = pages(conn, NOW)
    for v in VENUES:
        page = built[f"theatres/{v.slug}/index.html"]
        assert re.findall(r"<dt>(\w+)</dt>", plain(page)) == shown_specs() * len(v.rooms), v.name


def test_viff_page_has_a_room_picker(conn):
    page = pages(conn, NOW)["theatres/viff-centre/index.html"]
    assert '<option value="viff-lochmaddy">Lochmaddy Studio Theatre</option>' in page
    assert "<dt>Seats</dt><dd>41</dd>" in plain(page)
    assert "room-picker" not in pages(conn, NOW)["theatres/rio/index.html"]


def test_theatre_page_uses_its_full_logo(conn):
    page = pages(conn, NOW)["theatres/park/index.html"]
    assert 'class="theatre-full-logo" src="../../static/logos/park-full.png"' in page


def test_theatre_logos_get_about_the_same_area():
    from cineclock.render import logo_size

    sizes = [logo_size(f"logos/{v.mark}", 900, 12) for v in VENUES if v.mark_scale == 1]
    areas = [w * h for w, h in sizes]
    # Wide logos would drop below the minimum height, so allow some spread
    assert max(areas) / min(areas) < 1.3
    assert all(h >= 12 for _, h in sizes)


def test_showtimes_use_the_logo_as_the_theatre_name(conn):
    save(conn, show("Musk", at(18, 12)))
    page = pages(conn, NOW)["showtimes/index.html"]
    heading = page.split('class="venue-heading"')[1].split("</h3>")[0]
    assert 'alt="The Rio"' in heading
    assert ">The Rio<" not in heading


def test_theatres_list_uses_full_logos(conn):
    page = pages(conn, NOW)["theatres/index.html"]
    assert 'src="../static/logos/rio-full.png"' in page
    assert "rio-mark.png" not in page


def test_home_has_the_tagline(conn):
    save(conn, show("Musk", at(18, 12)))
    page = pages(conn, NOW)["index.html"]
    assert '<p class="tagline">Support local cinemas.</p>' in page
    assert "<title>cineclock: Support local cinemas</title>" in page


def test_several_showings_on_one_day_are_flagged():
    save(conn := db.connect(":memory:"), show("Jaws", at(19, 14)), show("Jaws", at(19, 19)))
    [p] = {id(x): x for x in film_pages(db.upcoming(conn, NOW), {}).values()}.values()
    assert p.tags == ["One day only"]
    save(conn, show("Jaws", at(19, 14)), show("Jaws", at(19, 19)), show("Jaws", at(20, 19)))
    [p] = {id(x): x for x in film_pages(db.upcoming(conn, NOW), {}).values()}.values()
    assert p.tags == []


def test_about_page_and_footer_links(conn):
    built = pages(conn, NOW)
    about = built["about/index.html"]
    assert "Hi, I'm Jordan." in about
    assert 'href="https://boxd.it/7T1D"' in about
    assert 'href="https://github.com/yogzoth"' in about
    home = built["index.html"]
    assert 'href="about/"' in home and 'href="https://boxd.it/7T1D"' in home


def test_theatre_page_has_a_photo_header_and_offer_pills(conn):
    page = pages(conn, NOW)["theatres/park/index.html"]
    assert 'class="theatre-hero"' in page and "static/theatres/park.jpg" in page
    assert 'class="tag tag-format">70mm<' in plain(page)


def test_theatre_pills_include_what_is_on_its_schedule(conn):
    save(
        conn, show("Gremlins", at(19, 19), note="Q&A with Zach Galligan"), show("Jaws", at(20, 19))
    )
    page = plain(pages(conn, NOW)["theatres/rio/index.html"])
    head = page.split('class="tags theatre-offers"')[1].split("</p>")[0]
    assert ">Q&amp;A<" in head and ">7.1 sound<" in head
    assert "One screening" not in head
