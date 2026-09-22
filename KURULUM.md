# BIST Emir Bozkurt Taraması

Her gün BIST'in tamamını TradingView'in **resmî tarayıcı API'si** üzerinden tarar,
Emir Bozkurt kriterlerini hesaplar, sonucu `data/latest.json` dosyasına yazar.
Akşam bülteni bu dosyayı okuyup raporu üretir.

* **Maliyet: 0 TL.** API anahtarı gerekmez.
* **Elle iş: yok.** Kurulumdan sonra tamamen otomatik.
* Çalışma saati: hafta içi **18:20 (TR)** — BIST kapanışından 20 dk sonra.

## Dosyalar

| Dosya | Yeri | Ne yapar |
|---|---|---|
| `tarama.py` | kök dizin | Taramayı yapar, JSON üretir |
| `bist-tarama.yml` | `.github/workflows/` | Her gün 18:20'de çalıştırır |
| `data/` | kök dizin | **Bot üretir, elleme** |

## Kriterler

| Kriter | Nasıl ölçülüyor |
|---|---|
| Aşırı satım | Kapanış ≤ Bollinger alt bandı (20,2), veya RSI < 30 |
| Hacim patlaması | Günlük hacim ÷ 10 günlük ortalama ≥ **2×** |
| Düşen bıçak (eleme) | MACD 0 altında **ve düşüyor** (sinyalin altında) **ve** fiyat 50MA altında |
| Dönüş teyidi | MACD 0 üstünde **veya** sinyalin üstüne çıkmış |
| Sermaye işlemi (eleme) | Günlük değişim ±%15'i aşıyor (bedelsiz/bölünme düzeltmesi) |
| **Tabloya girme** | aşırı satım **ve** dönüş teyidi **ve** hacim teyidi **ve** sermaye işlemi değil |

> Kritik ayrıntı: gerçek diplerde MACD zaten sıfırın altındadır ve fiyat 50MA'nın
> altındadır. Bu yüzden "düşen bıçak" elemesi MACD'nin **yönüne** bakar — sinyalin
> üzerine çıkmışsa bu dönüşün başlangıcıdır, elenmez.

Eşiği değiştirmek için `tarama.py` içindeki `HACIM_KAT = 2.0` satırını düzenle.

## Çıktı (`data/latest.json`)

```jsonc
{
  "tarih": "2026-09-22",
  "aktif_mod": "anonim",         // veya "oturumlu"
  "hisse_sayisi": 620,           // oturumlu modda ~630
  "rsi_mevcut": true,
  "hala_eksik": ["KRDMD", ...],  // taramaya girmeyen kodlar
  "notlar": [ ... ],             // her adımın sonucu — sorun teşhisi için
  "tam_kurulum": [ ... ],        // TÜM kriterleri geçenler
  "yakin_adaylar": [ ... ],      // aşırı satım var, dönüş teyidi yok
  "tum_hisseler": [ ... ]        // hepsi (BIST 30 tablosu + teknik sinyal için)
}
```

## Bilinen kapsam boşluğu

TradingView'in **anonim** tarayıcı API'si 620 sembol döndürüyor; oturum açılmış
tarayıcı ekranında 630 görünüyor. Aradaki farkta **KRDMD, EKGYO, ISCTR, KOZAL** var.
Sembol adları doğru, TradingView sayfaları mevcut — sadece anonim erişimin
kapsamı dışındalar.

Bunlar `hala_eksik` alanında listelenir; akşam bülteni o kodların fiyatını tekil
hisse sayfasından alır, teknik göstergelerine "veri yok" yazar.

**İsteğe bağlı çözüm:** `TV_SESSIONID` adlı bir GitHub Secret tanımlanırsa script
TradingView oturumuyla bağlanır ve bu semboller de gelir. Secret tanımlı değilse
ya da reddedilirse **anonim moda düşer ve çalışmaya devam eder** — çerez hiçbir
zaman ana işi durdurmaz.

## Bakım

1. **60 gün kuralı:** GitHub, 60 gün aktivite olmayan repolarda zamanlanmış işleri
   durdurur. Bot commit'leri bunu her gün tazeler.
2. **Çerez süresi:** `TV_SESSIONID` periyodik olarak geçersizleşir. O zaman
   `aktif_mod` sessizce `anonim`e döner — sistem çalışmaya devam eder.
3. **Teşhis:** Bir sorun olursa `data/latest.json` içindeki `notlar` alanına bak;
   hangi adımın neden başarısız olduğu orada yazar.
