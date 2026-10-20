// A public IMDb watchlist, read through IMDb's GraphQL API (the one imdb.com's
// own pages use). IMDb has no usernames: people are known by an id like
// ur12345678, which is in the address of their profile and watchlist pages.

const API = "https://api.graphql.imdb.com/";
const PAGE = 250;
const MAX_PAGES = 8;

// "ur12345678", or any IMDb link with one in it.
export function imdbUser(text) {
  const match = String(text || "").match(/\bur\d{4,12}\b/);
  return match ? match[0] : null;
}

async function ask(query, variables) {
  const response = await fetch(API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-imdb-client-name": "imdb-web-next",
      "x-imdb-user-country": "CA",
      Referer: "https://www.imdb.com/",
    },
    body: JSON.stringify({ query, variables }),
  });
  if (!response.ok) throw new Error(`IMDb answered ${response.status}`);
  const answer = await response.json();
  if (answer.errors?.length && !answer.data) throw new Error(answer.errors[0].message);
  return answer.data;
}

const LIST = `query ($user: ID!) {
  predefinedList(classType: WATCH_LIST, userId: $user) { id }
}`;

const ITEMS = `query ($id: ID!, $first: Int!, $after: ID) {
  list(id: $id) {
    items(first: $first, after: $after) {
      edges { node { listItem { ... on Title { id } } } }
      pageInfo { hasNextPage endCursor }
    }
  }
}`;

// The title ids on someone's watchlist, or null when there's no such list or
// it isn't public.
export async function readWatchlist(user) {
  const found = await ask(LIST, { user });
  const id = found?.predefinedList?.id;
  if (!id) return null;
  const ids = [];
  let after = null;
  for (let page = 0; page < MAX_PAGES; page++) {
    const data = await ask(ITEMS, { id, first: PAGE, after });
    const items = data?.list?.items;
    if (!items) return page === 0 ? null : { user, ids };
    for (const edge of items.edges) {
      const title = edge.node?.listItem?.id;
      if (title?.startsWith("tt")) ids.push(title);
    }
    if (!items.pageInfo?.hasNextPage) break;
    after = items.pageInfo.endCursor;
  }
  return { user, ids };
}
