"""Every theatre cineclock covers, its rooms, and what's known about each room.

Theatre -> room -> showtime. A single-screen theatre still has one room, so
every theatre works the same way and a multiplex would just have more rooms.

Specs are only recorded when a source states them, with that source alongside.
A spec is shown on the site only once every room has it (see shown_specs), so
theatre pages stay comparable and nothing is filled in by guesswork.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import quote, quote_plus

# The order specs appear in on theatre pages.
SPEC_FIELDS = ["Seats", "Screen", "Projection", "Sound"]

# Capabilities worth a pill on a theatre page, matched against its specs.
OFFERS = [
    ("70mm", r"\b70mm\b"),
    ("35mm", r"\b35mm\b"),
    ("16mm", r"\b16mm\b"),
    ("4K", r"\b4k\b"),
    ("3D", r"\b3d\b"),
    ("7.1", r"\b7\.1\b"),
    ("Curved", r"\bcurved\b"),
]


# Every theatre photo is openly licensed on Wikimedia Commons and credited on the page.
# tools/fetch_photos.py downloads and grades them into static/theatres and static/rooms.
LICENCES = {
    "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
}


@dataclass(frozen=True)
class Photo:
    file: str  # the Wikimedia Commons file name
    author: str
    licence: str  # a key of LICENCES

    @property
    def page_url(self) -> str:
        return "https://commons.wikimedia.org/wiki/File:" + quote(self.file.replace(" ", "_"))

    @property
    def licence_url(self) -> str:
        return LICENCES[self.licence]


@dataclass(frozen=True)
class Room:
    id: str  # stable, never shown; e.g. "viff-lochmaddy"
    name: str  # e.g. "Lochmaddy Studio Theatre"
    short: str = ""  # shown on showtimes at theatres with more than one room
    specs: dict[str, str] = field(default_factory=dict)
    sources: tuple[str, ...] = ()
    photo: Photo | None = None


@dataclass(frozen=True)
class Price:
    label: str  # "Adult"
    amount: str  # "$17", or "$17 / $15" for a theatre with two rooms
    detail: str = ""


@dataclass(frozen=True)
class Prices:
    """What a theatre charges, copied from its own website and dated, since prices change.
    Only what the theatre itself publishes goes in."""

    tickets: tuple[Price, ...] = ()
    # What a two-part price means, shown above the list ("VIFF Cinema / Lochmaddy")
    columns: str = ""
    deals: tuple[Price, ...] = ()  # memberships, ticket packs
    note: str = ""
    checked: str = ""  # "Oct 18, 2026"
    sources: tuple[tuple[str, str], ...] = ()  # (link text, url)
    # Where the prices come from, when it isn't the theatre's own website.
    origin: str = ""


@dataclass(frozen=True)
class Venue:
    name: str
    short: str
    slug: str
    neighbourhood: str
    address: str
    website: str
    blurb: str
    rooms: tuple[Room, ...]
    # Logo files in static/logos: a compact mark for pills, a full logo for its page.
    mark: str | None = None
    full_logo: str | None = None
    # Some marks read small at the shared size (the Cinematheque's is plain text).
    mark_scale: float = 1.0
    # Which part of the theatre's photo to keep when it's cropped into the header.
    photo_focus: str = "center"
    photo: Photo | None = None
    # The Rio and the Park make their own posters, which beat generic ones.
    own_posters: bool = False
    about: tuple[str, ...] = ()
    prices: Prices | None = None

    def room(self, room_id: str | None) -> Room | None:
        return next((r for r in self.rooms if r.id == room_id), None)

    @property
    def map_url(self) -> str:
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(self.address)}"

    @property
    def offers(self) -> list[str]:
        """What the theatre can show, read only from its recorded specs."""
        found = []
        for room in self.rooms:
            text = " ".join(room.specs.values()).lower()
            for label, pattern in OFFERS:
                if re.search(pattern, text) and label not in found:
                    found.append(label)
        if len(self.rooms) > 1:
            found.append(f"{len(self.rooms)} screens")
        return found

    @property
    def monogram(self) -> str:
        """Fallback badge text when there's no logo file: Rio -> R."""
        return "".join(word[0] for word in self.short.split()[:2]).upper()


