# Staging preview

The `staging` branch is a combined preview of **Nico's site** plus **Orlando's
features** (Up next, By time, greyed-out past sessions, cloud sync, notes, mobile
fixes). Use it to test before opening a PR to Nico's repo.

## Live URL

Deploy this branch to a **separate** GitHub Pages project so it does not touch
the production sites:

| Site | Branch | URL |
|------|--------|-----|
| Orlando (production) | `feature/talk-notes` | https://orlando-code.github.io/icrs2026/ |
| Nico (production) | `nico-rivas` | https://nirivas.github.io/icrs2026/ |
| **Staging preview** | `staging` | https://orlando-code.github.io/icrs2026-staging/ |

## One-time setup

1. On GitHub, create a new repo under `orlando-code` named **`icrs2026-staging`**
   (empty, no README).
2. From this machine, add it as a remote and push the staging branch:

```bash
git remote add staging git@github.com:orlando-code/icrs2026-staging.git
git push -u staging staging:main
```

3. In the **icrs2026-staging** repo on GitHub: **Settings → Pages → Deploy from
   branch → `main` / root**.

After a minute, open https://orlando-code.github.io/icrs2026-staging/

## What the staging build enables

- **Up next** tab and **By session / By time** layout (also on Nico's hostname)
- **Greyed-out** sessions and talks after their end time (Auckland)
- **Cloud sync** panel (Orlando staging + production URLs only)
- **Staging banner** at the top when served from `/icrs2026-staging/`
- Nico's **CV** link and **incognito notice**

## Updating the preview

```bash
git checkout staging
# …make changes or merge from feature/talk-notes / nico-rivas…
git push staging staging:main
```

Bump `CACHE` in `sw.js` when you need installed PWA users to pick up CSS/JS changes.
