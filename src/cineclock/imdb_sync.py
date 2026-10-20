"""Read the IMDb watchlists people connected on cineclock and hand them to the
Worker (relay/imdb.js). Run by the IMDb sync workflow, since IMDb's API answers
GitHub's servers but not Cloudflare's.

    python -m cineclock.imdb_sync

The Worker knows the job by a GitHub OIDC token, so there's no secret to keep.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

RELAY = "https://cineclock-relay.cineclock-relay.workers.dev"
IMDB_API = "https://api.graphql.imdb.com/"
PAGE = 250
MAX_PAGES = 8

LIST = "query ($user: ID!) { predefinedList(classType: WATCH_LIST, userId: $user) { id } }"
ITEMS = """query ($id: ID!, $first: Int!, $after: ID) {
  list(id: $id) {
    items(first: $first, after: $after) {
      edges { node { listItem { ... on Title { id } } } }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""

Ask = Callable[[str, dict], dict]


class Unreadable(Exception):
    pass


def watchlist_ids(ask: Ask, user: str) -> list[str]:
    """Every title id on a public watchlist, in IMDb's order."""
    found = ask(LIST, {"user": user}).get("predefinedList")
    if not found:
        raise Unreadable("private")
    ids, after = [], None
    for _ in range(MAX_PAGES):
        items = (
            ask(ITEMS, {"id": found["id"], "first": PAGE, "after": after}).get("list") or {}
        ).get("items")
        if not items:
            raise Unreadable("private")
        for edge in items["edges"]:
            title = ((edge.get("node") or {}).get("listItem") or {}).get("id")
            if title and title.startswith("tt"):
                ids.append(title)
        if not items["pageInfo"]["hasNextPage"]:
            break
        after = items["pageInfo"]["endCursor"]
    return ids


def request(
    url: str, body: dict | None = None, headers: dict | None = None, method: str | None = None
) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "cineclock-imdb-sync",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def ask_imdb(query: str, variables: dict) -> dict:
    answer = request(
        IMDB_API,
        {"query": query, "variables": variables},
        {
            "x-imdb-client-name": "imdb-web-next",
            "Referer": "https://www.imdb.com/",
            "User-Agent": "cineclock",
        },
    )
    if answer.get("errors") and not answer.get("data"):
        raise Unreadable("private")
    return answer.get("data") or {}


def github_token() -> str:
    url = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=cineclock-relay"
    return request(
        url, headers={"Authorization": "Bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]}
    )["value"]


def main() -> int:
    auth = {"Authorization": "Bearer " + github_token()}
    users = request(f"{RELAY}/imdb/wanted", headers=auth)["users"]
    lists = []
    for user in users:
        try:
            lists.append({"user": user, "ids": watchlist_ids(ask_imdb, user)})
        except Unreadable as error:
            lists.append({"user": user, "error": str(error)})
        except OSError as error:
            print(f"{user}: {error}")
        time.sleep(1)
    if lists:
        request(f"{RELAY}/imdb/lists", {"lists": lists}, auth, method="PUT")
    print(f"::notice::{len(users)} wanted, {sum('ids' in x for x in lists)} read")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.HTTPError as error:
        print(f"::error::{error.url}: {error.code} {error.read().decode()[:300]}")
        sys.exit(1)
