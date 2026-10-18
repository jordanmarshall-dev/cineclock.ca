"""Every venue cineclock covers, in the order they're shown."""

from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Venue:
    name: str
    slug: str
    address: str
    website: str
    blurb: str
    # The Rio and the Park make their own posters, which beat generic ones.
    own_posters: bool = False

    @property
    def map_url(self) -> str:
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(self.address)}"


VENUES = [
    Venue(
        name="The Rio",
        slug="rio",
        address="1660 East Broadway, Vancouver, BC V5N 1W1",
        website="https://riotheatre.ca/",
        blurb="Single-screen theatre on East Broadway with 409 seats and a full stage, "
        "mixing cult films, new releases and live shows.",
        own_posters=True,
    ),
    Venue(
        name="The Park",
        slug="park",
        address="3440 Cambie Street, Vancouver, BC V5Z 2W8",
        website="https://tickets.theparktheatre.ca/",
        blurb="Neighbourhood single-screen in Cambie Village, run by the same team as the Rio.",
        own_posters=True,
    ),
    Venue(
        name="The Cinematheque",
        slug="cinematheque",
        address="1131 Howe Street, Vancouver, BC V6Z 2L7",
        website="https://thecinematheque.ca/",
        blurb="Non-profit cinema on Howe between Helmcken and Davie, programming "
        "repertory series, restorations and world cinema.",
    ),
    Venue(
        name="VIFF Centre",
        slug="viff-centre",
        address="1181 Seymour Street, Vancouver, BC V6B 3M7",
        website="https://viff.org/whats-on/",
        blurb="The VIFF Cinema, the film festival's year-round main screen: "
        "a 33-foot screen with Dolby sound.",
    ),
    Venue(
        name="VIFF Lochmaddy",
        slug="viff-lochmaddy",
        address="1181 Seymour Street, Vancouver, BC V6B 3M7",
        website="https://viff.org/whats-on/",
        blurb="The Lochmaddy Studio Theatre, a 41-seat room inside the VIFF Centre.",
    ),
]

BY_NAME = {v.name: v for v in VENUES}
BY_SLUG = {v.slug: v for v in VENUES}


def order(name: str) -> int:
    """Sort key that puts venues in the order above; unknown ones go last."""
    names = [v.name for v in VENUES]
    return names.index(name) if name in names else len(names)
