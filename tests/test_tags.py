import pytest

from cineclock.tags import filter_slugs, kind, said_by_tags, screening_tags, slug, sort_tags


@pytest.mark.parametrize(
    "title, note, film_format, expected",
    [
        ("Dune: Part Three", "Presented in 70mm", None, ["70mm"]),
        ("Vertigo", None, "35mm", ["35mm"]),
        ("Vertigo", None, "35 mm", ["35mm"]),
        ("Pulse", None, "DCP", []),
        ("Avatar", "Presented in 3D", None, ["3D"]),
        ("Dune", "Dolby Atmos", None, ["Dolby Atmos"]),
        ("Ran", "Projected in 4K", None, ["4K"]),
        # A 4K restoration is about the restoration, not this screening
        ("Ran", "4K Restoration", None, []),
        (
            "Traces of Home",
            "With Filmmakers Dr. Gabor Maté & Colette Ghunim Q&A",
            None,
            ["Filmmaker Q&A"],
        ),
        ("Menopause: Coming in Hot", "Filmmakers in Attendance for Q&A", None, ["Filmmaker Q&A"]),
        ("Gremlins: In Conversation with Zach Galligan", None, None, ["Q&A"]),
        (
            "Shot in Vancouver: The Changeling, introduced by Sam Wiebe",
            None,
            None,
            ["Introduction"],
        ),
        ("Claudio Simonetti's Goblin Performs TENEBRE", None, None, ["Live accompaniment"]),
        ("Nosferatu", "With a live score by Tyondai Braxton", None, ["Live accompaniment"]),
        ("Queer Film Festival Opening Night", None, None, ["Festival"]),
        ("SFMF Shorts Programme 2", None, None, ["Shorts programme"]),
        ("The Fly", "Special Presentation", None, ["Special presentation"]),
        ("The Fly", "Special guest Jeff Goldblum", None, ["Guests"]),
        ("Dune: Part Three", "Advance Screening", None, ["Advance screening"]),
        ("Dune: Part Three", "Insider Screening", None, ["Insider screening"]),
        ("The Fly", "40th Anniversary Screening", None, []),
        # Words that only look like tags
        ("Alive", None, None, []),
        ("Live and Let Die", None, None, []),
        ("Intolerance", None, None, []),
        ("2350mm Dreams", None, None, []),
        ("Shortbus", None, None, []),
    ],
)
def test_screening_tags(title, note, film_format, expected):
    assert screening_tags(title, note, film_format) == expected


def test_sort_tags_puts_rare_showings_then_formats_first_and_dedupes():
    assert sort_tags(["Q&A", "One screening", "70mm", "Q&A"]) == ["One screening", "70mm", "Q&A"]


def test_each_tag_belongs_to_a_family():
    tags = ["One screening", "35mm", "Dolby Atmos", "Introduction", "Advance screening"]
    assert [kind(t) for t in tags] == ["rare", "format", "format", "event", "event"]


def test_filter_slugs_add_on_film_and_event():
    assert filter_slugs(["35mm", "Filmmaker Q&A"]) == ["35mm", "filmmaker-q-a", "on-film", "event"]
    assert filter_slugs(["IMAX"]) == ["imax"]


def test_slug():
    assert slug("One screening") == "one-screening"


@pytest.mark.parametrize(
    "note, tags, expected",
    [
        ("Advance Screening", ["Advance screening"], True),
        ("Presented in 70mm", ["70mm"], True),
        ("Insider Screening", ["Insider screening", "One screening"], True),
        ("With Filmmakers Dr. Gabor Maté & Colette Ghunim Q&A", ["Filmmaker Q&A"], False),
        ("40th Anniversary Screening", [], False),
        (None, ["70mm"], False),
    ],
)
def test_short_notes_a_pill_already_says(note, tags, expected):
    assert said_by_tags(note, tags) == expected
