BIST tarama hattı + akşam bülteni SAĞLIK NÖBETİ ve YEDEK GÖNDERİCİ. Amaç: (A) GitHub tarama hattının KRONİK arızasını, (B) tarama kalitesinin bozulmasını, (C) akşam portföy bülteninin GİTMEMESİNİ, (D) GitHub Actions çalışmasının HATA ile bitmesini yakalamak — ve (C) durumunda bülteni YEDEK olarak yeniden başlatmak. Bu görev bülten görevinden bağımsızdır ki bülten çökse bile arıza görülsün ve bülten yine de gitsin. Hafta içi 21:30 UTC'de (00:30 TR) çalışır — bültenin hard deadline'ı 20:45 UTC olduğundan ona 45 dk pay kalır.

ADIMLAR:
1) Bash: date -u +%F ve date -u +%u (6=Cmt, 7=Paz).
2) Hafta sonuysa → hiçbir şey yapma, sessiz bitir.
3) BIST TATİL KONTROLÜ: Bugün aşağıdaki tam gün tatillerden biriyse → sessiz bitir. İş günü farkı hesaplarken bu günleri de iş günü SAYMA.
   2026: 2026-10-29 (Cumhuriyet Bayramı).
   2027: 2027-01-01; 2027-03-10, 2027-03-11, 2027-03-12 (Ramazan Bayramı — yaklaşık); 2027-04-23; 2027-05-17, 2027-05-18, 2027-05-19 (Kurban Bayramı — yaklaşık; 19 Mayıs zaten tatil); 2027-07-15; 2027-08-30 (Zafer Bayramı); 2027-10-29 (Cumhuriyet Bayramı).
   Not: Bayram tarihleri yaklaşıktır; bugün bir bayram civarındaysa ve alarm verecek durum varsa, push atmadan önce WebSearch ile "Borsa İstanbul <tarih> tatil" doğrula. Yarım günler (arife, 28 Ekim) normal iş günüdür.
4) Verileri çek:
   curl -sS --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/latest.json?cb=$(date +%s%N)" -o /tmp/lt.json -w "%{http_code}"
   curl -sS --max-time 30 -o /tmp/td.json -w "%{http_code}" "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/$(date -u +%F).json?cb=$(date +%s%N)"
   curl -sS --max-time 30 -o /tmp/st.json -w "%{http_code}" "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/status.json?cb=$(date +%s%N)"
   Bugünün tarihli dosyası 200 döndüyse onu, aksi halde latest.json'u değerlendir.
5) (A) TAZELİK: Bir dosya "bugünün kapanış verisi" sayılır ancak "tarih" = bugün VE "uretim_zamani_utc" bugün 15:15 UTC veya sonrası ise (daha erken üretilmişse gün içi manuel çalışmadır → bugün için veri YOK say). Son GEÇERLİ kapanış verisinin tarihi ile bugün arasındaki iş günü farkını Python ile hesapla (Cmt/Paz ve 3. adımdaki tatiller hariç).
   - Fark 0 → sağlıklı.
   - Fark 1 → tek günlük gecikme; normal olabilir → bu madde için bildirim YOK.
   - Fark ≥2 → KRONİK ARIZA (bildirilecek).
   - latest.json hiç çekilemezse (HTTP ≠ 200 veya JSON bozuk) → ERİŞİM ARIZASI (bildirilecek).
6) (B) KALİTE (yalnızca değerlendirilen dosyanın tarihi BUGÜN veya DÜN ise): Şunlardan biri varsa KALİTE SORUNU:
   - aktif_mod "oturumlu" değil  VEYA  oturum_cerezi_tanimli false  → TV_SESSIONID süresi dolmuş olabilir
   - rsi_mevcut false
   - hisse_sayisi < 550
   - alan_seti "tam" değil
