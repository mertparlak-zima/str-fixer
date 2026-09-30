#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resync_srt.py — re-time a mis-synced (Turkish) .srt against a reference .srt.

Use case: a TR subtitle taken from a different cut (extended / director's cut /
other release) drifts out of sync with the video being watched. An EN (or any
language) subtitle with CORRECT timings for the target video is supplied as the
reference; this tool aligns the TR cues to the reference timeline, drops cues
that belong to scenes absent from the target cut, and writes BOM-less UTF-8.

Method (full reasoning: .claude/skills/srt-resync/references/algorithm.md):
    1. encoding detection for both inputs (cp1254/iso8859-9 TR support)
    2. anchor chain walk: offset-continuity window matching + shared-token
       (name/number) acceptance, re-lock on 2+ shared tokens after gaps
    3. bidirectional segment extension, ov-weighted conflict resolution (+-4),
       weighted-LIS monotone reconstruction, outlier pruning
    4. gap classification: same-timeline extras kept; in-insertion cues and
       cut-ending tails (no reference activity nearby) dropped
    5. optional manual calibration (--cal): text-verified offsets override the
       automatic ladder where dense-dialogue time-coincidences mislead it
    6. renumber, clamp overlaps, write UTF-8 (no BOM), CRLF preserved

Usage:
    python scripts/resync_srt.py REF.srt TR.srt [-o OUT.srt]
           [--cal 656:671:743.2 --cal 672:753:818.4] [--drop 751,752,753]
           [--audit]

    --cal A:B:OFF   force TR cue indexes [A..B] (0-based) to offset OFF seconds
    --drop I,J,...  drop specific TR cue indexes entirely
    --audit         after writing, print a 10-min sweep of output cues next to
                    their nearest reference cues (semantic check by eye)

Verified on: Terminator 2 director's-cut TR -> theatrical 4K EN (2026-09-30).

