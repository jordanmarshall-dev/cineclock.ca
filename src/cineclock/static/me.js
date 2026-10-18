// Personal touches from a visitor's Letterboxd, all in their own browser.
//
// A connected visitor is remembered in localStorage as { user: "yogzoth" }.
// Profiles the site syncs daily load from me/<user>.json; anyone else is read
// through the relay (relay/worker.js), since Letterboxd won't let a browser read
// profiles itself. Every film on a page carries data-film="<slug>"; we mark the
// ones that match, then tell the filters (which listen for "cineclock:personal").
(() => {
  const root = document.body.dataset.root || "";
  const KEY = "cineclock.letterboxd";
  const RELAY = document.body.dataset.relay || "";

  const ICONS = {
    bookmark: '<path d="M6.5 3.5h11a1 1 0 0 1 1 1v16l-6.5-4.5-6.5 4.5v-16a1 1 0 0 1 1-1z"/>',
    eye: '<path d="M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.5"/>',
  };
  const icon = (name, size = 12) =>
    `<svg class="icon" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

  function saved() {
    try {
      const value = JSON.parse(localStorage.getItem(KEY) || "null");
      return value && value.user ? value : null;
    } catch (e) {
      return null;
    }
  }

  function save(value) {
    try {
      if (value) localStorage.setItem(KEY, JSON.stringify(value));
      else localStorage.removeItem(KEY);
      return true;
    } catch (e) {
      return false;
    }
  }

  async function getJSON(path) {
    const response = await fetch(root + path, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.json();
  }

  // A film's place in a member's lists, in the same short keys the build uses:
  // w watchlist, s seen, r rating out of 10, d last diary date, old seen before
  // the diary feed reaches back.
  function statuses(profile, index) {
    const watchlist = new Set(profile.watchlist);
    const films = {};
    for (const film of index) {
      const lb = film.lb;
      if (!lb) continue;
      const found = {};
      if (watchlist.has(lb)) found.w = 1;
      if (lb in profile.watched) {
        found.s = 1;
        if (profile.watched[lb]) found.r = profile.watched[lb];
        if (profile.diary[lb]) found.d = profile.diary[lb];
        else if (profile.diary_since) found.old = 1;
      }
      if (Object.keys(found).length) films[film.slug] = found;
    }
    return films;
  }

  async function load(value = saved()) {
    if (!value) return null;
    try {
      const data = await getJSON(`me/${encodeURIComponent(value.user)}.json`);
      return { user: value.user, films: data.films, updated: data.updated };
    } catch (e) {
      if (!RELAY) throw e;
    }
    const response = await fetch(`${RELAY}/profile/${encodeURIComponent(value.user)}`);
    if (response.status === 404) throw new Error("missing");
    if (!response.ok) throw new Error("relay");
    const profile = await response.json();
    return { user: profile.user, films: statuses(profile, await getJSON("films.json")) };
  }

  // The finished cards (from films.json) for the films that pass a test.
  async function cards(films, test) {
    const index = await getJSON("films.json");
    return index
      .filter((f) => films[f.slug] && test(films[f.slug]))
      .map((f) => f.card.replaceAll("@root@", root))
      .join("");
  }

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function stars(rating) {
    if (!rating) return "";
    return " " + "★".repeat(Math.floor(rating / 2)) + (rating % 2 ? "½" : "");
  }

  // The pills for one film: watchlist, and when (and how much) they liked it.
  function pills(status) {
    const out = [];
    if (status.w) out.push(["bookmark", "On watchlist"]);
    if (status.s) {
      const year = 365 * 24 * 3600 * 1000;
      let when = "Seen";
      if (status.d && Date.now() - Date.parse(status.d) < year) {
        const [, m, d] = status.d.split("-").map(Number);
        when = `Seen ${MONTHS[m - 1]} ${d}`;
      } else if (status.old || status.d) {
        when = "Seen a while ago";
      }
      out.push(["eye", when + stars(status.r)]);
    }
    return out;
  }

  function mark(films) {
    for (const el of document.querySelectorAll("[data-film]")) {
      const status = films[el.dataset.film];
      if (!status) continue;
      const item = el.closest("[data-item]") || el;
      if (item.dataset.tags !== undefined) {
        const tags = item.dataset.tags.split(" ").filter(Boolean);
        if (status.w) tags.push("watchlist");
        if (status.s) tags.push("seen");
        item.dataset.tags = tags.join(" ");
      }
      const slot = el.querySelector(".personal");
      if (slot) {
        slot.innerHTML = pills(status)
          .map(([name, text]) => `<span class="tag tag-personal">${icon(name)}${text}</span>`)
          .join("");
        slot.hidden = false;
      }
      const art = el.querySelector(".card-art");
      if (art && !art.querySelector(".card-mark")) {
        art.insertAdjacentHTML(
          "beforeend",
          `<span class="card-mark" title="${status.w ? "On your watchlist" : "Seen"}">${icon(status.w ? "bookmark" : "eye", 14)}</span>`
        );
      }
    }
  }

  // Home: a shelf of watchlist films playing, drawn from films.json.
  async function shelf(films) {
    const spot = document.getElementById("mine-rail");
    if (!spot) return;
    // The build draws each card, so the shelf matches every other card on the site.
    const list = await cards(films, (f) => f.w);
    if (!list) return;
    spot.innerHTML = `<section class="rail rail-personal"><div class="rail-head"><h2><a href="${root}films/?tag=watchlist">From your watchlist</a></h2>
      <a class="see-all" href="${root}films/?tag=watchlist" aria-label="See all from your watchlist"><svg class="icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg></a></div>
      <ul class="rail-cards">${list}</ul></section>`;
  }

  function show(connected) {
    document.querySelectorAll("[data-needs-me]").forEach((el) => (el.hidden = !connected));
    document.querySelectorAll("[data-needs-no-me]").forEach((el) => (el.hidden = connected));
  }

  async function start() {
    const value = saved();
    show(Boolean(value));
    if (!value) return;
    try {
      const me = await load(value);
      if (!me) return;
      mark(me.films);
      await shelf(me.films);
      mark(me.films);
      window.cineclockPersonal = me;
      document.dispatchEvent(new CustomEvent("cineclock:personal", { detail: me }));
    } catch (e) {
      // A profile that stopped syncing shouldn't break the page.
      show(false);
    }
  }

  window.cineclockMe = { saved, save, load, cards, mark, root };
  start();
})();
