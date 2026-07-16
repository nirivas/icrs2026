"""Verify data/programme.json.

Two layers:
 1. Structural assertions (counts, joins, time sanity, no empty fields).
 2. Cross-check against the independent artifact: the ICRS 2026 Full Talk Grid PDF.
    The PDF was produced separately from the API, so agreement between them is
    real evidence the dataset is right rather than merely self-consistent.

Usage: python tools/verify_programme.py
Exits non-zero if any check fails.
"""

import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROG = os.path.join(ROOT, "data", "programme.json")
ABS = os.path.join(ROOT, "data", "abstracts.json")
PDF = os.path.join(HERE, "ICRS 2026 Full Talk Grid.pdf")

fails = []
warns = []


def check(cond, msg):
    if cond:
        print("  ok   %s" % msg)
    else:
        print("  FAIL %s" % msg)
        fails.append(msg)


def mins(t):
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def main():
    with open(PROG, encoding="utf-8") as f:
        d = json.load(f)

    sessions = d["sessions"]
    coded = [s for s in sessions if s["kind"] == "session"]
    talks = [t for s in coded for t in s["talks"]]
    rooms = {r["id"] for r in d["rooms"]}

    print("\n== structure ==")
    check(len(coded) == 223, "223 coded sessions (got %d)" % len(coded))
    check(len(talks) == 1480, "1480 talks in sessions (got %d)" % len(talks))
    check(len(d["rooms"]) == 14, "14 rooms (got %d)" % len(d["rooms"]))
    check(len(d["days"]) == 6, "6 days (got %d)" % len(d["days"]))

    print("\n== joins / completeness ==")
    no_room = [s["code"] for s in coded if not s["room"]]
    check(not no_room, "every coded session has a room (%d missing)" % len(no_room))
    bad_room = [s["room"] for s in coded if s["room"] not in rooms]
    check(not bad_room, "every session room is a known room (%d bad)" % len(bad_room))
    check(all(s["level"] for s in coded), "every coded session has a level")
    no_title = [t for t in talks if not t["title"].strip()]
    check(not no_title, "every talk has a title (%d empty)" % len(no_title))
    no_pres = [t for t in talks if not t["presenter"].strip()]
    check(not no_pres, "every talk has a presenter (%d empty)" % len(no_pres))
    ids = [t["id"] for t in talks]
    check(len(ids) == len(set(ids)), "talk ids unique (%d dupes)" % (len(ids) - len(set(ids))))
    # short ids back the share-link format, so a collision would silently hand
    # someone else's talk to a user restoring a shared schedule.
    allt = [t for s in sessions for t in s["talks"]]
    sids = [t["sid"] for t in allt]
    check(len(sids) == len(set(sids)),
          "short ids unique across all %d presentations (%d dupes)" % (len(allt), len(sids) - len(set(sids))))
    check(all(len(s) == 8 for s in sids), "every short id is 8 chars")
    skeys = [(s["code"], s["theme"]) for s in coded]
    check(len(skeys) == len(set(skeys)), "session code+theme unique (%d dupes)" % (len(skeys) - len(set(skeys))))

    print("\n== times ==")
    bad_range = [t["title"][:40] for t in talks if not t["start"] or not t["end"] or mins(t["end"]) <= mins(t["start"])]
    check(not bad_range, "every talk has end > start (%d bad)" % len(bad_range))
    # Talks must start within their session. A published talk may overrun the
    # session end slightly (the upstream programme has one 5-min speed talk at
    # 4:05pm in a session ending 4:00pm) -- allow that, but report it.
    outside, overrun = [], []
    for s in coded:
        for t in s["talks"]:
            st = mins(t["start"])
            if st < mins(s["start"]) - 1 or st > mins(s["end"]) + 15:
                outside.append("%s#%s %s @%s (session %s-%s)" % (
                    s["code"], s["theme"], t["title"][:28], t["start"], s["start"], s["end"]))
            elif st > mins(s["end"]) - 1:
                overrun.append("%s#%s %s @%s (session ends %s)" % (
                    s["code"], s["theme"], t["title"][:28], t["start"], s["end"]))
    check(not outside, "every talk starts inside its session window (%d outside)" % len(outside))
    for o in outside[:5]:
        print("       -", o)
    for o in overrun:
        print("  note  overruns session end (as published): %s" % o)
        warns.append(o)

    print("\n== abstracts ==")
    with open(ABS, encoding="utf-8") as f:
        abstracts = json.load(f)
    allt = [t for s in sessions for t in s["talks"]]
    by_sid = {t["sid"]: t for t in allt}
    no_abs = [t["title"][:44] for t in talks if not t.get("hasAbstract")]
    check(not no_abs, "all 1480 talks have an abstract (%d without)" % len(no_abs))
    for n in no_abs[:5]:
        print("       -", n)
    # a flag with no text behind it would render an empty panel in the app
    flagged = [t["sid"] for t in allt if t.get("hasAbstract")]
    orphan_flags = [s for s in flagged if not abstracts.get(s, "").strip()]
    check(not orphan_flags, "every hasAbstract talk has text in abstracts.json (%d empty)" % len(orphan_flags))
    orphan_keys = [k for k in abstracts if k not in by_sid]
    check(not orphan_keys, "no abstract key is orphaned (%d unmatched)" % len(orphan_keys))
    check(len(abstracts) == len(flagged),
          "abstracts.json count matches flagged talks (%d vs %d)" % (len(abstracts), len(flagged)))
    # Authors type <i>…</i> around species names (Endozoicomonas, Porites astreoides).
    # The app escapes everything and then re-enables only italics, so anything
    # OTHER than <i>/<em> would render as literal tags and must be caught here.
    tags = collections.Counter()
    for v in abstracts.values():
        for m in re.finditer(r"</?\s*([A-Za-z][A-Za-z0-9]{0,12})\s*/?>", v):
            tags[m.group(1).lower()] += 1
    unexpected = {t: c for t, c in tags.items() if t not in ("i", "em")}
    check(not unexpected, "only italic markup appears in abstracts (unexpected: %s)" % (unexpected or "none"))
    risky = [k for k, v in abstracts.items()
             if re.search(r"<\s*(script|iframe|img|style|svg|object|embed|a)\b|\son\w+\s*=\s*[\"']", v, re.I)]
    check(not risky, "no abstract carries scriptable markup (%d risky)" % len(risky))
    italic = sum(1 for v in abstracts.values() if re.search(r"<\s*i\s*>", v, re.I))
    print("  note  %d abstracts use <i> italics (species names) -> rendered as emphasis" % italic)
    empties = [k for k, v in abstracts.items() if len(v.strip()) < 50]
    check(not empties, "no suspiciously short abstract (%d under 50 chars)" % len(empties))
    # abstract text must not have leaked into the file the app loads on first paint
    prog_size = os.path.getsize(PROG) / 1048576.0
    check(prog_size < 1.5, "programme.json stays small for first paint (%.2f MB)" % prog_size)

    print("\n== room double-booking ==")
    clash = []
    byroom = {}
    for s in coded:
        byroom.setdefault((s["date"], s["room"]), []).append(s)
    for (date, room), ss in byroom.items():
        ss.sort(key=lambda x: mins(x["start"]))
        for a, b in zip(ss, ss[1:]):
            if mins(b["start"]) < mins(a["end"]):
                clash.append("%s %s: %s overlaps %s" % (date, room, a["code"], b["code"]))
    check(not clash, "no two sessions share a room at the same time (%d clashes)" % len(clash))
    for c in clash[:5]:
        print("       -", c)

    # ---- independent cross-check against the PDF ----
    print("\n== cross-check vs PDF (independent source) ==")
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  skip  pypdf not installed")
        return report()
    if not os.path.exists(PDF):
        print("  skip  PDF not found at %s" % PDF)
        return report()

    reader = PdfReader(PDF)
    pdf_text = "\n".join(p.extract_text() for p in reader.pages[1:6])
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
    flat = norm(pdf_text)

    # every session code+theme in the PDF should exist in our data
    pdf_sessions = set(re.findall(r"^([1-5][A-F])\s+#(\d+)", pdf_text, re.M))
    ours = {(s["code"], str(s["theme"])) for s in coded}
    missing = pdf_sessions - ours
    extra = ours - pdf_sessions
    check(len(pdf_sessions) == 223, "PDF lists 223 sessions (got %d)" % len(pdf_sessions))
    check(not missing, "every PDF session exists in our data (%d missing)" % len(missing))
    check(not extra, "no session in our data is absent from PDF (%d extra)" % len(extra))
    for x in list(missing)[:5]:
        print("       - missing:", x)

    # sample talk titles must appear in the PDF text
    import random
    random.seed(7)
    sample = random.sample(talks, 120)
    miss = []
    for t in sample:
        key = norm(t["title"])[:45]
        if key and key not in flat:
            miss.append(t["title"][:55])
    hit = len(sample) - len(miss)
    check(len(miss) <= 6, "%d/%d sampled talk titles found verbatim in PDF" % (hit, len(sample)))
    for m in miss[:8]:
        print("       - not found:", m)

    # presenter surnames should appear too
    pmiss = [t["presenter"] for t in sample
             if t["presenter"] and norm(t["presenter"].split()[-1]) not in flat]
    check(len(pmiss) <= 6, "%d/%d sampled presenters found in PDF" % (len(sample) - len(pmiss), len(sample)))
    for m in pmiss[:8]:
        print("       - presenter not found:", m)

    return report()


def report():
    print("\n" + "=" * 46)
    if fails:
        print("FAILED: %d check(s)" % len(fails))
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
