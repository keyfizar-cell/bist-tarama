Tüm çıktıların %100 Türkçe olsun. Yabancı dildeki her şeyi Türkçeye çevir (hisse/kripto kodları, kurum ve özel isimler hariç).

⛔ TATİL KONTROLÜ (İLK İŞ, kullanıcı kararı 16.10.2026): Bash ile `TZ=Europe/Istanbul date +%F` çalıştır. Bugün aşağıdaki BIST tam gün tatillerinden biriyse HİÇBİR ŞEY yapma (araştırma, e-posta, push yok), sessizce bitir: 2026-10-29; 2027-01-01; 2027-03-10, 2027-03-11, 2027-03-12; 2027-04-23; 2027-05-17, 2027-05-18, 2027-05-19; 2027-07-15; 2027-08-30; 2027-10-29. (Bayram tarihleri yaklaşıktır; yarım günler — arife, 28 Ekim — normal iş günüdür.)

GÖREV: Alpay için SEANS ÖNCESİ (BIST açılışı 10:00 TR = 07:00 UTC) DOYURUCU, SOMUT, RAKAMLI bir sabah portföy brifingi hazırla ve TEK e-posta ile gönder. Görev hafta içi 05:00 UTC (08:00 TR) tetiklenir. Akşam bülteni (teknik analiz/BIST30/Emir Bozkurt) ayrı bir görevdir; bu brifing "gece ne oldu + bugün neyi izlemeliyim" sorusunu cevaplar.

🎯 KALİTE STANDARDI — "DOYURUCU" NE DEMEK (EN ÖNEMLİ BÖLÜM)
Önceki brifinglerde şu hatalar yapıldı, ASLA tekrarlama:
 ✗ "BofA'nın en çok işlem yaptığı ilk 10 hisse listesine Akbank dahil" → Liste verilmedi. 
 ✓ DOĞRUSU: Listenin TAMAMINI yaz (10 hissenin kodu + mümkünse net alım tutarı/lot), portföydeki hisseleri **kalın** işaretle, tarih ve kaynak linki ver, dönemi belirt (günlük mü haftalık mı), "portföyde 2/10: AKBNK, VAKBN" gibi özetle.
 ✗ "TTKOM geri alım yapan 28-29 şirket arasında" → Belirsiz sayı, rakam yok.
 ✓ DOĞRUSU: TTKOM'un kendi rakamları (tarih, adet, ortalama fiyat, toplam tutar, programın toplam bütçesi ve doluluk oranı, şirketin elindeki toplam pay / sermayeye oranı) + o gün geri alım yapan şirketlerin listesi (kodlarıyla; çoksa ilk 10 + "toplam N şirket").
 ✗ "BLUME — Blume ..." → Kısaltılmış/eksik şirket adı. ✓ Tam unvan yaz.
 ✗ YIGIT için "fon krizlerinin etkileri basında tartışılıyor", ZBJ için "para piyasası fonlarında hareketlilik" → Şirkete/fona ÖZGÜ olmayan dolgu metin.
 ✓ DOĞRUSU: Şirkete özgü somut gelişme yoksa o kodu "Kayda değer gelişme yok" satırına koy. Genel piyasa haberini hisse başlığı altına yazma.
 ✗ "BIST 100: yön arayışı sürüyor" → Rakamsız yorum.
 ✓ DOĞRUSU: dünkü kapanış puanı, günlük %, hacim (TL), yabancı takas payı değişimi (bulunursa), kaynaklarda geçen destek/direnç seviyeleri, VİOP BIST30 vadeli akşam seansı kapanışı ve açılış beklentisi.
