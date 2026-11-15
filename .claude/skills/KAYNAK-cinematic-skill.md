Kaynak: https://github.com/Moh4696/cinematic-skill (MIT, commit bf43556, 14.11.2026). Yalnız skills/cinematic-film/ alındı; install.sh, eklenti manifestleri (.claude-plugin, .codex-plugin, .cursor-plugin, gemini), examples/ ve tests/ KURULMADI.

Kullanım notları (bu repo için):
- Bağımlılıklar ücretsiz: skia-python, numpy, pillow, (scipy), ffmpeg. Gerekirse oturumda kurulur; repo requirements'ına EKLENMEZ (ana tarama bunlara bağımlı değildir).
- Ağ: yalnız Wikimedia Commons (görsel+lisans), Google Fonts (raw.githubusercontent), jsdelivr (harita sınırları).
- Ses: varsayılan ücretsiz espeak-ng (Türkçe: `-v tr`) veya Alpay'ın kendi kaydı. ElevenLabs/OpenAI/PlayHT gibi ücretli TTS ve AI görsel üretimi (motion-assets) Alpay'ın açık onayı olmadan KULLANILMAZ.
- Film projeleri (çıktı, ses, görsel) repoya commit'lenmez; scratchpad'de üretilir, kişisel portföy verisi filmlere girmez.

Yerel değişiklikler (15.11.2026):
- `scripts/captions.py`, `scripts/burn_captions.py`: dikey videoda altyazı 1.85x büyük ve Shorts arayüzünün üstünde (y≈0.76); Türkçe büyük harf (`tr_upper`: i→İ). Yatay videoda davranış aynı.
- `scripts/xtts_say.py` (yeni): XTTS v2 ile referans sesten seslendirme; her satır Whisper ile denetlenir, uyuşmazsa başka tohumla yeniden üretilir. Kullanım: `tts_say.py --cmd "python3 scripts/xtts_say.py <ref.wav> {txt} {out}"`. Gerekenler: coqui-tts[codec], torch (PyPI), faster-whisper; model indirmesi için `HF_HUB_DISABLE_XET=1`. XTTS lisansı (CPML) ticari olmayan kullanım içindir.
- `scripts/engine.py` `Counter`: `sep` parametresi (binlik ayırıcı; Türkçe için `sep="."` → %1.000). Varsayılan "," değişmedi.
