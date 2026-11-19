---
name: keyfizar-haftalik
description: KeyfiZar YouTube kanalı için haftalık short partisi. Her Pazar bulut görevi 7 deyim/atasözü short'u üretir (senaryo, XTTS sesi, dikey 1080x1920 film, 3 marka katmanı, kalite kontrolü, meta.json), her birini ertesi günden başlayarak günde bir 19:00'a zamanlar, özel icerik-uretim deposuna gönderir ve Türkçe özet yazar. Stili Claude seçer (haftalık parti istisnası). "haftalık short partisi", "bu haftanın shortlarını üret", "7 short hazırla" gibi isteklerde kullanılır.
---

# KeyfiZar haftalık short partisi

Bu beceri bir bulut görevinin (Claude Code bulut, ortam `bist-tarama`, kaynaklar: `keyfizar-cell/bist-tarama` +
`keyfizar-cell/icerik-uretim`) her Pazar adım adım izlediği talimattır. Elle tek video istendiğinde KULLANILMAZ
(o zaman eski kural: numaralı stil listesi + Alpay seçer).

**Önce oku:** `bist-tarama/CLAUDE.md` (marka, ses, küfür, stil, ücretli araç kuralları — bu belgedeki her şeyden önce
gelir), `icerik-uretim/README.md` (meta.json alanları), `icerik-uretim/stiller.md`,
`.claude/skills/cinematic-film/SKILL.md`. Tüm yazışma Türkçe.

## Değişmez kurallar
- **Ücretli hiçbir şey yok:** ücretli TTS, AI görsel, HeyGen bulut modelleri, ✦ işaretli stiller (50, 64, 65) kullanılmaz.
- **Kişisel veri yok:** referans ses, e-posta, Drive kimliği depoya, meta.json'a, commit mesajına yazılmaz.
- **Referans ses depoya girmez:** yalnız geçici dizinde (`$TMPDIR` / `/tmp/kz-ref/`) durur, iş bitince silinir.
- **Hata = o videoyu atla.** Bir video herhangi bir adımda iki denemede düzelmezse klasörünü sil, özetin "Atlananlar"
  bölümüne nedeniyle yaz, kalanlarla devam et. Tek bir hata partiyi durdurmaz.
- `bist-tarama`ya bu görevde yazılmaz (yalnız okunur). Yalnız `icerik-uretim/videolar/<yeni klasörler>/` ve
  `icerik-uretim/stiller.md` (✅ işareti) değişir.

## Adımlar

### (a) Depoları güncelle
```bash
git -C bist-tarama pull --ff-only; git -C icerik-uretim pull --ff-only
```
Kurulum (tümü ücretsiz): `pip install "torch==2.8.0" "torchaudio==2.8.0" --index-url https://download.pytorch.org/whl/cpu`
(torch ≥ 2.9 coqui-tts için ayrıca torchcodec ister) + `pip install coqui-tts faster-whisper six skia-python numpy pillow
soundfile scipy`; ilk XTTS çağrısı modeli (~1,8 GB) indirir; ffmpeg yoksa `apt-get install -y ffmpeg`. `python3 .claude/skills/cinematic-film/scripts/check_setup.py` çalıştır.

### (b) 7 deyim / atasözü seç
1. Kullanılmışları topla: `icerik-uretim/yuklenenler.json` anahtarları + `videolar/*/meta.json` (`baslik`, `aciklama`,
   `etiketler`) + `stiller.md`'deki video adları. Aynı ya da çok benzer bir söz seçilmez.
2. Çeşitlilik: en az 3 atasözü + en az 3 deyim; konular farklı (hayvan, yemek, para, aile, iş, yolculuk, doğa...);
   en çok 1 argo/küfürlü söz (küfür kuralına göre işlenir).
3. Yalnız anlamı ve (varsa) kökeni sağlam kaynakta (TDK Güncel Türkçe Sözlük / Atasözleri ve Deyimler Sözlüğü,
   ansiklopedi) doğrulanabilen sözler. Doğrulanamayanı bırak, başka söz seç.

### (c) Senaryo (her video için)
- `script.json` (cinematic-film biçimi): 20–45 sn konuşma ≈ 50–110 kelime, 5–8 satır.
- Akış: söz (kanca) → kısa sahne/hikâye → **anlamı** → (varsa) köken → izleyiciye soru + "KeyfiZar'ı takip et".
- **Uydurma yok.** Köken belirsizse "rivayete göre" de; hiç bilinmiyorsa köken satırı konmaz. Her iddia için
  `fact_notes`'a kaynak notu yaz.
