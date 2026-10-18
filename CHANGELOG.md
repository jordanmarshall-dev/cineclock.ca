# Changelog

## 2.0.1 (October 18, 2026)

- Film pages use the theatre's own description when TMDB has no synopsis, so one-off events like Vampyr × Applied Silence still say what they are.
- The README screenshots are taken from the live data by a Screenshots workflow in GitHub Actions.

## 2.0.0 (October 18, 2026)

A redesign around one idea: every film looks the same everywhere, so you always know where to look.

### Design

- One poster card across the whole site: home rows, theatre rows, the Films grid and the watchlist shelf. Every card has the same three lines: the title, the year with the score on the right, and the date. Theatre logos sit over the poster's corner.
- Cards show the Letterboxd score, or the next source that has one (IMDb, Rotten Tomatoes, Metacritic). With no score, a tag like Q&A or Festival takes its place, or a quiet Unrated pill.
- A film with only one screening gets a small purple star on its date and a highlighted booking button, instead of a separate badge.
- The Films page is a poster grid, three across on a phone.
- Tag pills share one look everywhere, in sentence case.

### Home

- A swipeable spotlight of three highlights: tonight's pick, then the standout screenings of the next two weeks. Every slide has full backdrop art, a sliver of the next one peeks in, and it wraps around. Arrow keys work too.
- A Letterboxd button beside the tagline, and three shortcuts: Showtimes, On film and Events.
- "Just added" ignores everything from a theatre's first scrape, so adding a theatre doesn't flood it.

### Theatres

- Theatre pages open with poster rows. "Now playing" always lists every film there, so even a two-film theatre gets a full row; Leaving soon, Events, On film and Just added appear only when they have enough to show.
- Theatres with more than one room swipe between rooms instead of using a dropdown.
- The Dunbar joins the Rio, the Park, the Cinematheque and VIFF Centre.

### Film pages

- Tap the poster to see it full size.
- Every score source still shows here, each linking out.

### Tags

- Shorter names: Q&A (filmmaker Q&As included), Intro, Live music, Festival, Shorts, Event, Guests and Preview (advance, insider and sneak screenings).
- Festival programmes are tagged from the series the Cinematheque files them under, like "Small File Media Festival 2026".
- A listing with no year, no score and no tag is tagged Event.

### Letterboxd

- Connect a synced profile or upload your Letterboxd export (read in your browser, never uploaded) to see what's on your watchlist and what you've seen, with a "From your watchlist" row and a calendar feed of watchlist screenings.

### Sharing and finish

- Link previews: a shared page shows a proper card with a branded image, the film's backdrop or the theatre's photo.
- A 404 page that points you back to what's playing.
- A sitemap and canonical links for search engines.
- Date chips name the month once it changes ("Sun Nov 1").
- The version number in the footer.

## 1.0.0

The first version: scrapers for the Rio, the Park, the Cinematheque and VIFF Centre, tested against saved real responses; SQLite storage that updates instead of duplicating; film details from TMDB; scores from Letterboxd, IMDb, Rotten Tomatoes and Metacritic; home, Films, Showtimes, theatre and film pages; and a static site on GitHub Pages rebuilt every four hours.
