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
                 └─ "YouTube Emir Bozkurt Takip"  (youtube_tarama.py + youtube_konuk.py)
                                                   → data/youtube_emir.json, data/youtube_konuk.json
19:05  Günlük Portföy Bülteni ── tarama inene kadar 15 dk'da bir bekler (son 23:45) → e-posta
00:30  BIST Tarama Sağlık Nöbeti ── tazelik/kalite/bülten gitti mi; gitmediyse bülteni yeniden başlatır → push
```

BIST tam gün tatillerinde görevler çalışmaz (listeler görev talimatlarında).

---

## 3. REPO BİLEŞENLERİ — GÜNCEL SÜRÜMLER

| Bileşen | Sürüm | Tetik | Çıktı | Not |
|---|---|---|---|---|
| `tarama.py` + `bist-tarama.yml` ("BIST Emir Bozkurt Taraması") | — | workflow_dispatch (Cloudflare Worker, 15:20 UTC) | `latest.json`, `<tarih>.json`, `status.json` | TradingView screener birincil; yfinance/isyatirimhisse yedek. Secret: `TV_SESSIONID` |
| `kap_tarama.py` + `kap-tarama.yml` | **v3.4** | workflow_run + dispatch | `kap.json`, `geri_alim.json` | Kümülatif geri alım: `kumulatif_kaynak` = `sirket_beyani` \| `tablo_program`. Bültene YALNIZ `sirket_beyani` yazılır |
| `fon_tarama.py` + `fon-tarama.yml` | v1.0 | workflow_run + dispatch | `fon.json` | tefasmak 1.0.1 (+pytefas yedek) |
| `youtube_tarama.py` | **v2.2** | workflow_run + dispatch | `youtube_emir.json` | Video listesi: kanal RSS → playlist RSS → YouTube Data API. Transkript: **yalnız Gemini** (YouTube URL, `fps=0.1`). Aynı video tekrar işlenmez |
| `youtube_konuk.py` + `konuk_takip.json` | **v1.0** | aynı iş akışında 2. adım | `youtube_konuk.json` | Konuk uzmanların (şu an: Işık Ökte) son 7 gün videoları: Data API arama + Gemini; kişi başı ≤2 yeni video/çalışma, 30 gün saklama |
| `youtube-tarama.yml` ("YouTube Emir Bozkurt Takip") | v2.2 | workflow_run + dispatch | — | Harici paket yok (yalnız standart kütüphane) |
| `gorevler/*.md` (4 görev talimatı) + `gorevler/BASLATICILAR.md` | 1 | — | — | Zamanlanmış görevler her çalışmada `main`'den çeker |
| `araclar/gorev_kontrol.py` + `gorev-kontrol.yml` ("Görev Talimatı Kontrolü") | 1 | push/PR (gorevler/**) | — | Talimat dosyalarında zorunlu ifadeler, asgari uzunluk, EK bloğu yerinde mi |

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
| `youtube_konuk.json` | `kisiler{AD:{not, aday_sayisi, videolar[{baslik, kanal, kisi_konusuyor, atlandi, ozet, bahsedilen_hisseler}], son_basarili_utc, hata}}` |

---

## 5. ZAMANLANMIŞ GÖREVLER

Talimat dosyaları: `gorevler/sabah_brifingi.md`, `gorevler/aksam_bulteni.md`, `gorevler/saglik_nobeti.md`,
`gorevler/veri_kaynagi_arastirma.md`. Görevlerde yalnız İNCE BAŞLATICI (+ bültenlerde EK bloğu) var.

| Görev | ID | Zaman | Okur | Yazar / yapar |
|---|---|---|---|---|
| Sabah Portföy Brifingi | `trig_01DaVTFUontesJ7gXp78zAqV` | hafta içi 08:00 TR | latest/kap/fon/geri_alim.json, Drive portföy, web, Twelve Data (NVO, SPY/QQQ/DIA) | e-posta |
| Günlük Portföy Bülteni | `trig_01UjjJQe3p9x4D5SZc484Ryt` | hafta içi 19:05 TR | latest/<tarih>/kap/geri_alim.json, youtube_emir.json (7d), youtube_konuk.json (7e), Drive, web, Twelve Data (NVO) | e-posta (konu satırı sabit: "📊 Günlük Portföy Bülteni — GG.AA.YYYY") |
| BIST Tarama Sağlık Nöbeti | `trig_01KGyiz4sASMZ3jUXM67gce8` | hafta içi 00:30 TR | latest/<tarih>/status + kap/geri_alim/fon/youtube_emir/youtube_konuk.json, Gmail gönderilenler | push; bülten gitmediyse bülteni yeniden başlatır |
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
- **Twelve Data:** yalnız NVO ve ABD ETF'leri için; BIST için çağrılmaz.
- Alpay manuel/tekrarlayan bakımdan hoşlanmaz → bakım yükünü azaltan çözüm önceliklidir.

---

## 7. AÇIK KONULAR

1. ~~`YOUTUBE_API_KEY`~~ — 07.11.2026'da eklendi; konuk araması doğrulandı (Işık Ökte: 4 aday, 2'si işlendi).
2. Konuk takibi çalışma başına kişi başı en fazla 2 yeni video işler (`konuk_takip.json` →
   `calisma_basina_en_fazla_yeni_video`); kalanlar sonraki çalışmada işlenir.
3. Geri alım belgesi okunamayan kodlar: VAKBN, GARAN, GUBRF, SAHOL (`detay_durum: satir_yok`).
4. Gereksiz bağlantıların görevlerden kaldırılması (Bölüm 5) — Alpay arayüzden yapacak.

---

## 8. DEĞİŞİKLİK GÜNLÜĞÜ (en yeni üstte)

| Tarih | Ne değişti | Kim |
|---|---|---|
| 07.11.2026 | `YOUTUBE_API_KEY` eklendi (Alpay); konuk takibi Actions'ta doğrulandı (Işık Ökte: 4 aday, 2 video Gemini ile işlendi — 7.075 ve 4.702 karakter); Araştırma talimatındaki "AÇIK SORUN" kapatıldı | Claude Code |
| 07.11.2026 | **Aşama 1:** dört görevin talimatı `gorevler/*.md` dosyalarına taşındı; görevlerde İNCE BAŞLATICI + (bültenlerde) EK bloğu kaldı; `araclar/gorev_kontrol.py` + "Görev Talimatı Kontrolü" iş akışı eklendi; Araştırma görevinin bülten düzenleme kontrolü başlatıcı yapısına uyarlandı | Claude Code |
| 07.11.2026 | `SISTEM_DURUMU.md` + `CLAUDE.md` eklendi; dört zamanlanmış göreve "önce bu dosyayı oku" bloğu eklendi (geri kalan metin birebir korundu); Araştırma görevinin (C) (v3.4 canlı) ve (F) (v2.2, yalnız Gemini, konuk takibi, KALDIRILANLAR, `YOUTUBE_API_KEY` notu) bölümleri ve bölüm numaraları (7e) güncel duruma çekildi | Claude Code |
| 07.11.2026 | Akşam bültenine 7e "Konuk uzman videoları" (youtube_konuk.json) eklendi; Sağlık Nöbeti (E) adımına youtube_konuk.json bayatlık kontrolü eklendi | Başka bir Claude oturumu (12:07–12:09 UTC) |
| 07.11.2026 | `youtube_tarama.py` v2.2 (Gemini çağrısı istem/şema/fps parametreli); `youtube_konuk.py` v1.0 + `konuk_takip.json` eklendi; iş akışına konuk adımı. Gelen v2.1 dosyası eski transkript yolunu geri getirdiği için birebir alınmadı, birleştirildi | Claude Code |
| 06.11.2026 | `youtube_tarama.py` v2.1: youtube-transcript-api + proxy yolu kaldırıldı; iş akışından pip/proxy satırları çıktı | Claude Code |
| 06.11.2026 | `youtube_tarama.py` v2.0 (Gemini + Data API yedeği) ve `kap_tarama.py` v3.4 (şirket beyanı kümülatif) kuruldu; `GOOGLE_API_KEY` eklendi, Gemini Actions'ta doğrulandı | Claude Code |
| 05.11.2026 | YouTube takip hattı kuruldu (v1.0 → v1.2: proxy desteği, RSS tekrar deneme, önceki veriyi koruma); Araştırma görevine (F) bölümü eklendi | Claude Code |
