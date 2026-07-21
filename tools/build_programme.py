"""Build data/programme.json and data/abstracts.json for the ICRS 2026 planner.

Source of truth is the EventsAir agenda API used by the official programme site:

    POST https://websitegatewayae.eventsair.com/api/GetAgendaData
         ?tenant=innovators&projectid=23820057
    body: {statusIds: [...], handoutTypes: [...], includePresentingAuthors: true, ...}

Two things about this API are easy to get wrong:

  * A plain GET returns every session with an EMPTY `presentations` list. The
    individual talks only come back from a POST carrying `statusIds` -- the ones
    the official site is configured with (they sit in the programme page HTML).
  * Abstract text is not a field. It arrives as a "View abstract" *handout*, so
    it only appears when `handoutTypes` is passed, as documents[].plainText.

Abstracts are ~3.7 MB in total, so they are written to a separate
data/abstracts.json that the app loads lazily -- keeping first paint small.

Usage:
    python tools/build_programme.py                 # use cached raw JSON if present
    python tools/build_programme.py --fetch         # re-download from the API
    python tools/build_programme.py --cache DIR     # where to keep the raw snapshot
"""

import datetime
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "programme.json")
OUT_ABS = os.path.join(ROOT, "data", "abstracts.json")

# The raw snapshot is ~11 MB of API response. It lives OUTSIDE the project folder
# on purpose: this repo is uploaded through the GitHub website, which has no
# .gitignore to protect it, so anything sitting in the tree would get swept up.
DEFAULT_CACHE = os.path.join(os.path.dirname(ROOT), "_api_cache")

API = ("https://websitegatewayae.eventsair.com/api/GetAgendaData"
       "?tenant=innovators&projectid=23820057")
SITE = "https://innovators-icrs2026programme.eventsairsite.com/"

# Presentation statuses the official programme displays.
STATUS_IDS = [
    "794bf86c-0919-4ea3-aefd-cd62296e17f7",  # Accepted // session
    "c64409a2-62b7-4ea0-9e6d-f99b73ccdd60",  # Accepted // 5 min speed talk
    "ca85bc87-bf92-422a-bd42-7995c73c54cb",  # Accepted // 15 min oral talk
    "476f70f0-e17a-4394-bb09-0e1bdaecd6ef",  # Plenary
    "f92a7288-9c18-4e72-b764-6ca8bbab3d02",  # Panel
    "559b9f1d-02cb-42fd-8c6e-9aae7496fc09",  # Accepted // poster
]

# Handout types (from ListDocumentTypes). "View abstract" carries the abstract
# body as plain text -- this is the only way to get abstracts out of the API.
HANDOUT_TYPES = [
    "8739e7ab-a97a-4b7e-86fc-c2cb2304e32e",  # View abstract
]


def cache_dir():
    if "--cache" in sys.argv:
        return os.path.abspath(sys.argv[sys.argv.index("--cache") + 1])
    return DEFAULT_CACHE

# "1A | Te Paepae Theatre | #25 Temporal changes in ..."
SESSION_RE = re.compile(r"^([1-5][A-F])\s*\|\s*([^|]+?)\s*\|\s*#(\d+)\s+(.+)$", re.S)
# theme string: "5. #25 | Temporal changes in coral reefs..."
THEME_RE = re.compile(r"^(\d+)\.\s*#(\d+)\s*\|\s*(.+)$", re.S)


def fetch(raw_path):
    body = json.dumps({
        "statusIds": STATUS_IDS,
        "handoutTypes": HANDOUT_TYPES,
        "includePresentingAuthors": True,
        "includeNonPresentingAuthors": True,
        "includeKeywords": True,
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "User-Agent": "Mozilla/5.0 Chrome/120",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": SITE.rstrip("/"),
        "Referer": SITE,
    })
    print("fetching agenda + abstracts from the API ...")
    raw = urllib.request.urlopen(req, timeout=240).read()
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, "wb") as f:
        f.write(raw)
    print("cached %.1f MB -> %s" % (len(raw) / 1048576.0, raw_path))
    return json.loads(raw.decode("utf-8"))


def load():
    raw_path = os.path.join(cache_dir(), "agenda_full.json")
    if "--fetch" in sys.argv or not os.path.exists(raw_path):
        return fetch(raw_path)
    with open(raw_path, encoding="utf-8") as f:
        return json.load(f)


def abstract_of(pres):
    """Abstract body, delivered as a 'View abstract' handout rather than a field."""
    for doc in (pres.get("documents") or []):
        txt = (doc.get("plainText") or "").strip()
        if txt:
            return re.sub(r"[ \t]+\n", "\n", txt).strip()
    return ""


