# Zamanlanmış görev başlatıcıları

Her zamanlanmış görevin prompt'u yalnız aşağıdaki kısa başlatıcıdır; asıl talimat `gorevler/<dosya>.md` içindedir.
Bülten görevlerinde başlatıcının ALTINA, Araştırma görevinin otomatik yönettiği `═══ EK ÜCRETSİZ KAYNAK ENTEGRASYONU` bloğu gelir (o blok yalnız görevde durur, burada değil).
Bir görev yeniden kurulursa (ör. bağlantı temizliği) prompt = aşağıdaki başlatıcı + GİZLİ PARAMETRELER bloğu + (bültenlerde) görevdeki güncel EK bloğu.

## GİZLİ PARAMETRELER (07.11.2026)
Repo herkese açık olduğu için talimat dosyalarında kişisel değerler yer tutucuyla geçer. Gerçek değerler
YALNIZ zamanlanmış görevin kendi prompt'unda, başlatıcının hemen altındaki şu blokta durur
(değerler bu dosyaya, repoya veya GitHub'a YAZILMAZ; görevden `get_trigger` ile okunur):

```text
═══ GİZLİ PARAMETRELER (yalnız bu görevde; talimat dosyasındaki yer tutucuları bu değerlerle değiştirerek uygula; bu değerleri hiçbir repo dosyasına, GitHub'a veya e-posta dışı bir çıktıya yazma) ═══
{E_POSTA} = <alıcı e-posta adresi>
{PORTFOY_DOSYA_ID} = <Google Drive portföy tablosu kimliği>        (yalnız bültenlerde)
{YEDEK_LISTE} = <tarih + türe göre açık pozisyon kodları>          (yalnız bültenlerde)
```
| Görev | E_POSTA | PORTFOY_DOSYA_ID | YEDEK_LISTE |
|---|---|---|---|
| Sabah Portföy Brifingi | ✓ | ✓ | ✓ |
| Günlük Portföy Bülteni | ✓ | ✓ | ✓ |
| BIST Veri Kaynağı Alternatif Araştırması | ✓ | — | — |
| BIST Tarama Sağlık Nöbeti | — | — | — |

## Sabah Portföy Brifingi
- Görev ID: `trig_01DaVTFUontesJ7gXp78zAqV`
- Talimat: `gorevler/sabah_brifingi.md`
- EK bloğu görevde: evet

```text
═══ İNCE BAŞLATICI — Sabah Portföy Brifingi (07.11.2026) ═══
Bu görevin TAM talimatı repoda sürüm kontrollü tutulur: gorevler/sabah_brifingi.md. İLK İŞ olarak Bash ile iki dosyayı çek:
for i in 1 2 3; do curl -sSf --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/gorevler/sabah_brifingi.md?cb=$(date +%s%N)" -o /tmp/gorev.md && [ -s /tmp/gorev.md ] && break; sleep 20; done
curl -sS --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/SISTEM_DURUMU.md?cb=$(date +%s%N)" -o /tmp/sistem.md
Sonra /tmp/gorev.md dosyasını Read ile BAŞTAN SONA oku (uzunsa parça parça; hiçbir bölümü atlama) ve oradaki talimatı AYNEN uygula — o dosya bu görevin talimatının kendisidir. /tmp/sistem.md'yi de oku: güncel sürümler, kararlar ve KALDIRILANLAR oradadır; çelişkide SISTEM_DURUMU.md geçerlidir.
Talimat dosyası 3 denemede çekilemezse (HTTP hatası veya boş dosya): hiçbir şey uydurma, işi yapma; PushNotification (status:"proactive", <routine_summary> içinde) ile "Sabah Portföy Brifingi: talimat dosyası gorevler/sabah_brifingi.md çekilemedi — görev bu çalışmada yapılmadı" uyarısı gönder ve bitir.
Aşağıdaki "═══ EK ÜCRETSİZ KAYNAK ENTEGRASYONU" bloğu talimatın PARÇASIDIR: dosyadaki ilgili bölümlere yerleştirerek uygula. Bu blok Araştırma görevi tarafından otomatik güncellendiği için repoda değil burada durur.
```

## Günlük Portföy Bülteni
- Görev ID: `trig_01UjjJQe3p9x4D5SZc484Ryt`
- Talimat: `gorevler/aksam_bulteni.md`
- EK bloğu görevde: evet

```text
═══ İNCE BAŞLATICI — Günlük Portföy Bülteni (07.11.2026) ═══
Bu görevin TAM talimatı repoda sürüm kontrollü tutulur: gorevler/aksam_bulteni.md. İLK İŞ olarak Bash ile iki dosyayı çek:
for i in 1 2 3; do curl -sSf --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/gorevler/aksam_bulteni.md?cb=$(date +%s%N)" -o /tmp/gorev.md && [ -s /tmp/gorev.md ] && break; sleep 20; done
curl -sS --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/SISTEM_DURUMU.md?cb=$(date +%s%N)" -o /tmp/sistem.md
Sonra /tmp/gorev.md dosyasını Read ile BAŞTAN SONA oku (uzunsa parça parça; hiçbir bölümü atlama) ve oradaki talimatı AYNEN uygula — o dosya bu görevin talimatının kendisidir. /tmp/sistem.md'yi de oku: güncel sürümler, kararlar ve KALDIRILANLAR oradadır; çelişkide SISTEM_DURUMU.md geçerlidir.
Talimat dosyası 3 denemede çekilemezse (HTTP hatası veya boş dosya): hiçbir şey uydurma, işi yapma; PushNotification (status:"proactive", <routine_summary> içinde) ile "Günlük Portföy Bülteni: talimat dosyası gorevler/aksam_bulteni.md çekilemedi — görev bu çalışmada yapılmadı" uyarısı gönder ve bitir.
Bu oturuma send_later ile gelen "DEVAM:" mesajında talimat bu oturumda zaten okunmuşsa yeniden çekmen gerekmez; okunmamışsa (ör. bağlam özetlendiyse) yukarıdaki gibi yeniden çek.
Aşağıdaki "═══ EK ÜCRETSİZ KAYNAK ENTEGRASYONU" bloğu talimatın PARÇASIDIR: dosyadaki ilgili bölümlere yerleştirerek uygula. Bu blok Araştırma görevi tarafından otomatik güncellendiği için repoda değil burada durur.
```

## BIST Tarama Sağlık Nöbeti
- Görev ID: `trig_01KGyiz4sASMZ3jUXM67gce8`
- Talimat: `gorevler/saglik_nobeti.md`
- EK bloğu görevde: hayır

```text
═══ İNCE BAŞLATICI — BIST Tarama Sağlık Nöbeti (07.11.2026) ═══
Bu görevin TAM talimatı repoda sürüm kontrollü tutulur: gorevler/saglik_nobeti.md. İLK İŞ olarak Bash ile iki dosyayı çek:
for i in 1 2 3; do curl -sSf --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/gorevler/saglik_nobeti.md?cb=$(date +%s%N)" -o /tmp/gorev.md && [ -s /tmp/gorev.md ] && break; sleep 20; done
curl -sS --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/SISTEM_DURUMU.md?cb=$(date +%s%N)" -o /tmp/sistem.md
Sonra /tmp/gorev.md dosyasını Read ile BAŞTAN SONA oku (uzunsa parça parça; hiçbir bölümü atlama) ve oradaki talimatı AYNEN uygula — o dosya bu görevin talimatının kendisidir. /tmp/sistem.md'yi de oku: güncel sürümler, kararlar ve KALDIRILANLAR oradadır; çelişkide SISTEM_DURUMU.md geçerlidir.
Talimat dosyası 3 denemede çekilemezse (HTTP hatası veya boş dosya): hiçbir şey uydurma, işi yapma; PushNotification (status:"proactive", <routine_summary> içinde) ile "BIST Tarama Sağlık Nöbeti: talimat dosyası gorevler/saglik_nobeti.md çekilemedi — görev bu çalışmada yapılmadı" uyarısı gönder ve bitir.
```

## BIST Veri Kaynağı Alternatif Araştırması
- Görev ID: `trig_01ViuA5ZKASerVpJMqYkoeoz`
- Talimat: `gorevler/veri_kaynagi_arastirma.md`
- EK bloğu görevde: hayır

```text
═══ İNCE BAŞLATICI — BIST Veri Kaynağı Alternatif Araştırması (07.11.2026) ═══
Bu görevin TAM talimatı repoda sürüm kontrollü tutulur: gorevler/veri_kaynagi_arastirma.md. İLK İŞ olarak Bash ile iki dosyayı çek:
for i in 1 2 3; do curl -sSf --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/gorevler/veri_kaynagi_arastirma.md?cb=$(date +%s%N)" -o /tmp/gorev.md && [ -s /tmp/gorev.md ] && break; sleep 20; done
curl -sS --max-time 30 "https://raw.githubusercontent.com/keyfizar-cell/bist-tarama/main/SISTEM_DURUMU.md?cb=$(date +%s%N)" -o /tmp/sistem.md
Sonra /tmp/gorev.md dosyasını Read ile BAŞTAN SONA oku (uzunsa parça parça; hiçbir bölümü atlama) ve oradaki talimatı AYNEN uygula — o dosya bu görevin talimatının kendisidir. /tmp/sistem.md'yi de oku: güncel sürümler, kararlar ve KALDIRILANLAR oradadır; çelişkide SISTEM_DURUMU.md geçerlidir.
Talimat dosyası 3 denemede çekilemezse (HTTP hatası veya boş dosya): hiçbir şey uydurma, işi yapma; PushNotification (status:"proactive", <routine_summary> içinde) ile "BIST Veri Kaynağı Alternatif Araştırması: talimat dosyası gorevler/veri_kaynagi_arastirma.md çekilemedi — görev bu çalışmada yapılmadı" uyarısı gönder ve bitir.
```
