# SRT Kodlama Referansı (Türkçe)

## Neden bozuluyor

SRT formatı kodlama bilgisi **taşımaz** (BOM hariç hiçbir metadata yoktur).
Oynatıcı/convertor dosyayı tahmin eder; Türkçe altyazılar çoğunlukla tek
baytlık bir Türkçe kodlamasıyla (ISO-8859-9 / Windows-1254) dağıtılır ve
karşı taraf bunu UTF-8 ya da ISO-8859-1 sanınca karakterler bozuk görünür.
Yani çoğu zaman dosya **bozuk değildir — yanlış okunmaktadır**. Çözüm her
zaman aynıdır: doğru kodlamayla çöz, BOM'suz UTF-8 olarak geri yaz.

## Belirti → teşhis → çözüm tablosu

| Ekranda görünen | Dosyada olan | Teşhis | Çözüm |
|---|---|---|---|
| `ð ý þ Ð Ý Þ` (İzlandaca harfler) | ISO-8859-9/CP1254 kodlu; oynatıcı ISO-8859-1 gibi okuyor | TR imza baytları mevcut | `decode('cp1254')` → `encode('utf-8')` |
| `Ã¼ Ã§ Ã¶ Ä± ÅŸ ÄŸ Ä°` | UTF-8 baytları CP125x ile okunup **tekrar UTF-8 kaydedilmiş** (çift kodlama) | strict UTF-8 decode BAŞARILI + `Ã/Ä/Å` içeriyor | `text.encode('cp1254' veya 'cp1252').decode('utf-8')` |
| `A�utos`, `�` kutuları | Geçersiz UTF-8 sanılıyor / bozuk bayt | strict UTF-8 decode BAŞARISIZ | tek baytlık tespit (karar ağacı 3. adım) |
| Değişik/GLYPH karakterler, hepsi kayıp | UTF-16 veya başka kodlama | BOM baytı `FF FE` / `FE FF` | `decode('utf-16')` → UTF-8 |

## Türkçe imza baytları (tek baytlık kodlama tespiti)

ISO-8859-9 ile ISO-8859-1 aynı 0x80–0xFF aralığını paylaşır; yalnız 6 pozisyon
Türkçe'ye özeldir. Bir altyazıda bu baytlardan biri bile yüksek sayıda varsa
kodlama %99 ISO-8859-9/CP1254'tür:

| Bayt | ISO-8859-9 / CP1254 | ISO-8859-1 / CP1252 (yanlış okuma) |
|---|---|---|
| 0xD0 | Ğ | Ð |
| 0xDD | İ | Ý |
| 0xDE | Ş | Þ |
| 0xF0 | ğ | ð |
| 0xFD | ı | ý |
| 0xFE | ş | þ |

Dikkat: `0xD1 0xD2 0xF1 0xF2` (Ñ Ò ñ ò) **imza değildir** — her iki kodlama
ailesinde de aynıdırlar. Yukarıdaki 6 bayt dışındakiler ayırt edici değildir.

Paylaşılan baytlar (iki ailede de aynı, ayırt etmezler):
`0xC7 Ç, 0xE7 ç, 0xD6 Ö, 0xF6 ö, 0xDC Ü, 0xFC ü, 0xE2 â`.

### ISO-8859-9 ile Windows-1254 farkı

0xA0–0xFF aralığında **birebir aynıdırlar**. Fark yalnız 0x80–0x9F'tedir:
CP1254'te tipografik karakterler („ ‚ € ™ …), ISO-8859-9'da C1 kontrol
karakterleri var. Pratik sonuç: önce `cp1254` ile strict decode dene (punct
aralığını da doğru çözer), hata verirse `iso8859_9`'a düş. Temiz dosyalarda
bu aralık hiç görünmez, ikisi de aynı sonucu verir.

## Mojibake (çift kodlama) tablosu

UTF-8'de Türkçe karakterler 2 baytlıktır (`ç = 0xC3 0xA7`); bu baytlar CP125x
ile okununca iki garip Latin karakteri olarak görünür ve öyle kaydedilir:

| Görünen | Aslında | | Görünen | Aslında |
|---|---|---|---|---|
| `Ã§` | ç | | `Ã‡` | Ç |
| `Ã¼` | ü | | `Ãœ` | Ü |
| `Ã¶` | ö | | `Ã–` | Ö |
| `Ä±` | ı | | `Ä°` | İ |
| `ÄŸ` | ğ | | `Äž` | Ğ |
| `ÅŸ` | ş | | `Åž` | Ş |

