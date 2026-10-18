// Tests for the relay, run with: node relay/test.mjs
// They use the same saved Letterboxd pages as the Python tests.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import worker, { parseGrid, parseRss, readProfile } from "./worker.js";

const page = (name) =>
  readFileSync(new URL(`../tests/fixtures/letterboxd_user/${name}`, import.meta.url), "utf8");

const watchlist = parseGrid(page("watchlist_page1.html"));
assert.equal(Object.keys(watchlist.films).length, 28);
assert.equal(watchlist.lastPage, 24);

const watched = parseGrid(page("films_page1.html")).films;
assert.equal(Object.keys(watched).length, 72);
assert.equal(Object.values(watched).filter(Boolean).length, 63);

assert.equal(Object.keys(parseRss(page("rss.xml"))).length, 50);

// The whole read, against a stand-in Letterboxd.
const fake = async (url) => {
  if (url.includes("/watchlist/")) return new Response(page("watchlist_page1.html"));
  if (url.endsWith("/films/")) return new Response(page("films_page1.html"));
  if (url.endsWith("/rss/")) return new Response(page("rss.xml"));
  return new Response("", { status: 404 });
};
const profile = await readProfile("yogzoth", fake);
assert.equal(profile.watchlist.length, 28);
assert.equal(Object.keys(profile.watched).length, 87); // diary films count as watched
assert.equal(profile.diary_since, "2026-08-10");

assert.equal(await readProfile("nobody", async () => new Response("", { status: 404 })), null);

const bad = await worker.fetch(new Request("https://relay.test/profile/no%20spaces"), {}, null);
assert.equal(bad.status, 404);

console.log("relay tests passed");
