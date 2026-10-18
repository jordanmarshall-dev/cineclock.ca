// Personal touches from a visitor's Letterboxd, all in their own browser.
//
// A connected visitor is remembered in localStorage as either
//   { user: "yogzoth" }                 a profile the site syncs (me/<user>.json)
//   { upload: { name, entries, at } }   lists read from their Letterboxd export
// Every film on a page carries data-film="<slug>"; we mark the ones that
// match, then tell the filters (which listen for "cineclock:personal").
(() => {
  const root = document.body.dataset.root || "";
  const KEY = "cineclock.letterboxd";

  const ICONS = {
    bookmark: '<path d="M6.5 3.5h11a1 1 0 0 1 1 1v16l-6.5-4.5-6.5 4.5v-16a1 1 0 0 1 1-1z"/>',
    eye: '<path d="M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.5"/>',
  };
  const icon = (name, size = 12) =>
    `<svg class="icon" viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

  function saved() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || "null");
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

  // "The Thing" and "the thing!" should match; years keep same-titled films apart.
  const norm = (title) => (title || "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "");
  const key = (title, year) => `${norm(title)}|${year || ""}`;

  async function getJSON(path) {
    const response = await fetch(root + path, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.json();
  }

  // Map an uploaded export onto the films playing now, by title and year.
  function matchUpload(entries, index) {
    const films = {};
    for (const film of index) {
      const candidates = [key(film.title, film.year), key(film.alt, film.year)];
      const hit = candidates.map((k) => entries[k]).find(Boolean);
      if (hit) films[film.slug] = hit;
    }
    return films;
  }

  async function load(value = saved()) {
    if (!value) return null;
    if (value.user) {
      const data = await getJSON(`me/${encodeURIComponent(value.user)}.json`);
      return { label: value.user, synced: true, films: data.films, updated: data.updated };
    }
    if (value.upload) {
      const index = await getJSON("films.json");
      return { label: value.upload.name, synced: false, films: matchUpload(value.upload.entries, index) };
    }
    return null;
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
    const index = await getJSON("films.json");
    const picks = index.filter((f) => films[f.slug] && films[f.slug].w);
    if (!picks.length) return;
    const esc = (s) => String(s).replace(/[&<>"]/g, (c) => `&#${c.charCodeAt(0)};`);
    const cards = picks
      .map(
        (f) => `<li class="card" data-film="${esc(f.slug)}"><a href="${root}films/${esc(f.slug)}/">
        <span class="card-art"><span class="poster"><span class="poster-fallback" aria-hidden="true">${esc(f.title)}</span>${
          f.poster ? `<img src="${esc(f.poster)}" alt="${esc(f.title)}" loading="lazy" onerror="this.hidden = true">` : ""
        }</span><span class="card-venues">${f.venues
          .map((v) => `<span class="venue-pill"><img src="${root}${v.src}" alt="${esc(v.name)}" width="${v.w}" height="${v.h}"></span>`)
          .join("")}</span></span>
        <span class="card-title">${esc(f.title)}${f.year ? ` <span class="year">${f.year}</span>` : ""}</span>
        <span class="card-next"><svg class="icon" viewBox="0 0 24 24" width="12" height="12" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>${esc(f.next)}</span></a></li>`
      )
      .join("");
    spot.innerHTML = `<section class="rail rail-personal"><div class="rail-head"><h2><a href="${root}films/?tag=watchlist">From your watchlist</a></h2>
      <a class="see-all" href="${root}films/?tag=watchlist" aria-label="See all from your watchlist"><svg class="icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg></a></div>
      <ul class="rail-cards">${cards}</ul></section>`;
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

  // --- Reading a Letterboxd export (zip or its CSVs), all in the browser ---

  function parseCSV(text) {
    const rows = [];
    let row = [];
    let cell = "";
    let quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; }
        else if (c === '"') quoted = false;
        else cell += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(cell); cell = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(cell); rows.push(row); row = []; cell = "";
      } else cell += c;
    }
    if (cell || row.length) { row.push(cell); rows.push(row); }
    const [head, ...body] = rows.filter((r) => r.some(Boolean));
    return (body || []).map((r) => Object.fromEntries((head || []).map((h, i) => [h.trim(), r[i]])));
  }

  // Just enough of the zip format to pull out the CSVs Letterboxd puts in its export.
  async function unzip(buffer) {
    const view = new DataView(buffer);
    const files = {};
    let end = buffer.byteLength - 22;
    while (end >= 0 && view.getUint32(end, true) !== 0x06054b50) end--;
    if (end < 0) throw new Error("not a zip file");
    let at = view.getUint32(end + 16, true);
    const count = view.getUint16(end + 10, true);
    for (let n = 0; n < count; n++) {
      const method = view.getUint16(at + 10, true);
      const size = view.getUint32(at + 20, true);
      const nameLength = view.getUint16(at + 28, true);
      const extra = view.getUint16(at + 30, true);
      const comment = view.getUint16(at + 32, true);
      const local = view.getUint32(at + 42, true);
      const name = new TextDecoder().decode(new Uint8Array(buffer, at + 46, nameLength));
      at += 46 + nameLength + extra + comment;
      if (!/^[^/]*\.csv$/.test(name)) continue; // top-level CSVs only
      const start = local + 30 + view.getUint16(local + 26, true) + view.getUint16(local + 28, true);
      const bytes = new Uint8Array(buffer, start, size);
      files[name] = method === 0
        ? new TextDecoder().decode(bytes)
        : await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate-raw"))).text();
    }
    return files;
  }

  async function readExport(fileList) {
    const files = {};
    for (const file of fileList) {
      if (/\.zip$/i.test(file.name)) Object.assign(files, await unzip(await file.arrayBuffer()));
      else files[file.name.replace(/^.*\//, "")] = await file.text();
    }
    const entries = {};
    const touch = (row) => (entries[key(row.Name, row.Year)] ||= {});
    for (const row of parseCSV(files["watchlist.csv"] || "")) touch(row).w = 1;
    for (const row of parseCSV(files["watched.csv"] || "")) touch(row).s = 1;
    for (const row of parseCSV(files["ratings.csv"] || "")) {
      const entry = touch(row);
      entry.s = 1;
      entry.r = Math.round(parseFloat(row.Rating) * 2) || undefined;
    }
    for (const row of parseCSV(files["diary.csv"] || "")) {
      const entry = touch(row);
      entry.s = 1;
      const day = row["Watched Date"] || row.Date;
      if (day && (!entry.d || day > entry.d)) entry.d = day;
    }
    const total = Object.keys(entries).length;
    if (!total) throw new Error("No Letterboxd lists found in that file.");
    return entries;
  }

  window.cineclockMe = { saved, save, load, readExport, show, root };
  start();
})();
