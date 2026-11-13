# -*- coding: utf-8 -*-
"""youtube_tarama.py v2.3 Gemini kota yedegi testleri (ag yok)."""
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import youtube_tarama as yt  # noqa: E402

SEMA = {"type": "OBJECT"}


def hata429(govde):
    return urllib.error.HTTPError("u", 429, "kota", {}, io.BytesIO(govde.encode()))


def basari():
    return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": '{"ozet": ["a"]}'}]},
                                            "finishReason": "STOP"}]})


class KotaYedegi(unittest.TestCase):
    def setUp(self):
        yt.TUKENEN.clear()
        yt._MODEL_ONBELLEK[:] = []
        self.env = mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "k", "GEMINI_MODEL": ""})
        self.env.start()
        self.liste = mock.patch.object(yt, "gemini_modelleri", return_value=["m1", "m2", "m3-lite"])
        self.liste.start()

    def tearDown(self):
        self.env.stop()
        self.liste.stop()
        yt.TUKENEN.clear()

    def model(self, url):
        return url.split("/models/")[1].split(":")[0]

    def test_gunluk_kota_dolunca_siradaki_model(self):
        cagri = []

        def post(url, govde, timeout=None):
            cagri.append(self.model(url))
            if self.model(url) == "m1":
                raise hata429('{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}')
            return basari()
        with mock.patch.object(yt, "http_post_json", side_effect=post):
            j, kaynak, _ = yt.gemini_transkript("v", sema=SEMA)
            j2, kaynak2, _ = yt.gemini_transkript("v2", sema=SEMA)
        self.assertEqual(kaynak, "gemini:m2")
        self.assertEqual(kaynak2, "gemini:m2")
        self.assertEqual(cagri, ["m1", "m2", "m2"])  # m1 ikinci videoda tekrar denenmez
        self.assertEqual(yt.TUKENEN, {"m1"})

    def test_tum_modeller_dolunca_429_hatasi(self):
        with mock.patch.object(yt, "http_post_json", side_effect=lambda *a, **k: (_ for _ in ()).throw(
                hata429('{"quotaId": "PerDay"}'))):
            with self.assertRaises(RuntimeError) as c:
                yt.gemini_transkript("v", sema=SEMA)
        self.assertIn("429", str(c.exception))
        self.assertEqual(yt.TUKENEN, {"m1", "m2", "m3-lite"})

    def test_dakikalik_sinirda_bekleyip_ayni_model(self):
        sayac = {"n": 0}

        def post(url, govde, timeout=None):
            sayac["n"] += 1
            if sayac["n"] == 1:
                raise hata429('{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}')
            return basari()
        with mock.patch.object(yt, "http_post_json", side_effect=post), mock.patch.object(yt.time, "sleep") as uyku:
            _, kaynak, _ = yt.gemini_transkript("v", sema=SEMA)
        self.assertEqual(kaynak, "gemini:m1")
        uyku.assert_called_once_with(60)
        self.assertEqual(yt.TUKENEN, set())

    def test_429_disi_hata_kota_sayilmaz(self):
        def post(url, govde, timeout=None):
            raise urllib.error.HTTPError(url, 500, "x", {}, io.BytesIO(b"sunucu"))
        with mock.patch.object(yt, "http_post_json", side_effect=post):
            with self.assertRaises(RuntimeError) as c:
                yt.gemini_transkript("v", sema=SEMA)
        self.assertNotIn("429", str(c.exception))
        self.assertEqual(yt.TUKENEN, set())


class KisaYanit(unittest.TestCase):
    """v2.4: Emir yolu (sema=None) kısa transkriptte sıradaki modeli dener; konuk/kanal (sema) etkilenmez."""
    def setUp(self):
        yt.TUKENEN.clear()
        self.env = mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "k", "GEMINI_MODEL": ""})
        self.env.start()
        self.liste = mock.patch.object(yt, "gemini_modelleri", return_value=["m1", "m2", "m3"])
        self.liste.start()

    def tearDown(self):
        self.env.stop()
        self.liste.stop()

    def yanit(self, uzunluk):
        return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(
            {"transkript": "a" * uzunluk, "ozet": ["o"], "bahsedilen_hisseler": []})}]}, "finishReason": "STOP"}]})

    def test_kisa_yanitta_siradaki_model_yalniz_transkript(self):
        cagri = []

        def post(url, govde, timeout=None):
            cagri.append((url.split("/models/")[1].split(":")[0], govde["contents"][0]["parts"][1]["text"],
                          govde["generationConfig"]))
            if len(cagri) == 1:
                return self.yanit(400)
            return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": "b" * 5000}]}, "finishReason": "STOP"}]})
        with mock.patch.object(yt, "http_post_json", side_effect=post):
            tr, _, kaynak, ozet, _, _ = yt.gemini_transkript("v", min_karakter=1000)
        self.assertEqual(len(tr), 5000)
        self.assertEqual(kaynak, "gemini:m2 (yalniz transkript)")
        self.assertEqual(ozet, ["o"])  # ozet ilk (semali) yanittan korunur
        self.assertNotIn("ONEMLI", cagri[0][1])
        self.assertIn("ONEMLI", cagri[1][1])
        self.assertEqual(cagri[0][2]["responseMimeType"], "application/json")
        self.assertEqual(cagri[1][2]["responseMimeType"], "text/plain")
        self.assertNotIn("responseSchema", cagri[1][2])

    def test_hepsi_kisa_ise_en_uzunu_ve_deneme_siniri(self):
        uz = iter([300, 700, 500])

        def post(url, govde, timeout=None):
            n = next(uz)
            if govde["generationConfig"]["responseMimeType"] == "text/plain":
                return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": "a" * n}]}, "finishReason": "STOP"}]})
            return self.yanit(n)
        with mock.patch.object(yt, "http_post_json", side_effect=post) as p:
            tr, *_ = yt.gemini_transkript("v", min_karakter=1000)
        self.assertEqual(len(tr), 700)
        self.assertEqual(p.call_count, 1 + yt.KISA_YENIDEN_DENEME)

    def test_sema_yolu_etkilenmez(self):
        with mock.patch.object(yt, "http_post_json", return_value=self.yanit(50)) as p:
            j, kaynak, _ = yt.gemini_transkript("v", sema={"type": "OBJECT"})
        self.assertEqual(p.call_count, 1)
        self.assertEqual(kaynak, "gemini:m1")


class ModelListesi(unittest.TestCase):
    def test_38_flash_once(self):
        self.assertEqual(yt.GEMINI_TERCIH[0], "gemini-3.8-flash")
        self.assertNotIn("gemini-2.5-flash", yt.GEMINI_TERCIH)

    def test_lite_modeller_sona_yedek(self):
        yt._MODEL_ONBELLEK[:] = []
        modeller = {"models": [{"name": "models/" + n, "supportedGenerationMethods": ["generateContent"]}
                               for n in ("gemini-3-flash-preview", "gemini-flash-latest", "gemini-3.5-flash-lite",
                                         "gemini-3-flash-tts")]}
        with mock.patch.dict(os.environ, {"GEMINI_MODEL": ""}), \
                mock.patch.object(yt, "http_get", return_value=(200, json.dumps(modeller))):
            sira = yt.gemini_modelleri("k")
        self.assertEqual(sira[0], "gemini-3-flash-preview")
        self.assertEqual(sira[-1], "gemini-3.5-flash-lite")
        self.assertNotIn("gemini-3-flash-tts", sira)
        yt._MODEL_ONBELLEK[:] = []


if __name__ == "__main__":
    unittest.main()
