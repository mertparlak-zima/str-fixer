# PGS Çıkarma Teslim Öncesi Checklist

Script otomatik kontrollerin çoğunu koşar (`extract_pgs.py` çıktısındaki
`[dogrulama]` satırları); kalan maddeler gözle/kullanıcıyla.

## Checklist

- [ ] Track seçimi `mkvmerge -J` üzerinden yapıldı (elle sayılan id yok)
- [ ] Doğru track'te olduğu doğrulandı: **yaygın kelime oranı** ≥ %25
      beklenen dilde (düşükse yanlış track ya da yanlış OCR dili —
      vakadaki Fransızca hatası bu testle yakalanırdı)
- [ ] Cue sayısı makul: tam film için ~800-1200 (SDH'de daha fazla);
      film süresinin %70'inden önce biten altyazı şüphelidir
- [ ] Çöp karakter oranı < %5 (OCR bozulması göstergesi)
- [ ] Örnek satırlar gözle okundu: filmdeki bilinen replikler aranır
      (ör. "Hasta la vista" / "John Connor") — rakam ve isimler OCR'da
      en güvenilir işaretlerdir
- [ ] Çıktı BOM'suz UTF-8 + CRLF; zaman kodları geçerli
- [ ] Kullanıcı çıktıyı hedef videoda test etti (resync referansı olarak
      kullanılacaksa zamanlama birebir olmalı — PGS zamanları diskten
      gelir, sorunsuz beklenir)

## Belirti → neden tablosu

| Belirti | Neden | Çözüm |
|---|---|---|
| `--list` boş / "altyazı track'i yok" | gömülü altyazı yok | yanlış dosya — harici srt ara |
| Yanlış dilde metin çıktı | track off-by-one ya da yanlış etiket | `--list` + `--track N` |
| Kelime oranı ~%0 | OCR dili ≠ metin dili | `-l` doğru dil; gerekiyorsa `--engine rapidocr` |
| Cue sayısı film için çok az | yanlış track (commentary/forced) | `--without commentary,forced` |
| Her satırda bozuk karakter | düşük kaliteli bitmap / yanlış threshold | `--tesseract-threshold` düşür, rapidocr dene |
| `tesseract not found` ama kurulu | PATH tuzağı | script kullan; manuelde PATH'e ekle |
| `.sup` çıktı ama `.srt` yok | pgsrip OCR adımı patladı | `pgsrip doctor`, traineddata indirme izni |

## Zincir notu

Çıktı bu repoda iki amaçla kullanılır:
1. Doğrudan izleme → kodlama kontrolü (`fix_srt.py --check`) yeter.
2. **Resync referansı** → PGS zamanlaması kesindir; OCR metni sadece
   içerik doğrulamada kullanılır (hizalama zamanlarla yapılır). Bu
   durumda metin %100 kusursuz olmasa da sorun değildir; ama **cue
   sayısı/iskelet** bozuksa (birleşik/bölünmüş cue'lar) resync skill'indeki
   yoğunluk toleransları bunu zaten karşılar.
