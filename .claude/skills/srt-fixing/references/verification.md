# Teslim Öncesi Doğrulama Checklist

Her madde koşulmadan düzeltilmiş dosya teslim edilmez. Fail veren madde varsa
dosya kullanıcıya "düzeltildi" olarak sunulmaz.

## Checklist

- [ ] Teşhis raporlanmış: kaynak kodlama, imza bayt sayısı veya mojibake
      deseniyle **gerekçeli** ( kör deafult yok)
- [ ] Çıktı kodlaması: `file CIKTI.srt` → `UTF-8 text` (ne `with BOM` ne
      `ISO-8859`)
- [ ] **Gidiş-dönüş birebirliği**: orijinalin doğru kodlamayla çözülmüş
      metni == çıktının çözülmüş metni (aşağıdaki test kodu)
- [ ] Türkçe karakter kalıntısı yok: `Ã Ä Å Ý Þ Ð ý þ ð` geçmiyor
      (`â` meşrudur — kâbus)
- [ ] SRT yapısı bozulmadı: blok sayısı, numaralandırma dizisi, zaman kodu
      formatı, satır sonları (CRLF → CRLF)
- [ ] Dosya adı ve klasör değişmedi (yerinde güncelleme)
- [ ] Kullanıcıya örnek önce/sonra satırlar gösterildi
- [ ] Kullanıcı ekranda görsel onay verdi (varsayımla kapatma)

## Stremio son testi (en sık yapılan hata burada)

**srt dosyası Stremio'ya import edilmez / açılmaz.** Stremio bir srt'yi medya
dosyası gibi açmaya kalktığında `Unsupported file` der — bu, altyazının bozuk
olduğu anlamına **gelmez**, yükleme yönteminin yanlış olduğu anlamına gelir.

Doğru yöntem:

1. Stremio'da **filmi oynatmaya başla** (kaynak ne olursa olsun).
2. Windows Explorer'dan srt'yi tut, **oynayan video ekranının üzerine**
   sürükle-bırak (ana kütüphane ekranına değil).
3. Altyazı otomatik yüklenir; sağ alttaki altyazı menüsünde yerel track
   olarak görünür.

Sorun çıkarsa:

- **Sürükleyince hiçbir şey olmuyor / tarayıcı açılıyor**: Stremio 6'nın
  bilinen drag-drop bug'ları (stremio-bugs #2827, #608) — Stremio'yu
  güncelle/yeniden başlat.
- **"No track" yükleniyor ama görünmüyor**: çıktının BOM'suz UTF-8 olduğundan
  emin ol; `Settings → Playback → Subtitles → Default language`'i İngilizce
  dışı bir değere (ör. Turkish) çevir.
- Her iki durumda da dosyayı VLC/mpv ile açıp doğrulamak hatayı izole eder:
  orada doğru görünüp Stremio'da görünmüyorsa sorun dosyada değil oynatıcıda.

## Test Kodu (Python)

Köşeli parantezleri gerçek dosya adlarıyla doldurup koş — tüm assert'ler
geçmeli:

```python
import re

OUT  = open('[CIKTI].srt', 'rb').read()   # düzeltilmiş dosya
ORIG = open('[ORIJINAL].srt', 'rb').read()  # düzeltme öncesi yedek
SRC_CODEC = 'cp1254'  # teşhis edilen kaynak kodlama (vacaya göre değiştir)

# 1) hedef format
assert not OUT.startswith(b'\xef\xbb\xbf'), 'BOM var!'
text = OUT.decode('utf-8')  # strict — geçemezse UTF-8 değil

# 2) kalıntı yok
assert not re.search(r'[ÃÄÅÝÞÐýþð]', text), 'kotu-latin kalintisi!'

# 3) gidiş-dönüş birebirliği (metin ve satır sonlari)
assert text == ORIG.decode(SRC_CODEC), 'icerik degismis!'

# 4) SRT yapisi
blocks = [b for b in re.split(r'\r?\n\r?\n', text.strip()) if b.strip()]
assert blocks, 'blok yok!'
ts = re.compile(r'^\d{2}:\d{2}:\d{2}[,.]\d{3} --> \d{2}:\d{2}:\d{2}[,.]\d{3}')
for i, b in enumerate(blocks, 1):
    lines = b.splitlines()
    assert lines[0].strip().lstrip('﻿').isdigit() and ts.match(lines[1].strip()), f'{i}. blok bozuk'

print(f'PASS: {len(blocks)} blok, icerik birebir, format UTF-8 (BOMsuz)')
```

## Belirti → neden tablosu (hata ayıklama)

| Belirti | Neden |
|---|---|
| Stremio "Unsupported file" | srt medya olarak açılmaya çalışılmış — dosya sorunu değil |
| Hâlâ `ð ý þ` görünüyor | dosya yanlış kodlamayla çözüldü ya da **eski dosya** açılıyor (önbellek/yanlış kopya) |
| `Ã¼` görünüyor | mojibake katmanı atlandı (karar ağacı 2b adımı) |
| Bazı satırlar iyi, bazıları bozuk | karışık kodlama — otomatik akış yetmez, blok bazında elle incele |
| Test `icerik degismis!` veriyor | dönüşüm sırasında metin değiştirilmiş (normalize/edit) — yasak |