def to24(t):
    """'10:15 AM' -> '10:15'; '2 PM' -> '14:00'."""
    if not t:
        return None
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*([AaPp])", t.strip())
    if not m:
        return None
    h = int(m.group(1)) % 12
    if m.group(3).lower() == "p":
        h += 12
    return "%02d:%02d" % (h, int(m.group(2) or 0))


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def room_id(label):
    lab = label.strip()
    if lab.lower().startswith("te paepae"):
        return "te-paepae"
    m = re.search(r"(\d{3})", lab)
    return m.group(1) if m else re.sub(r"[^a-z0-9]+", "-", lab.lower()).strip("-")


def room_label(rid):
    return "Te Paepae Theatre" if rid == "te-paepae" else "Room " + rid


def level_of(location):
    m = re.search(r"Level\s*(\d)", location or "")
    return "L" + m.group(1) if m else None


def repair_ampm(talks, s_start, s_end, log, session_name):
    """Fix AM/PM typos in the upstream programme data.

    The official feed has a few talks stamped e.g. '2:30 AM' inside a 2:30 PM
    session (one of them even pairs a 2:30 AM start with a 2:45 PM end). Only
    shift a time when +12h lands it inside the session window: that makes the
    repair unambiguous rather than a guess. Talks that merely overrun the
    session end are left exactly as published.
    """
    if not s_start or not s_end:
        return
    lo, hi = mins(s_start), mins(s_end)
    for t in talks:
        for key in ("start", "end"):
            v = t.get(key)
            if not v:
                continue
            m = mins(v)
            if lo - 1 <= m <= hi + 15:
                continue
            alt = m + 12 * 60
            if alt < 24 * 60 and lo - 1 <= alt <= hi + 15:
                t[key] = "%02d:%02d" % (alt // 60, alt % 60)
                log.append("%s | %s | %s %s -> %s" % (
                    session_name[:34], t["title"][:34], key, v, t[key]))


def presenter_of(pres):
    """Presenting author (name, honorific, affiliation) for a presentation."""
    speakers = pres.get("speakers") or []
    pa = pres.get("presentationAuthors") or []
    pick = next((s for s in speakers if s.get("isPresentingAuthor")), None) or \
           (speakers[0] if speakers else None)
    if pick:
        honor = (pick.get("title") or "").strip()
        company = (pick.get("company") or "").strip()
        position = (pick.get("position") or "").strip()
        return pick.get("name", "").strip(), honor, company, position
    pick = next((a for a in pa if a.get("isPresentingAuthor")), None) or (pa[0] if pa else None)
    if pick:
        return pick.get("name", "").strip(), (pick.get("title") or "").strip(), "", ""
    return "", "", "", ""


def build(data):
    """Transform the raw API payload into the two output structures. No I/O.

    check_programme.py imports this so its diff sees exactly what a rebuild
    would write -- AM/PM repairs and whitespace collapsing included. Diffing
    the raw feed directly invents changes no rebuild would ever produce: the
    repaired 2:30 AM slots come back, and stray upstream double spaces look
    like retitles.
    """
    days_seen = {}
    rooms = {}
    sessions = []
    events = []
    unresolved = []
    repairs = []
    abstracts = {}

    for item in data:
        name = (item.get("name") or "").strip()
        date = item.get("date")
        start = to24(item.get("startTime"))
        end = to24(item.get("endTime"))
        location = item.get("location") or ""
        atype = item.get("agendaType") or ""
        pres_list = item.get("presentations") or []
        if date:
            days_seen.setdefault(date, True)

        m = SESSION_RE.match(name)
        talks = []
        for p in pres_list:
            nm, honor, company, position = presenter_of(p)
            if not nm:
                unresolved.append(p.get("title", "")[:60])
            tstart = to24(p.get("startTime")) or start
            tend = to24(p.get("endTime")) or end
            tm = THEME_RE.match((p.get("theme") or "").strip())
            sid = (p.get("id") or "").replace("-", "")[:8]
            body = abstract_of(p)
            if body:
                abstracts[sid] = body
            talks.append({
                # 8-hex-char prefix of the GUID: stable across rebuilds and short
                # enough that a shared schedule URL stays manageable. Uniqueness
                # is asserted by verify_programme.py.
                "sid": sid,
                "id": p.get("id"),
                # abstract text lives in data/abstracts.json, keyed by sid
                "hasAbstract": bool(body),
                "title": re.sub(r"\s+", " ", (p.get("title") or "").strip()),
                "start": tstart,
                "end": tend,
                "presenter": nm,
                "honorific": honor,
                "affiliation": company,
                "position": position,
                "authors": [a for a in (p.get("authors") or []) if a],
                "themeCat": int(tm.group(1)) if tm else None,
            })
        repair_ampm(talks, start, end, repairs, name)
        talks.sort(key=lambda t: (mins(t["start"]) if t["start"] else 0))

        if m:
            code, rlabel, theme, title = m.group(1), m.group(2), int(m.group(3)), m.group(4)
            rid = room_id(rlabel)
            lvl = level_of(location)
            rooms[rid] = {"id": rid, "label": room_label(rid), "level": lvl}
            themeCat = next((t["themeCat"] for t in talks if t["themeCat"]), None)
            sessions.append({
                "id": item.get("id"),
                "kind": "session",
                "code": code,
                "theme": theme,
                "themeCat": themeCat,
                "title": re.sub(r"\s+", " ", title.strip()),
                "room": rid,
                "level": lvl,
                "location": location,
                "date": date,
                "start": start,
                "end": end,
                "talks": talks,
            })
        elif talks:
            kind = ("poster" if "poster session" in name.lower()
                    else "plenary" if "plenary" in name.lower()
                    else "special")
            rid = room_id(location.split("|")[0]) if location else None
            if rid and (rid == "te-paepae" or rid.isdigit()):
                rooms.setdefault(rid, {"id": rid, "label": room_label(rid), "level": level_of(location)})
            else:
                rid = None
            sessions.append({
                "id": item.get("id"),
                "kind": kind,
                "code": None,
                "theme": None,
                "themeCat": None,
                "title": re.sub(r"\s+", " ", name),
                "room": rid,
                "level": level_of(location),
                "location": location,
                "date": date,
                "start": start,
                "end": end,
                "talks": talks,
            })
        else:
            events.append({
                "id": item.get("id"),
                "kind": atype or "information",
                "title": re.sub(r"\s+", " ", name),
                "date": date,
                "start": start,
                "end": end,
                "location": location,
            })

    order = sorted(days_seen)
    days = []
    for i, dt in enumerate(order):
        d = datetime.date.fromisoformat(dt)
        days.append({
            "id": dt,
            "date": dt,
            "label": d.strftime("%A"),
            "short": d.strftime("%a %-d %b") if os.name != "nt" else d.strftime("%a %d %b").replace(" 0", " "),
            "index": i,
        })

    sessions.sort(key=lambda s: (s["date"] or "", mins(s["start"]) if s["start"] else 0, s["room"] or ""))
    events.sort(key=lambda e: (e["date"] or "", mins(e["start"]) if e["start"] else 0))

    room_order = ["te-paepae", "301", "302", "305", "501", "502", "503", "504", "505",
                  "513", "515", "516", "517", "518"]
    room_list = [rooms[r] for r in room_order if r in rooms] + \
                [v for k, v in sorted(rooms.items()) if k not in room_order]

    out = {
        "meta": {
            "name": "ICRS 2026",
            "longName": "15th International Coral Reef Symposium",
            "venue": "NZICC, Auckland, New Zealand",
            "timezone": "Pacific/Auckland",
            # the real build date -- the footer shows this, so a stale literal
            # here would tell people the data is fresher (or older) than it is
            "capturedAt": datetime.date.today().isoformat(),
            "source": SITE,
            "note": "Programme is subject to change.",
        },
        "days": days,
        "rooms": room_list,
        "sessions": sessions,
        "events": events,
    }

    return out, abstracts, {"unresolved": unresolved, "repairs": repairs}


def main():
    out, abstracts, stats = build(load())
    sessions, events = out["sessions"], out["events"]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    with open(OUT_ABS, "w", encoding="utf-8") as f:
        json.dump(abstracts, f, ensure_ascii=False, separators=(",", ":"))

    coded = [s for s in sessions if s["kind"] == "session"]
    talk_count = sum(len(s["talks"]) for s in coded)
    with_abs = sum(1 for s in coded for t in s["talks"] if t["hasAbstract"])
    print("days:              %d" % len(out["days"]))
    print("rooms:             %d" % len(out["rooms"]))
    print("coded sessions:    %d  (expect 223)" % len(coded))
    # the talk count drifts as presenters withdraw mid-conference, so there is
    # no stable "expect" to print -- verify_programme.py asserts a band instead
    print("talks in sessions: %d" % talk_count)
    print("posters:           %d" % sum(len(s["talks"]) for s in sessions if s["kind"] == "poster"))
    print("plenaries:         %d" % sum(1 for s in sessions if s["kind"] == "plenary"))
    print("special sessions:  %d" % sum(1 for s in sessions if s["kind"] == "special"))
    print("other events:      %d" % len(events))
    print("presenter unresolved: %d" % len(stats["unresolved"]))
    for u in stats["unresolved"][:10]:
        print("   !", u)
    print("AM/PM typos repaired in source data: %d" % len(stats["repairs"]))
    for r in stats["repairs"]:
        print("   ~", r)
    print("talks with an abstract: %d / %d" % (with_abs, talk_count))
    print("abstracts total (incl. posters/plenaries): %d" % len(abstracts))
    print("wrote %s (%.1f KB)" % (OUT, os.path.getsize(OUT) / 1024.0))
    print("wrote %s (%.1f KB)" % (OUT_ABS, os.path.getsize(OUT_ABS) / 1024.0))


if __name__ == "__main__":
    main()
