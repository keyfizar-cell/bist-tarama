import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import youtube_deney as d  # noqa: E402


class TestYoutubeDeney(unittest.TestCase):
    def test_parca_plani(self):
        self.assertEqual(d.parca_planla(1500, 10, 4), [(0, 600), (600, 1200), (1200, 1500)])
        self.assertEqual(len(d.parca_planla(99999, 10, 4)), 4)
        self.assertEqual(d.parca_planla(None, 10, 2), [(0, 600), (600, 1200)])

    def test_sure(self):
        self.assertEqual(d.sure_iso_sn("PT1H2M3S"), 3723)
        self.assertEqual(d.sure_iso_sn("PT45M"), 2700)
        self.assertIsNone(d.sure_iso_sn("x"))

    def test_turkce(self):
        self.assertTrue(d.turkce_mu("Bu hafta piyasada çok önemli bir gelişme var ve bunu konuşacağız."))
        self.assertFalse(d.turkce_mu("This is an English sentence and it is not Turkish at all."))
        self.assertFalse(d.turkce_mu(""))

    def test_sonuc_durumu(self):
        kisa = d.sonuc("x", "deneniyor", "Bu çok kısa bir metin ve bir de şu var.")
        self.assertEqual(kisa["durum"], "kisa")
        uzun = d.sonuc("x", "deneniyor", "Bu hafta çok önemli bir gelişme var ve bunu konuşacağız. " * 30)
        self.assertEqual(uzun["durum"], "basarili")
        self.assertLessEqual(len(uzun["onizleme"]), 400)

    def test_sse_ve_json(self):
        sse = 'data: {"choices":[{"delta":{"content":"Mer"}}]}\n\ndata: {"choices":[{"delta":{"content":"haba"}}]}\ndata: [DONE]\n'
        self.assertEqual(d.openai_sohbet_metni(sse), "Merhaba")
        self.assertEqual(d.openai_sohbet_metni('{"choices":[{"message":{"content":"Selam"}}]}'), "Selam")

    def test_vtt(self):
        vtt = "WEBVTT\nKind: captions\n\n00:00:01.000 --> 00:00:02.000\nmerhaba <c>dostlar</c>\n\n00:00:02.000 --> 00:00:03.000\nmerhaba dostlar\nbugün\n"
        self.assertEqual(d.vtt_metin(vtt), "merhaba dostlar bugün")

    def test_cozum_adayi_iki_gun(self):
        g = d.gecmis_guncelle({}, [{"ad": "a", "durum": "basarili", "karakter": 5000}], "2026-11-13T07:00")
        self.assertEqual(d.cozum_adaylari(g), [])
        g = d.gecmis_guncelle(g, [{"ad": "a", "durum": "basarili", "karakter": 5000}], "2026-11-14T07:00")
        self.assertEqual(d.cozum_adaylari(g), ["a"])

    def test_anahtarsiz_deney_atlanmaz(self):
        os.environ.pop("ZAI_API_KEY", None)
        r = d.url_video_deneyi("glm_url", "ZAI_API_KEY", d.ZAI_TABAN, "M", "m")({"url": "u"})
        self.assertEqual(r["durum"], "anahtar_yok")
        os.environ.pop("SILICONFLOW_API_KEY", None)
        r = d.ses_deneyi("sf", "SILICONFLOW_API_KEY", "M", "m", None)([])
        self.assertEqual(r["durum"], "anahtar_yok")


if __name__ == "__main__":
    unittest.main()
