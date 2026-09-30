# str-fixer — Bozuk Türkçe SRT Düzeltici

Sık gelen Türkiye içerikli `.srt` altyazılarındaki karakter bozulmalarını
teşhis edip **BOM'suz UTF-8**'e çeviren kural seti, script ve doğrulama
checklist'i. Amaç: her seferinde AI'a durumu anlatmak yerine, bozuk dosyayı
verip "bu repodaki kurallara göre düzelt" demek.

Kural seti gerçek bir vakada uçtan uca doğrulandı (Terminator 2 TR altyazısı,
ISO-8859-9 kaynaklı bozulma → Stremio'da kullanıcı testi, 30 Eylül 2026).

## Deposu yapısı

```
.
├── README.md                        # bu dosya
├── .gitignore                       # kök .srt'ler ve .agent-tmp hariç tutulur
├── samples/                         # regresyon fixture'ları (yerel test, push edilmez)
│   ├── terminator2-fgt.iso8859-9.srt    # bozuk gelen orijinal
│   └── terminator2-fgt.utf8.fixed.srt   # beklenen düzeltilmiş çıktı
├── scripts/
│   └── fix_srt.py                   # teşhis + yerinde düzeltme CLI'sı
└── .claude/skills/srt-fixing/
    ├── SKILL.md                     # ana skill: iş akışı + yasaklar
    └── references/
        ├── encoding-reference.md    # bayt tabloları, karar ağacı, sınır durumları
        └── verification.md          # teslim öncesi checklist + test kodu
```

Claude Code oturumlarında skill otomatik listelenir ve `/srt-fixing` olarak
çağrılabilir.

## Hızlı başlangıç

```bash
# önce teşhis (yazmaz)
python scripts/fix_srt.py BOZUK.srt --check

# yerinde düzelt
python scripts/fix_srt.py BOZUK.srt
```

Script: BOM/UTF-8/mojibake/tek-baytlık tespiti yapar, dönüşümü uygular,
blok-zaman kodu doğrulaması ve kalıntı kontrolüyle rapor verir. Elle müdahale
yalnızca sınır durumlarında gerekçelendirilebilir (bkz.
`references/encoding-reference.md`).

Sonra `references/verification.md`'deki checklist'i koş ve **Stremio'da
video oynarken sürükleyip** test et.

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
6. Gidiş-dönüş doğrulaması ve kullanıcı görsel onayı olmadan iş kapatılmaz.
7. Çalışma altyazıları repoya commit edilmez (`/*.srt` ignore'dur);
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
