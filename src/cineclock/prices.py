"""Ticket prices, read from each theatre's own website once a month.

Prices change rarely, so the scrape re-reads each theatre's price page when the
saved copy is over 30 days old. A page that can't be read, or no longer reads
the way the parser expects, leaves the last good prices in place; until a
theatre's prices have been read once, its page shows the copy in venues.py.

The Park publishes no prices (they show at checkout), so its page shows the
Rio's published prices, labelled as such: same team, same membership. The Dunbar's ticketing site
blocks automated visits, so its prices stay as recorded in venues.py.
"""

import re
from dataclasses import asdict, replace
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from cineclock.venues import BY_NAME, Price, Prices

REFRESH = timedelta(days=30)

VIFF_URL = "https://viff.org/ticket-info/"
RIO_URL = "https://riotheatre.ca/ticket-info/"
CINEMATHEQUE_VISIT_URL = "https://thecinematheque.ca/about/visit"
CINEMATHEQUE_PACKS_URL = "https://thecinematheque.ca/shop/ticket-pack"


def text_of(page: str) -> str:
    soup = BeautifulSoup(page, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def money(amount: str) -> str:
    """$16.00 -> $16, $12.50 stays."""
    return "$" + amount.removesuffix(".00")


# VIFF's labels, reworded to read like the rest of the site. A label VIFF adds
# later still shows, as VIFF writes it.
VIFF_LABELS = {
    "Adult": "Adult",
    "Senior/Student": "Senior or student",
    "VIFF+": "VIFF+ member",
    "VIFF+ Premium/U25": "VIFF+ Premium or under 25",
    "Accessible": "Accessible",
}
VIFF_ORDER = list(VIFF_LABELS.values())


def parse_viff(page: str) -> Prices | None:
    soup = BeautifulSoup(page, "html.parser")
    header = soup.find(string=re.compile("Lochmaddy Studio Theatre"))
    table = header.find_parent("table") if header else None
    if not table:
        return None
    tickets = []
    for row in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) == 3 and all(re.fullmatch(r"\$\d+(\.\d\d)?", c) for c in cells[1:]):
            label = VIFF_LABELS.get(cells[0], cells[0])
            tickets.append(Price(label, f"{money(cells[1][1:])} / {money(cells[2][1:])}"))
    tickets.sort(key=lambda p: VIFF_ORDER.index(p.label) if p.label in VIFF_ORDER else 99)
    member = re.search(r"Memberships start at \$(\d+)", text_of(page))
    deals = ()
    if member:
        deals = (
            Price(
                "VIFF+ membership",
                f"From ${member.group(1)} a year",
                "Cheaper tickets all year, free guest tickets, popcorn vouchers,"
                " festival discounts",
            ),
        )
    if not tickets:
        return None
    return Prices(
        tickets=tuple(tickets),
        columns="VIFF Cinema / Lochmaddy Studio Theatre",
        deals=deals,
        note="Prices are before GST.",
        sources=(("VIFF ticket info", VIFF_URL),),
    )


def rio_membership(text: str) -> Price | None:
    price = re.search(r"Memberships? for sale[^$]{0,60}\$(\d+(?:\.\d\d)?)", text)
    saving = re.search(r"saves you \$(\d+(?:\.\d\d)?) off", text)
    if not price:
        return None
    detail = "Free popcorn and soda refills"
    if saving:
        detail = (
            f"{money(saving.group(1))} off regular films at both theatres,"
            " free popcorn and soda refills"
        )
    return Price("Rio and Park membership", f"{money(price.group(1))} a year", detail)


def parse_rio(page: str) -> Prices | None:
    text = text_of(page)
    adult = re.search(r"Regular Adult\s*[–-]\s*\$(\d+(?:\.\d\d)?)", text)
    concession = re.search(r"Concession \(([^)]*)\)\s*[–-]\s*\$(\d+(?:\.\d\d)?)", text)
    if not adult:
        return None
    tickets = [Price("Adult", money(adult.group(1)))]
    if concession:
        tickets.append(
            Price(
                "Member, senior or student",
                money(concession.group(2)),
                "Bring your ID or membership pass",
            )
        )
    membership = rio_membership(text)
    return Prices(
        tickets=tuple(tickets),
        deals=(membership,) if membership else (),
        sources=(("Rio ticket info", RIO_URL),),
    )


