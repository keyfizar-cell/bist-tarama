# BIST Portföy Otomasyonu — SİSTEM DURUMU (tek kaynak)

> **Son güncelleme: 07.11.2026** · Bu dosya sistemin GÜNCEL hâlinin tek kaynağıdır.
> Claude Code oturumları ve zamanlanmış görevler işe başlamadan önce bunu okur.
> Ham adres: `https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/SISTEM_DURUMU.md`
> Buradaki bilgi bir görev talimatındaki veya başka bir sohbetten gelen dosyadaki
> bilgiyle çelişirse **bu dosya geçerlidir** (daha yenidir).

---

## 1. DEĞİŞİKLİK KURALLARI (birinin yaptığını diğeri bozmasın)

1. **Repo kodunu yalnız Claude Code oturumu değiştirir** (Alpay'ın isteğiyle). Zamanlanmış
   görevler repoya yazmaz; kod önerisini e-postayla yama olarak verir.
2. **Yama her zaman repodaki GÜNCEL dosyanın üzerine yapılır.** Önce dosyayı
   `raw.githubusercontent.com/.../main/<dosya>` adresinden çek, sürüm numarasını bu
   dosyadaki tabloyla karşılaştır. Yeni sürüm numarası buradakinden BÜYÜK olmalı.
3. **Başka bir sohbetten gelen dosya eski bir sürüme dayanıyorsa birebir kopyalanmaz**;
   yalnız yeni işlevi güncel dosyaya eklenir. Bölüm 6'daki KALDIRILANLAR geri getirilmez.
4. **Her değişiklikten sonra bu dosya aynı commit'te güncellenir**: Bölüm 3 sürüm tablosu
   ve Bölüm 8 değişiklik günlüğü (en yeni üstte).
5. **Zamanlanmış görev talimatları repodadır: `gorevler/*.md`** (Aşama 1, 07.11.2026). Görevin
   davranışı bu dosyalarda değiştirilir; her değişiklik commit'lenir ve `araclar/gorev_kontrol.py`
   (iş akışı "Görev Talimatı Kontrolü") geçmelidir. Görevin kendisinde yalnız kısa **İNCE BAŞLATICI**
   (metinleri: `gorevler/BASLATICILAR.md`) ve bültenlerde sondaki EK bloğu durur. Başlatıcı veya EK
   bloğu değiştirilecekse görev hemen önce `get_trigger` ile YENİDEN okunur; okunduktan sonra
   değiştiyse değişiklik iptal edilip yeni hâl üzerinden yapılır.
6. Araştırma görevi bültenlerin yalnız "═══ EK ÜCRETSİZ KAYNAK ENTEGRASYONU" bloğunu
   otomatik değiştirebilir (Alpay yetkisi, 29.09.2026). O bloktan önceki metne,
   Sağlık Nöbeti'ne ve kendi talimatına dokunmaz.
7. Tüm betiklerin ortak güvenlik ilkesi korunur: **ana taramayı asla bozmaz, her durumda
   kendi JSON dosyasını yazar, `exit(0)` ile biter.**

---

## 2. GÜNLÜK AKIŞ (hafta içi, TR saati)

```
08:00  Sabah Portföy Brifingi  ── latest.json (dünkü kapanış), kap.json, fon.json, geri_alim.json,
                                   Google Drive portföy dosyası, web → e-posta
09:37  Veri Kaynağı Alternatif Araştırması ── sağlık kontrolleri + kaynak araştırma → (gerekirse) e-posta
18:20  Cloudflare Worker "bist-tetik" → GitHub App ile workflow_dispatch
        └─ "BIST Emir Bozkurt Taraması" (tarama.py) → data/latest.json, data/<tarih>.json, data/status.json  (~18:45 iner)
             └─ bitince (workflow_run) paralel:
                 ├─ "BIST KAP Bildirim Taraması"  (kap_tarama.py)  → data/kap.json, data/geri_alim.json
                 ├─ "BIST Fon Taraması"           (fon_tarama.py)  → data/fon.json
                 ├─ "YouTube Emir Bozkurt Takip"  (youtube_tarama.py + youtube_konuk.py + youtube_kanallar.py)
                 │                                 → data/youtube_emir.json, data/youtube_konuk.json,
                 │                                   data/youtube_kanallar.json
                 │    └─ bitince: "Sosyal Nabız" (sosyal_nabiz.py) → data/sosyal_nabiz.json
                 └─ "Bülten Girdisi Hazırla"      (bulten_hazirla.py; ana tarama VE KAP taraması sonrası)
                                                   → data/bulten_girdi.json
19:05  Günlük Portföy Bülteni ── tarama inene kadar 15 dk'da bir bekler (son 23:45) → e-posta
00:30  BIST Tarama Sağlık Nöbeti ── tazelik/kalite/bülten gitti mi; gitmediyse bülteni yeniden başlatır → push
```

BIST tam gün tatillerinde görevler çalışmaz (listeler görev talimatlarında).

**Hafta sonu (08.11.2026):** "YouTube Emir Bozkurt Takip" Cumartesi ve Pazar 13:17 TR'de (10:17 UTC, `schedule`)
kendiliğinden çalışır — Gemini kotası 7 güne yayılır, Pazartesi bülteni hafta sonu videolarını özetli alır.
Ardından "Sosyal Nabız" ÇALIŞMAZ (borsa kapalı; cuma verisinin üzerine yazmasın).

---

## 3. REPO BİLEŞENLERİ — GÜNCEL SÜRÜMLER

| Bileşen | Sürüm | Tetik | Çıktı | Not |
|---|---|---|---|---|
| `tarama.py` + `bist-tarama.yml` ("BIST Emir Bozkurt Taraması") | — | workflow_dispatch (Cloudflare Worker, 15:20 UTC) | `latest.json`, `<tarih>.json`, `status.json` | TradingView screener birincil; yfinance/isyatirimhisse yedek. Secret: `TV_SESSIONID` |
| `kap_tarama.py` + `kap-tarama.yml` | **v3.4** | workflow_run + dispatch | `kap.json`, `geri_alim.json` | Kümülatif geri alım: `kumulatif_kaynak` = `sirket_beyani` \| `tablo_program`. Bültene YALNIZ `sirket_beyani` yazılır |
| `fon_tarama.py` + `fon-tarama.yml` | v1.0 | workflow_run + dispatch | `fon.json` | tefasmak 1.0.1 (+pytefas yedek) |
| `youtube_tarama.py` | **v2.3** | workflow_run + dispatch | `youtube_emir.json` | Video listesi: kanal RSS → playlist RSS → YouTube Data API. Transkript: **yalnız Gemini** (YouTube URL, `fps=0.1`). Aynı video tekrar işlenmez. **v2.3 kota yedeği:** günlük kotası dolan model o çalışmada atlanır, sıradaki modelle (en sonda flash-lite) devam edilir; dakikalık sınırda 60 sn bekler. Konuk ve kanal betikleri de bunu kullanır |
| `youtube_konuk.py` + `konuk_takip.json` | **v1.0** | aynı iş akışında 2. adım | `youtube_konuk.json` | Konuk uzmanların (şu an: Işık Ökte) son 7 gün videoları: Data API arama + Gemini; kişi başı ≤2 yeni video/çalışma, 30 gün saklama |
| `youtube_kanallar.py` + `kanal_takip.json` | **v1.2** | aynı iş akışında 3. adım | `youtube_kanallar.json` | 25 kanal (Finansal Özgürlük + 08.11.2026'da eklenen 26 kanaldan 24'ü; EKONOMİBİZ ve Burak Aktaş her gün yüklediği için `liste_disi`). Kanal kimliği Data API `forHandle` ile bir kez bulunur ve saklanır; liste RSS → Data API; shorts (<3 dk) ve canlı yayın elenir. **Bütçe:** çalışma başına TOPLAM ≤20 video (08.11.2026'da 10→20; gerçek kota `kota_gunlugu` ile ölçülüyor), kanallar arası sırayla (tur başına kanal başı 1, en yeni önce); işlenemeyenler `bekleyenler`'de başlık+link ile bekler. **Günlük yükleyen kuralı:** son 7 günde ≥5 uzun video yükleyen kanal `liste_disi` (işlenmez, bültene girmez); kalıcı çıkarılanlar `kanal_takip.json` → `liste_disi` dizisinde, hiç taranmaz; `zorla_takip: true` muaf. Tam transkript alınmaz (yalnız özet alanları) |
| `youtube_kanallar.json` | Ek kanallar (şu an: Finansal Özgürlük @finansal_ozgurluk): kanal kimliği Data API `forHandle` ile bir kez bulunur ve saklanır; liste RSS → Data API; shorts (<3 dk) ve canlı yayın elenir; Gemini ile özet + ana mesaj + bahsedilen hisseler + konuşmacının kendi çekinceleri + içerik türü; kanal başı ≤2 yeni video/çalışma, 30 gün saklama |
| `sosyal_nabiz.py` + `sosyal-nabiz.yml` ("Sosyal Nabız") | **v1.3** | YouTube takibi bitince (workflow_run) + dispatch | `sosyal_nabiz.json` | Ücretsiz: (1) takip edilen + son 2 günün en çok yorum alan borsa videolarının yorumlarında BIST kodu sayımı (Data API ~130 birim/gün; kelime olan kodlar yalnız #/$/"hisse" ile); (2) Gemini + Google Search ile Reddit/Ekşi/forum taraması (ücretsiz katmanda arama kotası 0 → 429 beklenir; o zaman akşam bülteni Reddit/Ekşi'yi kendi WebSearch'üyle tarar; 2.5 modelleri yeni kullanıcıya kapalı; kaynaksız sonuç atılır); (3) ipucu işareti (hacim_orani ≥2 → 🔥) ve 5/20 işlem günü getiri karnesi. Kullanıcı adı saklanmaz |
| `youtube-tarama.yml` ("YouTube Emir Bozkurt Takip") | v2.4 | workflow_run + dispatch + hafta sonu schedule (Ct/Pz 10:17 UTC) | — | Harici paket yok (yalnız standart kütüphane) |
| `gorevler/*.md` (4 görev talimatı) + `gorevler/BASLATICILAR.md` | 1 | — | — | Zamanlanmış görevler her çalışmada `main`'den çeker |
| `araclar/gorev_kontrol.py` + `gorev-kontrol.yml` ("Görev Talimatı Kontrolü") | 1 | push/PR (gorevler/**) | — | Talimat dosyalarında zorunlu ifadeler, asgari uzunluk, EK bloğu yerinde mi |
| `bulten_hazirla.py` + `bulten-hazirla.yml` ("Bülten Girdisi Hazırla") | **v1.0** | workflow_run (ana tarama, KAP) + dispatch | `bulten_girdi.json` | Aşama 2: akşam bülteninin kurallı hesapları (Emir Bozkurt 7a/7b + yakın adaylar, 7c geçmişi, BIST30, teknik plan, retail radar, geri alım özeti). Önce testler çalışır. **Bülten henüz bu dosyayı kullanmıyor** (gözlem dönemi) |
| `araclar/portfoy_hesapla.py` | **v1.0** | yalnız görev oturumunda (yerel) | yerel `/tmp` dosyası | Portföy tablosundan açık pozisyonlar, ağırlık, maliyete göre K/Z, 7c "Portföy Kâr" (kapalı ve açık lotlar ayrı). **Gizlilik: çıktı repoya/data/'ya yazılamaz.** Bülten henüz kullanmıyor (gözlem dönemi) |
| `testler/` + `testler.yml` ("Testler") | — | push/PR (*.py, testler/**) | — | `python -m unittest discover -s testler` |

### Secret'lar (GitHub → Settings → Secrets → Actions)
| Secret | Durum | Kullanan |
|---|---|---|
| `TV_SESSIONID` | tanımlı | tarama.py |
| `GOOGLE_API_KEY` | tanımlı (AI Studio `AQ.` anahtarı) | Gemini (her iki YouTube betiği) |
| `YOUTUBE_API_KEY` | tanımlı (07.11.2026; Google Cloud "My First Project", yalnız YouTube Data API v3 ile kısıtlı) | YouTube Data API (konuk araması + Emir RSS yedeği) |
| `GEMINI_MODEL` | opsiyonel | model zorlamak için |
| `WEBSHARE_PROXY_USERNAME/PASSWORD` | tanımlı ama **kullanılmıyor** — silinebilir | — |

---

## 4. VERİ DOSYALARI (hepsi `data/`, bot üretir, elle değiştirilmez)

| Dosya | Önemli alanlar |
|---|---|
| `latest.json`, `<tarih>.json` | `tarih`, `uretim_zamani_utc` (≥15:15 UTC = kapanış verisi), `tum_hisseler[]`, `hala_eksik`, `aktif_mod`, `rsi_mevcut` |
| `status.json` | son tarama: `sonuc`, `zaman_utc`, `tetik`, `url` |
| `kap.json` | portföy kodları için son ~4 gün KAP bildirimleri |
| `geri_alim.json` | 01.09.2026'dan piyasa geneli geri alım; `portfoy_ozet[KOD]`: `kumulatif_kaynak`, `kumulatif_lot`, `sermaye_orani_yuzde`, `detay_bildirim_tarih`. `kumulatif_tutar_tl` bültene YAZILMAZ |
| `fon.json` | `fonlar{KOD:{son_fiyat, fiyat_tarih, getiriler, icerik}}`, `basari_sayisi`, `hata_sayisi` |
| `youtube_emir.json` | `surum`, `transkript_var`, `son_basarili_utc`, `video_liste_kaynagi`, `en_yeni_video{baslik, yayin_tarihi, url, transkript, transkript_kaynagi, ozet, bahsedilen_hisseler}`, `hata`, `denemeler` |
| `bulten_girdi.json` | `kaynak{tarih, kapanis_verisi}`, `emir_bozkurt{7a_watchlist, 7b_diger, yakin_adaylar}`, `sinyal_gecmisi{satirlar, ozet}`, `bist30`, `teknik_plan{KOD:{giris, stop, tp1, tp2, h52_konum_yuzde, rsi, macd, tv_sinyal}}`, `retail_radar`, `geri_alim{satirlar}` (kümülatif yalnız şirket beyanıysa dolu), `hata` |
| `youtube_kanallar.json` | `kanallar{AD:{handle, channel_id, kanal_adi, not, aday_sayisi, son7_uzun_video, liste_disi, videolar[{baslik, yayin_tarihi, sure_dk, atlandi, ana_mesaj, ozet, bahsedilen_hisseler, konusmacinin_riskleri, icerik_turu, islendi_utc}], bekleyenler[], son_basarili_utc, hata}}`, `liste_disi[]`, `butce{toplam_sinir, islenen, bekleyen, kota_bitti}` |
| `youtube_konuk.json` | `kisiler{AD:{not, aday_sayisi, videolar[{baslik, kanal, kisi_konusuyor, atlandi, ozet, bahsedilen_hisseler}], son_basarili_utc, hata}}` |

---

## 5. ZAMANLANMIŞ GÖREVLER

Talimat dosyaları: `gorevler/sabah_brifingi.md`, `gorevler/aksam_bulteni.md`, `gorevler/saglik_nobeti.md`,
`gorevler/veri_kaynagi_arastirma.md`. Görevlerde yalnız İNCE BAŞLATICI (+ bültenlerde EK bloğu) var.

| Görev | ID | Zaman | Okur | Yazar / yapar |
|---|---|---|---|---|
| Sabah Portföy Brifingi | `trig_01DaVTFUontesJ7gXp78zAqV` | hafta içi 08:00 TR | latest/kap/fon/geri_alim.json, Drive portföy, web, Twelve Data (NVO, SPY/QQQ/DIA) | e-posta |
| Günlük Portföy Bülteni | `trig_01UjjJQe3p9x4D5SZc484Ryt` | hafta içi 19:05 TR | latest/<tarih>/kap/geri_alim.json, youtube_emir.json (7d), youtube_konuk.json (7e), youtube_kanallar.json (7f), sosyal_nabiz.json (8.5-4), Drive, web, Twelve Data (NVO) | e-posta (konu satırı sabit: "📊 Günlük Portföy Bülteni — GG.AA.YYYY") |
| BIST Tarama Sağlık Nöbeti | `trig_01KGyiz4sASMZ3jUXM67gce8` | hafta içi 00:30 TR | latest/<tarih>/status + kap/geri_alim/fon/youtube_emir/youtube_konuk/youtube_kanallar/sosyal_nabiz.json, Gmail gönderilenler | push; bülten gitmediyse bülteni yeniden başlatır |
| BIST Veri Kaynağı Alternatif Araştırması | `trig_01ViuA5ZKASerVpJMqYkoeoz` | hafta içi 09:37 TR | tüm data dosyaları, web, pypi/github | bültenlerin EK bloğu (otomatik), e-posta, hafıza `/areas/bist-veri-hatti-alternatifleri.md` |

**Bağlantılar (connector) — 06.11.2026 analizi:** Gerekli olanlar Gmail (hepsi), Google Drive
(iki bülten), Claude Code Remote (akşam bülteni, Sağlık Nöbeti, Araştırma), Twelve Data (iki
bülten). Descript, Splice, Canva, Superhuman Docs, Claude Docs hiçbir görevde kullanılmıyor;
Twelve Data Sağlık Nöbeti ve Araştırma'da gereksiz. Bağlantılar yalnız claude.ai arayüzünden
düzenlenebilir (araçla değil). Borsa MCP (saidsurucu) talimatlarda "ekliyse" yedeği olarak geçiyor
ama hiçbir göreve bağlı değil.

---

## 6. KALICI KARARLAR ve KALDIRILANLAR (geri getirme)

- **KALDIRILDI (06.11.2026):** `youtube-transcript-api` ve Webshare/genel proxy ile transkript
  yolu. GitHub Actions IP'lerinden her seferinde RequestBlocked/429 veriyordu. Transkript yalnız
  Gemini ile alınır. `pip install youtube-transcript-api` ve `WEBSHARE_*`/`YT_PROXY_URL` env
  satırları iş akışına geri eklenmez.
- **SEÇİLMEDİ:** ücretli Residential proxy, YouTube çerezi (hesap ban riski).
- **Tetik:** GitHub schedule cron yerine Cloudflare Worker + GitHub App (PAT emekli). Yeni tetik
  mimarisi önerilmez.
- **Geri alım:** kümülatif lot/oran bültene yalnız `kumulatif_kaynak == "sirket_beyani"` ise
  yazılır; `kumulatif_tutar_tl` hiç yazılmaz.
- **Sadeleştirme (24.10.2026):** fon tablosu, aracı kurum listeleri, temettü/bedelsiz/halka arz ve
  ekonomik takvim yalnız SABAH; geri alım detayı ve kapanış tablosu yalnız AKŞAM.
- **GİZLİLİK (07.11.2026):** Repo HERKESE AÇIK (görevler veriyi şifresiz raw adresinden çeker). Portföy
  verisi (pozisyon, maliyet, K/Z, hesap sahipleri) ASLA repoya, `data/` klasörüne, Actions'a, Actions
  günlüğüne, testlere veya bu belgeye yazılmaz; portföy hesabı yalnız zamanlanmış görevin kendi oturumunda
  `araclar/portfoy_hesapla.py` ile yapılır. Testler yalnız kurgusal veri kullanır. (Bu nedenle Actions için
  kurulan Google servis hesabı `GDRIVE_SA_JSON` iptal edildi.)
- **Kişisel değerler (07.11.2026):** e-posta adresi, portföy tablosu Drive kimliği ve yedek pozisyon listesi
  talimat dosyalarında `{E_POSTA}`, `{PORTFOY_DOSYA_ID}`, `{YEDEK_LISTE}` yer tutucularıyla geçer; gerçek
  değerler yalnız görevlerin GİZLİ PARAMETRELER bloğundadır (`gorevler/BASLATICILAR.md`).
  `araclar/gorev_kontrol.py` e-posta / Drive kimliği / pozisyon listesi görürse hata verir. Not: bu değerler
  07.11.2026 öğleden sonra birkaç saat talimat dosyalarında açık kaldı; git geçmişinde duruyor (geçmiş
  yeniden yazılmadı — Alpay kararı).
- **Sosyal medya (07.11.2026):** X/Twitter kazınamaz; resmî X API ücretli (okunan gönderi başı ~$0,005), Grok `x_search`
  ücretli (~$5/1.000 arama) → Alpay kararıyla ŞİMDİLİK YOK (istenirse `XAI_API_KEY` ile eklenebilir). Reddit girişsiz okuma
  403, API onay istiyor → KULLANILMAZ; Reddit/Ekşi/forumlar Gemini + Google Search ile dolaylı taranır.
- **Twelve Data:** yalnız NVO ve ABD ETF'leri için; BIST için çağrılmaz.
- **Yatırım koçu (07.11.2026):** Akşam bülteninde "🧑‍🏫 KOÇ NOTLARI" (Piyasa Pusulası'ndan sonra). Profil Alpay'ın
  Drive'ındaki **"Yatırımcı Profili (Koç)"** Google Docs belgesindedir; repo açık olduğu için içeriği repoya, `data/`'ya,
  SISTEM_DURUMU'na YAZILMAZ. Görev belgeyi başlığıyla bulur. Öğrenme: Alpay bülten/brifing e-postasına "KOÇ: …" (veya "koç …") diye yanıt verir; SORU ise ertesi akşam "❓ Sorunun yanıtı" ile cevaplanır →
  görev Gmail'de bulur → Drive aracı belge gövdesini düzenleyemediği için profili YENİ belge olarak yazar, eskisini çöpe atar.
  Koç ayrıca haftanın son iş günü videolardaki ve tanınmış yatırımcıların (son 3 ay, kaynaklı) YÖNTEMLERİNDEN en fazla 2'sini
  profilin Bölüm 7'sine [deneme] olarak ekler; Alpay'ın "KOÇ: benimse/bırak" yanıtına göre [benimsendi]/[bırakıldı] olur
  (Alpay'ın tercihi her zaman önce gelir). Notlarda bu yöntemler düşünme merceği olarak kullanılır.
  Koç al/sat/miktar önerisi vermez; uyum, portföy bağlantısı, kör nokta, "kendine sor" türünde ≤4 kısa madde yazar.
- Alpay manuel/tekrarlayan bakımdan hoşlanmaz → bakım yükünü azaltan çözüm önceliklidir.

---

## 7. AÇIK KONULAR

1. ~~`YOUTUBE_API_KEY`~~ — 07.11.2026'da eklendi; konuk araması doğrulandı (Işık Ökte: 4 aday, 2'si işlendi).
2. Konuk takibi çalışma başına kişi başı en fazla 2 yeni video işler (`konuk_takip.json` →
   `calisma_basina_en_fazla_yeni_video`); kalanlar sonraki çalışmada işlenir.
3. Geri alım belgesi okunamayan kodlar: VAKBN, GARAN, GUBRF, SAHOL (`detay_durum: satir_yok`).
4. Gereksiz bağlantıların görevlerden kaldırılması (Bölüm 5) — Alpay arayüzden yapacak.
5. **Yatırım koçu** (07.11.2026 kuruldu): ilk gerçek akşam bülteninde "Koç Notları" ve profil okuma/güncelleme
   adımlarının çalıştığı doğrulanacak.

---

## 8. DEĞİŞİKLİK GÜNLÜĞÜ (en yeni üstte)

| Tarih | Ne değişti | Kim |
|---|---|---|
| 10.11.2026 | Koç K2 düzeltmesi: Gmail araması yalnız "Re:" yanıtlarını sayar (bültenin kendi "KOÇ:" alt yazısı yanlış eşleşiyordu), sabah brifingi yanıtları ve "koç" (iki noktasız) da geçerli; SORU türü yanıtlar bir sonraki akşam bülteninde "❓ Sorunun yanıtı" olarak cevaplanır. Sabah 7.5(c) fon tablosuna "Alınabilir mi" sütunu (TEFAS'ta kapalı fonlar: TZV yalnız Ziraat, TSI yalnız İş Bankası Maksimum Hesap) | Claude Code |
| 10.11.2026 | Değişiklik günlüğünün 6 satırı (08–09.11) yanlışlıkla Bölüm 3 tablosuna yazılmıştı → buraya taşındı. Claude Code oturumları için kişisel bulut ortamı "bist-tarama" oluşturuldu (izinli: bigpara, Yahoo query1/2, Mynet Finans, İş Yatırım); zamanlanmış görevlerin ortamı değişmedi. Portföy tablosunda ALTIN sertifikası için Google Finance desteği yok → Mynet IMPORTXML önerildi (tablo Alpay'da) | Claude Code |
| 09.11.2026 | Pazartesi kontrolü: akşam bülteni bulten_girdi.json ile birebir (7a/7b LYDHO, 7c 42/22/20/−%0,04, BIST30 30/30); Koç Notları ve 8.5(4) çalıştı; 7f'de kalan 14 video yine tek satır verilmişti → talimata açık yasak eklendi | Claude Code |
| 08.11.2026 | Bülten 7f (B): kalan videolar tek satır yerine "önemli bilgi özeti" (ana mesaj + en önemli 2-3 madde + kod görüşleri + çekince) — Alpay kararı | Claude Code |
| 08.11.2026 | YouTube takibi hafta sonu da çalışır (Ct/Pz 13:17 TR, Alpay kararı); Sosyal Nabız hafta sonu zamanlı çalışmanın ardından atlanır | Claude Code |
| 08.11.2026 | **Gemini kota yedeği** (Alpay onayı, seçenek 1-2): `youtube_tarama.py` v2.3 (429'da sıradaki model, lite yedek, dakikalık sınırda bekleme) + 5 test; `youtube_kanallar.py` v1.2 (bütçe 20, `kota_gunlugu`); Sağlık Nöbeti'ne "GEMINI KOTASI YETMİYOR" (3 çalışma üst üste kota dolarsa). DeepSeek vb. metin modelleri video izleyemediği için eklenmedi | Claude Code |
| 08.11.2026 | İlk ölçüm (Actions): 27 kanalın tümünün kimliği çözüldü; 10 video özetlendi, 9 bekliyor. Her gün yükleyen 2 kanal (EKONOMİBİZ 15, Burak Aktaş 5 video/7 gün) `kanal_takip.json` → `liste_disi`'ne taşındı | Claude Code |
| 08.11.2026 | **26 YouTube kanalı eklendi** (Alpay listesi); `youtube_kanallar.py` v1.1: toplam video bütçesi + kanallar arası sıralı seçim + `bekleyenler`; her gün video yükleyen kanallar otomatik liste dışı (Alpay kararı); kanal videolarında tam transkript kaldırıldı; iş akışı süresi 75 dk; bülten 7f: en fazla 6 tam + önemli bilgi özeti + bekleyenler; 8 test yeniden yazıldı | Claude Code |
| 07.11.2026 | `sosyal_nabiz.py` v1.2–1.3 (iki 429'dan sonra durur): Actions'ta doğrulandı — YouTube 21 video / 824 yorum işlendi; Gemini Google Search tüm modellerde 429 (ücretsiz kota yok), 2.5 serisi 404 → forum taraması yedeği akşam bülteninin WebSearch'üne bağlandı | Claude Code |
| 07.11.2026 | **Sosyal nabız (ücretsiz):** `sosyal_nabiz.py` v1.0 + "Sosyal Nabız" iş akışı + 9 test; akşam bülteni 8.5'e (4) "Yorum & Forum Nabzı" (🔥 konuşuluyor+hacim / 💬 yalnız konuşma / ⚠️ pompa olabilir, ipucu karnesi); koça kör nokta notu; Sağlık Nöbeti'ne bayatlık/hata kontrolü. X ve Reddit API kullanılmıyor (Bölüm 6) | Claude Code |
| 07.11.2026 | **Koç — yatırımcılardan öğrenme:** akşam talimatına K2.5 (haftalık, kaynaklı ≤2 yöntem) + evrilme kuralı ([deneme]→[benimsendi]/[bırakıldı]); profil belgesine Bölüm 7 "Benimsenen yöntemler" (başlangıç: Marks, Druckenmiller, Dalio) eklendi | Claude Code |
| 07.11.2026 | **Yatırım koçu:** akşam bültenine "KOÇ NOTLARI" (K1 profil okuma, K2 "KOÇ:" yanıtlarından öğrenme, K3 ≤4 ipucu); profil Drive'da "Yatırımcı Profili (Koç)" belgesi (Alpay'ın yanıtlarıyla oluşturuldu); gorev_kontrol zorunlu ifadelerine eklendi. Ek kanal takibi Actions'ta doğrulandı (Finansal Özgürlük: kanal kimliği çözüldü, 1 video Gemini ile işlendi) | Claude Code |
| 07.11.2026 | **Ek kanal takibi:** `youtube_kanallar.py` v1.0 + `kanal_takip.json` (Finansal Özgürlük) + 7 test; iş akışı v2.3 (3. adım); akşam bültenine 7f "Takip edilen kanallar"; Sağlık Nöbeti'ne `youtube_kanallar.json` bayatlık/hata kontrolü | Claude Code |
| 07.11.2026 | **Gizlilik düzeltmesi:** talimat dosyalarından e-posta, Drive kimliği, yedek pozisyon listesi ve gerçek işlem örneği çıkarıldı (yer tutucu); değerler görevlerin GİZLİ PARAMETRELER bloğuna taşındı; kontrol betiğine kişisel veri yasağı eklendi | Claude Code |
| 07.11.2026 | **Aşama 2 (portföy):** `araclar/portfoy_hesapla.py` v1.0 + 9 test (kurgusal çalışma kitabı). Gerçek tabloyla yalnız oturum içinde doğrulandı (sonuçlar burada tutulmaz). Kapalı ve açık lotlar ayrı hesaplanır — eski bülten kuralı aynı kodda hem açık hem kapalı lot varsa yanlış sonuç verebiliyordu. Repo açık olduğu için portföy hesabı Actions'a taşınmadı; servis hesabı iptal | Claude Code |
| 07.11.2026 | **Aşama 2 (1. adım):** `bulten_hazirla.py` v1.0 + "Bülten Girdisi Hazırla" iş akışı + 13 birim testi + "Testler" iş akışı. 06.11 verisiyle doğrulandı: 5 sinyal (7a KTLEV; 7b GUNDG, LYDHO, HEDEF, BULGS) — taramanın 12'lik listesinden farkı bültenin ek güvenlik filtreleri (bb_alt>0, piyasa değeri ≥1 mlr). Akşam bülteni talimatı DEĞİŞMEDİ; dosya en az bir gerçek akşam doğrulandıktan sonra bağlanacak | Claude Code |
| 07.11.2026 | `YOUTUBE_API_KEY` eklendi (Alpay); konuk takibi Actions'ta doğrulandı (Işık Ökte: 4 aday, 2 video Gemini ile işlendi — 7.075 ve 4.702 karakter); Araştırma talimatındaki "AÇIK SORUN" kapatıldı | Claude Code |
| 07.11.2026 | **Aşama 1:** dört görevin talimatı `gorevler/*.md` dosyalarına taşındı; görevlerde İNCE BAŞLATICI + (bültenlerde) EK bloğu kaldı; `araclar/gorev_kontrol.py` + "Görev Talimatı Kontrolü" iş akışı eklendi; Araştırma görevinin bülten düzenleme kontrolü başlatıcı yapısına uyarlandı | Claude Code |
| 07.11.2026 | `SISTEM_DURUMU.md` + `CLAUDE.md` eklendi; dört zamanlanmış göreve "önce bu dosyayı oku" bloğu eklendi (geri kalan metin birebir korundu); Araştırma görevinin (C) (v3.4 canlı) ve (F) (v2.2, yalnız Gemini, konuk takibi, KALDIRILANLAR, `YOUTUBE_API_KEY` notu) bölümleri ve bölüm numaraları (7e) güncel duruma çekildi | Claude Code |
| 07.11.2026 | Akşam bültenine 7e "Konuk uzman videoları" (youtube_konuk.json) eklendi; Sağlık Nöbeti (E) adımına youtube_konuk.json bayatlık kontrolü eklendi | Başka bir Claude oturumu (12:07–12:09 UTC) |
| 07.11.2026 | `youtube_tarama.py` v2.2 (Gemini çağrısı istem/şema/fps parametreli); `youtube_konuk.py` v1.0 + `konuk_takip.json` eklendi; iş akışına konuk adımı. Gelen v2.1 dosyası eski transkript yolunu geri getirdiği için birebir alınmadı, birleştirildi | Claude Code |
| 06.11.2026 | `youtube_tarama.py` v2.1: youtube-transcript-api + proxy yolu kaldırıldı; iş akışından pip/proxy satırları çıktı | Claude Code |
| 06.11.2026 | `youtube_tarama.py` v2.0 (Gemini + Data API yedeği) ve `kap_tarama.py` v3.4 (şirket beyanı kümülatif) kuruldu; `GOOGLE_API_KEY` eklendi, Gemini Actions'ta doğrulandı | Claude Code |
| 05.11.2026 | YouTube takip hattı kuruldu (v1.0 → v1.2: proxy desteği, RSS tekrar deneme, önceki veriyi koruma); Araştırma görevine (F) bölümü eklendi | Claude Code |
