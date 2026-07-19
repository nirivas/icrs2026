# ICRS 2026 Planner

A small web app for the **15th International Coral Reef Symposium** (NZICC, Auckland, 19–24 July 2026). Thank you LLMs!

It lists every talk by **day, session, and room**, and lets you star the ones you want into your own
schedule. It's a plain static site — no server, no build step, no accounts.

- **1,480 talks** across **223 sessions** in **14 parallel rooms**, plus 10 plenaries and 561 posters
- **Click any talk** for its **full abstract**, room number, session, presenter, and co-authors
- Search by title, author, affiliation, or topic; filter by day, room, and theme
- **Personal notes** with **Revisit** and **Contact** tags on any talk
- **Clash warnings** when two of your picks overlap (easy to miss with 14 rooms running at once)
- **Works offline** — install it to your phone's home screen and it keeps working with no wifi
- **Share link** to move starred talks from laptop to phone
- **Notes (.md)** export and **Backup / Restore** for picks and notes

## Picks, notes, and your data

Everything is stored in your browser's `localStorage` on **this device and this site address only**.

- **Share links** copy starred talks to another device. **Notes are not included.**
- **Notes disappear** if you clear browser/site data or use private browsing.
- Use **My schedule → Backup** to save picks and notes, then **Restore** on the same URL (e.g. the GitHub Pages address) on another device.

## Moving your schedule between devices

**My schedule → Copy share link**. Open that link on the other device and accept the prompt. The link
carries your picks in the URL itself (no server involved), so it also works for sending your plan to a
colleague. For notes, use **Notes (.md)** or **Backup** instead.

## Notes

- All times are **venue local** (Auckland, NZST = UTC+12 in July).
- The programme is **subject to change** — the footer shows the capture date. Re-run the build to refresh.


## Where the data comes from

The programme is pulled from the official ICRS 2026 programme site, which is powered by EventsAir:

```
POST https://websitegatewayae.eventsair.com/api/GetAgendaData?tenant=innovators&projectid=23820057
```

Two things about this API are easy to miss, and `tools/build_programme.py` handles both:

## Repository layout

```
index.html               app shell
assets/app.js            all the logic (picks, notes, clashes, share, profiles, talk detail)
assets/styles.css        styling, light + dark
data/programme.json      sessions + talks (~1 MB) - loaded first
data/abstracts.json      1,480 abstracts (~3.9 MB) - loaded lazily in the background
sw.js                    offline cache
tools/build_programme.py API -> data/*.json
tools/verify_programme.py structural checks + PDF cross-check + abstract checks
tools/make_icons.py      PWA icons
```
