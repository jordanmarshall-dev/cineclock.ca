import httpx

USER_AGENT = "cineclock (+https://github.com/yogzoth/cineclock)"


def make_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