# The Park publishes no prices of its own (they show at checkout, behind a
# reCAPTCHA). It's run by the Rio's team and shares the Rio's membership, so the
# Park's page shows the Rio's published prices and says that's what they are.
PARK_ORIGIN = (
    "The Park doesn't publish its prices; these are the Rio's, from the same team"
    " and membership. The Park's checkout shows the exact price."
)


def parse_park(page: str) -> Prices | None:
    rio = parse_rio(page)
    if not rio:
        return None
    return replace(
        rio,
        origin=PARK_ORIGIN,
        sources=(
            ("Park tickets", "https://tickets.theparktheatre.ca/"),
            ("Rio ticket info", RIO_URL),
        ),
    )


CINEMATHEQUE_LABELS = {"General": "General", "Senior": "Senior", "Student": "Student"}


def parse_cinematheque(visit: str, packs: str) -> Prices | None:
    text = text_of(visit)
    rates = re.search(r"Ticket Rates (.*?) Screenings", text)
    if not rates:
        return None
    tickets = []
    for amount, label, detail in re.findall(
        r"\$(\d+(?:\.\d\d)?) (General|Senior|Student)(?: \(([^)]*)\))?", rates.group(1)
    ):
        detail = re.sub(r"(\d+)\+", r"\1 and over", detail)
        tickets.append(Price(CINEMATHEQUE_LABELS[label], money(amount), detail))
    if re.search(r"Free admission for First Nations, Inuit, and Métis", text):
        tickets.append(Price("First Nations, Inuit and Métis", "Free"))
    deals = []
    for count, amount in re.findall(r"(\d+) Pack \(\$(\d+)\)", text_of(packs)):
        each = int(amount) / int(count)
        each_text = f"${each:.0f}" if each == int(each) else f"${each:.2f}"
        deals.append(Price(f"{count}-film pack", money(amount), f"{each_text} a film"))
    if not tickets:
        return None
    return Prices(
        tickets=tuple(tickets),
        deals=tuple(deals),
        note="Special events can cost more. Every ticket includes the society membership"
        " that lets the Cinematheque show unrated films.",
        sources=(
            ("Cinematheque visit info", CINEMATHEQUE_VISIT_URL),
            ("Ticket packs", CINEMATHEQUE_PACKS_URL),
        ),
    )


# Each theatre: the pages to read, and how to turn them into prices.
SOURCES = {
    "VIFF Centre": ((VIFF_URL,), parse_viff),
    "The Rio": ((RIO_URL,), parse_rio),
    "The Park": ((RIO_URL,), parse_park),
    "The Cinematheque": ((CINEMATHEQUE_VISIT_URL, CINEMATHEQUE_PACKS_URL), parse_cinematheque),
}


def checked_label(when: datetime) -> str:
    return f"{when:%b} {when.day}, {when.year}"


def to_json(prices: Prices) -> dict:
    return asdict(prices)


def from_json(data: dict) -> Prices:
    return Prices(
        tickets=tuple(Price(**p) for p in data.get("tickets", [])),
        columns=data.get("columns", ""),
        deals=tuple(Price(**p) for p in data.get("deals", [])),
        note=data.get("note", ""),
        checked=data.get("checked", ""),
        sources=tuple(tuple(s) for s in data.get("sources", [])),
        origin=data.get("origin", ""),
    )


def fetch(client, venue: str, now: datetime) -> Prices | None:
    urls, parse = SOURCES[venue]
    pages = []
    for url in urls:
        response = client.get(url)
        response.raise_for_status()
        pages.append(response.text)
    found = parse(*pages)
    return replace(found, checked=checked_label(now)) if found else None


def current(stored: dict[str, Prices]) -> dict[str, Prices]:
    """Each theatre's prices: the last good read, or the copy in venues.py."""
    out = {name: venue.prices for name, venue in BY_NAME.items() if venue.prices}
    out.update(stored)
    return out
