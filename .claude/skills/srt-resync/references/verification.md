# Re-sync Teslim Öncesi Checklist

Her madde koşulmadan teslim yok. Kalibrasyon içeren işlerde özellikle
4-6 numaralı maddeler zorunlu.

## Checklist

- [ ] Segment merdiveni raporu kurgu farkıyla tutarlı (kümülatif son offset
      ≈ kurgu süre farkı; örn. SE ↔ theatrical farkı)
- [ ] Çıktı format: BOM'suz UTF-8, CRLF, blok başına numara + geçerli
      zaman kodu, monoton başlangıçlar
- [ ] Çıktının son cue'u referansın film bitiminden SONRA bitmiyor
      (jeneriğe taşmıyor)
- [ ] **10dk süpürme denetimi** (aşağıda) koşuldu ve tüm pencerelerde
      TR↔EN çiftleri çeviri olarak okunuyor, ±2s üzeri sistematik sapma yok
- [ ] Sapma bulunan bölgeler metin-doğrulamalı kalibrasyonla düzeltildi ve
      **süpürme bir kez daha koşuldu**
- [ ] Düşürülen cue envanteri raporlandı (hangi sahneler, toplam süre) ve
      kullanıcının hedef kurgusunda gerçekten olmayan içerik
- [ ] Kullanıcı hedef videoda görsel test yaptı (en az: açılış, orta film
      1 nokta, şikayet edilen bölge, final)

## 10dk Süpürme Denetimi (kullanıcının taktiği)

Her 10 dakika işaretinin ±1 dakikalık penceresindeki çıktı cue'ları, en
yakın referans cue'larıyla yan yana listelenir; **içerik gözle okunarak**
çiftlerin gerçek çeviri olduğu doğrulanır. Otomatik metin benzerliği
kullanılmaz — TR/EN çeviriler token paylaşmaz, insan gözü (ya da AI)
semantiği görür.

Script: `python scripts/resync_srt.py REF.srt TR.srt --cal ... --audit`

Elle:

```python
import re, bisect
def parse(t):
    r = []
    for b in re.split(r'\r?\n\r?\n', t.strip()):
        L = b.splitlines()
        m = re.match(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)', L[1].strip())
        g = list(map(int, m.groups()))
        r.append((g[0]*3600+g[1]*60+g[2]+g[3]/1000, ' '.join(L[2:])))
    return r
O = parse(open('CIKTI.srt', encoding='utf-8').read())
E = parse(open('REFERANS.srt', encoding='utf-8').read())
es = [c[0] for c in E]
for mark in range(10, 135, 10):
    w = [c for c in O if abs(c[0] - mark*60) <= 60]
    for st, tx in w[::max(1, len(w)//4)][:4]:
        k = bisect.bisect_left(es, st)
        best = min(E[max(0,k-2):k+3], key=lambda c: abs(c[0]-st))
        print(f"{int(st//60):02d}:{st%60:05.2f} TR {tx[:40]!r:42s} EN{best[0]-st:+5.1f} {best[1][:34]!r}")
```

**Nasıl okunur:**
- `EN ±0-1s` + metinler çeviri → PASS
- `EN ±3-8s` tutarlı + metinler çeviri → küçük yerel kayma; izlenebilirliği
  bozmuyorsa geç, bozuyorsa kalibre et
- Metinler çeviri DEĞİL (bağımsız satırlar) → **zaman-tesadüfü zehirlenmesi**
  → `algorithm.md`'deki kalibrasyon akışı
- Ekran-yazısı cue'ları ("SIVI NİTROJEN" gibi) EN karşılıksız → normal

## Belirti → neden tablosu

| Belirti | Neden | Çözüm |
|---|---|---|
| Tek nokta ±30-90s kayma, metinler bağımsız | sahne ortası eklemeye zaman-tesadüfü kilitlenme | metin-doğrulamalı `--cal` |
| Tüm dosya boyunca yavaş artan sapma | fps/dişilim farkı | kapsam dışı — lineer düzeltme gerekir |
| Son ~3dk hiç yok / yanlış içerik | alternatif final | kuyruk kuralı + elle gözden geçir |
| Ara bölgede 20+ cue yok | ek sahne düşürme (doğru) | envanteri raporla, kullanıcı doğrulasın |
| Anchor < 5 | referans/desynced aynı film değil ya da çok farklı kurgu | girdileri teyit et |
