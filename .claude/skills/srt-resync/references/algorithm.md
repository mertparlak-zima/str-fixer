# Hizalama Algoritması Referansı

## Problem modeli

Kaymış altyazı = farklı kurgudan çevrilmiş kaynak. İki dosya arasında:

- **Parçalı sabit offset merdiveni**: hedef kurguda olmayan her ek sahne,
  kaynaktaki tüm sonraki cue'ları o sahnenin süresi kadar ileri taşır.
  Offset tekdüze artar, basamaklar ek sahne sınırlarındadır.
  (Örnek vaka: 0 → +59.6 → +261 → +311 → +510 → +588 → +729 → +743 → +818
  → +876 → +928 → +961.8/965 s; toplam +15.5 dk, T2 SE ≈ +16 dk ile uyumlu.)
- **Sahne-dışı cue'lar**: kaynak kurgunun ek sahnelerindeki diyaloglar
  hedefte yok → düşürülmeli. Kaynağın ek **ekran-yazıları** (bilgisayar
  metni, "YEDEK GÜÇ" gibi) hedefte aynı anda var ama referans altyazıda
  cue yok → doğru offset ile kalmalı.
- **Yapısal farklar**: çevirmen cue birleştirir/böler, referans şarkı
  sözü ve ünlem cue'ları ekler → index eşliği YOKtur, yalnız zaman
  yakınlığı ve içerik kullanılabilir.

## Pipeline (scripts/resync_srt.py)

1. **Kodlama tespiti** (fix_srt ile aynı imza-bayt yöntemi) ve parse.
2. **Anchor zinciri walk'u**: güncel offset'in ±1s penceresinde aday;
   kabul = ortak token (isim/rakam) **veya** |dt| ≤ 0.55. Offset = son 7
   anchor'ın medyanı. 5 miss → 2+ ortak tokenli cue ileriye taranarak
   yeniden kilitleme (dt sınırsız ileri).
3. **İki yönlü segment uzatma**: segment uçlarından aynı offset ile geri/
   ileri doldurma (köprü cue'ları geri kazanır).
4. **Çatışma çözümü**: aynı TR veya EN indeksini claim eden segmentler
   arasında ±4 pencerede **ov-ağırlıklı yoğunluk** kazanır (ortak tokenli
   "altın" anchor 5-9x ağırlık — çeviri çiftleri neredeyse hep doğrudur).
5. **Ağırlıklı LIS**: monoton (i ve j artan) en yüksek destekli zincir.
   Tek başına kalan sahte anchor'lar zinciri bloklayamaz.
6. **Aykırı budama + segmentleme**: segment medianından >2.5s sapan
   anchor atılır; komşu offset sıçraması >1.2s = segment sınırı.
7. **Gap sınıflama**:
   - anchor: kendi segment offseti
   - aynı-zaman-çizgisi gap (iki tarafın offseti eşit): **kalır** (ekran
     yazıları, çevirmen ekstra cue'ları doğru zamanda durur)
   - insertion gap (offsetler farklı): `m_p > E2+0.1` ve `m_n < E1-0.1`
     → ek sahne içi → **düşür**; aksi halde EN-faaliyet (±3.5s referans
     cue'u) varsa ilgili offsetle kal, yoksa düşür
   - kuyruk (son anchor sonrası): EN-faaliyeti yoksa düşür (kaynağın
     alternatif finali vb.)
8. **Montaj**: monotonluk, min süre 0.3s, gerçek çakışma kırpma (bitişik
   cue stili normaldir), yeniden numaralama, BOM'suz UTF-8 + CRLF.

## Başarısızlık modu: zaman-tesadüfü zehirlenmesi (en önemli ders)

Diyalog-yoğun bölgede referans cue yoğunluğu ~1/3-4s'dir. Yanlış (eski)
offsetle taranan bir TR cue'u ±0.5s'de mutlaka BİR referans cue'u bulur.
Sonuç: sahnenin ortasına giren küçük eklemelerde (+10-80s) walk farkı
hiç anlamadan yanlış çiftlere kilitlenir; zincir offset'i hiç
"eskitmez", sessizce yanlış içerik eşleşmeleriyle devam eder.

**Belirtiler** (süpürme denetiminde görülür): TR metni ile en yakın EN
metni çeviri değil (ör. "Ölümden bile mi?" ↔ "Yeah, I guess, 45"), ±2-6s
küçük sistematik sapmalar, içeriğin ~30-75s kayması.

**Otomatik çözüm denemeleri ve neden başarısız olduğu** (tekrar
denemeye gerek yok):
- süre-uyum şartı eklemek: çevirmen cue birleştirdiği için gerçek
  çiftlerin çoğu da eleniyor
- süre-uyumlu ardışık run arayan re-lock sondası: yoğun diyalogda yanlış
  runlar da oluşuyor, offset merdivenini parçalıyor
- global Hough rejim keşfi: arka plan oyları gerçek basamakları gömüyor

**İşleyen çözüm = metin-doğrulamalı manuel kalibrasyon:**
1. Sapılan bölgede ayırt edici çeviri çiftleri ara (substring taraması:
   isimler, yıl/rakamlar, nadil ifadeler; örn. "1984", "Adios",
   "Tatile ihtiyacım var" ↔ "I need a vacation").
2. Çiftin TR ve EN zamanlarından gerçek `dt` hesapla; bölge boyunca
   3-4 çiftle doğrula (±2s içinde tutarlı olmalı).
3. `--cal A:B:OFFSET` ile bölgeyi sabitle (pencere >±2s sarsıyorsa böl).
4. Kalibrasyon öncesi/sonrası sınır cue'larını süpürmede gözle doğrula.
5. Kalibre bölgedeki anchor'lar otomatik olarak devre dışı kalır
   (script CAL aralıklarındaki anchor'ları düşürür).

## Sınır durumları

- **Küçük eklemeler** (<~10s) pencere toleransının altında kalabilir →
  ±1-2s'lik yerel kayma olarak görünür; izlenebilirliği bozmuyorsa
  dokunma, bozuyorsa kalibre et.
- **Alternatif final**: kaynağın finali hedefinkinden farklıysa (SE
  park-finali gibi) kuyruk kuralı düşürür; hedef finalin kısa
  anlatımı kaynaktaki farklı kurguda olabilir → eksik kabul edilir,
  elle eklenebilir (nadiren gerekir).
- **Farklı dişilim (fps)**: basamaklar yerine sürekli kayma görürsen
  (rejim egimleri >5s/saat) lineer düzeltme gerekir — bu script
  kapsamı dışı, elle değerlendir.
- Referans **SDH** olabilir (şarkı sözü/[ses] cue'ları) — zararsız,
  sadece referansın cue sayısını artırır.
