BIST tarama hattı + akşam bülteni SAĞLIK NÖBETİ ve YEDEK GÖNDERİCİ. Amaç: (A) GitHub tarama hattının KRONİK arızasını, (B) tarama kalitesinin bozulmasını, (C) akşam portföy bülteninin GİTMEMESİNİ, (D) GitHub Actions çalışmasının HATA ile bitmesini yakalamak — ve (C) durumunda bülteni YEDEK olarak yeniden başlatmak. Bu görev bülten görevinden bağımsızdır ki bülten çökse bile arıza görülsün ve bülten yine de gitsin. Hafta içi 21:30 UTC'de (00:30 TR) çalışır — bültenin hard deadline'ı 20:45 UTC olduğundan ona 45 dk pay kalır.

ADIMLAR:
1) Bash: date -u +%F ve date -u +%u (6=Cmt, 7=Paz).
2) Hafta sonuysa → hiçbir şey yapma, sessiz bitir.
3) BIST TATİL KONTROLÜ: Bugün aşağıdaki tam gün tatillerden biriyse → sessiz bitir. İş günü farkı hesaplarken bu günleri de iş günü SAYMA.
   2026: 2026-10-29 (Cumhuriyet Bayramı).
   2027: 2027-01-01; 2027-03-10, 2027-03-11, 2027-03-12 (Ramazan Bayramı — yaklaşık); 2027-04-23; 2027-05-17, 2027-05-18, 2027-05-19 (Kurban Bayramı — yaklaşık; 19 Mayıs zaten tatil); 2027-07-15; 2027-08-30 (Zafer Bayramı); 2027-10-29 (Cumhuriyet Bayramı).
   Not: Bayram tarihleri yaklaşıktır; bugün bir bayram civarındaysa ve alarm verecek durum varsa, push atmadan önce WebSearch ile "Borsa İstanbul <tarih> tatil" doğrula. Yarım günler (arife, 28 Ekim) normal iş günüdür.
4–6) (A) TAZELİK ve (B) KALİTE denetimleri 24.11.2026'dan beri 'Sağlık Denetimi' GitHub Actions iş akışında (araclar/saglik.py; sorun varsa iş kırmızı biter ve GitHub e-postası gider). BU GÖREVDE YAPMA — veri dosyalarını ÇEKME.
7) (C) BÜLTEN KONTROLÜ: mcp__Gmail__search_threads ile query = 'in:sent subject:"Portföy Bülteni" newer_than:1d' ara. Konu satırında bugünün tarihi (GG.AA.YYYY) geçen bir e-posta YOKSA → BÜLTEN GİTMEDİ. (Bülten konu formatı: "📊 Günlük Portföy Bülteni — GG.AA.YYYY". Sabah gelen "Portföy Brifingi" e-postası SAYILMAZ.) Gmail aracı hata verirse 1 kez daha dene; yine hata verirse bülten durumunu "bilinmiyor" say ve YEDEK ÇALIŞMAYI YİNE DE BAŞLAT (çift e-posta, hiç e-posta gitmemesinden iyidir).
   ➜ BÜLTEN GİTMEDİYSE (veya durum bilinmiyorsa) YEDEK ÇALIŞMA: mcp__claude-code-remote__fire_trigger(trigger_id="trig_01UjjJQe3p9x4D5SZc484Ryt", text="YEDEK ÇALIŞMA (Sağlık Nöbeti tarafından <saat UTC>'de başlatıldı): Bugünün akşam bülteni gönderilmemiş görünüyor. AKILLI BEKLEME ve send_later KULLANMA, hard deadline geçti sayılır. Elindeki en iyi veriyle (bugünün kapanış taraması varsa onu, yoksa tekil kaynak fiyatlarını kullanarak) bülteni HEMEN kur ve gönder. Başına '⚠️ Yedek çalışma: asıl bülten zamanında gönderilemediği için Sağlık Nöbeti tarafından yeniden başlatıldı' notu koy. Konu satırı değişmez."). fire_trigger hata verirse 1 kez daha dene.
   ➜ YEDEK ÇALIŞMA YENİDEN DENEME (Alpay kararı 24.11.2026; kullanıcı onayı: bülten gitmezse sistem komut beklemeden kendisi tekrar denesin):
   a) fire_trigger'dan sonra Bash ile bekle: `sleep 540` komutunu 5 kez ARDIŞIK çağır (toplam ~45 dk; tek çağrı 10 dk sınırını aşmasın). Bu süre bülten görevinin yedek çalışmasının bitmesi içindir.
   b) Gmail'i aynı sorguyla yeniden ara (in:sent subject:"Portföy Bülteni" newer_than:1d, konuda bugünün tarihi). Bulunduysa → yeniden deneme gerekmez; (C) için bildirim "yedek çalışma ile gönderildi" olarak tek satıra insin (hâlâ başka sorun varsa onlarla birlikte).
   c) Bulunmadıysa → fire_trigger'ı BİR KEZ daha çağır (metin başına "2. YEDEK DENEME" ekle), yine 45 dk bekle, Gmail'i yeniden ara. En çok 2 deneme; üçüncü deneme YOK (e-posta yağmuru olmasın).
   d) İki deneme sonunda bülten hâlâ yoksa → PushNotification: "BÜLTEN GİTMEDİ: yedek çalışma 2 kez denendi, hâlâ e-posta yok — elle müdahale gerekli." Başarısız fire_trigger çağrısının hata metnini ekle.
   e) Her fire_trigger çağrısından önce bugün için daha önce tetiklendi mi kontrol et (yalnız bu oturumda sayaç tut); aynı oturumda 2'den fazla tetikleme yapma.
   f) fire_trigger izin hatasıyla reddedilirse yeniden deneme anlamsızdır: tekrar tekrar çağırma, hemen push gönder ("yedek çalışma izin nedeniyle başlatılamadı").
8–9) (D) ACTIONS SONUCU ve (E) YAN DOSYALAR da 'Sağlık Denetimi' iş akışında (24.11.2026). BU GÖREVDE YAPMA.

BİLDİRİM KURALI (24.11.2026'dan beri yalnız C):
- Bülten gitmediyse/yedek çalışma başarısızsa → PushNotification (status:"proactive") TEK SEFER, mesaj <routine_summary> içinde. Örnek: "BÜLTEN GİTMEDİ: <GG.AA.YYYY> akşam bülteni zamanında gönderilmedi; yedek çalışma <saat UTC>'de başlatıldı." (fire_trigger başarısız olduysa: "yedek çalışma BAŞLATILAMADI: <hata>".)
- Bülten gittiyse TAMAMEN SESSİZ kal. Veri hattı sorunları için 'Sağlık Denetimi' iş akışının kırmızı sonucuna ve GitHub e-postasına bakılır; bu görev onları bildirmez.
