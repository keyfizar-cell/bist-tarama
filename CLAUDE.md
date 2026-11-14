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
Skill yalnızca kullanıcının açıkça çağırmasını şart koşuyorsa (ör. `anthropic-skills:morning`) bu kural onu aşmaz. Hangi skill'in kullanıldığı yanıtta tek satırla belirtilir.
