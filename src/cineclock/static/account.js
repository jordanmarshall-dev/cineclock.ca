// Signing in, saving films and theatres, and the rating source.
//
// The account itself lives on the Worker at data-api (relay/account.js). A copy
// is kept in localStorage so pages draw saved marks and scores straight away,
// then it's refreshed from the Worker. Saves made while signed out stay in
// localStorage and are merged into the account on sign-in.
(() => {
  const API = document.body.dataset.api || "";
  // The same Worker at its workers.dev address, for networks that can't find
  // api.cineclock.ca. There the session travels as a token instead of a cookie.
  const FALLBACK = document.body.dataset.relay || "";
  const ACCOUNT = "cineclock.account";
  const TOKEN = "cineclock.session";
  const LOCAL = "cineclock.saved";
  const SOURCES = { letterboxd: "Letterboxd", imdb: "IMDb", rt: "Rotten Tomatoes", metacritic: "Metacritic" };

  const read = (key, fallback) => {
    try {
      return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
    } catch (e) {
      return fallback;
    }
  };
  const write = (key, value) => {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {}
  };

  let account = read(ACCOUNT, null);
  const emptySaves = () => ({ film: [], theatre: [] });

  function savedList(kind) {
    const source = account ? account.saved : read(LOCAL, emptySaves());
    return source[kind] || [];
  }

  function changed() {
    write(ACCOUNT, account);
    document.dispatchEvent(new CustomEvent("cineclock:account", { detail: account }));
    drawButtons();
    drawHeader();
  }

  // The header's account link: "Sign in", or the first letter of your email.
  function drawHeader() {
    for (const link of document.querySelectorAll("[data-account-link]")) {
      const email = account?.email || "";
      link.classList.toggle("signed-in", Boolean(account));
      const initial = link.querySelector(".account-initial");
      initial.textContent = email.slice(0, 1) || "?";
      initial.hidden = !account;
      link.setAttribute("aria-label", account ? `Your cineclock, signed in as ${email}` : "Sign in");
    }
  }

  let base = API;

  async function send(host, method, path, body) {
    const headers = body === undefined ? {} : { "Content-Type": "application/json" };
    const token = read(TOKEN, null);
    if (token) headers.Authorization = `Bearer ${token}`;
    return fetch(host + path, {
      method,
      credentials: "include",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  }

  async function call(method, path, body) {
    let response;
    try {
      response = await send(base, method, path, body);
    } catch (error) {
      // Couldn't reach api.cineclock.ca at all: try the workers.dev address once.
      if (!FALLBACK || base === FALLBACK) throw error;
      base = FALLBACK;
      response = await send(base, method, path, body);
    }
    if (response.status === 401 && path === "/auth/google") {
      const answer = await response.json().catch(() => ({}));
      throw new Error(`Google sign-in was refused (${answer.reason || "no reason given"})`);
    }
    if (response.status === 401) {
      account = null;
      write(TOKEN, null);
      changed();
      throw new Error("signed out");
    }
    if (!response.ok) {
      const answer = await response.json().catch(() => ({}));
      throw new Error(`cineclock's server had a problem (${answer.detail || response.status})`);
    }
    const data = await response.json();
    if (data.token) {
      write(TOKEN, data.token);
      delete data.token;
    }
    return data;
  }

  async function refresh() {
    if (!API || !account) return account;
    try {
      account = await call("GET", "/me");
      changed();
    } catch (e) {
      // Offline or the Worker is down: keep the copy we have.
    }
    return account;
  }

  async function signIn(credential) {
    account = await call("POST", "/auth/google", { credential });
    const local = read(LOCAL, emptySaves());
    const items = [
      ...local.film.map((ref) => ({ kind: "film", ref })),
      ...local.theatre.map((ref) => ({ kind: "theatre", ref })),
    ];
    if (items.length) {
      account = await call("POST", "/me/saved", { items });
      write(LOCAL, null);
    }
    changed();
    return account;
  }

  async function signOut() {
    try {
      await call("POST", "/auth/signout");
    } catch (e) {}
    account = null;
    write(TOKEN, null);
    changed();
  }

  async function deleteAccount() {
    await call("DELETE", "/me");
    account = null;
    write(TOKEN, null);
    changed();
  }

  async function toggle(kind, ref) {
    const on = !savedList(kind).includes(ref);
    if (!account) {
      const local = read(LOCAL, emptySaves());
      local[kind] = on ? [...local[kind], ref] : local[kind].filter((r) => r !== ref);
      write(LOCAL, local);
      changed();
      return on;
    }
    // Show it straight away; the Worker's answer replaces this copy.
    account.saved[kind] = on ? [...account.saved[kind], ref] : account.saved[kind].filter((r) => r !== ref);
    changed();
    account = await call("PUT", "/me/saved", { kind, ref, saved: on });
    changed();
    return on;
  }

  async function settings(values) {
    account = await call("PUT", "/me/settings", values);
    changed();
  }

  async function setImdb(ids) {
    account = await call("PUT", "/me/imdb", { ids });
    changed();
  }

  // An IMDb list export: a CSV whose "Const" column holds ids like tt0073195.
  function imdbIds(csv) {
    const lines = csv.split(/\r?\n/).filter(Boolean);
    const header = (lines.shift() || "").split(",").map((h) => h.replace(/"/g, "").trim());
    const column = header.indexOf("Const");
    const ids = new Set();
    for (const line of lines) {
      const cell = column >= 0 ? line.split(",")[column] : line;
      const match = (cell || "").match(/tt\d{5,10}/);
      if (match) ids.add(match[0]);
    }
    return [...ids];
  }

  function source() {
    return account?.rating_source || "letterboxd";
  }

  // Save buttons: <button data-save="film" data-ref="naza-2026" hidden>.
  function drawButtons() {
    for (const button of document.querySelectorAll("[data-save]")) {
      const on = savedList(button.dataset.save).includes(button.dataset.ref);
      button.hidden = false;
      button.setAttribute("aria-pressed", String(on));
      button.querySelector("[data-save-label]").textContent = on ? "Saved" : "Save";
    }
  }

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-save]");
    if (!button) return;
    button.disabled = true;
    try {
      await toggle(button.dataset.save, button.dataset.ref);
    } catch (e) {
      drawButtons();
    } finally {
      button.disabled = false;
    }
  });

  window.cineclockAccount = {
    get current() {
      return account;
    },
    ready: refresh(),
    savedList,
    signIn,
    signOut,
    deleteAccount,
    toggle,
    settings,
    setImdb,
    imdbIds,
    source,
    SOURCES,
    enabled: Boolean(API),
  };
  drawButtons();
  drawHeader();
})();
