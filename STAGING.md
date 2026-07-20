# Staging preview

**https://orlando-code.github.io/icrs2026-staging/**

Built from **Nico's live site** (`nirivas/icrs2026`) plus Orlando's test features
(hide finished talks, Auckland today default, schedule scroll, etc.). Staging banner
only — no purple theme, no cloud sync.

## Push updates

```bash
git push staging feature/talk-notes:main
```

## Data safety

Deploys **never wipe** picks or notes:

- Storage keys are unchanged (`icrs2026.profiles`, `icrs2026.picks.*`, `icrs2026.notes.*`)
- Service worker cache bumps only refresh static files, not `localStorage`
- Cloud sync is **not loaded** on staging or Nico's live site
- `saveNotes()` merges into existing storage instead of replacing the whole object

Users on staging (separate origin from `nirivas.github.io`) have their own browser storage.

## Sites

| Site | URL |
|------|-----|
| Nico (production) | https://nirivas.github.io/icrs2026/ |
| Orlando (personal) | https://orlando-code.github.io/icrs2026/ |
| Staging preview | https://orlando-code.github.io/icrs2026-staging/ |