CHECKED = "Oct 18, 2026"

# The Rio's ticket page covers the membership it shares with the Park.
RIO_PARK_MEMBERSHIP = Price(
    "Rio and Park membership",
    "$30 a year",
    "$3 off regular films at both theatres, free popcorn and soda refills",
)

RIO_PRICES = Prices(
    tickets=(
        Price("Adult", "$16"),
        Price("Member, senior or student", "$13", "Bring your ID or membership pass"),
    ),
    deals=(RIO_PARK_MEMBERSHIP,),
    checked=CHECKED,
    sources=(("Rio ticket info", "https://riotheatre.ca/ticket-info/"),),
)

PARK_PRICES = Prices(
    tickets=RIO_PRICES.tickets,
    deals=(RIO_PARK_MEMBERSHIP,),
    checked=CHECKED,
    origin="The Park doesn't publish its prices; these are the Rio's, from the same team"
    " and membership. The Park's checkout shows the exact price.",
    sources=(
        ("Park tickets", "https://tickets.theparktheatre.ca/"),
        ("Rio ticket info", "https://riotheatre.ca/ticket-info/"),
    ),
)

CINEMATHEQUE_PRICES = Prices(
    tickets=(
        Price("General", "$15", "18 and over"),
        Price("Senior", "$13", "65 and over"),
        Price("Student", "$11"),
        Price("First Nations, Inuit and Métis", "Free"),
    ),
    deals=(
        Price("5-film pack", "$55", "$11 a film"),
        Price("10-film pack", "$100", "$10 a film"),
        Price("50-film pack", "$450", "$9 a film"),
    ),
    note="Special events can cost more. Every ticket includes the society membership"
    " that lets the Cinematheque show unrated films.",
    checked=CHECKED,
    sources=(
        ("Cinematheque visit info", "https://thecinematheque.ca/about/visit"),
        ("Ticket packs", "https://thecinematheque.ca/shop/ticket-pack"),
    ),
)

VIFF_PRICES = Prices(
    tickets=(
        Price("Adult", "$17 / $15"),
        Price("Senior or student", "$15 / $13"),
        Price("VIFF+ member", "$14 / $12"),
        Price("VIFF+ Premium or under 25", "$12 / $10"),
        Price("Accessible", "$12 / $10"),
    ),
    deals=(
        Price(
            "VIFF+ membership",
            "From $49 a year",
            "Cheaper tickets all year, free guest tickets, popcorn vouchers, festival discounts",
        ),
    ),
    columns="VIFF Cinema / Lochmaddy Studio Theatre",
    note="Prices are before GST.",
    checked=CHECKED,
    sources=(("VIFF ticket info", "https://viff.org/ticket-info/"),),
)

# The Dunbar's ticketing site blocks automated visits and it has no other site, so
# these are as reported in Nov 2024. The two articles disagree on Tuesdays ($8.50
# in both texts, $9.50 in one table); the texts agree, so $8.50.
DUNBAR_PRICES = Prices(
    tickets=(
        Price("Evening", "$12.99"),
        Price("Matinee", "$11.99"),
        Price("Student", "$11.99", "With ID"),
        Price("Senior or child", "$9.99", "65 and over, or 3 to 13"),
        Price("Cheap Tuesday", "$8.50", "All day, everyone"),
    ),
    note="3D is $3 more.",
    checked="Nov 2024",
    origin="Reported by local guides in November 2024, not by the Dunbar itself, so they"
    " may be out of date. Check at the box office.",
    sources=(
        (
            "The Best Vancouver",
            "https://www.thebestvancouver.com/guide-to-dunbar-theatre-vancouver/",
        ),
        (
            "Vancouver Is Awesome",
            "https://www.vancouverisawesome.com/events-and-entertainment/"
            "cheapest-day-go-see-movie-vancouver-bc-6442307",
        ),
    ),
)

