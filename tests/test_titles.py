import pytest

from cineclock.titles import clean_title, credits_year, split_year


@pytest.mark.parametrize(
    "raw, title, note",
    [
        ("Musk", "Musk", None),
        (
            "The Rocky Horror Picture Show (Rockytober!)",
            "The Rocky Horror Picture Show",
            "Rockytober!",
        ),
        ("Jim Queen (Advance Screening)", "Jim Queen", "Advance Screening"),
        (
            "John Woo's 'A Better Tomorrow' (40th Anniversary Restoration)",
            "John Woo's 'A Better Tomorrow'",
            "40th Anniversary Restoration",
        ),
        # Real titles that must survive untouched
        ("(500) Days of Summer", "(500) Days of Summer", None),
        ("Suspiria (1977)", "Suspiria (1977)", None),
        (
            "Gremlins: In Conversation with Zach Galligan",
            "Gremlins: In Conversation with Zach Galligan",
            None,
        ),
        # WordPress sends HTML entities
        ("Harold &amp; Maude", "Harold & Maude", None),
        ("Don&#8217;t Look Now", "Don’t Look Now", None),
        ("  Stalker  ", "Stalker", None),
    ],
)
def test_clean_title(raw, title, note):
    assert clean_title(raw) == (title, note)


@pytest.mark.parametrize(
    "text, year",
    [
        ("TONY (Matt Johnson, 2026 / 106 mins / 14A) A 19-year-old...", 2026),
        ("MUSK (Alex Gibney, 2026 / PG / 235 mins)", 2026),
        ("STALKER (Andrei Tarkovsky, 1979 / 161 mins / PG)", 1979),
        # Real Rio line with no comma before the year
        ("SCREAM (Wes Craven 1996 /  111 min / 14A)", 1996),
        ("Doors at 7. (Ages 19+) No credits here.", None),
        ("(15 Year Anniversary)", None),
        ("Tickets $15 (subject to availability) / 2026 season", None),
        ("", None),
    ],
)
def test_credits_year(text, year):
    assert credits_year(text) == year


@pytest.mark.parametrize(
    "title, expected",
    [
        ("The Thing (1982)", ("The Thing", 1982)),
        ("Suspiria(1977)", ("Suspiria", 1977)),
        ("The Thing", ("The Thing", None)),
        ("Blade Runner 2049", ("Blade Runner 2049", None)),
        ("1917", ("1917", None)),
        ("(500) Days of Summer", ("(500) Days of Summer", None)),
        ("Metropolis (3000)", ("Metropolis (3000)", None)),
    ],
)
def test_split_year(title, expected):
    assert split_year(title) == expected
