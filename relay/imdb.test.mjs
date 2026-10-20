// Tests for IMDb watchlists by username, run with: node relay/imdb.test.mjs
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { AUDIENCE, handleImdb, imdbUser, REPOSITORY } from "./imdb.js";

function fakeD1() {
  const sqlite = new DatabaseSync(":memory:");
  const statement = (sql, args = []) => ({
    bind: (...values) => statement(sql, values),
    first: async () => sqlite.prepare(sql).get(...args) ?? null,
    all: async () => ({ results: sqlite.prepare(sql).all(...args) }),
    run: async () => sqlite.prepare(sql).run(...args),
    sql,
    args,
  });
  return {
    prepare: (sql) => statement(sql),
    batch: async (statements) => {
      sqlite.exec("BEGIN");
      try {
        for (const s of statements) sqlite.prepare(s.sql).run(...s.args);
        sqlite.exec("COMMIT");
      } catch (error) {
        sqlite.exec("ROLLBACK");
        throw error;
      }
    },
    sqlite,
  };
}

const NOW = Date.parse("2026-10-19T12:00:00Z");
const HOUR = 3600 * 1000;
const pair = await crypto.subtle.generateKey(
  { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
  true,
  ["sign", "verify"],
);
const keys = [{ ...(await crypto.subtle.exportKey("jwk", pair.publicKey)), kid: "gh", alg: "RS256" }];
const b64 = (data) => Buffer.from(JSON.stringify(data)).toString("base64url");

async function githubToken(claims = {}) {
  const head = b64({ alg: "RS256", kid: "gh", typ: "JWT" });
  const body = b64({
    iss: "https://token.actions.githubusercontent.com",
    aud: AUDIENCE,
    repository: REPOSITORY,
    exp: NOW / 1000 + 600,
    ...claims,
  });
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", pair.privateKey, new TextEncoder().encode(`${head}.${body}`));
  return `${head}.${body}.${Buffer.from(signature).toString("base64url")}`;
}

async function call(env, method, path, { body, token, origin = "https://cineclock.ca", now = NOW } = {}) {
  const headers = { Origin: origin };
  if (token) headers.Authorization = `Bearer ${token}`;
  const request = new Request(`https://api.cineclock.ca${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const response = await handleImdb(request, env, { now, keys });
  return { status: response.status, json: await response.json() };
}

// Links and bare ids both work.
assert.equal(imdbUser("https://www.imdb.com/user/ur12345678/watchlist/?ref_=nv"), "ur12345678");
assert.equal(imdbUser("m.imdb.com/user/ur999999/"), "ur999999");
assert.equal(imdbUser("yogzoth"), null);
assert.equal(imdbUser("https://www.imdb.com/user/p.h2ouytvlcsyuesmhpcj673m3gq?ref_=wl_usr_ov"), "p.h2ouytvlcsyuesmhpcj673m3gq");

const env = { DB: fakeD1() };

// Connecting starts a pending list.
let r = await call(env, "POST", "/imdb/connect", { body: { user: "https://www.imdb.com/user/ur12345678/" } });
assert.equal(r.status, 200);
assert.deepEqual(r.json, { user: "ur12345678", ids: [], ready: false, updated: null, error: null });
assert.equal((await call(env, "POST", "/imdb/connect", { body: { user: "nope" } })).status, 400);
assert.equal((await call(env, "POST", "/imdb/connect", { body: { user: "ur1234" }, origin: "https://evil.example" })).status, 403);

// Only the GitHub job can see what's wanted or post results.
assert.equal((await call(env, "GET", "/imdb/wanted")).status, 403);
assert.equal((await call(env, "GET", "/imdb/wanted", { token: await githubToken({ repository: "someone/else" }) })).status, 403);
assert.equal((await call(env, "GET", "/imdb/wanted", { token: await githubToken({ aud: "other" }) })).status, 403);
assert.equal((await call(env, "GET", "/imdb/wanted", { token: await githubToken({ exp: NOW / 1000 - 1 }) })).status, 403);
const token = await githubToken();
r = await call(env, "GET", "/imdb/wanted", { token });
assert.deepEqual(r.json.users, ["ur12345678"]);

// The job's results show up for the browser, junk ids dropped.
r = await call(env, "PUT", "/imdb/lists", { token, body: { lists: [{ user: "ur12345678", ids: ["tt0073195", "nope"] }] } });
assert.equal(r.json.saved, 1);
r = await call(env, "GET", "/imdb/ur12345678");
assert.deepEqual(r.json.ids, ["tt0073195"]);
assert.equal(r.json.ready, true);

// Fresh lists aren't wanted again until they're six hours old.
assert.deepEqual((await call(env, "GET", "/imdb/wanted", { token })).json.users, []);
assert.deepEqual((await call(env, "GET", "/imdb/wanted", { token: await githubToken({ exp: NOW / 1000 + 8 * 3600 }), now: NOW + 7 * HOUR })).json.users, ["ur12345678"]);

// A list that went private keeps its last ids and says why.
await call(env, "PUT", "/imdb/lists", { token, body: { lists: [{ user: "ur12345678", error: "private" }] } });
r = await call(env, "GET", "/imdb/ur12345678");
assert.deepEqual(r.json.ids, ["tt0073195"]);
assert.equal(r.json.error, "private");

// Connecting again after fixing it gets it read on the next run.
await call(env, "POST", "/imdb/connect", { body: { user: "ur12345678" } });
assert.deepEqual((await call(env, "GET", "/imdb/wanted", { token })).json.users, ["ur12345678"]);

assert.equal((await call(env, "GET", "/imdb/ur5555555")).status, 404);
console.log("imdb tests passed");