VENUES = [
    Venue(
        name="The Rio",
        short="Rio",
        slug="rio",
        prices=RIO_PRICES,
        neighbourhood="East Broadway at Commercial",
        address="1660 East Broadway, Vancouver, BC V5N 1W1",
        website="https://riotheatre.ca/",
        blurb="A 1938 single-screen mixing cult films, new releases and live shows.",
        rooms=(
            Room(
                "rio-main",
                "Main auditorium",
                specs={
                    "Seats": "409",
                    "Screen": "30 ft",
                    "Projection": "Digital",
                    "Sound": "7.1",
                },
                sources=("https://riotheatre.ca/", "Jordan's venue research, Oct 2026"),
                photo=Photo("Rio Theatre interior 2026.JPEG", "Canmenwalker", "CC BY 4.0"),
            ),
        ),
        mark="rio-mark.png",
        full_logo="rio-full.png",
        own_posters=True,
        photo=Photo("RIO Theatre 2026.jpg", "Canmenwalker", "CC BY 4.0"),
        about=(
            "Built in 1938 and restored with a digital projector, surround sound and a large "
            "stage, so nights here swing between repertory screenings, burlesque and comedy.",
            "Every ticket includes a membership in the Vancouver Art House Society.",
        ),
    ),
    Venue(
        name="The Park",
        short="Park",
        slug="park",
        prices=PARK_PRICES,
        neighbourhood="Cambie Village",
        address="3440 Cambie Street, Vancouver, BC V5Z 2W8",
        website="https://tickets.theparktheatre.ca/",
        blurb="A 1941 neighbourhood single-screen, reopened in 2026 by the Rio's team.",
        rooms=(
            Room(
                "park-main",
                "Main auditorium",
                specs={
                    "Seats": "504",
                    "Screen": "35 ft, curved",
                    "Projection": "Digital, 35mm, 70mm",
                    "Sound": "7.1",
                },
                sources=(
                    "https://en.wikipedia.org/wiki/Park_Theatre_(Vancouver)",
                    "Jordan's venue research, Oct 2026",
                ),
                photo=Photo("The Park Theatre inside 2025.jpg", "Canmenwalker", "CC BY 4.0"),
            ),
        ),
        mark="park-mark.png",
        full_logo="park-full.png",
        own_posters=True,
        photo=Photo("The Park Theatre in Vancouver 202510.jpg", "Canmenwalker", "CC BY 4.0"),
        about=(
            "Opened in August 1941. A 2005 renovation brought new seats, the larger screen "
            "and Dolby Digital sound.",
            "Closed under Cineplex in 2025 and reopened in 2026, run by the team behind the Rio.",
        ),
    ),
    Venue(
        name="The Cinematheque",
        short="Cinematheque",
        slug="cinematheque",
        prices=CINEMATHEQUE_PRICES,
        neighbourhood="Downtown, Howe at Helmcken",
        address="1131 Howe Street, Vancouver, BC V6Z 2L7",
        website="https://thecinematheque.ca/",
        blurb="Non-profit cinema showing repertory series, restorations and world cinema.",
        rooms=(
            Room(
                "cinematheque-main",
                "Main auditorium",
                specs={
                    "Seats": "153",
                    "Screen": "31 ft",
                    "Projection": "Digital, 35mm, 16mm",
                    "Sound": "7.1",
                },
                sources=(
                    "Jordan's venue research, Oct 2026",
                    "https://thecinematheque.ca/about/visit",
                    "https://thecinematheque.ca/about",
                ),
            ),
        ),
        mark="cinematheque-mark.png",
        mark_scale=1.3,
        full_logo="cinematheque-full.png",
        photo=Photo("The Cinematheque Marquee 2020.jpg", "EmptySockets", "CC BY-SA 4.0"),
        about=(
            "A non-profit film society and educational institution, supported by the Canada "
            "Council, the BC Arts Council, the City of Vancouver, donors and volunteers.",
            "Buying a ticket makes you a member of the Pacific Cinémathèque Pacifique Society. "
            "That status lets it show films not reviewed by Consumer Protection BC, which is "
            "why most screenings are 18+.",
        ),
    ),
    Venue(
        name="VIFF Centre",
        short="VIFF",
        slug="viff-centre",
        prices=VIFF_PRICES,
        neighbourhood="Downtown, Seymour at Davie",
        address="1181 Seymour Street, Vancouver, BC V6B 3M7",
        website="https://viff.org/whats-on/",
        blurb="The film festival's year-round home, with a main cinema and a studio room.",
        rooms=(
            Room(
                "viff-main",
                "VIFF Cinema",
                short="VIFF Cinema",
                specs={
                    "Seats": "169",
                    "Screen": "33 ft",
                    "Projection": "4K digital, 35mm",
                    "Sound": "7.1",
                },
                sources=("https://viff.org/rent-our-venue/",),
            ),
            Room(
                "viff-lochmaddy",
                "Lochmaddy Studio Theatre",
                short="Lochmaddy",
                specs={
                    "Seats": "41",
                    "Screen": "17 ft",
                    "Projection": "2K digital",
                    "Sound": "Surround",
                },
                sources=("https://viff.org/rent-our-venue/lochmaddy-studio-theatre/",),
            ),
        ),
        mark="viff.svg",
        full_logo="viff.svg",
        photo=Photo("Vancity Theatre.jpg", "Tom Niu", "CC BY-SA 3.0"),
        about=(
            "Home of the Vancouver International Film Festival, programming new releases, "
            "restorations and series all year.",
            "The bar is licensed, so patrons 19 and over can bring a drink into the film.",
        ),
    ),
    Venue(
        name="The Dunbar",
        short="Dunbar",
        slug="dunbar",
        prices=DUNBAR_PRICES,
        neighbourhood="Dunbar-Southlands",
        address="4555 Dunbar Street, Vancouver, BC",
        website="https://ticketing.uswest.veezi.com/sessions/?siteToken=sap55z6c6aj6b96yshhtj7vyw4",
        blurb="A 1935 neighbourhood single-screen showing first-run films.",
        rooms=(
            Room(
                "dunbar-main",
                "Main auditorium",
                specs={
                    "Seats": "320",
                    "Screen": "32 ft",
                    "Projection": "Digital, 3D",
                    "Sound": "7.1",
                },
                sources=(
                    "Jordan's venue research, Oct 2026",
                    "https://www.biv.com/news/entertainment-media-sports/"
                    "vancouver-single-screen-cinema-has-force-8245070",
                ),
            ),
        ),
        mark="dunbar-mark.png",
        full_logo="dunbar-full.png",
        photo=Photo("Dunbar Theatre 20190103 1.jpg", "Gjtreat", "CC BY-SA 3.0"),
        about=(
            "Built in 1935 and one of the last neighbourhood movie houses in Vancouver.",
            "Run independently by Ken Charko since 1998, with a focus on first-run films.",
        ),
    ),
]

BY_NAME = {v.name: v for v in VENUES}


def order(name: str) -> int:
    """Sort key that puts venues in the order above; unknown ones go last."""
    names = [v.name for v in VENUES]
    return names.index(name) if name in names else len(names)


def shown_specs() -> list[str]:
    """Spec fields known for every room, in display order. Only these are shown."""
    rooms = [room for venue in VENUES for room in venue.rooms]
    return [f for f in SPEC_FIELDS if all(room.specs.get(f) for room in rooms)]


def room_label(venue_name: str, room_id: str | None) -> str | None:
    """A room's short name, for theatres with more than one room."""
    venue = BY_NAME.get(venue_name)
    room = venue.room(room_id) if venue else None
    if not room or len(venue.rooms) == 1:
        return None
    return room.short or room.name
