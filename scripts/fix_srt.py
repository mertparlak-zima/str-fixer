#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_srt.py — repair broken character encoding in Turkish .srt subtitles.

Detects the real encoding of an .srt file and rewrites it in place as
BOM-less UTF-8 (the format verified to play correctly in Stremio).
Line endings (CRLF/LF), block numbering, timestamps and every character of
the text are preserved byte-for-byte after the round trip.

Detection order (full reasoning: .claude/skills/srt-fixing/references/encoding-reference.md):
    1. BOM present          -> decode as UTF-8-SIG / UTF-16
    2. strict UTF-8 decode succeeds:
         a. contains mojibake (Ã, Ä, Å ...) -> reverse it: encode CP1254/CP1252, decode UTF-8
         b. otherwise        -> already clean, leave unchanged
    3. strict UTF-8 fails   -> single-byte codec:
         - Turkish signature bytes present (0xD0 0xDD 0xDE 0xF0 0xFD 0xFE)
                                  -> decode CP1254 (fallback ISO-8859-9)
         - none                -> decode CP1252, report low confidence

Usage:
    python scripts/fix_srt.py FILE.srt [--check] [--output OUT] [--backup]

    --check     diagnose and report only, do not write anything
    --output    write the result elsewhere instead of in place
    --backup    keep a copy of the original bytes as FILE.srt.bak

Exit codes: 0 = fixed / no change needed, 1 = error.
"""
import argparse
import re
import sys
from pathlib import Path

# In ISO-8859-9 / CP1254 these bytes are Ğ İ Ş ğ ı ş; in ISO-8859-1 / CP1252
# they read as Ð Ý Þ ð ý þ (Icelandic). Their presence in a Turkish subtitle
# is a near-certain single-byte-Turkish-encoding marker.
# NOTE: 0xD1 0xD2 0xF1 0xF2 are NOT signatures (Ñ Ò ñ ò in both families).
TR_SIG_BYTES = (0xD0, 0xDD, 0xDE, 0xF0, 0xFD, 0xFE)

# Chars that must not survive into the final text. 'â' is legitimate Turkish
# (kâbus) and intentionally not flagged.
MOJIBAKE_LEADS = "ÃÄÅ"          # UTF-8 misread as CP125x (Ã¼, Ä±, ÅŸ, ...)
BAD_LATIN = "ÃÄÅÝÞÐýþð"         # any residue after conversion = wrong diagnosis

TS_RE = re.compile(r"^\d{2}:\d{2}:\d{2}[,.]\d{3} --> \d{2}:\d{2}:\d{2}[,.]\d{3}")
TR_CHARS = "ğışçöüĞİŞÇÖÜ"


def mojibake_count(text):
    return sum(text.count(c) for c in MOJIBAKE_LEADS)


def tr_count(text):
    return sum(text.count(c) for c in TR_CHARS)


def sniff_bom(data):
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    return None


def decode_single_byte(data):
    """Return (text, codec_label, signature_byte_count)."""
    sig = sum(data.count(bytes([b])) for b in TR_SIG_BYTES)
    if sig:
        for codec in ("cp1254", "iso8859_9"):
            try:
                return data.decode(codec), codec, sig
            except UnicodeDecodeError:
                continue
        return data.decode("iso8859_9", errors="replace"), "iso8859-9 (replace)", sig
    if any(b >= 0x80 for b in data):
        return data.decode("cp1252"), "cp1252 (low confidence, no TR signature)", 0
    return data.decode("ascii"), "ASCII", 0


def try_fix_mojibake(text):
    """Reverse UTF-8-bytes-read-as-CP125x corruption. Returns (text, codec)."""
    for codec in ("cp1254", "cp1252"):
        try:
            fixed = text.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if mojibake_count(fixed) < mojibake_count(text) and tr_count(fixed) > tr_count(text):
            return fixed, codec
    return text, None


def validate_srt(text):
    """Return (block_count, numbering_ok, timestamps_ok)."""
    blocks = [b for b in re.split(r"\r?\n\r?\n", text.strip()) if b.strip()]
    numbering_ok = timestamps_ok = True
    for i, blk in enumerate(blocks, 1):
        lines = blk.splitlines()
        first = lines[0].strip().lstrip("﻿") if lines else ""
        if not first.isdigit():
            numbering_ok = False
            timestamps_ok = False
            continue
        if int(first) != i:
            numbering_ok = False
        if len(lines) < 2 or not TS_RE.match(lines[1].strip()):
            timestamps_ok = False
    return len(blocks), numbering_ok, timestamps_ok


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    ap = argparse.ArgumentParser(description="Fix broken encoding of a Turkish .srt subtitle (-> BOM-less UTF-8).")
    ap.add_argument("file", help=".srt file to diagnose/fix")
    ap.add_argument("--check", action="store_true", help="report only, do not write")
    ap.add_argument("--output", help="write result to this path instead of in place")
    ap.add_argument("--backup", action="store_true", help="keep original bytes as FILE.srt.bak")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        print(f"[hata] dosya yok: {path}")
        return 1
    data = path.read_bytes()

    src, text, action = None, None, None
    bom = sniff_bom(data)
    if bom:
        text, src = data.decode(bom), bom
        action = "BOM kaldirildi" if bom == "utf-8-sig" else f"{bom} -> UTF-8"
    else:
        try:
            text, src = data.decode("utf-8"), "UTF-8"
        except UnicodeDecodeError:
            text, src, sig = decode_single_byte(data)
            action = f"{src} -> UTF-8 (TR imza bayti: {sig})" if sig else f"{src} -> UTF-8"

    if mojibake_count(text):
        fixed, codec = try_fix_mojibake(text)
        if codec:
            text = fixed
            action = f"{action} + mojibake geri cevrildi ({codec})" if action else f"mojibake geri cevrildi ({codec})"

    residue = sum(text.count(c) for c in BAD_LATIN)
    blocks, numbering_ok, ts_ok = validate_srt(text)

    print(f"[kaynak] {src}  ({len(data)} bayt)")
    print(f"[islem]  {action or 'degisiklik gerekmedi (zaten BOMsuz UTF-8)'}")
    print(f"[icerik] blok={blocks}  numaralandirma={'duzgun' if numbering_ok else 'BOZUK'}  "
          f"zaman_kodu={'gecerli' if ts_ok else 'GECERSIZ'}  TR_karakter={tr_count(text)}")
    if residue:
        print(f"[uyari]  cozumden sonra kotu-latin kalintisi: {residue} — teshis yanlis olabilir, elle incele")
    if src.startswith("cp1252 (low") or "replace" in src:
        print("[uyari]  dusuk guvenli teshis — ornek satirlari kullaniciya gostermeden kapatma")

    if args.check or not action:
        return 0

    out = Path(args.output) if args.output else path
    if args.backup and not args.output:
        path.with_suffix(".srt.bak").write_bytes(data)
    out.write_bytes(text.encode("utf-8"))
    print(f"[cikti]  {out} ({out.stat().st_size} bayt, BOMsuz UTF-8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
