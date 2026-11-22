import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / ".claude" / "skills" / "cinematic-film" / "scripts"))
import kalite_kontrol as kk  # noqa: E402

FFMPEG_VAR = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ornek_meta(**degis):
    meta = {
        "tur": "short",
        "baslik": "Deneme Sözü 🧪 Test Stili",
        "aciklama": "Kanca.\n\n\"Deneme sözü.\"\nAnlamı: Örnek anlam.\nKökeni bilinmiyor; halk arasında söylenir.\n\n"
                    "Sen ne dersin? Yorumlara yaz 👇 KeyfiZar'ı takip et.\n\n"
                    "Seslendirme yapay zekâ ile üretilmiştir.\n#deyim #KeyfiZar",
        "etiketler": ["deneme", "deyim", "atasözü", "halk sözleri", "türkçe", "anlamı", "kısa video", "KeyfiZar"],
        "kategori": "eglence",
        "gizlilik": "public",
        "yapay_icerik": True,
        "oynatma_listesi": "Deyimler ve Halk Sözleri",
        "yorum": "Sence? 👇",
        "yayin_zamani": "2026-12-06T19:00:00+03:00",
    }
    meta.update(degis)
    return meta


class TestKufur(unittest.TestCase):
    def test_sansursuz_yakalanir(self):
        for metin in ("El sikiyle gerdeğe", "Döner koyar götüne", "alnımıza değdi taşağı", "ya osurur ya sıçar",
                      "GÖTE GİREN ŞEMSİYE", "SİKERMİŞ"):
            self.assertTrue(kk.kufur_bul(metin), metin)

    def test_sansurlu_ve_masum_gecer(self):
        for metin in ("El s*kiyle gerdeğe", "g*tüne", "t*şağı", "s*çar", "eşyaları götürmek", "sıçan kaçtı",
                      "eski sikke", "klasik fizik", "sıçradı", "ağır siklet", "Sıkıyı görünce"):
            self.assertEqual(kk.kufur_bul(metin), [], metin)


class TestMeta(unittest.TestCase):
    def test_gecerli(self):
        self.assertEqual(kk.meta_kontrol(ornek_meta()), [])
        self.assertEqual(kk.kufur_kontrol(ornek_meta()), {})

    def test_hatalar(self):
        self.assertTrue(any("yayin_zamani" in h for h in kk.meta_kontrol(ornek_meta(yayin_zamani="2026-12-06T18:00:00+03:00"))))
        self.assertTrue(any("ISO" in h for h in kk.meta_kontrol(ornek_meta(yayin_zamani="yarın"))))
        self.assertTrue(any("başlık" in h for h in kk.meta_kontrol(ornek_meta(baslik="x" * 95))))
        self.assertTrue(any("son etiket" in h for h in kk.meta_kontrol(ornek_meta(etiketler=["a"] * 9))))
        self.assertTrue(any("etiket sayısı" in h for h in kk.meta_kontrol(ornek_meta(etiketler=["KeyfiZar"]))))
        m = ornek_meta()
        del m["yorum"]
        self.assertTrue(any("'yorum'" in h for h in kk.meta_kontrol(m)))
        yanlis = ornek_meta(yorum="Keyfizar'ı takip et")
        self.assertTrue(any("marka" in h for h in kk.meta_kontrol(yanlis)))

    def test_kufurlu_etiket(self):
        m = ornek_meta(etiketler=["götüne", "deyim", "a", "b", "c", "d", "e", "KeyfiZar"])
        self.assertIn("etiketler", kk.kufur_kontrol(m))


