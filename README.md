# str-fixer — Bozuk Türkçe SRT Düzeltici

Video dosyasından altyazı **çıkarma** (PGS OCR dahil), sık gelen TR
altyazılardaki **karakter bozulmalarını** düzeltme ve farklı kurgudan
kaynaklanan **süre kaymalarını** referansla düzeltme: üç akış, kural setleri,
script'ler ve doğrulama checklist'leri. Amaç: her seferinde AI'a durumu
anlatmak yerine, dosyayı verip "bu repodaki kurallara göre düzelt" demek.

Üç akış da gerçek vakalarda uçtan uca doğrulandı (Terminator 2, 30 Eylül
2026: MKV içinden PGS → OCR ile EN srt çıkarma; ISO-8859-9 kodlama düzeltmesi;
director's cut → theatrical re-sync — hepsi kullanıcı testi PASS).

## Depo yapısı

```
.
├── README.md                        # bu dosya
├── .gitignore                       # kök/input/output .srt'ler hariç tutulur
├── input/                           # kullanıcı bozuk/kaymış dosyaları buraya atar (ignore)
├── output/                          # düzeltilmiş çıktılar (ignore)
├── samples/                         # YEREL regresyon fixture'ları (gitignore — push edilmez)
├── scripts/
│   ├── extract_pgs.py               # MKV/MP4 gömülü altyazı + PGS OCR
│   ├── fix_srt.py                   # kodlama teşhisi + yerinde düzeltme
│   └── resync_srt.py                # referansa göre yeniden zamanlama (+--cal/--audit)
└── .claude/skills/
    ├── srt-fixing/                  # kodlama bozulması skill'i
    │   ├── SKILL.md
    │   └── references/ (encoding-reference, verification)
    ├── srt-resync/                  # süre kayması skill'i
    │   ├── SKILL.md
    │   └── references/ (algorithm, verification)
    └── pgs-extract/                 # video içinden altyazı çıkarma skill'i
        ├── SKILL.md
        └── references/ (toolchain, verification)
```

Claude Code oturumlarında skill'ler otomatik listelenir ve `/srt-fixing`,
`/srt-resync`, `/pgs-extract` olarak çağrılabilir.

## Hızlı başlangıç

**Video'dan altyazı çıkarma** (gömülü PGS/Blu-ray bitmap dahil):

```bash
python scripts/extract_pgs.py FILM.mkv --list      # track envanteri (elle sayma!)
python scripts/extract_pgs.py FILM.mkv --lang en   # seç + çıkar + OCR + doğrula
```

**Kodlama bozulması** (ð/ý/þ, Ã¼/Ä± görünüyorsa):

```bash
python scripts/fix_srt.py input/BOZUK.srt --check   # önce teşhis
python scripts/fix_srt.py input/BOZUK.srt           # yerinde düzelt
```

**Süre kayması** (farklı kurgudan altyazı):

```bash
python scripts/resync_srt.py input/REFERANS_EN.srt input/KAYMIS_TR.srt --audit
# sapma bulunan bölgeler için metin-doğrulamalı kalibrasyon:
python scripts/resync_srt.py input/REFERANS_EN.srt input/KAYMIS_TR.srt \
    --cal 656:671:743.2 --cal 672:753:818.4 --drop 751,752,753
```

Çıktılar `output/`'a yazılır (BOM'suz UTF-8). Sonra ilgili skill'in
`references/verification.md` checklist'ini koş ve **Stremio'da video oynarken
sürükleyip** test et.

## Kısa kurallar

1. **Videodan altyazı çıkarırken track numarası elle sayılmaz** —
   `mkvextract` tüm track'ler üzerinden 0'dan sayan mkvmerge id'sini bekler;
   JSON'dan (`--list`) okunur. Ayrıca dil kodları 3 harf ISO'dur (`tur`),
   önek eşleşmesi yanlış çalışır (`tur` ≠ `tr` öneki).
2. **Dosya çoğu zaman bozuk değildir, yanlış okunmaktadır** — SRT kodlama
   metadata'sı taşımaz; teşhis bayt analizinden konur, tahminden değil.
2. Türkçe imza baytları: `0xD0 Ğ, 0xDD İ, 0xDE Ş, 0xF0 ğ, 0xFD ı, 0xFE ş`
   (ISO-8859-1 okumasında `Ð Ý Þ ð ý þ` görünür). `0xD1/0xD2/0xF1/0xF2`
   imza değildir.
3. Hedef format **BOM'suz UTF-8**, satır sonları ve tüm içerik birebir
   korunur; dönüşüm yerinde yapılır.
4. `Ã¼/Ä±/ÅŸ` deseni çift kodlamadır: strict UTF-8 decode başarılı olur —
   geri çevir (encode CP125x → decode UTF-8).
5. **Stremio'da srt import edilmez**: video oynarken dosya oynatıcı ekranına
   sürüklenir. "Unsupported file" = yanlış yöntem, dosya hatası değil.
6. Re-sync'te offset **basamaklıdır** (ek sahne = sabit kayma); fps/dişilim
   farkı sürekli kayma üretir — bu ayrım olmadan düzeltme yapılmaz.
7. Diyalog-yoğun sahnede otomatik hizalama **zaman-tesadüfüyle
   zehirlenebilir**; teslimden önce 10dk süpürme denetimi (çiftleri gözle
   okuyarak) zorunludur, sapma varsa `--cal` kalibrasyonu.
8. Gidiş-dönüş/süpürme doğrulaması ve kullanıcı görsel onayı olmadan iş
   kapatılmaz.
9. Altyazı içerikleri repoya **asla** commit edilmez (`input/`, `output/`,
   `samples/`, kök — hepsi gitignore). Regresyon fixture'ları yalnız yerel
   diskte tutulur; repo GitHub'da yalnız kural seti + script + doküman
   içerir.

## Arka plan

- 30 Eylül 2026: Terminator 2 (FGT release) TR altyazısı `ð/ý/þ` bozuk geldi.
  Bayt analizi: 2.641 yüksek bayt, tam Türkçe imza profili, 0x80–0x9F ve
  0xC3 yok → temiz ISO-8859-9. `cp1254` decode → BOM'suz UTF-8 yaz;
  1.054 blok birebir korundu.
- İlk denemede "Unsupported file" alındı: sebep kodlama değil, srt'nin
  Stremio'ya medya gibi açılmasıydı. Doğru yöntem (oynarken sürükleme)
  uygulandığında altyazı doğru görüntülendi — bu ders checklist'e ve bu
  README'ye taşındı.

## Kaynaklar

- [Reddit — Drag n drop .srt "No track" issue](https://www.reddit.com/r/Stremio/comments/16lwhy9/drag_n_drop_srt_no_track_issue/) — UTF-8 yeniden kodlama çözümü
- [Reddit — Failed to load external subtitles](https://www.reddit.com/r/Stremio/comments/1dw989z/failed_to_load_external_subtitles/) — Default language ayarı
- [stremio-bugs #2827](https://github.com/stremio/stremio-bugs/issues/2827) — Stremio 6 drag-drop bug'ı
- [stremio-bugs #608](https://github.com/Stremio/stremio-bugs/issues/608) — harici altyazı yükleme hataları
- [Wikipedia — ISO/IEC 8859-9](https://en.wikipedia.org/wiki/ISO/IEC_8859-9) — Latin-5 kod tablosu
