"""Check the live programme against the data the app is currently serving.

Read-only. Fetches the feed, runs it through build_programme.build() and reports
what moved. Nothing under data/ is touched -- applying changes is a separate,
deliberate `python tools/build_programme.py --fetch`.

Three things make this different from eyeballing a JSON diff:

  * It compares BUILT data, not the raw feed. The raw feed still contains the
    AM/PM typos the build repairs and stray double spaces in titles, so a raw
    diff reports changes that a rebuild would never actually produce.
  * It splits changes into "still to come" and "already past". Mid-conference,
    a talk that moved on a day that has finished is noise; a talk that moved
    to this afternoon is the entire reason to run this. A change is "still to
    come" if EITHER its old or its new date is today or later -- a talk pulled
    off Friday onto a finished day is still live in the app until applied.
  * It diffs talks AND events (breaks, banquet, ceremonies), and then compares
    the whole rebuilt payload as a backstop. Reporting "no changes" is a claim
    about the entire file, so it is only made when the entire file agrees.

It cannot tell whether the working tree was ever uploaded. Matching the live
feed means the DISK is current, never that attendees are seeing it -- deploying
is a manual drag-and-drop into GitHub that only a human can do.

It also gates on the one thing that could hurt saved schedules: duplicate short
ids. Picks and notes are keyed by `sid`, so a collision would silently point
someone's saved talk at a different one. That exits 3 -- do not apply.

Exit codes:
    0  no changes, and the current build is recorded as uploaded
    1  changes found -- rebuild and re-upload
    2  fetch or build failed
    3  UNSAFE -- the rebuild would collide short ids; do not apply
    4  no changes, but the build on disk has never been confirmed as uploaded

Usage:
    python tools/check_programme.py                  # fetch fresh and compare
    python tools/check_programme.py --cached         # reuse last fetch (offline/testing)
    python tools/check_programme.py --mark-deployed  # record the tree as uploaded
"""

import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_programme as bp  # noqa: E402

PROG = os.path.join(ROOT, "data", "programme.json")
# a separate cache file: a truncated or failed check-fetch must never clobber
# the good agenda_full.json that a plain (non---fetch) rebuild depends on
RAW = os.path.join(bp.cache_dir(), "agenda_check.json")
# deliberately alongside it, OUTSIDE the repo: this folder gets dragged into
# the GitHub uploader wholesale, and a local bookkeeping file has no business
# being served to attendees
DEPLOYED = os.path.join(bp.cache_dir(), "deployed.json")

# talk fields whose change a person would actually want to hear about, in the
# order they matter when you are standing in a corridor deciding where to walk
WATCHED = [
    ("date", "day"),
    ("start", "time"),
    ("end", "end"),
    ("room", "room"),
    ("code", "session"),
    ("title", "title"),
    ("presenter", "presenter"),
]

# Breaks, the welcome function, the banquet, the ceremonies. No talks hang off
# them so they never appear in the talk diff, but the app renders them per day
# and attendees plan their evenings around them.
EVENT_WATCHED = [
    ("date", "day"),
    ("start", "time"),
    ("end", "end"),
    ("title", "title"),
    ("location", "location"),
]


def flatten(prog):
    """{talk id: talk fields + the session context the app shows beside it}."""
    out = {}
    for s in prog["sessions"]:
        for t in s["talks"]:
            out[t["id"]] = {
                "sid": t["sid"],
                "title": t["title"],
                "start": t["start"],
                "end": t["end"],
                "presenter": t["presenter"],
                "date": s["date"],
                "room": s["room"],
                "code": s["code"],
                "session": (s["title"] or "")[:60],
            }
    return out


def flatten_events(prog):
    """{event id: the fields the app renders for a break, banquet or ceremony}."""
    out = {}
    for e in prog.get("events", []):
        out[e["id"]] = {
            "title": e["title"],
            "date": e["date"],
            "start": e["start"],
            "end": e["end"],
            "location": e.get("location") or "",
        }
    return out


