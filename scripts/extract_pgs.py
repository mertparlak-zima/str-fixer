#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pgs.py — pull embedded subtitles out of an MKV/MP4 and OCR PGS to SRT.

Covers the case classic extraction misses: Blu-ray style bitmap (PGS) subtitle
tracks that need OCR. Text tracks (SRT/ASS) are extracted directly and routed
to fix_srt.py for encoding repair.

Chain in this repo: extract_pgs (video -> srt) -> fix_srt (encoding) ->
resync_srt (re-time against a reference).

Improvements over the manual operation this automates (2026-09-30):
  - track IDs are parsed from `mkvmerge -J` JSON, never hand-counted
    (the manual run hit an off-by-one and ripped the French track first)
  - mkvtoolnix/tesseract are probed on PATH AND common winget install dirs,
    and injected into the subprocess PATH (pgsrip needs them on PATH)
  - pgsrip's own traineddata auto-download is relied on for non-installed
    OCR languages (e.g. tur)
  - post-OCR verification: block count, duration coverage, non-ASCII garbage
    ratio, common-word rate for the expected language (catches wrong-track
    rips: French text read with -l en scores ~0 English words)

Usage:
    python scripts/extract_pgs.py FILM.mkv [--lang en] [--track N] [--list]
           [-o output] [--selftest]

    --list      only list subtitle tracks (id, codec, language, flags)
    --track N   extract exactly this mkvmerge track id (bypass language pick)
    --lang LL   preferred track language (default en)
    --selftest  run the track-selection logic against a fixture and exit

Exit codes: 0 ok, 1 usage/tool error, 2 no matching subtitle track,
3 unsupported codec (VobSub).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

