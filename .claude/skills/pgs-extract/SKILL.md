---
name: pgs-extract
description: Extracting embedded subtitles from video files (MKV/MP4) — especially Blu-ray bitmap PGS tracks that need OCR to become .srt — via mkvextract + Tesseract/pgsrip. Read before any "video'dan altyazı çıkarma", "gömülü altyazı", "PGS to SRT", "MKV subtitle extract/OCR" task.
---

# Video İçinden Altyazı Çıkarma (PGS OCR dahil)

Bu skill, MKV/MP4 içine gömülü altyazıları `.srt` olarak dışarı çıkarır.
Metin tabanlı track'ler (SRT/ASS) doğrudan çekilir; **Blu-ray kaynaklı
bitmap (PGS) track'ler OCR ile metne çevrilir**. Akış 30 Eylül 2026'da gerçek
bir vakada doğrulandı (T2 4K MKV: 6 PGS track, eng seçimi, ~1000 resim,
995 cue / 2:17 çıktı, bilinen replik teyidi).

Bu repo zincirinin **ilk halkasıdır**: `pgs-extract` (video → srt) →
`srt-fixing` (kodlama düzeltme) → `srt-resync` (referansa göre yeniden
zamanlama). Çıkan EN altyazı genelde resync'in referansı olur — PGS
zamanlamaları diskin kendisinden geldiği için **piksel hassasiyetinde
doğrudur**, OCR metin kalitesi ise ikincildir.

## Alt referanslar

- `references/toolchain.md` — araç kurulumları, PATH tuzağı, pgsrip'in
  bilinmeyen güçlü özellikleri, track-ID ve dil-kodu tuzakları
- `references/verification.md` — teslim öncesi checklist

## İş akışı

### 1. Track'leri listele (asla elle sayma)
```bash
python scripts/extract_pgs.py FILM.mkv --list
```
Track id + codec + dil + flag tablosu. **Track numarasını elsayla saymak
yasak** — mkvextract, mkvmerge'in tüm track'ler (video+ses+altyazı) üzerinden
0'dan sayan id'sini bekler; manuel çalıştırmada bu off-by-one yanlış track'i
(Fransızca'yı) çıkartmıştı. Script id'leri `mkvmerge -J` JSON'ından alır.

### 2. Çıkar + OCR
```bash
python scripts/extract_pgs.py FILM.mkv --lang en     # otomatik secim
python scripts/extract_pgs.py FILM.mkv --track 3     # manuel (yanlis etiketli track'ler)
```
Script: doğru track'i seçer (dil eşleşmesi ISO 639-2→1 dönüşümüyle),
mkvextract ile `.sup` çıkarır, pgsrip ile OCR'lar, çıktıyı `output/` klasörüne
yazar, `.sup`'ı temizler ve **doğrulamayı otomatik koşar** (cue sayısı, süre
kapsamı, dil kelime oranı, çöp karakter oranı).

Alternatif tek komut (track seçimi kritik değilse):
```bash
pgsrip rip -l en --one-per-language FILM.mkv
```
pgsrip extraction'ı da kendisi yapar (bkz. `toolchain.md`).

### 3. Metin track geldiyse
Script bunu kendine ayırt eder (OCR'suz çıkarır); kodlama bozuksa
`fix_srt.py` akışına yönlendirir.

### 4. Doğrulama
`references/verification.md` — script otomatik kontrolleri koşar; bilinen
replik/çoğu kelime kontrolü + Stremio testi kullanıcıyla birlikte yapılır.

## Yasaklar

1. **Track numarası elle sayılmaz** — her zaman `--list` / `mkvmerge -J`.
2. Dil etiketine körü körüne güvenilmez — yanlış etiketli track şüphesinde
   `--track` ile id seçilir ve doğrulamadaki **dil kelime oranı** bakılır
   (Fransızca metnin `-l en` OCR'ı ~%0 İngilizce kelime verir).
3. VobSub (DVD `idx/sub`) track'ler pgsrip ile OCR'lanamaz — SubtitleEdit
   CLI önerilir, kapsam dışı.
4. Doğrulama olmadan çıktı teslim edilmez; OCR çıktısında çöp karakter
   oranı yüksekse kullanıcıya örnek satırlar gösterilir.
