// cineclock relay: reads a public Letterboxd profile for the site.
//
// Letterboxd doesn't let other websites read profiles from a visitor's browser,
// and cineclock is plain files with no server, so this small Cloudflare Worker
// does the reading. GET /profile/<username> returns:
//
//   { user, watchlist: [slug], watched: { slug: rating or null },
//     diary: { slug: "YYYY-MM-DD" }, diary_since: "YYYY-MM-DD" or null }
//
// It reads the same pages as the site's own daily sync (profiles.py): every
// page of the watchlist, the first page of watched films (Letterboxd blocks
// the rest), and the diary feed. Answers are cached for six hours.

const BASE = "https://letterboxd.com";
const ALLOWED_ORIGINS = ["https://yogzoth.github.io", "http://localhost:8000", "http://127.0.0.1:8000"];
const CACHE_SECONDS = 6 * 60 * 60;
// Cloudflare's free plan allows 50 fetches per request; leave room for the rest.
const MAX_WATCHLIST_PAGES = 45;
const HEADERS = { "User-Agent": "cineclock relay (+https://github.com/yogzoth/cineclock)" };

export function parseGrid(page) {
  // Each film in a poster grid is an <li class="griditem ..."> with its slug in
  // data-item-slug and, on the watched list, a rated-N class for the stars.
  const films = {};
  for (const item of page.split(/<li class="griditem/).slice(1)) {
    const slug = item.match(/data-item-slug="([^"]+)"/);
    if (!slug) continue;
    const rated = item.match(/\brated-(\d+)\b/);
    films[slug[1]] = rated ? Number(rated[1]) : null;
  }
  const pages = [...page.matchAll(/\/page\/(\d+)\//g)].map((m) => Number(m[1]));
  return { films, lastPage: Math.max(1, ...pages) };
}

export function parseRss(feed) {
  // Diary entries: the film's slug from its link, and the date it was watched.
  const diary = {};
  for (const item of feed.split("<item>").slice(1)) {
    const watched = item.match(/<letterboxd:watchedDate>(\d{4}-\d{2}-\d{2})</);
    const slug = item.match(/<link>[^<]*\/film\/([^/<]+)\//);
    if (!watched || !slug) continue;
    if (!diary[slug[1]] || watched[1] > diary[slug[1]]) diary[slug[1]] = watched[1];
  }
  return diary;
}

async function get(fetcher, url) {
  const response = await fetcher(url, { headers: HEADERS });
  return response;
}

export async function readProfile(user, fetcher = fetch) {
  const first = await get(fetcher, `${BASE}/${user}/watchlist/`);
  if (first.status === 404) return null;
  if (!first.ok) throw new Error(`watchlist: ${first.status}`);
  const page1 = parseGrid(await first.text());
  const watchlist = new Set(Object.keys(page1.films));
  const last = Math.min(page1.lastPage, MAX_WATCHLIST_PAGES);
  const rest = [];
  for (let n = 2; n <= last; n++) rest.push(get(fetcher, `${BASE}/${user}/watchlist/page/${n}/`));

  const watchedResponse = get(fetcher, `${BASE}/${user}/films/`);
  const rssResponse = get(fetcher, `${BASE}/${user}/rss/`);

  for (const response of await Promise.all(rest)) {
    if (!response.ok) continue; // keep what we have rather than lose the lot
    for (const slug of Object.keys(parseGrid(await response.text()).films)) watchlist.add(slug);
  }
  const watchedPage = await watchedResponse;
  const watched = watchedPage.ok ? parseGrid(await watchedPage.text()).films : {};
  const rss = await rssResponse;
  const diary = rss.ok ? parseRss(await rss.text()) : {};

  // Films in the diary are watched even if the first page of the watched list
  // didn't reach them.
  for (const slug of Object.keys(diary)) if (!(slug in watched)) watched[slug] = null;
  const dates = Object.values(diary).sort();
  return { user, watchlist: [...watchlist], watched, diary, diary_since: dates[0] || null };
}

function respond(body, status, origin) {
  const headers = {
    "Content-Type": "application/json",
    "Cache-Control": `public, max-age=${CACHE_SECONDS}`,
    Vary: "Origin",
  };
  if (ALLOWED_ORIGINS.includes(origin)) headers["Access-Control-Allow-Origin"] = origin;
  return new Response(JSON.stringify(body), { status, headers });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const origin = request.headers.get("Origin") || "";
    const match = url.pathname.match(/^\/profile\/([A-Za-z0-9_]{1,30})\/?$/);
    if (request.method !== "GET" || !match) return respond({ error: "not found" }, 404, origin);
    const user = match[1].toLowerCase();

    const cache = typeof caches !== "undefined" ? caches.default : null;
    const key = new Request(`${url.origin}/profile/${user}`);
    const hit = cache && (await cache.match(key));
    if (hit) {
      const body = await hit.json();
      return respond(body, 200, origin);
    }

    try {
      const profile = await readProfile(user);
      if (!profile) return respond({ error: "no such profile" }, 404, origin);
      const response = respond(profile, 200, origin);
      if (cache && ctx) ctx.waitUntil(cache.put(key, response.clone()));
      return response;
    } catch (error) {
      return respond({ error: "Letterboxd didn't answer" }, 502, origin);
    }
  },
};
