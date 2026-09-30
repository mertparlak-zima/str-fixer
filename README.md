# str-fixer — Bozuk Türkçe SRT Düzeltici

Sık gelen Türkiye içerikli `.srt` altyazılarındaki **karakter bozulmalarını**
teşhis edip BOM'suz UTF-8'e çeviren ve **farklı kurgudan kaynaklanan süre
kaymalarını** referans altyazıyla düzelten kural seti, script'ler ve
doğrulama checklist'leri. Amaç: her seferinde AI'a durumu anlatmak yerine,
bozuk dosyayı verip "bu repodaki kurallara göre düzelt" demek.

Her iki akış gerçek vakalarda uçtan uca doğrulandı (Terminator 2, 30 Eylül
2026: ISO-8859-9 kodlama düzeltmesi + director's cut → theatrical re-sync,
ikisi de Stremio'da kullanıcı testi PASS).

## Depo yapısı

```
.
├── README.md                        # bu dosya
├── .gitignore                       # kök/input/output .srt'ler hariç tutulur
├── input/                           # kullanıcı bozuk/kaymış dosyaları buraya atar (ignore)
├── output/                          # düzeltilmiş çıktılar (ignore)
├── samples/                         # regresyon fixture'ları (yerel test, push edilmez)
│   ├── terminator2-fgt.iso8859-9.srt           # vaka 1: bozuk kodlama girdisi
│   ├── terminator2-fgt.utf8.fixed.srt          # vaka 1: beklenen çıktı
│   ├── t2-4k-theatrical.en.reference.srt       # vaka 2: referans (doğru zamanlar)
│   ├── t2-directors-cut.tr.desynced.srt        # vaka 2: kaymış TR girdisi
│   └── t2-directors-cut.tr.resynced.expected.srt  # vaka 2: beklenen çıktı
├── scripts/
│   ├── fix_srt.py                   # kodlama teşhisi + yerinde düzeltme
│   └── resync_srt.py                # referansa göre yeniden zamanlama (+--cal/--audit)
└── .claude/skills/
    ├── srt-fixing/                  # kodlama bozulması skill'i
    │   ├── SKILL.md
    │   └── references/ (encoding-reference, verification)
    └── srt-resync/                  # süre kayması skill'i
        ├── SKILL.md
        └── references/ (algorithm, verification)
```

Claude Code oturumlarında skill'ler otomatik listelenir ve `/srt-fixing`,
`/srt-resync` olarak çağrılabilir.

## Hızlı başlangıç

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

1. **Dosya çoğu zaman bozuk değildir, yanlış okunmaktadır** — SRT kodlama
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
9. Çalışma altyazıları (`input/`, `output/`, kök) repoya commit edilmez;
   `samples/` fixture'ları yerel regresyon içindir, repo hiçbir zaman
   altyazı içeriğiyle push edilmez.

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
