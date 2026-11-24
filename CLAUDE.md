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
- KeyfiZar video/short/film/içerik işleri ("video/film/belgesel yap", "short", "içerik üret", "tanıtım filmi") → ÖNCE `keyfizar-icerik` skill'i (marka, ses, küfür, biçim, stil seçimi, Opuscar, HyperFrames, yayın kuralları orada), sonra `cinematic-film` / Opuscar / HyperFrames.
- Yazılım geliştirme işleri (`.claude/skills/`, addyosmani/agent-skills, 14.11.2026): "fikri geliştir" → `idea-refine` · "şartname/spec yaz" → `spec-driven-development` · "planla, görevlere böl" → `planning-and-task-breakdown` · "test yazarak geliştir" → `test-driven-development` · "hatayı ayıkla, neden bozuldu" → `debugging-and-error-recovery` · "Actions/CI" → `ci-cd-and-automation` · "performans, yavaş" → `performance-optimization` · "loglama, izleme" → `observability-and-instrumentation` · "eskiyi kaldır, taşı" → `deprecation-and-migration` · "belgele, karar kaydı" → `documentation-and-adrs` · "beni sorgula/röportaj" → `interview-me`. Bu repodaki kurallar (SISTEM_DURUMU, exit(0), Türkçe, kişisel veri yasağı) bu skill'lerin genel önerilerinden ÖNCE gelir.
- **Ponytail (Alpay kararı 20.11.2026):** `.claude/skills/ponytail*` (DietrichGebert/ponytail, MIT; lisans `LICENSE-ponytail`). Bu repoda ve `icerik-uretim`de **her kodlama işinde varsayılan olarak açık (full)**: önce mevcut kod/stdlib/kurulu paket, sonra en küçük çalışan değişiklik; doğrulama, hata yakalama, güvenlik ve kişisel veri koruması asla kısılmaz; dallı/riskli mantığa bir küçük test; yanıt sonunda atlanan/kontrol edilmeyen şey ve risk tek satırda. Bilinçli kısayol `# shortcut: <sınır>, <ne zaman yükseltilir>` yorumuyla işaretlenir. "kodu incele" → `ponytail-review`, "tüm depoyu tara/denetle" → `ponytail-audit`, "kısayolları listele" → `ponytail-debt`. Raporlar Türkçe yazılır; Claude Code bandı ve hook'lar kurulmadı (bulut oturumunda çalışmaz).
- **Yeni skill eklenince (Alpay kararı 24.11.2026):** sormadan Türkçe tetik eşlemesi bu listeye (ya da ilgili skill'in açıklamasına) eklenir, lisans/KAYNAK notu konur, SISTEM_DURUMU'na yazılır; içerik üretimiyle ilgiliyse şablonu `icerik-uretim/sablonlar/`e ve `stiller.md`ye işlenir.
- **Arka plan işleri (Alpay kararı 24.11.2026, kullanım limiti):** uzun işler (TTS, render, indirme, CI) `run_in_background` + tek bitiş bildirimiyle beklenir; satır satır Monitor kurulmaz, her ara olay için mesaj yazılmaz. Her yeni iş için yeni, kısa oturum tercih edilir.
Skill yalnızca kullanıcının açıkça çağırmasını şart koşuyorsa (ör. `anthropic-skills:morning`) bu kural onu aşmaz. Hangi skill'in kullanıldığı yanıtta tek satırla belirtilir.

## Ücretli araçlar (Alpay kararı 14.11.2026)
Ücretli ya da kullanıma göre faturalanan (ücretsiz kredisi olsa bile) hiçbir servis, bağlayıcı, API, model veya paket **Alpay'ın açık onayı olmadan kurulmaz/eklenmez**. Önce ne olduğu, ücreti ve ücretsiz alternatifi tek mesajda söylenir; "onaylıyorum" denirse kurulur. Ücretsiz yol varsa o tercih edilir.