- `spoken` alanı: sayılar yazıyla; "KeyfiZar" sesli okunurken `spoken`'da "Keyfi Zar" yazılır (ekranda/altyazıda yine
  `KeyfiZar`). Küfür: `spoken`'da yer tutucu kelime ("tatata"), ekranda yıldız/`SANSÜR`, seste bip.

### (d) Referans ses
Google Drive bağlayıcısıyla başlıkta `BelgeselSesi.wav` ara (`İçerik Üretim` klasörü), içeriğini indir,
`/tmp/kz-ref/BelgeselSesi.wav` olarak kaydet. Bulunamazsa partiyi durdurma: özete "referans ses bulunamadı" yaz ve
görevi bitir (sentetik/ücretli ses kullanma).

### (e) Üretim — dikey 1080x1920
Stil seçimi (haftalık parti istisnası, CLAUDE.md):
- 7 videoda 7 farklı stil; son 2 haftada (`stiller.md` ✅ tarihleri ve `yuklenenler.json` zamanları) kullanılanlar
  tercih edilmez; ✦ stiller asla. İçeriğe uyan, bu ortamda üretilebilir stil seç.
- Hızlı yol: cinematic-film motoru (`look`: wall/slate/charcoal/paper/studio/blueprint/night + özel renk) ya da
  HyperFrames (stil 108; her komutta `HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1`). Opuscar stilleri (9–107)
  bu motorlarla görünümü uyarlanarak ya da lemo-opuscar klonlanarak (`git clone --depth 1`, depoya kopyalanmaz)
  yapılabilir; `icerik-uretim/sablonlar/` altındaki hazır şablonlar (golge-oyunu, casus-jenerigi, tek-cizgi,
  kazima-edit) varsa onları kullan.

Akış (cinematic-film, proje geçici dizinde, ör. `/tmp/kz/<sira>-<ad>/`):
1. `script.json` → her take için satırları boş satırla ayrılmış bir `.txt`.
2. Ses: `python3 scripts/xtts_say.py /tmp/kz-ref/BelgeselSesi.wav <take>.txt <proje>/audio/takes/<take>.wav`
   (XTTS v2 + Whisper denetimi; tohum puanı < 0.90 kalan satır varsa satırı sadeleştirip yeniden üret).
   Tek take'te 7 satır CPU'da ~10 dk sürer. "Keyfi Zar'ı" satırı Whisper'da bitişik duyulduğu için ~0.86 alır; bu kabul edilir.
3. `split_takes.py` → `build_narration.py` (zamanlama `audio/timing.json`).
4. **Yazı tipleri (atlanırsa altyazı taşar):** `cond` rolü için Bebas Neue'yu her zaman dosya olarak koy:
   `curl -sSfL -o <proje>/fonts/cond.ttf https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf`
   (`get_fonts.py` sistemde Impact bulursa onu kullanır; Impact geniş olduğu için dikeyde 6 kelimelik altyazı satırı
   taşar). El yazısı gerekiyorsa `hand.ttf` = Kalam Bold (`ofl/kalam/Kalam-Bold.ttf`). Türkçe glifleri
   (İ Ş Ğ ı ş ğ) `skia.Typeface.unicharsToGlyphs` ile denetle; sonra `prep_assets.py`.
5. `scene.py` yaz; `render.py --probe` ile her satırdan bir kare 540x960 al ve **bak**. Dikeyde görünen dünya
   genişliği 3840/zoom: en geniş yazı satırı bunun %85'ini geçmesin. İçeriği karenin üst %62'sine koy
   (altta altyazı bandı).
6. `render.py --cues` → `build_sfx.py` → `mix_soundtrack.py --sfx-db -6` → `render.py --size 1080x1920 --workers 3 --out out/temiz.mp4 --audio audio/mix.m4a`
   (4 çekirdekte 34 sn ≈ 5 dk).
7. `burn_captions.py --project <proje> --video out/temiz.mp4 --audio audio/mix.m4a --style highlighter --out out/altyazili.mp4`
   (**yollar proje köküne göre göreli verilir**; mutlak `--out` yolu betikte hata verir) →
   `marka.py --video <proje>/out/altyazili.mp4 --out <proje>/out/markali.mp4`.
