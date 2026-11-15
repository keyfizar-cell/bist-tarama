# CLAUDE.md — keyfizar-cell/bist-tarama

Bu repo Alpay'ın BIST portföy otomasyonunun veri hattıdır. **Herhangi bir değişiklikten önce
`SISTEM_DURUMU.md` dosyasını oku**: güncel sürümler, iş akışı, zamanlanmış görevler, kalıcı
kararlar, KALDIRILANLAR ve değişiklik günlüğü oradadır.

Kısa kurallar (ayrıntısı SISTEM_DURUMU.md Bölüm 1):
- Her değişiklikte `SISTEM_DURUMU.md` aynı commit'te güncellenir (sürüm tablosu + değişiklik günlüğü).
- Dışarıdan gelen dosyalar eski sürüme dayanıyorsa birebir kopyalanmaz; güncel dosyaya birleştirilir.
- KALDIRILANLAR geri getirilmez (ör. youtube-transcript-api / proxy yolu).
- Betikler ana taramayı bozmaz, her durumda JSON yazar ve `exit(0)` ile biter.
- `data/` altını bot üretir; elle değiştirme.
- Zamanlanmış görevlerin davranışı `gorevler/*.md` dosyalarında değiştirilir (görev her çalışmada `main`'den çeker); değişiklikten sonra `python araclar/gorev_kontrol.py` geçmeli. Görevdeki başlatıcıya/EK bloğuna dokunmadan hemen önce görevi yeniden oku.
- **Repo herkese açık:** portföy verisi, e-posta, Drive kimliği gibi kişisel bilgiler repoya, `data/`'ya, testlere, Actions'a yazılmaz; talimat dosyalarında yer tutucu kullanılır (bkz. SISTEM_DURUMU.md Bölüm 6).
- Python değişikliklerinden sonra `python -m unittest discover -s testler` geçmeli.
- Tüm yazışma Türkçe.

## Skill kullanımı (Alpay kararı 14.11.2026)
Alpay bir skill'in adını söylemese bile, Türkçe yazdığı kelimelerden ihtiyaç anlaşılıyorsa uygun skill **sormadan, o an** kullanılır. Örnek eşleşmeler:
- "Excel", "xlsx", "tablo dosyası", "csv" → `anthropic-skills:xlsx` · "Word", "docx" → `anthropic-skills:docx` · "sunum", "slayt", "pptx" → `anthropic-skills:pptx` · "PDF" → `anthropic-skills:pdf`
- "Google E-Tablolar/Sheets/Dokümanlar'da değiştir/düzenle", "Portföy Takip dosyasına ekle" → `anthropic-skills:google-workspace`
- "grafik", "çizelge", "görselleştir", "pano/dashboard" → `dataviz` (sayfa/artifact ise `artifact-design` de)
- "derinlemesine araştır", "karşılaştırmalı rapor", "kaynakları tara ve raporla" → `anthropic-skills:deep-research`
- "kodu incele", "hata var mı bak" → `code-review` · "güvenlik kontrolü" → `security-review` · "sadeleştir", "temizle" → `simplify`
- "mutabakat", "bilanço/gelir tablosu hazırla", "sapma/varyans analizi" → ilgili `finance:*` skill'i
- "her X dakikada bir", "düzenli kontrol et" (bu oturum içinde) → `loop`
- "video/film/belgesel yap", "anlatımlı video", "açıklayıcı video", "içerik üret (X/YouTube/TikTok için)", "tanıtım filmi" → `cinematic-film` (`.claude/skills/cinematic-film`, Moh4696/cinematic-skill, 14.11.2026). Ses varsayılan ücretsiz espeak-ng (`-v tr`) ya da Alpay'ın kaydı; ücretli TTS/AI görsel onaysız kullanılmaz; filmlere kişisel portföy verisi girmez, çıktılar repoya commit'lenmez. **Yayın:** bitmiş video `video.mp4` + `meta.json` olarak özel `keyfizar-cell/icerik-uretim` reposunda `videolar/<sıra>-<ad>/` altına `main`'e gönderilir; Actions YouTube'a yükler (şablon ve kurallar o reponun README'sinde). **Biçim kararı (Alpay, 15.11.2026) Claude'undur:** anlatım ≤60 sn → `tur: short` (dikey 1080x1920, hedef 20–45 sn); 60 sn üstü (köken hikâyesi, derleme, belgesel) → `tur: video` (yatay 1920x1080 + `kapak.jpg` 1280x720); içerik biçime sığsın diye zorla kısaltılmaz/uzatılmaz. Her videoda tasarım teması değişir (ör. vaka dosyası, aile ağacı, haber bülteni, mahkeme tutanağı); ses `scripts/xtts_say.py` (XTTS v2 + Whisper denetimi, referans ses Alpay'ın Drive'ında `İçerik Üretim` klasöründe `BelgeselSesi.wav`: Google Drive bağlayıcısıyla başlıktan aranıp indirilir, repoya konmaz); küfür yer tutucu kelime + bip + ekranda yıldız/SANSÜR.
- Yazılım geliştirme işleri (`.claude/skills/`, addyosmani/agent-skills, 14.11.2026): "fikri geliştir" → `idea-refine` · "şartname/spec yaz" → `spec-driven-development` · "planla, görevlere böl" → `planning-and-task-breakdown` · "test yazarak geliştir" → `test-driven-development` · "hatayı ayıkla, neden bozuldu" → `debugging-and-error-recovery` · "Actions/CI" → `ci-cd-and-automation` · "performans, yavaş" → `performance-optimization` · "loglama, izleme" → `observability-and-instrumentation` · "eskiyi kaldır, taşı" → `deprecation-and-migration` · "belgele, karar kaydı" → `documentation-and-adrs` · "beni sorgula/röportaj" → `interview-me`. Bu repodaki kurallar (SISTEM_DURUMU, exit(0), Türkçe, kişisel veri yasağı) bu skill'lerin genel önerilerinden ÖNCE gelir.
Skill yalnızca kullanıcının açıkça çağırmasını şart koşuyorsa (ör. `anthropic-skills:morning`) bu kural onu aşmaz. Hangi skill'in kullanıldığı yanıtta tek satırla belirtilir.

## Ücretli araçlar (Alpay kararı 14.11.2026)
Ücretli ya da kullanıma göre faturalanan (ücretsiz kredisi olsa bile) hiçbir servis, bağlayıcı, API, model veya paket **Alpay'ın açık onayı olmadan kurulmaz/eklenmez**. Önce ne olduğu, ücreti ve ücretsiz alternatifi tek mesajda söylenir; "onaylıyorum" denirse kurulur. Ücretsiz yol varsa o tercih edilir.

