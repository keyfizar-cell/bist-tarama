# KRDMD tarama düzeltmesi — kurulum notu (23.09.2026)

## Sorun
KRDMD (portföyde), EKGYO, ISCTR, KOZAL her gün taramaya **boş** geliyordu
(`hala_eksik` listesinde, `ticker_ile_tamamlanan: []`). Sebep: `tarama.py`
içindeki `eksikleri_tamamla` fonksiyonu eksik sembolleri `set_tickers` ile
çekerken **`.set_markets("turkey")` kullanmıyordu**. Kanarya testi bunu
kanıtladı: aynı sorguda THYAO dönüyor ama KRDMD/EKGYO/ISCTR/KOZAL dönmüyordu.

## EN İYİ ÇÖZÜM (kod değişikliği gerektirmez): TV_SESSIONID sırrı
`tarama.py` ZATEN `TV_SESSIONID` GitHub secret'ını destekliyor ve kodun kendi
yorumu şunu diyor: *"oturumlu ~630 sembol (KRDMD, KRDMB, EKGYO, ISCTR, KOZAL
açılır)"*. Bugünkü veride `oturum_cerezi_tanimli: false`, `aktif_mod: anonim`
— yani cookie tanımsız, o yüzden anonim modda 620 sembol geliyor ve tam da bu
4 kod eksik kalıyor.

**Yapılacak:** TradingView'e (ücretsiz hesap yeter) giriş yap → tarayıcı
çerezlerinden `sessionid` değerini kopyala → GitHub repo → Settings → Secrets
and variables → Actions → **New repository secret** → Name: `TV_SESSIONID`,
Value: <sessionid>. Sonra Actions'tan elle tetikle. Büyük olasılıkla KRDMD ve
diğer 3 kod artık ana taramada gelir. (Not: sessionid ~aylarca geçerli;
düşerse kod otomatik anonime döner, iş çökmez.)

## Düzeltme (kod tarafı — cookie'siz yedek)
Cookie koymak istemezsen ya da yetmezse, yeni `tarama.py` tamamlama adımını
bir **deneme matrisine** çevirdi ve `turkey` market'e sabitlenmiş denemeleri
en başa aldı:
1. `turkey market + ticker (tam alan)`  ← en olası çözüm
2. `turkey market + ticker (mini alan)`
3. `global + ticker + kanarya (eski yöntem)`
4. `global + ticker (tam alan)`

İlk **gerçek eksik dolduran** deneme kazanır; hangisinin işe yaradığı
`notlar` alanına yazılır. Hiçbiri getirmezse davranış öncekiyle aynıdır
(`hala_eksik` dolar, ana tarama bozulmaz) — bülten o kodların fiyatını
tekil kaynaktan çeker, teknik göstergeleri "veri yok" yazar. Yani bu
değişiklik **ana taramayı bozamaz** (tümü try/except, sadece tamamlama adımı).

## Nasıl yüklenir + doğrulanır
1. `keyfizar-cell/bist-tarama` reposunda kök dizindeki `tarama.py`'yi bu
   dosyayla değiştir (commit et).
2. GitHub → Actions → "BIST Emir Bozkurt Taraması" → **Run workflow** ile
   elle tetikle.
3. Çalışma bitince `data/latest.json` içindeki şu alanlara bak:
   - `ticker_ile_tamamlanan` → KRDMD vb. burada görünüyorsa **düzeldi**.
   - `notlar` → hangi denemenin "ISE YARADI" dediğini gösterir.
   - `hala_eksik` → boşaldıysa tamamdır.
4. Hâlâ boşsa: bu, TradingView'in `turkey` evreninin bu kodları hiç
   servis etmediği anlamına gelir (kod tarafında yapılabilecek bir şey
   kalmaz). O durumda bülten zaten fiyatı tekil kaynaktan çekmeye devam
   eder; teknik göstergeler "veri yok" kalır. Bir sonraki adım olarak
   (istersen) bu 4 kod için ayrı bir OHLCV kaynağından gösterge hesaplama
   eklenebilir — söyle, kurayım.

## EK: Eksik kodlara gösterge hesabı (Yahoo) — onaylandı, eklendi
Cookie/kod düzeltmesi bile KRDMD'yi açmazsa, gösterge hücreleri artık boş
kalmayacak: yeni `tarama.py`, `hala_eksik`'te kalan her kod için Yahoo
Finance'ten (KOD.IS, ~1 yıl OHLCV) **RSI(14)/MACD(12,26,9)/Bollinger(20,2)/
EMA50** hesaplayıp kaydı ekler (kaynak: "yahoo (gosterge hesabi)"). Bu kayıtlar
mevcut kriter mantığından geçtiği için Emir Bozkurt taramasına da tutarlı
biçimde girer. tv_sinyal Yahoo'da olmadığından "veri yok" kalır.
- Bunun için **workflow'a `yfinance` bağımlılığı** eklendi → yeni
  `bist-tarama.yml`'i de repodaki `.github/workflows/bist-tarama.yml` ile
  değiştir (pip satırına `yfinance` eklendi; ayrıca `TV_SESSIONID` env'i zaten
  vardı).
- yfinance bu Cowork ortamında 403 alır ama GitHub Actions'ta açık internetle
  çalışır; hepsi try/except içinde, ana taramayı bozamaz.

Yükleme sırası: (1) `tarama.py` değiştir, (2) `.github/workflows/bist-tarama.yml`
değiştir, (3) isteğe bağlı `TV_SESSIONID` secret'ı ekle, (4) Actions'tan elle
tetikle, (5) `latest.json` → `ticker_ile_tamamlanan` / `notlar` / `hala_eksik`
+ KRDMD kaydında `veri_kaynagi` ve gerçek RSI/MACD değerlerini doğrula.

Not: Bu ortamdan `scanner.tradingview.com` ve Yahoo kapalı olduğu için
düzeltmeleri burada canlı test edemedim (yalnızca sözdizimi doğrulandı);
gerçek doğrulama yukarıdaki elle tetikleme ile repoda yapılır.