7) (C) BÜLTEN KONTROLÜ: mcp__Gmail__search_threads ile query = 'in:sent subject:"Portföy Bülteni" newer_than:1d' ara. Konu satırında bugünün tarihi (GG.AA.YYYY) geçen bir e-posta YOKSA → BÜLTEN GİTMEDİ. (Bülten konu formatı: "📊 Günlük Portföy Bülteni — GG.AA.YYYY". Sabah gelen "Portföy Brifingi" e-postası SAYILMAZ.) Gmail aracı hata verirse 1 kez daha dene; yine hata verirse bülten durumunu "bilinmiyor" say ve YEDEK ÇALIŞMAYI YİNE DE BAŞLAT (çift e-posta, hiç e-posta gitmemesinden iyidir).
   ➜ BÜLTEN GİTMEDİYSE (veya durum bilinmiyorsa) YEDEK ÇALIŞMA: mcp__claude-code-remote__fire_trigger(trigger_id="trig_01UjjJQe3p9x4D5SZc484Ryt", text="YEDEK ÇALIŞMA (Sağlık Nöbeti tarafından <saat UTC>'de başlatıldı): Bugünün akşam bülteni gönderilmemiş görünüyor. AKILLI BEKLEME ve send_later KULLANMA, hard deadline geçti sayılır. Elindeki en iyi veriyle (bugünün kapanış taraması varsa onu, yoksa tekil kaynak fiyatlarını kullanarak) bülteni HEMEN kur ve gönder. Başına '⚠️ Yedek çalışma: asıl bülten zamanında gönderilemediği için Sağlık Nöbeti tarafından yeniden başlatıldı' notu koy. Konu satırı değişmez."). fire_trigger hata verirse 1 kez daha dene.
8) (D) ACTIONS SONUCU: /tmp/st.json alanları: sonuc (success/failure/cancelled), zaman_utc, tetik (schedule/workflow_dispatch), url.
   - sonuc "success" değilse VE zaman_utc son 36 saat içindeyse → ACTIONS HATASI (bildirilecek; sonuc + zaman + url'yi ekle).
   - status.json çekilemezse (404 vb.) → arıza SAYMA, yalnızca başka bir bildirim zaten gidiyorsa sonuna "status.json okunamadı" notu ekle.
   - Başka bir sorun bildirilecekse (A/B/C), bildirimin sonuna her durumda son Actions çalışmasının sonuc/zaman/url bilgisini ekle.

9) (E) YAN DOSYALAR (kullanıcı kararı 06.11.2026; yalnız uyarı — yedek çalıştırma/fire_trigger YOK): Bash ile çek:
   for f in kap geri_alim fon youtube_emir youtube_konuk youtube_kanallar sosyal_nabiz; do curl -sS --max-time 30 -o /tmp/$f.json -w "$f:%{http_code}\n" "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/$f.json?cb=$(date +%s%N)"; done
   • kap.json, geri_alim.json, fon.json: üst düzey "uretim_zamani_utc" alanının tarihi ile bugün arasındaki iş günü farkını 5. adımdaki yöntemle hesapla (tatiller hariç). Fark ≥2 → YAN DOSYA BAYAT (dosya adı + son üretim zamanı). fon.json'da hata_sayisi > basari_sayisi ise → YAN DOSYA HATALI. Bir dosya hiç çekilemezse (HTTP ≠ 200) → YAN DOSYA ERİŞİLEMEDİ.
   • youtube_emir.json: uretim_zamani_utc farkı ≥2 iş günü → YOUTUBE BAYAT. Ayrıca dosyada "son_basarili_utc" alanı VARSA (youtube_tarama.py v2.0+) ve bu tarih ile bugün arasındaki iş günü farkı ≥2 ise → YOUTUBE TRANSKRİPT YOK (hata alanının ilk 120 karakterini ekle). Alan YOKSA (eski v1.2) transkript için ayrı uyarı verme; yalnız başka bir bildirim zaten gidiyorsa sonuna "YouTube: transkript_var=<..>, hata=<ilk 80 karakter>" notu ekle.
   • youtube_konuk.json (konuk uzman takibi, 07.11.2026): dosya VARSA ve uretim_zamani_utc farkı ≥2 iş günü ise → YOUTUBE KONUK BAYAT; dosya yoksa (404) henüz kurulmamıştır → arıza SAYMA. Yeni video çıkmaması arıza değildir.
   • youtube_kanallar.json (ek kanal takibi, 07.11.2026): dosya VARSA ve uretim_zamani_utc farkı ≥2 iş günü ise → YOUTUBE KANALLAR BAYAT; dosya yoksa (404) henüz kurulmamıştır → arıza SAYMA. Bir kanalın hata alanı 3 iş günüdür doluysa (son_basarili_utc eski) → KANAL HATASI: <ad> + hatanın ilk 80 karakteri. kota_gunlugu[] son 3 kaydında kota_bitti=true ise → GEMINI KOTASI YETMİYOR: bekleyen <butce.bekleyen> video, dolan modeller <kotasi_dolan_modeller> (Alpay ücretli Gemini seçeneğini değerlendirebilir). Yeni video çıkmaması arıza değildir.
   • sosyal_nabiz.json (yorum & forum nabzı, 07.11.2026): dosya VARSA ve uretim_zamani_utc farkı ≥2 iş günü ise → SOSYAL NABIZ BAYAT; dosya yoksa (404) arıza SAYMA. youtube.hata VE forum.hata ikisi birden doluysa → SOSYAL NABIZ HATALI (ikisinin ilk 60 karakteri). Yalnız forum.hata doluysa arıza sayma (Gemini arama kotası olabilir).
   • Bu maddeler tek başına bülten yedek çalıştırmasını TETİKLEMEZ; yalnız bildirime eklenir.