Exit codes: 0 ok, 1 usage/file error, 2 alignment too sparse (<5 anchors).
"""
import argparse
import bisect
import re
import sys
from collections import defaultdict
from statistics import median

TR_SIG_BYTES = (0xD0, 0xDD, 0xDE, 0xF0, 0xFD, 0xFE)
TOK = re.compile(r"[a-z0-9]{3,}|\d+")
TS_LINE = re.compile(r"(\d{2}:\d{2}:\d{2})[,.](\d{3}) --> (\d{2}:\d{2}:\d{2})[,.](\d{3})")


def detect_and_decode(data):
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16"
    try:
        return data.decode("utf-8"), "UTF-8"
    except UnicodeDecodeError:
        pass
    sig = sum(data.count(bytes([b])) for b in TR_SIG_BYTES)
    if sig:
        try:
            return data.decode("cp1254"), "cp1254"
        except UnicodeDecodeError:
            return data.decode("iso8859_9", errors="replace"), "iso8859-9 (replace)"
    return data.decode("cp1252"), "cp1252 (low confidence)"


def parse(path):
    text, codec = detect_and_decode(open(path, "rb").read())
    cues = []
    for b in re.split(r"\r?\n\r?\n", text.strip()):
        if not b.strip():
            continue
        lines = b.splitlines()
        m = TS_LINE.match(lines[1].strip()) if len(lines) > 1 else None
        if not m:
            continue
        t1, ms1, t2, ms2 = m.groups()

        def ts(t, ms):
            h, mi, s = t.split(":")
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000

        body = lines[2:]
        cues.append({
            "start": ts(t1, ms1), "end": ts(t2, ms2),
            "text": " ".join(x.strip() for x in body), "lines": body,
        })
    for c in cues:
        s = c["text"].lower().replace("ı", "i").replace("İ", "i").replace("â", "a")
        c["tok"] = set(TOK.findall(s))
        c["dur"] = c["end"] - c["start"]
    return cues, codec


def anchor_chain(TR, EN, en_range):
    anchors, off_hist = [], []
    i = j = 0
    miss = 0
    while i < len(TR) and j < len(EN):
        off = median(off_hist[-7:]) if off_hist else 0.0
        a = TR[i]
        best = None
        for jj in en_range(a["start"] - off - 1.6, a["start"] - off + 1.6):
            if jj < j:
                continue
            dt = a["start"] - EN[jj]["start"] - off
            if abs(dt) > 1.0:
                continue
            ov = len(a["tok"] & EN[jj]["tok"])
            sc = ov * 3 + (1.0 - abs(dt))
            if best is None or sc > best[0]:
                best = (sc, jj, ov, dt)
        if best is not None and (best[2] >= 1 or abs(best[3]) <= 0.55):
            anchors.append((i, best[1]))
            off_hist.append(a["start"] - EN[best[1]]["start"])
            j = best[1] + 1
            miss = 0
            i += 1
            continue
        miss += 1
        if miss >= 5:
            # ov>=2 yeniden kilitleme (dt ileri dogru sinirsiz)
            found = None
            for k in range(i, min(i + 80, len(TR))):
                for jj in range(max(0, j - 4), min(j + 150, len(EN))):
                    b = EN[jj]
                    if b["start"] > TR[k]["start"] - off + 30:
                        break
                    if len(TR[k]["tok"] & b["tok"]) >= 2 and abs(TR[k]["dur"] - b["dur"]) <= 1.4:
                        found = (k, jj)
                        break
                if found:
                    break
            if found is None:
                i += 1
                continue
            k, jj = found
            anchors.append((k, jj))
            off_hist = [TR[k]["start"] - EN[jj]["start"]]
            j = jj + 1
            i = k + 1
            miss = 0
        else:
            i += 1
    return anchors


def split_segments(anchors, offs):
    segs, cur = [], [0]
    for k in range(1, len(anchors)):
        if anchors[k][0] <= anchors[k - 1][0]:
            segs.append(cur)
            cur = []
            continue
        if abs(offs[k] - offs[k - 1]) > 1.2 and abs(offs[k] - median(offs[max(0, k - 6):k])) > 1.2:
            segs.append(cur)
            cur = []
        cur.append(k)
    segs.append(cur)
    return [s for s in segs if len(s) >= 2]


def extend_seg(TR, EN, en_range, pairs, off):
    pairs = sorted(pairs)
    for _ in range(2):
        for direction in (1, -1):
            grew = True
            while grew:
                grew = False
                i, j = pairs[-1] if direction == 1 else pairs[0]
                rng = range(i + 1, min(i + 30, len(TR))) if direction == 1 else range(i - 1, max(i - 30, -1), -1)
                for ii in rng:
                    hit = None
                    for jj in en_range(TR[ii]["start"] - off - 1.0, TR[ii]["start"] - off + 1.0):
                        if (direction == 1 and jj <= j) or (direction == -1 and jj >= j):
                            continue
                        dt = TR[ii]["start"] - EN[jj]["start"] - off
                        if abs(dt) > 1.0:
                            continue
                        if len(TR[ii]["tok"] & EN[jj]["tok"]) >= 1 or abs(dt) <= 0.55:
                            hit = (ii, jj)
                            break
                    if hit:
                        if direction == 1:
                            pairs.append(hit)
                        else:
                            pairs.insert(0, hit)
                        i, j = hit
                        grew = True
                    elif (direction == 1 and ii > i + 6) or (direction == -1 and ii < i - 6):
                        break
        pairs = sorted(set(pairs))
        off = median([TR[i2]["start"] - EN[j2]["start"] for i2, j2 in pairs])
    return pairs, off


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="Re-time a desynced .srt against a reference .srt with correct timings.")
    ap.add_argument("reference", help="reference .srt (correct timings, e.g. EN of the target cut)")
    ap.add_argument("desynced", help=".srt to re-time (may be from a different cut / encoding)")
    ap.add_argument("-o", "--output", help="output path (default: output/<desynced name>.srt)")
    ap.add_argument("--cal", action="append", default=[], metavar="A:B:OFFSET",
                    help="force TR cue range [A..B] to OFFSET seconds (text-verified calibration)")
    ap.add_argument("--drop", default="", metavar="I,J,...", help="drop these TR cue indexes")
    ap.add_argument("--audit", action="store_true", help="print 10-min sweep of output vs reference after writing")
    args = ap.parse_args()

    EN, enc_ref = parse(args.reference)
    TR, enc_tr = parse(args.desynced)
    print(f"[kaynak] referans: {len(EN)} cue ({enc_ref}) | desynced: {len(TR)} cue ({enc_tr})")
    if len(EN) < 5 or len(TR) < 5:
        print("[hata] cue sayisi cok az")
        return 1

    EN_STARTS = [c["start"] for c in EN]

    def en_range(t0, t1):
        return range(max(0, bisect.bisect_left(EN_STARTS, t0)), min(len(EN), bisect.bisect_right(EN_STARTS, t1)))

    anchors = anchor_chain(TR, EN, en_range)
    offs = [TR[i]["start"] - EN[jj]["start"] for i, jj in anchors]
    print(f"[walk] {len(anchors)} anchor")

    segs = split_segments(anchors, offs)
    ext = []
    for seg in segs:
        pairs = [(anchors[k][0], anchors[k][1]) for k in seg]
        off = median([offs[k] for k in seg])
        pairs, off = extend_seg(TR, EN, en_range, pairs, off)
        ext.append((pairs, off))

    i_claims, j_claims = defaultdict(list), defaultdict(list)
    for s, (pairs, _) in enumerate(ext):
        for i, j in pairs:
            i_claims[i].append(s)
            j_claims[j].append(s)

    def denser(owners, center, key):
        best, bestw = None, -1.0
        for o2 in owners:
            w = 0.0
            for p in ext[o2][0]:
                if abs(p[key] - center) <= 4:
                    w += 1 + 4 * min(len(TR[p[0]]["tok"] & EN[p[1]]["tok"]), 2)
            if w > bestw:
                best, bestw = o2, w
        return best

    final = []
    for s, (pairs, _) in enumerate(ext):
        keep = []
        for i, j in pairs:
            ok = True
            for claims, center, key in ((i_claims, i, 0), (j_claims, j, 1)):
                owners = set(claims[center])
                if len(owners) > 1 and denser(sorted(owners), center, key) != s:
                    ok = False
            if ok:
                keep.append((i, j))
        final.append(keep)
    anchors = sorted(p for pairs in final if len(pairs) >= 2 for p in pairs)
    byi = {}
    for p in anchors:
        w = 1 + 4 * min(len(TR[p[0]]["tok"] & EN[p[1]]["tok"]), 2)
        if p[0] not in byi or w > byi[p[0]][1]:
            byi[p[0]] = (p, w)
    seq = [byi[i] for i in sorted(byi)]
    n = len(seq)
    dpw = [w for _, w in seq]
    par = [-1] * n
    for x in range(n):
        for y in range(x):
            if seq[y][0][1] < seq[x][0][1] and dpw[y] + seq[x][1] > dpw[x]:
                dpw[x] = dpw[y] + seq[x][1]
                par[x] = y
    end = max(range(n), key=lambda x2: dpw[x2]) if n else -1
    chain = []
    while end != -1:
        chain.append(seq[end][0])
        end = par[end]
    anchors = sorted(chain[::-1])
    offs = [TR[i]["start"] - EN[jj]["start"] for i, jj in anchors]
    # aykiri budama: segment medianindan >2.5s sapma tasiyan anchor at
    segs = split_segments(anchors, offs)
    keep_pos = sorted(k for seg in segs
                      if (o := median([offs[k] for k in seg])) is not None
                      for k in seg if abs(offs[k] - o) <= 2.5)
    anchors = [anchors[k] for k in keep_pos]
    offs = [TR[i]["start"] - EN[jj]["start"] for i, jj in anchors]
    seginfo = []
    for s, seg in enumerate(split_segments(anchors, offs)):
        o = median([offs[k] for k in seg])
        seginfo.append((seg, o))
        a0, a1 = anchors[seg[0]], anchors[seg[-1]]
        print(f"[seg{ s:>2}] TR {a0[0]:>4}-{a1[0]:>4} off={o:>7.2f} n={len(seg):>3}")
    print(f"[anchor] {len(anchors)} | TR kapsam {len(set(i for i, _ in anchors))}/{len(TR)}")
    if len(anchors) < 5:
        print("[hata] cok az anchor — referans/desynced eslesmiyor olabilir")
        return 2

    CAL = []
    for spec in args.cal:
        a, b, o2 = spec.split(":")
        CAL.append((int(a), int(b), float(o2)))
    CAL_DROP = {int(x) for x in args.drop.split(",") if x.strip().isdigit()}

    seginfo = [([k for k in seg if not any(a <= anchors[k][0] <= b for a, b, _ in CAL)], o)
               for seg, o in seginfo]
    seginfo = [(seg, o) for seg, o in seginfo if len(seg) >= 2]
    keep_pos = sorted(k for seg, o in seginfo for k in seg)
    pos_map = {old: new for new, old in enumerate(keep_pos)}
    seginfo = [([pos_map[k] for k in seg], o) for seg, o in seginfo]
    anchors = [anchors[k] for k in keep_pos]
    offs = [TR[i]["start"] - EN[jj]["start"] for i, jj in anchors]
    print(f"[kalibrasyon] {len(CAL)} bolge, {len(CAL_DROP)} zorla dusurme, kalan anchor {len(anchors)}")

    seg_of_anchor = {}
    for s, (seg, o) in enumerate(seginfo):
        for k in seg:
            seg_of_anchor[k] = s
    anchor_idx = {i: k for k, (i, j) in enumerate(anchors)}
    prev_anchor_of, pk = {}, None
    for i in range(len(TR)):
        prev_anchor_of[i] = pk
        if i in anchor_idx:
            pk = anchor_idx[i]
    nxt_anchor_of, nk = {}, None
    for i in range(len(TR) - 1, -1, -1):
        nxt_anchor_of[i] = nk
        if i in anchor_idx:
            nk = anchor_idx[i]

    def en_activity_near(t, win=3.5):
        for kk in en_range(t - win, t + win):
            c = EN[kk]
            if c["start"] - win <= t <= c["end"] + win:
                return True
        return False

    kept, dropped = [], []
    for i, c in enumerate(TR):
        if i in CAL_DROP:
            dropped.append(i)
            continue
        cal_off = next((o2 for a, b, o2 in CAL if a <= i <= b), None)
        if cal_off is not None:
            kept.append({"i": i, "start": c["start"] - cal_off, "end": c["end"] - cal_off, "kind": "cal"})
            continue
        if i in anchor_idx:
            s = seg_of_anchor[anchor_idx[i]]
            kept.append({"i": i, "start": c["start"] - seginfo[s][1], "end": c["end"] - seginfo[s][1], "kind": "anchor"})
            continue
        pkn, nkn = prev_anchor_of[i], nxt_anchor_of[i]
        if pkn is None:
            kept.append({"i": i, "start": c["start"] - seginfo[0][1], "end": c["end"] - seginfo[0][1], "kind": "head"})
            continue
        if nkn is None:
            s = seg_of_anchor[pkn]
            kept.append({"i": i, "start": c["start"] - seginfo[s][1], "end": c["end"] - seginfo[s][1], "kind": "tail"})
            continue
        sp, sn = seg_of_anchor[pkn], seg_of_anchor[nkn]
        off_p, off_n = seginfo[sp][1], seginfo[sn][1]
        E1 = EN[anchors[pkn][1]]["start"]
        E2 = EN[anchors[nkn][1]]["start"]
        if abs(off_p - off_n) <= 1.2:
            kept.append({"i": i, "start": c["start"] - off_p, "end": c["end"] - off_p, "kind": "gap-same"})
            continue
        m_p, m_n = c["start"] - off_p, c["start"] - off_n
        if m_p > E2 + 0.1:
            if m_n < E1 - 0.1 or not en_activity_near(m_n):
                dropped.append(i)
            else:
                kept.append({"i": i, "start": c["start"] - off_n, "end": c["end"] - off_n, "kind": "gap-n"})
        else:
            if not en_activity_near(m_p):
                dropped.append(i)
            else:
                kept.append({"i": i, "start": c["start"] - off_p, "end": c["end"] - off_p, "kind": "gap-p"})

    kept.sort(key=lambda r: (r["start"], r["i"]))
    tail_dropped = []
    for r in kept[:]:
        if r["kind"] == "tail" and not en_activity_near(r["start"]):
            tail_dropped.append(r["i"])
            kept.remove(r)

    for k in range(1, len(kept)):
        if kept[k]["start"] < kept[k - 1]["start"] + 0.04:
            kept[k]["start"] = kept[k - 1]["start"] + 0.04
    for k in range(len(kept)):
        if kept[k]["end"] < kept[k]["start"] + 0.30:
            kept[k]["end"] = kept[k]["start"] + 0.30
    for k in range(len(kept) - 1):
        if kept[k]["end"] > kept[k + 1]["start"] and kept[k + 1]["start"] > kept[k]["start"] + 0.25:
            kept[k]["end"] = kept[k + 1]["start"]

    print(f"[sonuc] kept={len(kept)} insertion-drop={len(dropped)} kuyruk-drop={len(tail_dropped)}")

    def fmt(t):
        t = max(t, 0.0)
        ms = round(t * 1000)
        h, r = divmod(ms, 3600000)
        m, r = divmod(r, 60000)
        s, ms = divmod(r, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    out_path = args.output or ("output/" + args.desynced.replace("\\", "/").split("/")[-1])
    out = []
    for num, r in enumerate(kept, 1):
        c = TR[r["i"]]
        out.append(f"{num}\r\n{fmt(r['start'])} --> {fmt(r['end'])}\r\n" + "\r\n".join(c["lines"]))
    open(out_path, "wb").write(("\r\n\r\n".join(out) + "\r\n\r\n").encode("utf-8"))
    print(f"[cikti] {out_path} | {len(kept)} blok | son {fmt(kept[-1]['end'])} (referans son {fmt(EN[-1]['end'])})")

    if args.audit:
        print("\n[denetim] 10dk isaretleri, cikti <-> en yakin referans (icerik gozle kontrol edilir):")
        for mark in range(10, int(EN[-1]["end"] / 60) + 1, 10):
            w = [r for r in kept if abs(r["start"] - mark * 60) <= 60]
            if not w:
                print(f"--- {mark}dk: cue yok ---")
                continue
            print(f"--- {mark}dk ---")
            for r in w[::max(1, len(w) // 4)][:4]:
                k = bisect.bisect_left(EN_STARTS, r["start"])
                best = min(EN[max(0, k - 2):k + 3], key=lambda c: abs(c["start"] - r["start"]))
                print(f"  {int(r['start']//60):02d}:{r['start']%60:05.2f} TR {TR[r['i']]['text'][:40]!r:42s} "
                      f"EN{best['start']-r['start']:+5.1f} {best['text'][:34]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