@unittest.skipUnless(FFMPEG_VAR, "ffmpeg yok")
class TestVideo(unittest.TestCase):
    """ffmpeg ile küçük sentetik videolar üretip ölçümleri doğrular (süre eşiği testte 5 sn'ye indirilir)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = pathlib.Path(cls.tmp.name)
        cls._eski = (kk.SURE_MIN, kk.SURE_MAX)
        kk.SURE_MIN, kk.SURE_MAX = 5.0, 45.0

        # İyi video: 1080x1920, 6 sn, gürültülü gri zemin (donmaz), sürekli ton ≈ −14 LUFS (sine kaynağı −18 dBFS; +7 dB),
        # son 2 sn kararma + ortada koyu kutu içinde açık "harfler" (imza benzeri).
        iyi = cls.dir / "iyi"
        iyi.mkdir()
        harfler = ",".join(f"drawbox=x={320 + 80 * i}:y=935:w=24:h=50:color=white:t=fill:enable='gte(t,4)'"
                           for i in range(6))
        vf = ("noise=alls=20:allf=t,"
              "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.6:t=fill:enable='gte(t,4)',"
              "drawbox=x=200:y=900:w=680:h=120:color=0x0C0C0E:t=fill:enable='gte(t,4)'," + harfler)
        cls._ffmpeg(["-f", "lavfi", "-i", "color=c=0x606060:s=1080x1920:d=6:r=10",
                     "-f", "lavfi", "-i", "sine=f=440:d=6:sample_rate=48000",
                     "-vf", vf, "-af", "volume=7dB", str(iyi / "video.mp4")])
        (iyi / "meta.json").write_text(json.dumps(ornek_meta(), ensure_ascii=False), encoding="utf-8")
        cls.iyi = iyi

        # Kötü video: 640x360, ilk 1 sn siyah, ilk 2 sn sessiz, sol kenardan taşan "yazı" çubukları, imza yok.
        kotu = cls.dir / "kotu"
        kotu.mkdir()
        kesik = ",".join(f"drawbox=x=0:y={40 + 30 * i}:w=60:h=12:color=white:t=fill" for i in range(8))
        cls._ffmpeg(["-f", "lavfi", "-i", "color=c=0x606060:s=640x360:d=6:r=10",
                     "-f", "lavfi", "-i", "sine=f=440:d=4:sample_rate=48000",
                     "-vf", "noise=alls=20:allf=t," + kesik + ",drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='lt(t,1)'",
                     "-af", "adelay=2000:all=1,apad,volume=7dB", "-t", "6", str(kotu / "video.mp4")])
        (kotu / "meta.json").write_text(json.dumps(ornek_meta(baslik="Göte Giren Şemsiye"), ensure_ascii=False),
                                        encoding="utf-8")
        cls.kotu = kotu

        # Donuk video: tamamen sabit görüntü.
        cls.donuk = cls.dir / "donuk.mp4"
        cls._ffmpeg(["-f", "lavfi", "-i", "color=c=0x606060:s=320x568:d=5:r=10",
                     "-f", "lavfi", "-i", "sine=f=440:d=5:sample_rate=48000", "-af", "volume=7dB",
                     str(cls.donuk)])

    @classmethod
    def tearDownClass(cls):
        kk.SURE_MIN, kk.SURE_MAX = cls._eski
        cls.tmp.cleanup()

    @staticmethod
    def _ffmpeg(args):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args[:-1], "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", args[-1]], check=True)

    def _sonuc(self, s):
        return {k["ad"]: k["gecti"] for k in s["kontroller"]}

    def test_iyi_video_gecer(self):
        s = kk.denetle(self.iyi / "video.mp4")
        self.assertTrue(s["gecti"], json.dumps(s, ensure_ascii=False, indent=1))

    def test_kotu_video_yakalanir(self):
        r = self._sonuc(kk.denetle(self.kotu / "video.mp4"))
        for ad in ("cozunurluk", "sessiz_baslangic", "siyah_kare", "kenar_kesik_yazi", "imza_son_2sn",
                   "sansursuz_kufur"):
            self.assertFalse(r[ad], ad)
        self.assertTrue(r["sure"])
        self.assertTrue(r["meta_alanlari"])

    def test_donuk_video(self):
        r = self._sonuc(kk.denetle(self.donuk))
        self.assertFalse(r["donmus_kare"])
        self.assertFalse(r["meta_alanlari"])  # yanında meta.json yok

    def test_cikis_kodlari_ve_json(self):
        cikti = self.dir / "sonuc.json"
        with open(os.devnull, "w") as bos:
            eski, sys.stdout = sys.stdout, bos
            try:
                self.assertEqual(kk.main([str(self.iyi), "--json", str(cikti)]), 0)
                self.assertEqual(kk.main([str(self.kotu)]), 1)
                self.assertEqual(kk.main([str(self.dir / "yok")]), 2)
            finally:
                sys.stdout = eski
        j = json.loads(cikti.read_text(encoding="utf-8"))
        self.assertTrue(j["gecti"])
        self.assertEqual(len(j["videolar"]), 1)


if __name__ == "__main__":
    unittest.main()
