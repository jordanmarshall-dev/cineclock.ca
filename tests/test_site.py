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
    assert "Letterboxd</a>" not in page.split("<main>")[1].split("</main>")[0]


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
    pages_only = [html for path, html in built.items() if path.endswith(".html")]
    assert all("<script>alert(1)</script>" not in html for html in pages_only)
    # films.json is data, not a page; the browser escapes it before showing it
    assert '"<script>alert(1)</script>"' in built["films.json"]


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
    film_list = list({id(p): p for p in page_of.values()}.values())
    return {r.title: r for r in rails(film_list, now, db.venue_debuts(conn))}


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


def test_a_new_theatre_does_not_fill_just_added(conn):
    save(conn, show("Old", at(20, 19)))
    later = NOW + timedelta(days=2)
    db.sync_venue(conn, "The Rio", [show("Old", at(20, 19)), show("New", at(22, 19))], later)
    db.sync_venue(conn, "The Dunbar", [show("Dunbar debut", at(23, 19), venue="The Dunbar")], later)
    titles = [c.page.title for c in rail_titles(conn, later)["Just added"].cards]
    assert titles == ["New"]


def test_highly_rated_needs_enough_ratings(conn):
    save(conn, show("Classic", at(18, 19), year=1970), show("Obscure", at(18, 20), year=2020))
    db.save_film(conn, film("Classic", 1970, 1, letterboxd_rating=4.1, letterboxd_count=50_000))
    db.save_film(conn, film("Obscure", 2020, 2, letterboxd_rating=4.9, letterboxd_count=12))
    found = rail_titles(conn)
    assert [c.page.title for c in found["Highly rated"].cards] == ["Classic"]
    assert found["Highly rated"].cards[0].why is None
    assert found["Highly rated"].cards[0].next_label == "Today, 7:00 pm"
    assert found["Highly rated"].more == "films/?sort=rated"


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
    save(conn, show("Musk", at(22, 12)))
    assert set(rail_titles(conn)) == {"This week"}


def test_leaving_soon_lists_films_whose_last_showing_is_this_week(conn):
    save(
        conn,
        show("Stays", at(19, 19)),
        show("Stays", at(30, 19)),
        show("Goes Later", at(19, 19)),
        show("Goes Later", at(23, 19)),
        show("Goes", at(19, 14)),
        show("Goes", at(20, 19)),
        show("Once", at(19, 19)),
    )
    rail = rail_titles(conn)["Leaving soon"]
    # A single screening isn't a run that's ending, so "Once" stays out
    assert [c.page.title for c in rail.cards] == ["Goes", "Goes Later"]
    assert rail.cards[0].why == "Ends Tue 20"
    assert rail.more == "films/?sort=leaving"


def test_this_week_skips_what_is_on_today(conn):
    save(conn, show("Today", at(18, 19)), show("Later", at(25, 19)), show("Soon", at(19, 19)))
    assert [c.page.title for c in rail_titles(conn)["This week"].cards] == ["Soon", "Later"]


# Tags and filters


def test_rows_carry_tags_and_filter_data(conn):
    save(conn, show("Dune: Part Three", at(18, 19), "The Park", note="Presented in 70mm"))
    page = pages(conn, NOW)["showtimes/index.html"]
    assert 'data-venues="park"' in page
    assert 'data-tags="one-screening 70mm on-film"' in page
    assert 'class="tag tag-format tag-70mm">70mm<' in plain(page)
    assert 'data-value="on-film"' in page


def test_a_single_screening_highlights_its_time_instead_of_a_badge(conn):
    save(conn, show("Twice", at(18, 19)), show("Twice", at(19, 19)), show("Once", at(18, 21)))
    page = pages(conn, NOW)["showtimes/index.html"]
    assert "tag-one-screening" not in page
    assert page.count("time time-rare") == 1
    assert page.count('data-tags="one-screening"') == 1


def test_film_page_shows_tags(conn):
    save(
        conn, Screening("The Cinematheque", "Vertigo", at(19, 19), "https://x", film_format="35mm")
    )
    page = pages(conn, NOW)["films/vertigo/index.html"]
    assert ">35mm<" in page and ">One screening<" not in page
    assert "time time-rare" in page


def test_every_rail_has_a_see_all_link(conn):
    save(conn, show("Lots", at(18, 19)), show("Lots", at(19, 19)), show("Soon", at(20, 19)))
    for rail in rail_titles(conn).values():
        assert rail.more.startswith(("films/", "showtimes/")), rail.title


def test_next_label_for_later_days(conn):
    save(conn, show("Later", at(24, 20, 15)))
    [card] = rail_titles(conn)["This week"].cards
    assert card.next_label == "Oct 24, 8:15 pm"


