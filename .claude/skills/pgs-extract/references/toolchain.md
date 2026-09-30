# Araç Zinciri ve Tuzaklar

## Kurulumlar (hepsi açık kaynak; winget/pip)

| Araç | Kurulum | Rolü |
|---|---|---|
| MKVToolNix | `winget install MoritzBunkus.MKVToolNix` | `mkvmerge -J` (track envanteri), `mkvextract` (track ayırma) |
| Tesseract | `winget install UB-Mannheim.TesseractOCR` | OCR motoru |
| pgsrip | `pip install pgsrip` | PGS resimlerini OCR'layıp zaman kodlu .srt üretir |

Doğrulama: `pgsrip doctor` (bağımlılık sağlık kontrolü).

## Tuzak 1: PATH (en sık tekrar eden sorun)

winget kurulumları `C:\Program Files\...` altına kurulur ve **agent
shell'lerinin PATH'inde görünmeyebilir** (Git Bash, bazı subprocess
ortamları). Belirti: pgsrip/doctor "tesseract not found" der, `where
tesseract` boş döner, ama araç gerçekte kuruludur.

Çözüm: `scripts/extract_pgs.py` bilinen dizinleri kendine probing yapar
(`C:\Program Files\MKVToolNix\`, `C:\Program Files\Tesseract-OCR\`) ve bu
dizinleri pgsrip subprocess'inin PATH'ine enjekte eder. Manuel çalıştırmada
PATH'e kendin ekle.

## Tuzak 2: track numaralandırması (rapor edilen off-by-one)

`mkvextract tracks DOSYA N:çıktı` — buradaki `N`, **mkvmerge'in tüm
track'ler (video+ses+altyazı) üzerinden 0'dan saydığı track id'sidir**.
"3. altyazı track'i" diye elle saymak yanlış track'i verir (vakada Fransızca
çıktı). Doğru yöntem:

```bash
mkvmerge -J FILM.mkv     # JSON: her track'in id/codec/language/flag'i
```

Script `--list` bunun okunabilir halini basar.

## Tuzak 3: dil kodları

mkvmerge 3 harfli ISO 639-2 raporlar (`eng`, `fre`, `tur`), kullanıcı 2
harf verir (`en`, `fr`, `tr`). **Önek eşleşmesi kullanılmaz** — `tur`'nun
öneki `tr` değil `tu`'dur (sadece `eng→en` şans eseri tutar). Script
ISO 639-2→1 tablosuyla eşleştirir (`language_ietf` varsa önce o).

## pgsrip'in bilinmeyen güçlü özellikleri (kullanın)

- `pgsrip rip -l en FILM.mkv` — **doğrudan medya dosyasını** alır;
  extraction'ı da kendisi yapar. `--one-per-language` aynı dilin SDH
  kopyasını atlar. Track seçimi kritik değilse en kısa yol budur.
- **Eksik OCR dili otomatik iner**: `--tesseract-download` varsayılan açık;
  sistemde `tur.traineddata` olmasa bile `-l tr` çalışır (tessdata_best
  deposundan indirir). `--no-tesseract-download` ile kapatılabilir.
- `--with/--without forced|sdh|cc|commentary` — track flag filtreleri.
- `--engine rapidocr` (alternatif OCR) ve hatta `--openai-url` ile
  vision-model OCR zinciri; `--tesseract-threshold` güven eşiği.
- `--post-processor cleanit` (default) + `-t no-sdh,no-lyrics` etiketleri —
  OCR artıkları ve SDH içerik temizliği.
- `-e utf-8` çıktı kodlaması (bu reponun hedefi BOM'suz UTF-8; pgsrip
  varsayılanı UTF-8'dir, BOM eklemez).

## Format matrisi

| Track codec | Yol |
|---|---|
| `S_HDMV/PGS` | mkvextract → `.sup` → pgsrip OCR (script'in ana yolu) |
| `S_TEXT/UTF8`, `S_TEXT/ASS` | mkvextract ile doğrudan çıkar → kodlama için `fix_srt.py` |
| `S_VOBSUB` (DVD idx/sub) | pgsrip desteklemez → SubtitleEdit CLI (kapsam dışı) |

MP4 kapları: gömülü altyazı nadiren `mp4s`/tx3g olur; PGS içermez.
MKV olmayan dosyada gömülü altyazı görünmüyorsa kaynak yanlış kabul edilir.

## Performans notu

~1000 PGS resmi ~1 dakikada OCR'lanır (4 worker). OCR süresi resim
sayısıyla doğru orantılı; 4K kaynaklarda resimler büyüktür ama pgsrip
`--tesseract-width` ile ölçekler.