def canonical(prog):
    """The whole payload as a stable string, minus the field that always moves.

    The field-by-field diff above only covers what an attendee reads. This is
    the backstop: if it disagrees, SOMETHING would change on a rebuild, and the
    script must not print "matches the live programme" just because the fields
    it happens to watch are equal. `capturedAt` is the build date, so it moves
    every day by design and is excluded.
    """
    p = json.loads(json.dumps(prog))
    p.get("meta", {}).pop("capturedAt", None)
    return json.dumps(p, sort_keys=True, ensure_ascii=False)


def sw_cache():
    """The service-worker cache name in the working tree.

    Printed on every run because it is the only local signal of which build is
    sitting here waiting to be uploaded -- see deploy_status().
    """
    try:
        with open(os.path.join(ROOT, "sw.js"), encoding="utf-8") as f:
            m = re.search(r"CACHE\s*=\s*'([^']+)'", f.read())
        return m.group(1) if m else None
    except Exception:
        return None


def deploy_status():
    """Whether the build sitting on this disk has been uploaded.

    Applying a refresh and deploying it are independent: applying rewrites
    data/ locally, deploying is a drag-and-drop into GitHub that only a human
    can do. Once a run applies, the tree matches the feed, so every later run
    finds "no changes" -- and without this, goes quiet about an upload that
    never happened. Reported on EVERY run for that reason.

    Nothing here can see GitHub Pages, so this is a local record, written by
    --mark-deployed once a human confirms the upload.
    """
    cache = sw_cache()
    try:
        with open(DEPLOYED, encoding="utf-8") as f:
            rec = json.load(f)
    except Exception:
        return "UNKNOWN -- no upload recorded yet (tree has %s)" % (cache or "?")
    was = rec.get("cache")
    if was == cache:
        return "up to date -- %s uploaded %s" % (was, rec.get("at", "?"))
    return "PENDING -- tree has %s, last recorded upload was %s" % (cache or "?", was)


def daylabel(prog):
    """'2026-07-22' -> 'Wed 22 Jul', falling back to the bare date."""
    lab = {}
    for d in prog.get("days", []):
        lab[d["date"]] = d.get("short") or d["date"]
    return lambda dt: lab.get(dt, dt or "?")


def where(t):
    room = t["room"] or "-"
    room = "Te Paepae" if room == "te-paepae" else "Room " + room
    return "%s%s" % (room, ", " + t["code"] if t["code"] else "")


