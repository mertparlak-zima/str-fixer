---
name: srt-resync
description: Re-timing a desynced Turkish .srt subtitle against a reference .srt with correct timings — cut differences (extended/director's cut vs theatrical), release offsets, cumulative drift. Aligns cues to the reference timeline, drops scenes absent from the target cut. Read before any subtitle sync/offset/drift repair task ("altyazı kayıyor", "süre kayması", "senkron", "resync", "extended altyazıyı theatrical'a uydur").
---

# SRT Re-sync (kaymış altyazıyı referansa göre yeniden zamanlama)

Bu skill, doğru zamanlanmış bir **referans** altyazıya (genelde izlenen videonun EN
sürümü) karşı **farklı kurgudan/dişilimden** gelen bir TR altyazıyı yeniden
zamanlar. 30 Eylül 2026'da uçtan uca doğrulandı: T2 director's cut TR →
theatrical 4K EN (1054 → 930 cue, 12 offset basamağı, kullanıcı testi PASS).

## Alt referanslar

- `references/algorithm.md` — hizalama algoritması, bozulma modelleri, başarısızlık
  modları ve manuel kalibrasyon yöntemi (en kritik dersler burada)
- `references/verification.md` — teslim öncesi checklist + 10dk süpürme denetimi

## İş akışı

### 1. Girdileri yerleştir
Kullanıcıdan iki dosya alınır: referans (doğru zamanlar) + kaymış TR.
Klasör kuralı: girdiler `input/`, çıktılar `output/`. Referansın hangi kurgu
için doğru olduğu mutlaka teyit edilir (film adı + release).

### 2. Script'i çalıştır
```bash
python scripts/resync_srt.py input/REFERANS.srt input/KAYMIS.srt
```
Script iki dosyanın kodlamasını da kendisi çözer (cp1254 dahil), anchor
zinciri kurar, segment merdivenini çıkarır, çıktıyı `output/`'a yazar
(BOM'suz UTF-8). Raporu oku: segment tablosundaki offset merdiveni kurgu
farkıyla tutarlı mı? (Örnek: T2 SE ≈ +16dk kümülatif.)

### 3. Süpürme denetimini koş (`--audit` ya da elle)
`references/verification.md`'deki **10dk süpürme** yöntemi: her 10dk işaretinin
±1 dakikasındaki çıktı cue'ları, en yakın referans cue'larıyla yan yana
listelenir ve **içerik gözle okunarak** eşleşme doğrulanır (çeviri çiftleri
açıkça görülür). ±2s üzeri sistematik sapma = kalibrasyon gereken bölge.

### 4. Sorunlu bölgeleri kalibre et
Diyalog-yoğun sahnelerde sahnenin ortasına giren küçük eklemeler otomatik
tespit edilemeyebilir (neden: `algorithm.md` → zaman-tesadüfü zehirlenmesi).
Orada `algorithm.md`'deki **metin-doğrulamalı kalibrasyon** yöntemi uygula:
çeviri çiftlerini bul (isim/rakayum/ayırt edici ifade), gerçek offset'i ölç,
`--cal A:B:OFFSET` ile geçir. Kalibrasyon penceresi ±2s'yi aşarsa bölgeyi
böl (aynı kural script'in otomatik segmentleri için de geçerli).

### 5. Doğrulama checklist'i
`references/verification.md`'nin tamamı — özellikle süpürme temizliği ve
kullanıcının hedef videoda görsel testi.

### 6. Teslim + arşiv
Çıktı `output/`'ta kalır. Vaka yeni bir sorun tipi öğrettiyse yerel
`samples/` klasörüne fixture (gitignore — repoya girmez) +
`algorithm.md`'ye ders olarak eklenir.

## Yasaklar

1. Referansı oluşturmak için **içerik tahmini yapılmaz** — zaman kayması
   düzeltmesi referansın zamanlarını kullanır, film bilgisiyle offset
   "tahmin edilmez".
2. Kalibre edilmemiş bölge **"muhtemelen doğrudur" ile geçilmez** — süpürme
   denetimi görülmeden teslim yok.
3. Metin içeriği değiştirilmez; yalnız zaman kodları ve sahne-dışı cue'ların
   çıkarılması.
4. Çok az anchor (<5) varsa alignment başarısızdır — referans/desynced
   gerçekten aynı film mi, kontrol edilmeden çıktı verilmez.
5. Altyazı içerikleri (`input/`, `output/`, `samples/`) repoya commit
   edilmez — fixture'lar yalnız yerel diskte.
