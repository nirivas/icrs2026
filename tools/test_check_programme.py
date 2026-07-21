"""Regression tests for check_programme.py.

There is no test framework in this repo; this is a plain script. It exists
because all three cases below were REAL bugs found in review, and each one
failed silently -- the checker printed "No changes. The app's data matches the
live programme." and exited 0 while a rebuild would have written something
different. A silent false negative in this tool means an unattended run tells
the user there is nothing to do while attendees read a stale programme.

It works by feeding check_programme a synthetic "live feed": build/fetch are
monkeypatched to return a mutated copy of the committed data, so no network is
touched and nothing under data/ is written.

Usage: python tools/test_check_programme.py
Exits non-zero if any case fails.
"""

import contextlib
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_programme as bp  # noqa: E402
import check_programme as cp  # noqa: E402

with open(os.path.join(ROOT, "data", "programme.json"), encoding="utf-8") as f:
    BASE = json.load(f)


def run(mutate):
    """Run cp.main() against a mutated feed; return (exit code, stdout)."""
    new = copy.deepcopy(BASE)
    mutate(new)
    bp.fetch = lambda path: {}
    bp.build = lambda raw: (new, {}, {})
    buf = io.StringIO()
    sys.argv = ["check_programme.py", "--cached"]
    with contextlib.redirect_stdout(buf):
        try:
            code = cp.main()
        except SystemExit as e:
            code = e.code
    return code, buf.getvalue()


def ev(d, needle):
    return next(e for e in d["events"] if needle in e["title"])


def has_event(needle):
    return any(needle in e["title"] for e in BASE["events"])


def upcoming_session(d, date):
    return next(s for s in d["sessions"]
                if s["date"] == date and s["kind"] == "session" and s["talks"])


# (name, mutation, expected exit, text that must appear, required event)
CASES = [
    # Events carry no talks, so a talk-only diff never sees them -- yet people
    # plan their evenings around the banquet and the closing ceremony.
    ("event: banquet retimed",
     lambda d: ev(d, "Banquet").__setitem__("start", "18:30"), 1, "STILL TO COME", "Banquet"),
    ("event: banquet removed",
     lambda d: d["events"].remove(ev(d, "Banquet")), 1, "STILL TO COME", "Banquet"),
    ("event: closing ceremony retimed",
     lambda d: ev(d, "closing ceremony").__setitem__("start", "13:30"), 1, "STILL TO COME",
     "closing ceremony"),
    ("event on a finished day is not urgent",
     lambda d: ev(d, "Morning Tea").__setitem__("start", "09:50"), 1, "no action needed",
     "Morning Tea"),

    # Fields flatten() copies or that only exist session-side: caught by the
    # whole-payload backstop rather than the field-by-field diff.
    ("backstop: talk end time",
     lambda d: d["sessions"][0]["talks"][0].__setitem__("end", "23:59"), 1, None, None),
    ("backstop: session title",
     lambda d: d["sessions"][0].__setitem__("title", "ZZZ"), 1, None, None),
    ("backstop: hasAbstract flag",
     lambda d: d["sessions"][0]["talks"][0].__setitem__("hasAbstract", False), 1, None, None),

    ("control: a watched field still trips the normal diff",
     lambda d: d["sessions"][0].__setitem__("room", "999"), 1, None, None),
]


def redate_last_day_onto_a_finished_one(d):
    """A talk pulled OFF the last day onto a day that is over.

    Classifying on the new date alone buries this under "no action needed",
    which is backwards: the app is still advertising it on the last day, so it
    is exactly the case that needs applying.
    """
    last = max(s["date"] for s in d["sessions"] if s["date"])
    first = min(s["date"] for s in d["sessions"] if s["date"])
    upcoming_session(d, last)["date"] = first


def main():
    today = __import__("datetime").date.today().isoformat()
    cases = list(CASES)
    # Only meaningful while the conference still has a day left to move things
    # off; after it ends every date is in the past and the case is vacuous.
    if max(s["date"] for s in BASE["sessions"] if s["date"]) >= today:
        cases.append(("re-dated off the last day onto a finished one",
                      redate_last_day_onto_a_finished_one, 1, "STILL TO COME", None))

    fails = skips = 0
    for name, mutate, want, want_text, needs in cases:
        if needs and not has_event(needs):
            print("  skip %-52s (no %r in data)" % (name, needs))
            skips += 1
            continue
        code, out = run(mutate)
        ok = code == want
        why = "exit %s, wanted %s" % (code, want)
        if ok and want_text:
            ok = want_text in out
            why = "%r missing from output" % want_text
        if ok and name.startswith("re-dated"):
            # the apply instructions only print for upcoming changes
            ok = "To apply:" in out
            why = "apply hint was suppressed"
        print("  %s %-52s %s" % ("ok  " if ok else "FAIL", name, "" if ok else why))
        if not ok:
            fails += 1
            for ln in out.strip().splitlines()[:12]:
                print("        " + ln)

    print("\n" + "=" * 46)
    if fails:
        print("FAILED: %d of %d case(s)" % (fails, len(cases) - skips))
        return 1
    print("ALL %d CASES PASSED%s" % (len(cases) - skips, " (%d skipped)" % skips if skips else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