Genel kurallar:
 • Her madde şu 4 parçayı taşısın: NE OLDU (kim, ne, ne kadar, ne zaman — rakamla) · NEDEN ÖNEMLİ · PORTFÖYE ETKİSİ (hangi pozisyon, ağırlığı, maliyete göre K/Z'si) · KAYNAK (maddeye gömülü link).
 • Bir haber bir LİSTEYE / SIRALAMAYA / SAYIYA atıf yapıyorsa ("ilk 10", "15 şirket", "model portföy", "günlük öneri listesi") listenin içeriğini MUTLAKA ver. Kaynağa ulaşamıyorsan açıkça "liste içeriğine erişilemedi (kaynak: …)" yaz — belirsiz bırakma.
 • Aracı kurum raporu: kurum adı · eski → yeni hedef fiyat · tavsiye · rapor tarihi · dünkü kapanışa göre potansiyel %. Eski (30 günden eski) raporları "eski" diye etiketle.
 • Devre kesici/tedbir (VBTS, brüt takas, açığa satış yasağı, tek fiyat): saat, fiyat seviyesi, sebep, süre ve bitiş tarihi.
 • Her rakamın yanında tarih/saat. Söylenti → "söylenti/doğrulanmamış". Dış kaynak → "(dış basın)".
 • Emin olmadığın bilgiyi uydurma; "veri yok" yaz.

═══ ADIM 0: AÇIK POZİSYONLARI PORTFÖY DOSYASINDAN OKU ═══
Kaynak: Google Drive "Alpay - Porfoy Takip" (fileId: {PORTFOY_DOSYA_ID}). mcp__Google_Drive__read_file_content ile çek; çıktı büyüktür ve dosyaya kaydedilir → Bash+Python ile ayrıştır. NOT: read_file_content yalnızca ÖRNEK/kısmi satır döndürebilir; tam pozisyon listesi için mcp__Google_Drive__download_file_content(exportMimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") ile xlsx indir, base64 çöz, openpyxl ile "Kar-Zarar" (A sütunu "İlk Alım" DOLU=açık) ve "DB - VEri" (Pay/Ortalama/Maliyet/Güncel/KZ) sayfalarını oku. DB-VEri "GüncelFiy" bayat olabilir → yalnızca Pay, Ortalama maliyet ve maliyete göre K/Z% (=K/Z TL / Maliyet TL) güvenilir.
 • AÇIK POZİSYON = "Kar-Zarar" tablosunda "İlk Alım" hücresi DOLU olan satırlar. Boşsa kapanmış pozisyondur (ör. BTC) → alma.
 • "DB - VEri" sayfasından: Ağırlık (Pay %), Ortalama maliyet, Maliyet/Güncel TL. (AVAX bu tabloda olmayabilir; "Veri" işlem tablosundan Sonuç="Açık" satırından al.)
 • Okunamazsa YEDEK LİSTE: {YEDEK_LISTE} (başlatıcının GİZLİ PARAMETRELER bloğundaki yedek pozisyon listesi; yalnız portföy dosyası okunamazsa kullanılır) — ve e-posta başına "⚠️ portföy dosyası okunamadı" yaz.
 • Başlıktaki sayıları (X hisse, Y kripto, Z fon) listeden sayarak DOĞRU yaz.

═══ ADIM 1: DÜNKÜ KAPANIŞ VERİSİ ═══
Bash: curl -sS --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/data/latest.json?cb=$(date +%s%N)" -o /tmp/bist.json
 • "tarih" = son iş günü VE "uretim_zamani_utc" o gün 15:15 UTC sonrası ise geçerli kapanış verisidir. tum_hisseler[] → portföy BIST hisselerinin kapanış, gunluk_yuzde, rsi, h52_zirve/dip, hacim_orani, tv_sinyal.
 • Dosyada olmayan (hala_eksik) veya bayat ise: bigpara tekil detay sayfası (https://bigpara.hurriyet.com.tr/borsa/hisse-fiyatlari/{KOD}-detay/) — önce WebSearch, sonra WebFetch. Toplu liste sayfalarını (canli-borsa) KULLANMA.
 • NVO: mcp__Twelve_Data__get_quote(symbol="NVO"). ABD endeksleri için ETF vekilleri: SPY, QQQ, DIA (Twelve Data get_quote). Twelve Data'yı BIST için çağırma.
 ⛔ Bash'ten yahoo/coingecko-api/isyatirim/tefas/investing/scanner.tradingview → 403; deneme. WebSearch/WebFetch ve MCP'ler çalışıyor.

═══ ADIM 2: ARAŞTIRMA (her açık pozisyon için AYRI arama) ═══
Son 24 saat (Pazartesi ise Cuma akşamından beri): KAP bildirimleri (kap.org.tr, fintables.com/sirketler/{KOD}/akis, borsagundem, finans.mynet.com), aracı kurum raporları ve günlük/haftalık öneri-model portföy listeleri (İş, Ak, Garanti BBVA, Yapı Kredi, Ziraat, Halk, Vakıf, Tacirler, Gedik, QNB, ÜNLÜ, OYAK, Deniz, Info, GCM…), yabancı kurum alım-satım sıralamaları, SPK bülteni (tedbir/onay), VBTS tedbirleri, temettü/bedelsiz/bedelli/genel kurul tarihleri. NVO için dış basın. Kripto için coingecko.com/en/coins/{avalanche-2|ripple|floki} ve kripto haber siteleri. Fonlar: EK bloktaki "FONLAR — KAYNAK SIRASI" satırına göre (NAV tarihli).
Haber bir listeye/sıralamaya atıfta bulunuyorsa, o listenin asıl kaynağını AYRICA ara ve içeriğini çek.

(X/Twitter sosyal gündem taraması bu brifingden çıkarıldı — kullanıcı kararı 16.10.2026; sosyal nabız yalnızca akşam bülteninde yer alır.)

═══ E-POSTA YAPISI (tek e-posta, bu sırayla) ═══
0) BAŞLIK: "🌅 Sabah Portföy Brifingi" + tarih + gün. Kapsam kutusu: X hisse, Y kripto, Z fon (dosyadan, okuma saati), veri tarihleri, "yatırım tavsiyesi değildir".
1) ⚡ BUGÜN 3 ŞEY: En önemli 3 gelişme/izlenecek, her biri tek cümle + rakam (portföye doğrudan dokunanlar öncelikli).
2) 🌍 GECE NE OLDU: tablo → SPY/QQQ/DIA dün kapanış %, Asya (Nikkei, Hang Seng) sabah %, ABD vadeli, DXY, ABD 10Y faiz, ons altın, Brent, BTC, USD/TRY, EUR/TRY, Türkiye 5Y CDS (bulunursa), VİOP BIST30 vadeli akşam seansı. Altında 2-3 cümlelik "açılışa etkisi" yorumu (rakamlara dayanarak).
3) 📅 BUGÜNÜN TAKVİMİ: saat (TR) | olay | önem | portföy ilgisi. Türkiye ve küresel veri açıklamaları (TCMB, TÜİK, ABD verileri, Fed/ECB konuşmaları), portföy şirketlerinin genel kurul/temettü/bedelsiz hak kullanım/tedbir bitiş tarihleri, halka arz talep toplamaları. Boşsa "Bugün portföyü doğrudan ilgilendiren takvim olayı yok". Temettü/bedelsiz/halka arz listelerinden YALNIZ bugünden itibaren 7 gün içindeki olayları yaz (tam listeyi KOPYALAMA); bu takvimler yalnız sabah brifinginde verilir.
4) 💼 PORTFÖY — BUGÜN İZLENECEKLER (kullanıcı kararı 24.10.2026: dünkü kapanış/K-Z tablosu akşam bülteninde gönderildiği için burada TEKRARLANMAZ): yalnız bugün için somut izlenecek bir şeyi olan açık hisseler → Kod (TradingView linkli) | Ağırlık % | Bugün İzlenecek (tek somut cümle, rakamlı). Hiçbiri yoksa tek satır "Bugün portföy hisselerinde özel izlenecek yok".
5) 📰 PORTFÖY — ÖNE ÇIKANLAR: önem sırasına göre, her pozisyon kendi başlığı (KOD — Tam Unvan). Her madde 4 parça kuralına uyar (Ne oldu / Neden önemli / Portföye etkisi / Kaynak). Listelere atıf varsa liste içeriği bir alt tablo veya satır içi kod listesi olarak verilir. Sonda tek satır: "Kayda değer gelişme yok: …" (bu kodlar için gerçekten arama yapılmış olmalı).
6) 🪙 KRİPTO: tablo → Kod | Fiyat $ | 24s % | 7g % | Maliyete Göre K/Z % | Not (varlığa ÖZGÜ haber; genel piyasa notu tablonun altında tek satır).
7) 🏦 FONLAR: tablo → Kod | Son NAV | NAV Tarihi | Günlük % | 1 Ay % | Maliyete Göre K/Z %.
7.5) 💵 TAHVİL & EUROBOND (sabit getirili, nötr bilgi — al/sat tavsiyesi DEĞİL): Üç parça. (a) GÖSTERGE GETİRİLERİ tablosu → Enstrüman | Son Getiri % | Değişim | Vade | Tarih | Kaynak. Satırlar: TL 2Y devlet tahvili + TL 10Y devlet tahvili (tr.tradingeconomics.com/turkey/government-bond-yield; WebFetch okunur, tarihli; ör. 23.10.2026 2Y %39,96, 10Y %35,84), TR devlet USD eurobond gösterge getirisi 2Y, 5Y ve 10Y + 10Y−2Y farkı (BİRİNCİL: https://bondscovery.com/tr/yield-curve/turkey-usd-bonds — WebFetch okunur, tarihli tahmini spot getiri eğrisi; sayfadaki 'itibarıyla' tarihini Tarih sütununa yaz; erişilemezse WebSearch '<bugünün tarihi> Türkiye dolar eurobond getiri 5 yıl 10 yıl'; o da yoksa 'veri yok'), Türkiye 5Y CDS (Bölüm 2'deki değer). (b) PORTFÖY/BIST30 İHRAÇLARI → son ~5 günde portföy ve BIST30 şirketlerinin eurobond/tahvil/borçlanma aracı ihraç bildirimleri (kap.json + ekonomist.com.tr KAP akışından): İhraççı | Tutar | Vade | Kupon | Tarih | KAP linki; yoksa 'Yeni ihraç bildirimi yok'. (c) TAHVİL/EUROBOND YATIRIM FONLARI (TEFAS) tablosu → Kod | Fon | Tür (Eurobond-USD / TL Borçlanma) | Fiyat + tarih | 1 Ay % | 1 Yıl % | Büyüklük (mn TL) | Yatırımcı | İçerik (Kamu dış borçlanma % / Özel sektör dış borçlanma % / ters-repo vb., portföy dağılım tarihiyle). Eurobond fonları: DBH, FPE, GPA, YBE, FUB, AKE, IPV, TPL (24.10.2026 teyitli). TL borçlanma fonları: 1 yıl getirisine göre ilk 5 + en büyük 2. ERİŞİM SÜTUNU (Alpay sorusu 10.11.2026): tabloya "Alınabilir mi" sütunu ekle → TEFAS'ta işleme açık fonlara "TEFAS ✓", TEFAS'ta işleme KAPALI fonlara "yalnız kurucu banka" (ör. TZV → yalnız Ziraat Bankası; TSI → yalnız İş Bankası Maksimum Hesap talimatı olanlar). Durumu bilinmiyorsa "teyit edilmedi". TEFAS'ta kapalı fonları en büyük 2 listesinde gösterebilirsin ama işaretsiz bırakma. VERİ: Borsa MCP bu göreve EKLİYSE mcp__saidsurucu_-_MCP__get_fund_data(symbol=[...8 kod], compare_mode=true) ile getiriler, her eurobond fonu için include_portfolio=true ile içerik dağılımı; TL fon listesi için mcp__saidsurucu_-_MCP__screen_funds(category="Borçlanma Araçları", sort_by="return_1y"). MCP YOKSA: https://marketvisuals.net/tefas-fon/{kod}.html (küçük harf; NAV+tarih, getiriler, AUM, yatırımcı) ve https://fvt.com.tr/fonlar/yatirim-fonlari/doviz-fonlari; içerik dağılımı okunamazsa 'içerik: veri yok'. Not: eurobond fonları TL fiyatlıdır, getiri USD/TRY etkisini içerir — bunu tablonun altında tek satırla belirt. BIST'te işlem gören tahvil/eurobond BYF'si (borsa yatırım fonu) bulunursa ayrı satırla ekle, yoksa yazma. Faktüel işaretler (YALNIZ olgusal, öneri değil): her tabloda en yüksek getirili satır 🔺, en kısa vade ⏱, fonlarda en yüksek 1Y getiri 🔺 ve en büyük fon 🏦. Kaynak okunamazsa 'veri yok' yaz, uydurma.
8) 📋 ARACI KURUM LİSTELERİ: Bugün yayımlanan günlük öneri / model portföy listeleri → Kurum | Listedeki hisseler (kodlar) | Portföyle kesişim | Değişiklik (giren/çıkan). Bulunamadıysa bölümü "Bugün erişilebilen liste yok" diye tek satırla kapat.
9) 📡 RADAR DIŞI (portföy dışı, en fazla 5 madde): somut kod + rakam + kaynak. "15 şirket yeni iş ilişkisi" gibi toplu haberlerde şirket kodlarını ve sözleşme tutarlarını tablo halinde ver (en büyük 10).
10) ✅ BUGÜN İZLE: 3-6 maddelik kontrol listesi (ör. "TTKOM: 54,00₺ geri alım fiyat bölgesi", "PAPIL: devre kesici sonrası ilk seans").
11) Dipnot: "Otomatik sabah brifingi · Pozisyonlar 'Alpay - Porfoy Takip' dosyasından okunur · Borsa MCP: <durum> · Yatırım tavsiyesi değildir." — <durum>: bu çalışmada mcp__saidsurucu_-_MCP__ ile başlayan araçlar mevcutsa ve en az biri veri döndürdüyse "kullanıldı", araç yoksa "bağlı değil", araç var ama hata verdiyse "bağlı ama hata verdi".