Geri dönüşüm: metni `cp1254` ile (başarısızsa `cp1252`) yeniden baytlara
çevir ve UTF-8 olarak çöz. Doğrulama: mojibake sayısı sıfıra iner, Türkçe
karakter sayısı artar.

Pratik not: gerçek dünyadaki mojibake'i üreten kodlayıcı neredeyse her zaman
`cp1252`'dir — `ş`'nin UTF-8 ikinci baytı 0x9F, cp1252'de `Ÿ`'dir ama
`cp1254`'te **tanımsızdır** (0x81 0x8D 0x8F 0x90 0x9D 0x9E gibi yuvalar
cp1254'te boştur). Dolayısıyla `ÅŸ` içeren bir metin `cp1254` ile encode
edilemez ve çözüm otomatik olarak `cp1252` fallback'ine düşer; bu sıra
(script'teki gibi) iki yönü de kapsar.

## Teşhis karar ağacı (scripts/fix_srt.py ile birebir aynı)

1. **BOM var mı?** `EF BB BF` → UTF-8-SIG, `FF FE`/`FE FF` → UTF-16.
   Çöz ve doğrudan UTF-8 yaz (BOM kaldırılır).
2. **strict UTF-8 decode dene.**
   - Başarılı + `Ã/Ä/Å` yok → dosya zaten temiz, **dokunma**.
   - Başarılı + `Ã/Ä/Å` var → mojibake'yi geri çevir (yukarıdaki yöntem).
   - Başarısız → 3. adım.
3. **TR imza baytları say.** (0xD0, 0xDD, 0xDE, 0xF0, 0xFD, 0xFE)
   - Varsa → `cp1254` strict (hata olursa `iso8859_9`) ile çöz.
   - Yoksa → `cp1252` ile çöz, **düşük güven** raporla: Türkçe karakter
     bulunamadı; belki dosyada Türkçe hiç yoktur ya da nadir bir kodlamadır.
4. Çözülen metinde kalıntı kontrolü: `Ã Ä Å Ý Þ Ð ý þ ð` geçmemeli.
   Geçiyorsa teşhis yanlıştır — `â` meşru Türkçedir (kâbus), flaglenmez.

## Hedef format (Stremio'da doğrulanmış)

- **BOM'suz UTF-8.** BOM'lu UTF-8 çoğu oynatıcıda çalışır; ancak Stremio
  drag-drop akışında BOM'suz ile test edilip onaylanmıştır (kullanıcı testi,
  2026-09-30). Farklı bir hedef oynatıcı (eski TV, bazı Windows uygulamaları)
  BOM isterse `--output` ile ayrı varyant üretip ayrıca test ettir.
- **Satır sonları olduğu gibi korunur** (CRLF kalır CRLF) — dönüşüm sadece
  kodlamadır, format düzenlemesi değildir.
- **Yerinde yazılır**: dosya adı, klasör, zaman kodları, numaralandırma,
  içerik birebir aynı kalır.

## Sınır durumları

- **Katmanlı bozulma**: hem imza baytları hem `Ã` dizileri aynı dosyada
  olabilir → önce tek baytlık decode, ardından mojibake geri çevirmesi
  (script ikisini sırayla uygular, maksimum 2 katman).
- **Karışık kodlama**: dosyanın bir kısmı UTF-8, bir kısmı Latin-5 (editör
  kazaları). strict decode başarısız olur ama imza tespiti yanıltabilir →
  blok bazında elle incele, otomatik akışa güvenme.
- **CP857 (DOS Türkçe)**: günümüz altyazılarında nadir; denk gelirse ayrı
  ele al (16-bit tablo, bu script kapsamı dışı).
- **HTML entity** (`&#252;`), **SSA/ASS**, **VTT**: kapsam dışı — bu repo
  yalnız SRT kodlama bozulmalarını kapsar.

## Vaka kanıtı (doğrulanmış örnek)

Terminator 2 FGT (yerel fixture: `samples/terminator2-fgt.*.srt`, gitignore)
— 74.117 bayt, 1.054 blok: yüksek bayt dağılımı
`0xFD × 1078, 0xFE × 342, 0xF0 × 261, 0xFC × 363 …` tam Türkçe imza
profili; 0x80–0x9F boş, 0xC3 yok (mojibake katmanı yok). `cp1254` decode →
UTF-8 yaz; gidiş-dönüş birebir. Regresyon: fixture çifti arasında
`fix_srt.py` çıktısı bayt bayt eşleşmeli.
