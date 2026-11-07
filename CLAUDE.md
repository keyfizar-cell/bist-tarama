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
- Zamanlanmış görev talimatını değiştirmeden hemen önce yeniden oku; yalnız gereken bölümü değiştir.
- Tüm yazışma Türkçe.