def test_home_cards_show_year_score_next_showing_and_theatres(conn):
    save(
        conn,
        show("Classic", at(18, 19), year=1970),
        show("Classic", at(20, 19), "The Cinematheque", year=1970),
    )
    db.save_film(conn, film("Classic", 1970, 1, letterboxd_rating=4.1, letterboxd_count=50_000))
    home = pages(conn, NOW)["index.html"]
    assert '<span class="year">1970</span>' in home
    assert 'title="4.1 on Letterboxd"' in home
    assert '<span class="card-next">Today, 7:00 pm</span>' in plain(home)
    assert 'title="The Rio"' in home and 'title="The Cinematheque"' in home


def test_films_page_lists_each_film_once_with_dates(conn):
    save(conn, show("Musk", at(18, 12)), show("Musk", at(25, 12)), show("Pulse", at(19, 20)))
    page = pages(conn, NOW)["films/index.html"]
    assert page.count('<li class="card"') == 2
    assert "Oct 18 to Oct 25" in page
    assert 'class="card-next rare" title="One screening">' in page
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
    for name in ("site.css", "filters.js", "calendar.js", "me.js", "hero.js"):
        shutil.copy(render.STATIC / name, tmp_path / name)
    monkeypatch.setattr(render, "STATIC", tmp_path)
    save(conn, show("Musk", at(18, 12)))
    page = pages(conn, NOW)["index.html"]
    assert '<span class="monogram" role="img" aria-label="The Rio">R</span>' in page


def test_cards_show_letterboxd_before_any_other_score(conn):
    save(conn, show("Alien", at(18, 20), year=1979), show("Obscure", at(18, 21), year=2001))
    db.save_film(conn, film("Alien", 1979, 1, letterboxd_rating=4.2, imdb_rating=8.5))
    db.save_film(conn, film("Obscure", 2001, 2, rt_score=71, metacritic=60))
    page = pages(conn, NOW)["films/index.html"]
    assert 'title="4.2 on Letterboxd"' in page and "8.5" not in page
    assert 'title="71% on Rotten Tomatoes"' in page


def test_ratings_show_on_listings_without_toggles(conn):
    save(conn, show("The Thing", at(18, 20), year=1982))
    db.save_film(conn, film("The Thing", 1982, 1091, imdb_rating=8.2, metacritic=57))
    page = pages(conn, NOW)["showtimes/index.html"]
    # Listings carry one score: Letterboxd, or the next source that has one.
    assert 'class="card-rating card-rating-imdb" title="8.2 on IMDb"' in page
    assert "metacritic" not in page.split("<footer")[0].lower()
    film_page = pages(conn, NOW)["films/the-thing-1982/index.html"]
    assert "IMDb" in film_page
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
    assert 'class="tag tag-format tag-70mm">70mm<' in plain(page)


def test_theatre_pills_include_what_is_on_its_schedule(conn):
    save(
        conn, show("Gremlins", at(19, 19), note="Q&A with Zach Galligan"), show("Jaws", at(20, 19))
    )
    page = plain(pages(conn, NOW)["theatres/rio/index.html"])
    head = page.split('class="theatre-offers"')[1].split("</p>")[0]
    assert ">Q&amp;A<" in head and ">7.1 sound<" in head
    assert "One screening" not in head


def test_calendar_months_link_days_with_showings():
    from cineclock.site import calendar_months

    shows = [show("Jaws", at(18, 19)), show("Jaws", at(31, 19))]
    days = group_days(shows, film_pages(shows, {}), {}, NOW)
    [october] = calendar_months(days, NOW)
    assert october.title == "October 2026"
    cells = [d for week in october.weeks for d in week if d]
    assert [d.date.day for d in cells if d.anchor] == [18, 31]
    assert [d.date.day for d in cells if d.today] == [18]
    assert october.weeks[0][:4] == [None] * 4  # Oct 1, 2026 is a Thursday


def test_showtimes_page_has_the_calendar(conn):
    save(conn, show("Jaws", at(19, 19)))
    page = pages(conn, NOW)["showtimes/index.html"]
    assert 'class="cal-pop"' in page and 'href="#d20261019"' in page


def test_spotlight_prefers_tonights_best_rated_film_with_art(conn):
    from cineclock.site import spotlight

    save(conn, show("Jaws", at(18, 19)), show("Alien", at(18, 21)), show("Later", at(19, 19)))
    db.save_film(conn, film("Jaws", None, 1, backdrop_url="https://b/j", letterboxd_rating=4.0))
    db.save_film(conn, film("Alien", None, 2, backdrop_url="https://b/a", letterboxd_rating=4.3))
    db.save_film(conn, film("Later", None, 3, backdrop_url="https://b/l", letterboxd_rating=4.9))
    page_of = film_pages(db.upcoming(conn, NOW), db.films_by_key(conn))
    assert spotlight(list({id(p): p for p in page_of.values()}.values()), NOW).title == "Alien"