8. Son kodlama (boyut ve ses seviyesi, ~18 MB / 34 sn):
   `ffmpeg -i out/markali.mp4 -vf hqdn3d=3:3:4:4 -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -af loudnorm=I=-14:TP=-1.5:LRA=11 -c:a aac -b:a 160k -ar 48000 -movflags +faststart video.mp4`

**Üç marka katmanı (her video):** (1) `marka.py` köşe filigranı (dikey sol üst) + son 2 sn imza; (2) temaya gömülü tek
bir marka öğesi (ör. tahtada "KeyfiZar Tebeşir Dersi" başlığı, "KeyfiZar Haber" bandı) — `font="marka"` ile;
(3) kapanış cümlesinde "KeyfiZar'ı takip et". Yazım her yerde tam `KeyfiZar`. Açılışa logo konmaz.

### (f) Kalite kontrolü (her video, geçmeyen düzeltilir ya da atlanır)
```bash
ffprobe -v error -show_entries stream=width,height:format=duration -of default=nw=1 video.mp4   # 1080x1920, 20–45 sn
ffmpeg -i video.mp4 -af loudnorm=print_format=summary -f null - 2>&1 | grep "Input Integrated"  # ≈ -14 LUFS (−16…−12)
ffmpeg -v error -i video.mp4 -vf "fps=1/4,scale=540:-1,tile=4x3" -frames:v 1 kontrol.jpg         # kareler
```
- Kontrol karesine ve en az 4 tekil kareye (açılış, orta, anlam satırı, son 2 sn imza) **bak**: altyazı ve yazılar
  kenardan/Shorts arayüz bölgesinden taşmıyor (sağ 12 %, alt 18 % boş kalmalı); "KeyfiZar" doğru yazılmış
  (filigran, tema öğesi, imza); karanlık zeminde koyu yazı yok.
- Sesi Whisper ile metne karşı bir kez daha kontrol et (benzerlik ≥ 0.90); sessiz/kesik satır yok.
- Kareler ve ara dosyalar depoya girmez.

### (g) meta.json
Klasör: `icerik-uretim/videolar/<sıradaki 3 haneli no>-<kısa-ad>/` → `video.mp4` + `meta.json`. Mevcut short'lardaki
(ör. `videolar/012-*`, `videolar/005-*`) biçim aynen:
- `tur: "short"`, `baslik` (≤ 92 karakter, emoji serbest, `#shorts`'u yükleyici ekler), `aciklama` (kanca + söz +
  "Anlamı:" + varsa köken + soru 👇 + "KeyfiZar'ı takip et." + hashtag'ler + "Seslendirme yapay zekâ ile üretilmiştir."),
  `etiketler` (8–10, sonuncusu `KeyfiZar`), `kategori` (`egitim` ya da `eglence`), `gizlilik: "public"`,
  `yapay_icerik: true`, `oynatma_listesi: "Deyimler ve Halk Sözleri"`, `yorum` (izleyiciye soru, emoji).
- `yayin_zamani`: ertesi günden başlayarak her gün `YYYY-MM-DDT19:00:00+03:00`. Kuyrukta (`videolar/*/meta.json`,
  `video.mp4`'ü depoda duran) zaten o güne zamanlanmış video varsa o gün atlanır, sonraki boş güne geçilir.
- Doğrula: `cd icerik-uretim && python araclar/yukle.py --kuru` — hata yoksa devam.

### (h) Stil kataloğu
`stiller.md`'de kullanılan her stilin satırına `✅ <video adı> (GG.AA.YYYY)` ekle (Opuscar tablolarında "Not",
KeyfiZar temalarında "Kullanıldığı video" sütunu). Numaralar ve diğer satırlar değişmez.

### (i) Gönder
```bash
cd icerik-uretim && git add videolar/<yeni klasörler> stiller.md
git commit -m "Haftalık parti GG.AA.YYYY: 7 short (…)" && git push origin main
```
Push reddedilirse `git pull --rebase` ve bir kez daha dene. Referans sesi ve `/tmp/kz*` dizinlerini sil.

### (j) Türkçe özet (görevin son mesajı)
```
| Gün | Yayın | Deyim / atasözü | Stil (no · ad) | Süre |
|---|---|---|---|---|
| Pzt 24.11 | 19:00 | Dimyat'a pirince giderken… | 24 · Kara Tahta Tebeşir | 34 sn |
…
Atlananlar: (varsa, nedeniyle)
Değiştirmek istediğin stil varsa söyle; o videoyu seçtiğin stille yeniden üretirim.
```
