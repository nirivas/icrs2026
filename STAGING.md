# Staging preview

**https://orlando-code.github.io/icrs2026-staging/**

Combined preview of Nico's site plus Orlando's features (Up next, By time,
hide finished talks, cloud sync, notes, mobile fixes).

## Push updates

```bash
git push staging feature/talk-notes:main
```

Wait ~1 minute for GitHub Pages to rebuild.

## One-time GitHub Pages setup

If the URL returns 404, enable Pages in **icrs2026-staging → Settings → Pages**
(deploy from branch `main` / root), or:

```bash
gh api --method POST repos/orlando-code/icrs2026-staging/pages \
  -f build_type=legacy \
  -f 'source[branch]=main' \
  -f 'source[path]=/'
```

Note: quote the `source[...]` fields in zsh.

## Sites

| Site | URL |
|------|-----|
| Orlando (production) | https://orlando-code.github.io/icrs2026/ |
| Nico (production) | https://nirivas.github.io/icrs2026/ |
| Staging preview | https://orlando-code.github.io/icrs2026-staging/ |

Bump `CACHE` in `sw.js` when you need installed PWA users to pick up CSS/JS changes.
