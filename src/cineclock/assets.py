"""Logo files the dev workspace can't download, fetched by the deploy instead.

Run before building: python -m cineclock.assets. Files already present are
left alone; a failed download just means that badge falls back to letters.
"""

from pathlib import Path

import httpx

from cineclock.scrapers import make_client

STATIC = Path(__file__).parent / "static"

REMOTE = {
    # Letterboxd's own logo files, offered for linking to Letterboxd:
    # https://letterboxd.com/about/brand/
    "logos/letterboxd.svg": "https://a.ltrbxd.com/logos/letterboxd-decal-dots-neg-rgb.svg",
    "logos/park.png": (
        "https://pro-igniter-production.commondatastorage.googleapis.com"
        "/uploads/images/logos/237/original/ParkTheatre_Logo_Light_Blue.png"
    ),
}


def fetch_missing(client: httpx.Client, static: Path = STATIC) -> list[str]:
    fetched = []
    for path, url in REMOTE.items():
        target = static / path
        if target.exists():
            continue
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as error:
            print(f"{path}: not downloaded ({error})")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        fetched.append(path)
    return fetched


def main():
    with make_client() as client:
        for path in fetch_missing(client):
            print(f"{path}: downloaded")


if __name__ == "__main__":
    main()
