import pytest

from cineclock.tags import screening_tags, slug, sort_tags


@pytest.mark.parametrize(
    "title, note, film_format, expected",
    [
        ("Dune: Part Three", "Presented in 70mm", None, ["70mm"]),
        ("Vertigo", None, "35mm", ["35mm"]),
        ("Vertigo", None, "35 mm", ["35mm"]),
        ("Pulse", None, "DCP", []),
        ("Traces of Home", "With Filmmakers Dr. Gabor Maté & Colette Ghunim Q&A", None, ["Event"]),
        ("Gremlins: In Conversation with Zach Galligan", None, None, ["Event"]),
        ("Shot in Vancouver: The Changeling, introduced by Sam Wiebe", None, None, ["Event"]),
        ("Menopause: Coming in Hot", "Filmmakers in Attendance for Q&A", None, ["Event"]),
        ("Claudio Simonetti's Goblin Performs TENEBRE", None, None, ["Event"]),
        ("Dune: Part Three", "Advance Screening", None, ["Preview"]),
        ("Dune: Part Three", "Insider Screening", None, ["Preview"]),
        ("The Fly", "40th Anniversary Screening", None, []),
        # Words that only look like tags
        ("Alive", None, None, []),
        ("Intolerance", None, None, []),
        ("2350mm Dreams", None, None, []),
    ],
)
def test_screening_tags(title, note, film_format, expected):
    assert screening_tags(title, note, film_format) == expected


def test_sort_tags_puts_formats_first_and_dedupes():
    assert sort_tags(["Event", "One screening", "70mm", "Event"]) == [
        "70mm",
        "Event",
        "One screening",
    ]


def test_slug():
    assert slug("One screening") == "one-screening"