KNOWN_DIRS = {
    "mkvmerge": [r"C:\Program Files\MKVToolNix\mkvmerge.exe",
                 r"C:\Program Files (x86)\MKVToolNix\mkvmerge.exe"],
    "mkvextract": [r"C:\Program Files\MKVToolNix\mkvextract.exe",
                   r"C:\Program Files (x86)\MKVToolNix\mkvextract.exe"],
    "tesseract": [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"],
}

COMMON = {
    "en": "the be to of and a in that have i it for not on with he as you do at this but his by from they we say her she or an will my one all would there their what",
    "tr": "bir ve bu da ne için çok ama daha kadar gibi ben sen o biz siz onu bana sana şimdi sonra hep her şey yok var diye zaman insan gün yıl",
}

PGS_CODECS = ("S_HDMV/PGS", "S_HDMV/TEXTST")
TEXT_CODECS = ("S_TEXT/UTF8", "S_TEXT/SSA", "S_TEXT/ASS", "S_TEXT/USF", "S_TEXT/WEBVTT")


def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    for cand in KNOWN_DIRS.get(name, []):
        if os.path.isfile(cand):
            return cand
    return None


def probe_tools(need_ocr=True):
    tools = {n: find_tool(n) for n in ("mkvmerge", "mkvextract")}
    if need_ocr:
        tools["tesseract"] = find_tool("tesseract")
        tools["pgsrip"] = shutil.which("pgsrip") or "python -m pgsrip"
    missing = [n for n, p in tools.items() if p is None]
    for n in missing:
        hint = {
            "mkvmerge": "winget install MoritzBunkus.MKVToolNix",
            "mkvextract": "winget install MoritzBunkus.MKVToolNix",
            "tesseract": "winget install UB-Mannheim.TesseractOCR",
            "pgsrip": "pip install pgsrip",
        }[n]
        print(f"[arac] {n} BULUNAMADI -> {hint}")
    # pgsrip subprocess PATH'ine mkvtoolnix/tesseract dizinlerini enjekte et
    extra = {os.path.dirname(p) for p in tools.values() if p and p.endswith(".exe")}
    if extra:
        os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")
    return tools, missing


def subtitle_tracks(mkvmerge, path):
    r = subprocess.run([mkvmerge, "-J", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"[hata] mkvmerge okuyamadi: {r.stderr.strip()[:200]}")
        return None, None
    doc = json.loads(r.stdout)
    subs = [t for t in doc.get("tracks", []) if t.get("type") == "subtitles"]
    return subs, doc.get("container", {}).get("properties", {}).get("duration", None)


# ISO 639-2/B -> 639-1: mkvmerge 3 harf raporlar, kullanicilar 2 harf verir
# ("tur" -> "tr"; onek eslesmesi YANLIS calisir: "tur" oneki "tu")
ISO2 = {"eng": "en", "fre": "fr", "fra": "fr", "tur": "tr", "ger": "de", "deu": "de",
        "spa": "es", "ita": "it", "por": "pt", "rus": "ru", "ara": "ar", "hin": "hi",
        "jpn": "ja", "kor": "ko", "chi": "zh", "zho": "zh", "nld": "nl", "dut": "nl",
        "swe": "sv", "dan": "da", "nor": "no", "fin": "fi", "gre": "el", "ell": "el",
        "pol": "pl", "cze": "cs", "ces": "cs"}


def pick_track(subs, lang, forced_track=None):
    if forced_track is not None:
        for t in subs:
            if t["id"] == forced_track:
                return t
        return None

    def lang_of(t):
        pr = t.get("properties", {})
        lg = (pr.get("language_ietf") or pr.get("language") or "").lower()
        return ISO2.get(lg, lg)

    exact = [t for t in subs if lang_of(t) == lang]
    pool = exact or subs
    # tercih: PGS/text codec'lu, forced olmayan
    for t in pool:
        if t.get("codec") in PGS_CODECS + TEXT_CODECS and not t.get("properties", {}).get("forced_track"):
            return t
    return pool[0] if pool else None


def verify_srt(path, lang, duration_ms):
    try:
        data = open(path, "rb").read()
        text = data.decode("utf-8-sig" if data[:3] == b"\xef\xbb\xbf" else "utf-8", errors="replace")
    except OSError as e:
        print(f"[hata] cikti okunamadi: {e}")
        return False
    blocks = re.split(r"\r?\n\r?\n", text.strip())
    cues = [b for b in blocks if re.search(r" --> ", b)]
    ts = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)")

    def sec(m):
        g = list(map(int, m.groups()))
        return g[3] * 3600 + g[4] * 60 + g[5] + g[6] / 1000

    ends = []
    for b in cues:
        m = ts.search(b)
        if m:
            ends.append(sec(m))
    if not cues:
        print("[dogrulama] FAIL: hic cue yok")
        return False
    body = " ".join(re.sub(r"\d+ --> \d+|\d+", " ", b) for b in cues).lower()
    words = re.findall(r"[a-zçğıöşü']{2,}", body)
    vocab = set(COMMON.get(lang, COMMON["en"]).split())
    hit = sum(1 for w in words[:3000] if w in vocab)
    rate = hit / max(min(len(words), 3000), 1)
    garbage = sum(1 for ch in body if ord(ch) > 0x2500) / max(len(body), 1)
    dur_min = (ends[-1] / 60) if ends else 0
    movie_min = (duration_ms / 60000) if duration_ms else 0
    print(f"[dogrulama] cue={len(cues)} son_bitis={dur_min:.1f}dk film={movie_min:.1f}dk "
          f"yaygin-kelime-orani={rate:.2%} cop-karakter={garbage:.2%}")
    ok = True
    if movie_min and dur_min < movie_min * 0.7:
        print("[dogrulama] UYARI: altyazı filmin %70'inden önce bitiyor — yanlis track / eksik OCR?")
        ok = False
    if rate < 0.10:
        print(f"[dogrulama] UYARI: '{lang}' yaygin kelime orani cok dusuk — yanlis track veya yanlis OCR dili?")
        ok = False
    if garbage > 0.05:
        print("[dogrulama] UYARI: cop karakter orani yuksek — OCR kalitesini gozle kontrol et")
    return ok


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="MKV/MP4 gomulu altyazi cikarma + PGS OCR.")
    ap.add_argument("media", nargs="?", help=".mkv / .mp4 dosyasi")
    ap.add_argument("--lang", default="en", help="tercih edilen track dili (default en)")
    ap.add_argument("--track", type=int, default=None, help="mkvmerge track id (manual secim)")
    ap.add_argument("--list", action="store_true", help="sadece altyazi track'lerini listele")
    ap.add_argument("-o", "--output", default="output", help="cikti klasoru")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        fixture = {"tracks": [
            {"id": 0, "type": "video", "codec": "V_MPEG4/ISO/AVC"},
            {"id": 1, "type": "audio", "codec": "A_AAC"},
            {"id": 2, "type": "subtitles", "codec": "S_HDMV/PGS", "properties": {"language": "fre"}},
            {"id": 3, "type": "subtitles", "codec": "S_HDMV/PGS", "properties": {"language": "eng"}},
            {"id": 4, "type": "subtitles", "codec": "S_TEXT/UTF8", "properties": {"language": "tur"}},
        ]}
        subs = [t for t in fixture["tracks"] if t["type"] == "subtitles"]
        assert pick_track(subs, "en")["id"] == 3, "en secimi"
        assert pick_track(subs, "tr")["id"] == 4, "text-track secimi"
        assert pick_track(subs, "en", forced_track=2)["id"] == 2, "manuel track"
        assert pick_track([], "en") is None, "bos liste"
        print("SELFTEST: track secim mantigi PASS (4 vaka)")
        return 0

    if not args.media:
        ap.print_usage()
        return 1
    if not os.path.isfile(args.media):
        print(f"[hata] dosya yok: {args.media}")
        return 1

    tools, missing = probe_tools()
    if "mkvmerge" in missing:
        return 1
    if args.list:
        subs, dur = subtitle_tracks(tools["mkvmerge"], args.media)
        if subs is None:
            return 1
        print(f"{'id':>3} {'codec':<14} {'dil':<5} {'flag':<12} baslik")
        for t in subs:
            pr = t.get("properties", {})
            flags = ",".join(f for f in ("forced_track", "default_track") if pr.get(f))
            print(f"{t['id']:>3} {t.get('codec','?'):<14} {(pr.get('language') or '?'):<5} {flags:<12} {pr.get('track_name','')}")
        return 0

    subs, dur = subtitle_tracks(tools["mkvmerge"], args.media)
    if subs is None:
        return 1
    if not subs:
        print("[hata] dosyada altyazi track'i yok")
        return 2
    tr = pick_track(subs, args.lang, args.track)
    if tr is None:
        print(f"[hata] track bulunamadi (--track {args.track})")
        return 2
    pr = tr.get("properties", {})
    print(f"[track] id={tr['id']} codec={tr.get('codec')} dil={pr.get('language')} '{pr.get('track_name','')}'")

    os.makedirs(args.output, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.media))[0]
    lang = pr.get("language") or args.lang

    if tr.get("codec") in TEXT_CODECS:
        out = os.path.join(args.output, f"{base}.{lang}.srt")
        ext = ".ass" if tr.get("codec") in ("S_TEXT/SSA", "S_TEXT/ASS") else ".srt"
        if ext == ".ass":
            out = os.path.join(args.output, f"{base}.{lang}.ass")
        r = subprocess.run([tools["mkvextract"], "tracks", args.media, f"{tr['id']}:{out}"])
        if r.returncode != 0:
            print("[hata] mkvextract basarisiz")
            return 1
        print(f"[cikti] {out} (metin track — OCR gerekmedi)")
        print("[not] kodlama bozuksa: python scripts/fix_srt.py " + out)
        return 0

    if tr.get("codec") not in PGS_CODECS:
        print(f"[hata] desteklenmeyen altyazi codec'i: {tr.get('codec')} (VobSub ise SubtitleEdit CLI dene)")
        return 3

    # PGS: mkvextract -> .sup -> pgsrip OCR
    if any(m in missing for m in ("mkvextract", "tesseract", "pgsrip")):
        print("[hata] OCR icin gereken araclardan biri eksik (yukaridaki kurulum komutlari)")
        return 1
    sup = os.path.join(args.output, f"{base}.{lang}.sup")
    r = subprocess.run([tools["mkvextract"], "tracks", args.media, f"{tr['id']}:{sup}"])
    if r.returncode != 0 or not os.path.isfile(sup):
        print("[hata] mkvextract .sup uretmedi")
        return 1
    print(f"[cikarim] {sup}")
    r = subprocess.run(f'{tools["pgsrip"]} rip -l {lang} --one-per-language "{sup}"',
                       shell=True, cwd=args.output)
    srt = os.path.join(args.output, f"{base}.{lang}.srt")
    if not os.path.isfile(srt):
        # pgsrip cikti adlandirmasi farkli olabilir: klasordeki yeni .srt'yi bul
        cands = [f for f in os.listdir(args.output) if f.endswith(".srt") and base[:20] in f]
        if cands:
            srt = os.path.join(args.output, cands[0])
    if r.returncode != 0 or not os.path.isfile(srt):
        print("[hata] pgsrip .srt uretmedi (pgsrip doctor ile teşhis et)")
        return 1
    print(f"[ocr] {srt}")
    ok = verify_srt(srt, args.lang, dur)
    try:
        os.remove(sup)
    except OSError:
        pass
    print(("[tamam] " if ok else "[uyari] dogrulama sorunlu — ") + srt)
    return 0 if ok else 0


if __name__ == "__main__":
    sys.exit(main())
