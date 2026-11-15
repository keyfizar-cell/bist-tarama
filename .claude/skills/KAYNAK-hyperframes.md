Kaynak: https://github.com/heygen-com/hyperframes (Apache-2.0, commit de1ce68, 15.11.2026; CLI hyperframes@0.9.53). Yalnız 4 skill alındı:
hyperframes, hyperframes-cli, hyperframes-registry, media-use. Alınmayanlar: figma, slideshow, remotion-to-hyperframes (gereksiz),
reverse-any-video ve style-sampling (başkalarının video/kanal görünümünü kopyalamaya dayanır; telif riski).

Bu repo için kurallar:
- Çalıştırma: `npx -y hyperframes@0.9.53 ...`; her komutta `HYPERFRAMES_NO_TELEMETRY=1 DO_NOT_TRACK=1` (kullanım istatistiği gönderilmez).
- Ağ: tarayıcı içinden `cdn.jsdelivr.net` kapalı → GSAP vb. kitaplıklar `npm install gsap@<sürüm>` ile indirilip projede yerel dosyaya bağlanır
  (render ağdan bağımsız ve tekrarlanabilir olur).
- Ücretli: HeyGen bulut render'ı, HeyGen ses/görüntü/müzik modelleri ve HyperFrames Studio Pro **onaysız kullanılmaz**; media-use yalnız ücretsiz
  yerel araçlarla. Ses bizim düzenimiz (xtts_say.py + bip + marka.py).
- Remotion kurulmadı (15.11.2026 değerlendirmesi): HyperFrames aynı işi Apache-2.0 ile ve hızlı yapıyor; Remotion'ın ücretsiz lisansı
  birey/≤3 çalışan şartına bağlı.
