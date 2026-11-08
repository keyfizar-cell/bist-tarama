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


class ModelListesi(unittest.TestCase):
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