BİLDİRİM KURALI:
- (A) fark ≥2, erişim arızası, (B) kalite sorunu, (C) bülten gitmedi veya (D) Actions hatası veya (E) yan dosya bayat/hatalı/erişilemedi / YouTube bayat / YouTube transkript yok durumlarından EN AZ BİRİ varsa → PushNotification aracını (status:"proactive") TEK SEFER çağır; mesajı <routine_summary> etiketi içine yaz. İlk cümle en önemli sorun olsun. Örnek içerikler:
  • "BÜLTEN GİTMEDİ: <GG.AA.YYYY> akşam bülteni zamanında gönderilmedi; yedek çalışma <saat UTC>'de başlatıldı, birkaç dakika içinde e-posta gelmeli." (fire_trigger başarısız olduysa bunu açıkça yaz: "yedek çalışma BAŞLATILAMADI: <hata>".)
  • "KRONİK: BIST taraması <N> iş günüdür üretilmedi (son veri: <tarih>). Son Actions: <sonuc> <zaman> <url>. Olası nedenler: tradingview-screener hatası, cron atlaması veya TV_SESSIONID süresi dolmuş."
  • "ACTIONS HATASI: Tarama çalışması <zaman_utc> itibarıyla '<sonuc>' ile bitti → <url> (log'u aç, hatalı adımı gör)."
  • "KALİTE: Tarama <tarih> kısıtlı modda üretildi (aktif_mod=<..>, rsi_mevcut=<..>, hisse_sayisi=<..>). TV_SESSIONID secret'ını yenile."
  • "YAN DOSYA BAYAT: geri_alim.json 2 iş günüdür güncellenmedi (son: <zaman>) — kap-tarama iş akışını kontrol et." / "YOUTUBE TRANSKRİPT YOK: son başarılı transkript <tarih>; hata: <..>"
  • "BIST tarama verisi (latest.json) erişilemiyor — repo/hat kontrol edilmeli."
  Birden fazla sorun varsa hepsini aynı bildirimde sırala.
- Hiçbir sorun yoksa (veya yalnızca 1 günlük gecikme varsa) TAMAMEN SESSİZ kal — bildirim gönderme. Bu görev kendisi e-posta göndermez; bülteni yalnızca fire_trigger ile yeniden başlatır.