def main():
    # unattended runs get piped or logged; a title with an accent in it must not
    # kill the whole check on a Windows console
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    today = datetime.date.today().isoformat()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if "--mark-deployed" in sys.argv:
        rec = {"cache": sw_cache(), "at": stamp}
        os.makedirs(os.path.dirname(DEPLOYED), exist_ok=True)
        with open(DEPLOYED, "w", encoding="utf-8") as f:
            json.dump(rec, f)
        print("recorded %s as uploaded at %s" % (rec["cache"], rec["at"]))
        return 0

    with open(PROG, encoding="utf-8") as f:
        cur = json.load(f)

    try:
        if "--cached" in sys.argv and os.path.exists(RAW):
            with open(RAW, encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = bp.fetch(RAW)
        new, _abstracts, _stats = bp.build(raw)
    except Exception as e:
        print("FAILED to fetch or build: %s: %s" % (type(e).__name__, e))
        print("The app keeps serving the current data -- nothing was changed.")
        return 2

    a, b = flatten(cur), flatten(new)
    lab = daylabel(new)

    print("== ICRS 2026 programme check -- %s ==" % stamp)
    print("in working tree: %d talks, %d events, captured %s, sw cache %s"
          % (len(a), len(flatten_events(cur)), cur["meta"].get("capturedAt", "?"),
             sw_cache() or "?"))
    print("live feed:       %d talks, %d events" % (len(b), len(flatten_events(new))))
    # "in working tree" is deliberate wording: this script can only compare the
    # feed against the files on this disk. Whether those files were ever
    # uploaded to GitHub Pages is invisible from here, so no run may imply that
    # matching the feed means attendees are seeing it.
    deploy = deploy_status()
    print("deploy:          %s" % deploy)

    # ---- saved-data safety, before anything else is worth reading ----
    sids = [t["sid"] for t in b.values()]
    dupes = len(sids) - len(set(sids))
    if dupes:
        print("\nUNSAFE: %d duplicate short id(s) in the live feed." % dupes)
        print("Applying this would repoint saved picks at the wrong talks. Do not rebuild.")
        return 3
    survive = sum(1 for i in a if i in b)
    print("saved-pick safety: %d/%d current ids survive (%.1f%%), 0 short-id collisions"
          % (survive, len(a), 100.0 * survive / max(len(a), 1)))

    # ---- diff ----
    upcoming, past = [], []

    def file_item(kind, rec, diffs, when):
        # `when` is the LATEST day the change touches, not just the new one. A
        # talk pulled off Friday back onto a day that has finished still needs
        # applying, because the app is what is still advertising it on Friday.
        # Classifying on the new date alone files that under "no action needed".
        (upcoming if (when or "") >= today else past).append((kind, rec, diffs))

    def diff_pair(olds, news, watched, what):
        for key, nt in news.items():
            ot = olds.get(key)
            if ot is None:
                file_item(what + ":added", nt, [], nt["date"])
                continue
            diffs = [(lbl, ot[f], nt[f]) for f, lbl in watched if ot[f] != nt[f]]
            if diffs:
                file_item(what + ":moved", nt, diffs,
                          max(ot["date"] or "", nt["date"] or ""))
        for key, ot in olds.items():
            if key not in news:
                file_item(what + ":withdrawn", ot, [], ot["date"])

    diff_pair(a, b, WATCHED, "talk")
    diff_pair(flatten_events(cur), flatten_events(new), EVENT_WATCHED, "event")

    def sort_key(item):
        kind, t, diffs = item
        return (t["date"] or "", t["start"] or "", t["title"])

    upcoming.sort(key=sort_key)
    past.sort(key=sort_key)

    # The loops above only cover what an attendee reads. Anything else a rebuild
    # would write -- session metadata, abstract flags, a room disappearing --
    # has to surface too, or a run reports "no changes" about data that differs.
    same = canonical(cur) == canonical(new)

    if not upcoming and not past:
        if same:
            print("\nNo changes. The working tree matches the live programme.")
            if not deploy.startswith("up to date"):
                # Exit 4, not 0: there is genuinely nothing to rebuild, but
                # "nothing to do" would be wrong -- a refresh applied earlier
                # may never have been uploaded, and once the tree matches the
                # feed this is the only run that can still say so.
                print("\nBut the upload is not confirmed (see deploy above). Attendees may")
                print("still be served an older build. Re-upload the folder contents, then:")
                print("  python tools/check_programme.py --mark-deployed")
                return 4
            return 0
        print("\nNo talk or event changes, but the rebuilt data still differs from")
        print("data/programme.json -- session metadata, abstract flags or similar.")
        print("Apply it so the two stay in step:")
        print("  python tools/build_programme.py --fetch")
        return 1

    def describe(what, t):
        if what == "event":
            return t.get("location") or "the programme"
        return "%s, %s" % (where(t), t["presenter"] or "presenter TBC")

    def show(items, heading):
        if not items:
            return
        print("\n%s (%d)" % (heading, len(items)))
        for kind, t, diffs in items:
            what, _, action = kind.partition(":")
            tag = "" if what == "talk" else "   [%s]" % what
            print("  %s %s  %s%s" % (lab(t["date"]), t["start"] or "--:--",
                                     t["title"][:66], tag))
            if action == "added":
                print("      ADDED -- %s" % describe(what, t))
            elif action == "withdrawn":
                print("      WITHDRAWN from %s" % describe(what, t))
            else:
                for lbl, old, newv in diffs:
                    print("      %-9s %s -> %s" % (lbl + ":", old or "-", newv or "-"))

    show(upcoming, "CHANGES STILL TO COME")
    show(past, "changes on days already finished -- no action needed")

    if upcoming or not same:
        print("\nTo apply: python tools/build_programme.py --fetch")
        print("          python tools/verify_programme.py")
        print("          bump CACHE in sw.js, then re-upload to GitHub")
    return 1


if __name__ == "__main__":
    sys.exit(main())