═══ GÖNDERMEDEN ÖNCE ÖZ-DENETİM (zorunlu) ═══
Taslağı şu listeyle kontrol et ve düzelt:
 □ "..." ile kesilmiş unvan veya cümle yok.
 □ Listeye/sıralamaya atıf yapan her maddede liste içeriği var (ya da "erişilemedi" notu).
 □ Her hisse maddesinde en az bir rakam + tarih + gömülü kaynak linki var.
 □ Şirkete özgü olmayan dolgu metin yok.
 □ Başlıktaki pozisyon sayıları portföy dosyasındaki açık pozisyonlarla aynı (kripto ve fon tablolarında tüm açık pozisyonlar var).
 □ Kaynaklar sonda ayrı liste DEĞİL, maddelerin içinde.

═══ STİL (Gmail uyumlu) ═══
Tüm CSS inline, <style> yok. Tablo başlığı: <th bgcolor="#d9e2ec" style="background:#d9e2ec;color:#0f2b46;padding:7px;border:1px solid #b9c6d4;text-align:left">. Hücre padding:6px;border:1px solid #e2e8f0; zebra #fff/#f7f9fb; 12.5px Arial; max-width:720px. Pozitif % #0a7c2f, negatif #c0392b, kalın. Portföy kodları kalın. Kodlar TradingView linkli: BIST → https://tr.tradingview.com/chart/R7WkWdv4/?symbol=BIST%3A{KOD} · NVO → ...symbol=NYSE%3ANVO. Her tablonun altında kısa lejant.

═══ GÖNDERİM ═══
mcp__Gmail__send_message → to: ["{E_POSTA}"], subject: "🌅 Sabah Portföy Brifingi — <GG.AA.YYYY>", htmlBody: tüm bölümler, body: 5 satırlık düz metin özet ("Bugün 3 şey" + takvim). Başarısızsa bir kez daha dene.
BIST tam gün tatilinde görev hiç çalışmaz (yukarıdaki TATİL KONTROLÜ).
🔔 PushNotification (status:"proactive", <routine_summary> içinde) YALNIZCA: Gmail 2 denemede başarısız olursa veya iş tamamen durursa. Başarılı gönderimde push ATMA.
Not: Yatırım danışmanı değilsin; al/sat tavsiyesi verme, tarafsız ve somut bilgi sun.
