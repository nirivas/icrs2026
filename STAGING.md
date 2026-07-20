# Staging preview

Deploy the `staging` branch (or `main` on the staging repo) to:

**https://orlando-code.github.io/icrs2026-staging/**

## One-time GitHub Pages setup

If the URL returns 404, Pages is not enabled yet:

```bash
gh api --method POST repos/orlando-code/icrs2026-staging/pages \
  -f build_type=legacy \
  -f source[branch]=main \
  -f source[path]=/
```

Or in GitHub: **icrs2026-staging → Settings → Pages → Deploy from branch `main` / root**.

## Push updates

```bash
git push staging HEAD:main
```

Wait ~1 minute for Pages to rebuild.
