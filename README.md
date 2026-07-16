# ICRS 2026 Planner

A small web app for the **15th International Coral Reef Symposium** (NZICC, Auckland, 19–24 July 2026).

It lists every talk by **day, session, and room**, and lets you star the ones you want into your own
schedule. It's a plain static site — no server, no build step, no accounts.

- **1,480 talks** across **223 sessions** in **14 parallel rooms**, plus 10 plenaries and 561 posters
- **Click any talk** for its **full abstract**, room number, session, presenter, and co-authors
- Search by title, author, affiliation, or topic; filter by day, room, and theme
- **Clash warnings** when two of your picks overlap (easy to miss with 14 rooms running at once)
- **Works offline** — install it to your phone's home screen and it keeps working with no wifi
- **Calendar export** (`.ics`) with times, rooms, and presenters
- **Share link** to move your schedule from laptop to phone

## Publishing it to GitHub Pages

### Option A — upload through the GitHub website (no git needed)

1. On github.com click **New repository**. Name it `icrs2026-planner`, choose **Public**, and add
   **nothing** — no README, no .gitignore, no license. Create it.
2. On the empty repo page click **uploading an existing file**.
3. Open the `icrs2026-planner` folder on your computer, select **everything inside it**
   (`index.html`, `assets`, `data`, `tools`, `README.md`), and drag it onto the page.
   - Upload the folder's **contents**, not the folder itself — `index.html` must land at the top
     level of the repo or Pages will 404.
   - If you have hidden files showing, leave out `.git` — that's git's own database, not part of the site.
4. Click **Commit changes** and wait for the uploads to finish.
5. Go to **Settings → Pages**, set **Source** to `Deploy from a branch`, pick **`main`** and
   **`/ (root)`**, and save.
6. A minute later it's live at `https://<you>.github.io/icrs2026-planner/`.

Every file in this folder is meant to be uploaded — there's no junk to filter out. The largest is
`data/abstracts.json` (~3.9 MB), well under GitHub's 25 MB web-upload limit.

### Option B — push with git

```bash
git remote add origin https://github.com/<you>/icrs2026-planner.git
git branch -M main
git push -u origin main
```

Then do step 5 above.

Open the URL on your phone and use *Add to Home Screen* — it then works offline at the venue.

> The repo must be public for GitHub Pages on a free account. Nothing here is sensitive: the programme
> is public, and your picks are never uploaded (see below).

## About the "login"

There isn't one, on purpose.

Your picks are saved in your browser's `localStorage`, which is already private to your own device and
browser. Different people using their own phones automatically get their own schedules — there's nothing
to collide and nothing to log into. On first open the app just asks for a **name**, which labels your
schedule, your calendar export, and your share link. One device can hold several named profiles (handy
for a shared laptop), and you can switch or delete them from the chip in the top-right.

A username and password on a purely static site would be **security theatre**: the check would run in
JavaScript that anyone can read with View Source, and there'd be no server to actually verify anything.
Since your picks never leave your device, there is nothing for a password to protect. If you later want
real accounts with automatic cross-device sync, that needs a backend (Supabase's free tier is a good
fit) and can drop in without changing the UI.

## Moving your schedule between devices

**My schedule → Copy share link**. Open that link on the other device and accept the prompt. The link
carries your picks in the URL itself (no server involved), so it also works for sending your plan to a
colleague.

## Where the data comes from

The programme is pulled from the official ICRS 2026 programme site, which is powered by EventsAir:

```
POST https://websitegatewayae.eventsair.com/api/GetAgendaData?tenant=innovators&projectid=23820057
```

Two things about this API are easy to miss, and `tools/build_programme.py` handles both:

- A plain `GET` returns sessions with **no talks in them**. The individual presentations only come back
  from a `POST` carrying the `statusIds` the official site is configured with.
- **Abstracts are not a field.** They're delivered as a *"View abstract"* handout, so they only appear
  when `handoutTypes` is passed — then the text arrives as `documents[].plainText`. All **1,480 talks
  have one**.

Neither the programme website nor the official programme PDF exposes individual talk titles or
abstracts anywhere in their own UI.

```bash
python tools/build_programme.py --fetch    # re-download and rebuild both data files
python tools/verify_programme.py           # check the result
```

The ~11 MB raw API snapshot is cached in `../_api_cache/` — deliberately outside this folder, so that
everything here stays safe to upload. Override with `--cache DIR`.

If you rebuild the data, **bump `CACHE` in `sw.js`** (e.g. `icrs2026-v3`) so people who already have the
app installed pick up the new programme instead of the cached copy.

### Why abstracts are a separate file

`data/abstracts.json` is ~3.9 MB — too big to sit in the initial page load. The app loads
`programme.json` first, renders, and only then fetches the abstracts in the background; the service
worker caches them so everything works offline afterwards. Abstracts are keyed by the same short `sid`
used for picks and share links.

Abstract text is author-submitted, so the app escapes all of it and then re-enables **only** italics —
a few authors wrap species names in `<i>…</i>` (one writes the malformed `<i>X<i>`), which renders as
*Endozoicomonas* rather than showing raw tags. `verify_programme.py` fails the build if any other
markup ever appears.

### Verification

`tools/verify_programme.py` checks the dataset against the **`ICRS 2026 Full Talk Grid.pdf`** in `tools/`,
which was produced independently of the API — so agreement between them is real evidence, not just
self-consistency. It asserts 223 sessions and 1,480 talks, that every session joins to one of the 14
rooms, that no room is double-booked, that talk times sit inside their session, that all 1,480 talks
have an abstract with no orphaned keys, and that a random sample of talk titles and presenters appears
verbatim in the PDF.

Two known quirks in the **official** programme data, both reported by the build rather than hidden:

- Three timestamps are stamped `AM` inside a `2:30 PM` session (one pairs a `2:30 AM` start with a
  `2:45 PM` end). The build shifts a time by 12h only when that lands it inside the session window, so
  the correction is unambiguous rather than a guess.
- Two talks in session `3C #94` are published starting at/after their session's 4:00pm end. That's left
  exactly as published and simply noted.

## Layout

```
index.html               app shell
assets/app.js            all the logic (picks, clashes, .ics, share, profiles, talk detail)
assets/styles.css        styling, light + dark
data/programme.json      sessions + talks (~1 MB) - loaded first
data/abstracts.json      1,480 abstracts (~3.9 MB) - loaded lazily in the background
sw.js                    offline cache
tools/build_programme.py API -> data/*.json
tools/verify_programme.py structural checks + PDF cross-check + abstract checks
tools/make_icons.py      PWA icons
```

## Running it locally

```bash
python -m http.server 8765
# then open http://localhost:8765
```

Opening `index.html` straight off disk won't work — browsers block `fetch` of local data files over
`file://`.

## Notes

- All times are **venue local** (Auckland, NZST = UTC+12 in July). Calendar exports are converted to UTC
  so they land correctly whatever timezone your device is in.
- The programme is **subject to change** — the footer shows the capture date. Re-run the build to refresh.