def test_hero_has_three_highlights_all_with_art(conn):
    from cineclock.site import highlights

    save(
        conn,
        show("Alien", at(18, 21)),
        show("Vertigo", at(22, 19), note="35mm"),
        show("Jaws", at(20, 19)),
        show("Jaws", at(21, 19)),
        show("No Art", at(19, 19), note="35mm"),
        show("Far Off", NOW + timedelta(days=30)),
    )
    for i, title in enumerate(["Alien", "Vertigo", "Jaws", "Far Off"]):
        db.save_film(conn, film(title, None, i, backdrop_url=f"https://b/{i}", letterboxd_rating=4))
    page_of = film_pages(db.upcoming(conn, NOW), db.films_by_key(conn))
    slides = highlights(list({id(p): p for p in page_of.values()}.values()), NOW)
    assert [(s.page.title, s.label) for s in slides] == [
        ("Alien", "Tonight"),
        ("Vertigo", "35mm"),
        ("Jaws", "Coming up"),
    ]
    home = pages(conn, NOW)["index.html"]
    assert home.count('class="spotlight"') == 3 and "hero.js" in home


def test_a_note_every_showing_shares_moves_up_top(conn):
    note = "With Filmmakers Q&A"
    save(conn, show("Traces", at(25, 10), note=note), show("Traces", at(26, 10), note=note))
    [p] = {id(x): x for x in film_pages(db.upcoming(conn, NOW), {}).values()}.values()
    assert p.shared_note == note


def test_popular_leaves_out_what_highly_rated_shows(conn):
    save(conn, show("Classic", at(18, 19), year=1970), show("Blockbuster", at(18, 20), year=2020))
    db.save_film(conn, film("Classic", 1970, 1, letterboxd_rating=4.1, letterboxd_count=90_000))
    db.save_film(conn, film("Blockbuster", 2020, 2, letterboxd_rating=3.2, letterboxd_count=50_000))
    found = rail_titles(conn)
    assert [c.page.title for c in found["Highly rated"].cards] == ["Classic", "Blockbuster"]
    # Both are highly rated here, so nothing is left for Popular
    assert "Popular" not in found


def test_most_screenings_needs_a_real_run(conn):
    save(conn, show("Twice", at(19, 19)), show("Twice", at(20, 19)))
    save(conn, *[show("Lots", at(d, 19)) for d in (18, 19, 20, 21)])
    cards = rail_titles(conn)["Most screenings"].cards
    assert [(c.page.title, c.why) for c in cards] == [("Lots", "4 screenings")]


def test_theatre_page_frames_the_inside_photo_beside_the_specs(conn):
    page = pages(conn, NOW)["theatres/rio/index.html"]
    assert 'class="room-photo"' in page and "static/rooms/rio-main.jpg" in page
    viff = pages(conn, NOW)["theatres/viff-centre/index.html"]
    assert "static/rooms/viff-lochmaddy.jpg" in viff and "static/rooms/viff-main.jpg" in viff


def test_theatre_page_has_the_date_picker(conn):
    save(conn, show("Jaws", at(19, 19)), show("Jaws", at(20, 19)))
    page = pages(conn, NOW)["theatres/rio/index.html"]
    assert 'class="cal-pop"' in page and "static/calendar.js" in page


def test_film_without_a_poster_shows_its_title_in_the_frame(conn):
    save(conn, show("Obscure Thing", at(19, 19)))
    page = pages(conn, NOW)["films/index.html"]
    assert '<span class="poster-fallback" aria-hidden="true">Obscure Thing</span>' in page


def test_film_page_groups_days_under_their_theatre(conn):
    save(conn, show("Jaws", at(19, 19)), show("Jaws", at(19, 21)), show("Jaws", at(20, 19)))
    page = pages(conn, NOW)["films/jaws/index.html"]
    assert page.count('class="showing"') == 2
    assert page.count('class="venue-group panel"') == 1


def test_film_page_starts_a_new_block_when_the_theatre_changes(conn):
    save(
        conn,
        show("Jaws", at(19, 19)),
        show("Jaws", at(20, 19), "The Park"),
        show("Jaws", at(21, 19)),
        show("Jaws", at(22, 19)),
    )
    page = pages(conn, NOW)["films/jaws/index.html"]
    blocks = page.split('class="venue-group panel"')[1:]
    assert [b.count('class="showing"') for b in blocks] == [1, 1, 2]
