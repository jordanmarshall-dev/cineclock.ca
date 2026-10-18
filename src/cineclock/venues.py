"""Every venue cineclock covers, in the order they're shown.

Facts come from each venue's own website (and Wikipedia for the Park's
history), checked Oct 2026. Anything not stated there is left out rather than
guessed.
"""

from dataclasses import dataclass, field
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Venue:
    name: str
    short: str
    slug: str
    neighbourhood: str
    address: str
    website: str
    blurb: str
    # The Rio and the Park make their own posters, which beat generic ones.
    own_posters: bool = False
    # Logo file in static/logos, and whether it needs a light tile to show up.
    logo: str | None = None
    logo_on_light: bool = False
    specs: list[tuple[str, str]] = field(default_factory=list)
    about: list[str] = field(default_factory=list)

    @property
    def map_url(self) -> str:
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(self.address)}"

    @property
    def monogram(self) -> str:
        """Fallback badge text when there's no logo file: Rio -> R, VIFF Lochmaddy -> VL"""
        return "".join(word[0] for word in self.short.split()[:2]).upper()


VENUES = [
    Venue(
        name="The Rio",
        short="Rio",
        slug="rio",
        neighbourhood="East Broadway at Commercial",
        address="1660 East Broadway, Vancouver, BC V5N 1W1",
        website="https://riotheatre.ca/",
        blurb="A 1938 single-screen mixing cult films, new releases and live shows.",
        own_posters=True,
        logo="rio.png",
        specs=[
            ("Opened", "1938"),
            ("Screens", "1"),
            ("Seats", "409"),
            ("Projection", "Digital"),
            ("Sound", "Surround"),
            ("Stage", "Yes, for live shows"),
        ],
        about=[
            "Restored with a digital projector, surround sound and a large stage, so "
            "nights here swing between repertory screenings, burlesque and comedy.",
            "Every ticket includes a membership in the Vancouver Art House Society.",
            "Runs the Park on Cambie with the same team.",
        ],
    ),
    Venue(
        name="The Park",
        short="Park",
        slug="park",
        neighbourhood="Cambie Village",
        address="3440 Cambie Street, Vancouver, BC V5Z 2W8",
        website="https://tickets.theparktheatre.ca/",
        blurb="A 1941 neighbourhood single-screen, reopened in 2026 by the Rio's team.",
        own_posters=True,
        logo="park.png",
        specs=[
            ("Opened", "1941"),
            ("Screens", "1"),
            ("Seats", "504"),
            ("Screen size", "18 × 36 ft"),
            ("Projection", "Digital and 70mm"),
            ("Sound", "Dolby Digital"),
        ],
        about=[
            "Opened in August 1941. A 2005 renovation brought new seats, the larger screen "
            "and Dolby Digital sound.",
            "Closed under Cineplex in 2025 and reopened in 2026, run by the team behind the Rio.",
        ],
    ),
    Venue(
        name="The Cinematheque",
        short="Cinematheque",
        slug="cinematheque",
        neighbourhood="Downtown, Howe at Helmcken",
        address="1131 Howe Street, Vancouver, BC V6Z 2L7",
        website="https://thecinematheque.ca/",
        blurb="Non-profit cinema showing repertory series, restorations and world cinema.",
        logo="cinematheque.png",
        logo_on_light=True,
        specs=[
            ("Screens", "1"),
            ("Seats", "153"),
            ("Projection", "Digital and 35mm"),
            ("Ages", "18+ unless noted"),
            ("Accessibility", "Wheelchair accessible"),
        ],
        about=[
            "A non-profit film society and educational institution, supported by the "
            "Canada Council, the BC Arts Council, the City of Vancouver, donors and volunteers.",
            "Buying a ticket makes you a member of the Pacific Cinémathèque Pacifique Society. "
            "That status lets it show films not reviewed by Consumer Protection BC, which is "
            "why most screenings are 18+.",
            "Its projectionists still run 35mm prints alongside digital.",
        ],
    ),
    Venue(
        name="VIFF Centre",
        short="VIFF Centre",
        slug="viff-centre",
        neighbourhood="Downtown, Seymour at Davie",
        address="1181 Seymour Street, Vancouver, BC V6B 3M7",
        website="https://viff.org/whats-on/",
        blurb="The VIFF Cinema, the film festival's year-round main screen.",
        logo="viff.svg",
        specs=[
            ("Screen", "33 ft"),
            ("Sound", "Dolby surround"),
            ("Bar", "Licensed, 19+"),
        ],
        about=[
            "Home of the Vancouver International Film Festival, programming new releases, "
            "restorations and series all year.",
            "The box office opens 30 minutes before the day's first screening.",
        ],
    ),
    Venue(
        name="VIFF Lochmaddy",
        short="Lochmaddy",
        slug="viff-lochmaddy",
        neighbourhood="Inside the VIFF Centre",
        address="1181 Seymour Street, Vancouver, BC V6B 3M7",
        website="https://viff.org/whats-on/",
        blurb="The Lochmaddy Studio Theatre, a 41-seat room inside the VIFF Centre.",
        logo="viff.svg",
        specs=[
            ("Seats", "41"),
            ("Screen", "17 ft"),
            ("Sound", "Dolby surround"),
            ("Bar", "Licensed, 19+"),
        ],
        about=[
            "An intimate studio for VIFF's wider range of programming, with the same "
            "projection and Dolby sound standard as the main cinema.",
        ],
    ),
]

BY_NAME = {v.name: v for v in VENUES}
BY_SLUG = {v.slug: v for v in VENUES}


def order(name: str) -> int:
    """Sort key that puts venues in the order above; unknown ones go last."""
    names = [v.name for v in VENUES]
    return names.index(name) if name in names else len(names)
