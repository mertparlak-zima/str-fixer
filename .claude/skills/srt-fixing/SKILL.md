---
name: srt-fixing
description: Fixing broken character encoding in Turkish .srt subtitle files — mojibake (Ã¼, Ä±, ÅŸ), ISO-8859-9/CP1254 single-byte Turkish, wrong-codepage garbling — and converting them to BOM-less UTF-8 that plays correctly in Stremio. Read before any subtitle repair task ("bozuk altyazı", "karakter bozulması", "fix srt", "altyazı düzelt", "subtitle encoding").
---

# Bozuk Türkçe SRT Düzeltme

Bu skill, kodlaması bozuk görünen Türkçe `.srt` altyazılarını teşhis edip
**BOM'suz UTF-8**'e çevirir ve dosyayı **yerinde** düzeltir. Kural seti
30 Eylül 2026'da gerçek bir vaka üzerinde doğrulandı (Terminator 2 altyazısı,
ISO-8859-9 → UTF-8, Stremio'da kullanıcı tarafından test edildi).

## Alt referanslar

- `references/encoding-reference.md` — bayt tabloları, bozulma tipleri, teşhis karar ağacı
- `references/verification.md` — teslim öncesi checklist + çalıştırılabilir test kodu

## İş akışı

### 1. Semptomu netleştir
Kullanıcıdan ekranda gördüğü bozuk karakterleri al (ör. `ð ý þ` mi, `Ã¼ Ä±` mı,
`�` mi). Belirti tablosu `encoding-reference.md` içinde — her belirti farklı
kaynağı işaret eder.

### 2. Bayt analizi yap (asla tahminle yürüme)
```python
data = open('DOSYA.srt','rb').read()
data[:3] == b'\xef\xbb\xbf'          # BOM var mı
collections.Counter(b for b in data if b >= 0x80)  # yüksek bayt dağılımı
```
Bakılacak şeyler: BOM, TR imza baytları (0xD0 0xDD 0xDE 0xF0 0xFD 0xFE),
0x80–0x9F aralığı (varsa CP1254 noktalama), 0xC3 varlığı (mojibake işareti).

### 3. Teşhisi koy
`references/encoding-reference.md`'deki karar ağacını izle. Dört durum:
BOM'lu / temiz UTF-8 / mojibake'li UTF-8 / tek baytlık Türkçe kodlaması.

### 4. Dönüşümü script ile yap (elle yapma)
```bash
python scripts/fix_srt.py DOSYA.srt --check   # önce sadece teşhis raporu
python scripts/fix_srt.py DOSYA.srt           # yerinde düzelt
```
Script imza baytı tespiti, mojibake geri dönüşümü ve yapı doğrulamasını
otomatik yapar. Elle `decode/encode` zinciri yazmak ancak script'in
kapsamadığı bir sınır durumda gerekçelendirilebilir.

### 5. Doğrulama checklist'ini koş
`references/verification.md`'deki maddelerin tamamı — özellikle gidiş-dönüş
birebirliği ve kötü-latin kalıntısı kontrolleri. Bir madde bile fail ise dosya
teslim edilmez.

### 6. Kullanıcıya önce/sonra göster
Düzeltmeden sonra kullanıcıya örnek satırları göster ve onayını al:
```
29 Aðustos 1997  →  29 Ağustos 1997
hayatý sona erdi →  hayatı sona erdi
```

### 7. Stremio yükleme talimatını doğru ver (kritik ders)
**srt dosyası Stremio'ya "import edilmez / açılmaz".** Doğru yöntem:
video **oynarken** dosyayı oynatıcı ekranının üzerine sürüklemek.
"Unsupported file" hatası dosyanın bozuk olduğu anlamına gelmez — yanlış
yükleme yöntemi anlamına gelir. Detaylar `references/verification.md` sonunda.

## Yasaklar

1. **Metin içeriğine dokunma** — yalnızca kodlama dönüşümü yapılır; yazım,
   tire, noktalama, satır bölme, HTML etiketleri değiştirilmez.
2. **Satır sonları, numaralandırma, zaman kodları değiştirilmez** — CRLF
   kalır CRLF, blok yapısı aynen korunur.
3. Gidiş-dönüş doğrulaması (orijinal çözülen metin == çıktı metni) olmadan
   "düzeltildi" denmez.
4. Kullanıcının ekranda görsel onayı alınmadan iş kapatılmaz.
5. Altyazı içerikleri repoya commit edilmez (`/*.srt`, `samples/` gitignore);
   regresyon fixture'ları yalnız yerel diskte tutulur.
