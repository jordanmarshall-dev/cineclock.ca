import pytest

from cineclock.imdb_sync import LIST, Unreadable, watchlist_ids


def fake_imdb(pages, list_id="ls1"):
    calls = []

    def ask(query, variables):
        calls.append(variables)
        if query == LIST:
            return {"predefinedList": {"id": list_id} if list_id else None}
        n = sum(1 for c in calls if "id" in c) - 1
        edges = [{"node": {"listItem": {"id": t}}} for t in pages[n]]
        more = n + 1 < len(pages)
        return {
            "list": {
                "items": {"edges": edges, "pageInfo": {"hasNextPage": more, "endCursor": f"c{n}"}}
            }
        }

    return ask, calls


def test_reads_every_page_of_a_watchlist_in_order():
    ask, calls = fake_imdb([["tt0073195", "tt0078748"], ["tt0113277"]])
    assert watchlist_ids(ask, "ur1") == ["tt0073195", "tt0078748", "tt0113277"]
    assert calls[-1]["after"] == "c0"


def test_skips_items_that_arent_titles():
    ask, _ = fake_imdb([["tt0073195", None, "nm0000229"]])
    assert watchlist_ids(ask, "ur1") == ["tt0073195"]


def test_a_private_watchlist_says_so():
    ask, _ = fake_imdb([], list_id=None)
    with pytest.raises(Unreadable, match="private"):
        watchlist_ids(ask, "ur1")
