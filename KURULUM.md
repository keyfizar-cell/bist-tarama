# BIST Emir Bozkurt Taraması — Kurulum

Her gün BIST'in tamamını TradingView'in **resmî tarayıcı API'si** üzerinden tarar,
Emir Bozkurt kriterlerini hesaplar, sonucu `data/latest.json` dosyasına yazar.

* **Maliyet: 0 TL.** TradingView hesabı, API anahtarı, kredi kartı gerekmez.
* **Elle iş: yok.** Kurulumdan sonra tamamen otomatik.
* Akşam bülteni bu dosyayı okuyup Emir Bozkurt bölümünü gerçek verilerle doldurur.

---

## Kurulum (tek seferlik, ~5 dakika)

### 1. Yeni repo aç
GitHub'da **New repository** → ad: `bist-tarama` → **Public** seç → Create.

> **Neden Public?** Public repolarda GitHub Actions dakikaları **sınırsız ve ücretsiz**.
> Private'ta ayda 2.000 dakika ücretsiz — bu iş ayda ~45 dakika sürer, o da yeterli.
> Repoda kişisel veri yok (sadece herkese açık borsa fiyatları), Public güvenli.

### 2. Dosyaları yükle
Repoya şu üç dosyayı ekle (Add file → Upload files):

```
tarama.py
.github/workflows/bist-tarama.yml
KURULUM.md
```

> Web arayüzünden klasörlü dosya yüklemek için: "Create new file" deyip
> ad kutusuna `.github/workflows/bist-tarama.yml` yaz — klasörleri otomatik oluşturur.

### 3. Actions'a yazma izni ver
Repo → **Settings** → **Actions** → **General** → en altta
**Workflow permissions** → **Read and write permissions** seç → Save.

*(Bu olmadan sonuçları repoya işleyemez.)*

### 4. İlk çalıştırmayı elle tetikle
Repo → **Actions** sekmesi → soldan **BIST Emir Bozkurt Taraması** →
sağda **Run workflow** → Run.

1-2 dakika sürer. Yeşil tik geldiyse `data/latest.json` oluşmuştur — aç ve bak.

### 5. Bana repo adını söyle
`kullaniciadin/bist-tarama` şeklinde. Akşam bülteni görevini bu dosyayı
okuyacak şekilde bağlayayım.

---

## Çalışma saati

`cron: '20 15 * * 1-5'` = **hafta içi 18:20 (TR)**.
BIST 18:00'de kapanır, bülten 18:45'te gider — arada 25 dakika pay var.

GitHub'ın zamanlanmış işleri yoğun saatlerde birkaç dakika gecikebilir; 25 dakikalık
pay bunun için. Gecikme sorun olursa cron'u `'10 15 * * 1-5'` yapabilirsin.

---

## Kriterler (senin kurallarınla birebir)

| Kriter | Nasıl ölçülüyor |
|---|---|
| Aşırı satım | Kapanış ≤ Bollinger alt bandı (20,2) — RSI varsa <30 da sayılır |
| Hacim patlaması | Günlük hacim ÷ 10 günlük ort. ≥ **2×** |
| Düşen bıçak (eleme) | MACD 0 altında **ve düşüyor** (sinyalin altında) **ve** fiyat 50MA altında |
| Dönüş teyidi | MACD 0 üstünde **veya** sinyalin üstüne çıkmış (= sıfıra yakın pozitif eğilim) |
| **Tabloya girme** | aşırı satım **ve** dönüş teyidi **ve** (hacim ölçülebiliyorsa patlama var) |

> Kritik ayrıntı: gerçek diplerde MACD zaten sıfırın altındadır ve fiyat 50MA'nın
> altındadır. Bu yüzden "düşen bıçak" elemesi MACD'nin **yönüne** bakar —
> sinyalin üzerine çıkmışsa bu dönüşün başlangıcıdır, eleme yapılmaz.
> Bu kural 5 senaryoyla test edildi.

Eşiği değiştirmek istersen `tarama.py` içindeki `HACIM_KAT = 2.0` satırını düzenle.

---

## Çıktı formatı (`data/latest.json`)

```jsonc
{
  "tarih": "2026-09-22",
  "hisse_sayisi": 500,
  "rsi_mevcut": true,            // API RSI verdiyse true
  "tam_kurulum": [ ... ],        // TÜM kriterleri geçenler
  "yakin_adaylar": [ ... ],      // aşırı satım var, dönüş teyidi yok (ilk 10)
  "tum_hisseler": [ ... ]        // hepsi — BIST 30 tablosu ve teknik sinyal için
}
```

`tum_hisseler` içinde her hisse için `tv_sinyal` alanı var
(GÜÇLÜ AL / AL / NÖTR / SAT / GÜÇLÜ SAT) — TradingView'in kendi teknik özeti.
Bülten bunu BIST 30 tablosundaki "Teknik Sinyal" sütununda kullanacak.

---

## Bakım

Neredeyse yok. İki şeye dikkat:

1. **60 gün kuralı:** GitHub, 60 gün hiç aktivite olmayan repolarda zamanlanmış
   işleri durdurur. Bot commit'leri bunu her gün tazeliyor, ama repo bir süre
   boş kalırsa Actions sekmesinden "Enable workflow" demen gerekebilir.
2. **Alan uyumu:** `RSI` / `SMA50` alanlarının API'de bulunduğu doğrulanamadı
   (dokümantasyon sayfasında görünmedi). Script bunları **önce deniyor**, API
   reddederse otomatik olarak çekirdek alan setine düşüyor ve `rsi_mevcut: false`
   yazıyor. Yani her iki durumda da çalışır — ilk çalıştırma hangisi olduğunu gösterir.
