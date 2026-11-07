# -*- coding: utf-8 -*-
"""youtube_kanallar.py birim testleri (ag yok; http ve Gemini sahte)."""
import datetime
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import youtube_kanallar as k  # noqa: E402

AYAR = {"gun_penceresi": 7, "calisma_basina_en_fazla_yeni_video": 2}
KANAL = {"ad": "Test Kanal", "handle": "test_kanal", "channel_id": "", "not": ""}


def tarih(gun_once):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=gun_once)
            ).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def rss(*videolar):
    g = "".join("<entry><yt:videoId>%s</yt:videoId><title>Baslik %s</title><published>%s</published>"
                "</entry>" % (v, v, t) for v, t in videolar)
    return "<feed>%s</feed>" % g


class SahteHttp:
    def __init__(self, rss_xml, sureler, canli=()):
        self.rss_xml, self.sureler, self.canli, self.cagrilar = rss_xml, sureler, set(canli), []

    def __call__(self, url, headers=None, timeout=None):
        self.cagrilar.append(url)
        if "feeds/videos.xml" in url:
            return 200, self.rss_xml
        if "/channels?" in url:
            return 200, json.dumps({"items": [{"id": "UCabc123", "snippet": {"title": "Test Kanal TV"}}]})
        if "/videos?" in url:
            return 200, json.dumps({"items": [
                {"id": v, "contentDetails": {"duration": d},
                 "snippet": {"liveBroadcastContent": "live" if v in self.canli else "none"}}
                for v, d in self.sureler.items()]})
        raise AssertionError("beklenmeyen url " + url)


def gemini_cevap(url, istem=None, sema=None, fps=0.1):
    return ({"transkript": "metin", "ana_mesaj": "tez", "ozet": ["m1"],
             "bahsedilen_hisseler": [{"kod": "TEST", "ne_dedi": "x"}],
             "konusmacinin_riskleri": ["r1"], "icerik_turu": "piyasa_yorumu"}, "gemini:m", "STOP")


class KanalIsle(unittest.TestCase):
    def calistir(self, http, eski=None, kanal=KANAL, gemini=gemini_cevap):
        with mock.patch.object(k.yt, "http_get", http), \
                mock.patch.object(k.yt, "gemini_transkript", side_effect=gemini) as g, \
                mock.patch.object(k.yt.time, "sleep"):
            return k.kanal_isle(kanal, eski or {}, "ANAHTAR", AYAR), g

    def test_handle_cozulur_ve_video_islenir(self):
        http = SahteHttp(rss(("v1", tarih(1))), {"v1": "PT25M"})
        kayit, g = self.calistir(http)
        self.assertEqual(kayit["channel_id"], "UCabc123")
        self.assertEqual(kayit["kanal_adi"], "Test Kanal TV")
        self.assertTrue(any("forHandle=%40test_kanal" in u for u in http.cagrilar))
        v = kayit["videolar"][0]
        self.assertEqual((v["ana_mesaj"], v["icerik_turu"]), ("tez", "piyasa_yorumu"))
        self.assertEqual(v["konusmacinin_riskleri"], ["r1"])
        self.assertIsNone(kayit["hata"])
        self.assertEqual(g.call_count, 1)

    def test_onbellekteki_kimlik_tekrar_sorulmaz(self):
        http = SahteHttp(rss(), {})
        kayit, _ = self.calistir(http, eski={"channel_id": "UCeski", "kanal_adi": "Eski"})
        self.assertEqual(kayit["channel_id"], "UCeski")
        self.assertFalse(any("/channels?" in u for u in http.cagrilar))

    def test_shorts_canli_ve_eski_video_elenir(self):
        http = SahteHttp(rss(("kisa", tarih(1)), ("canli", tarih(1)), ("eski", tarih(10)), ("iyi", tarih(2))),
                         {"kisa": "PT45S", "canli": "PT0S", "iyi": "PT12M"}, canli=["canli"])
        kayit, g = self.calistir(http)
        self.assertEqual(g.call_count, 1)
        durum = {v["video_id"]: v.get("atlandi") for v in kayit["videolar"]}
        self.assertEqual(durum["kisa"], "sure 1 dk")
        self.assertEqual(durum["canli"], "canli yayin")
        self.assertIsNone(durum["iyi"])
        self.assertNotIn("eski", durum)

    def test_calisma_basina_en_fazla_iki_video(self):
        http = SahteHttp(rss(*[("v%d" % i, tarih(i % 5)) for i in range(4)]),
                         {"v%d" % i: "PT20M" for i in range(4)})
        kayit, g = self.calistir(http)
        self.assertEqual(g.call_count, 2)
        self.assertEqual(len(kayit["videolar"]), 2)

    def test_islenmis_video_tekrar_islenmez(self):
        eski = {"channel_id": "UCabc123", "videolar": [{"video_id": "v1", "yayin_tarihi": tarih(1),
                                                        "ozet": ["eski"]}]}
        http = SahteHttp(rss(("v1", tarih(1))), {"v1": "PT20M"})
        kayit, g = self.calistir(http, eski=eski)
        self.assertEqual(g.call_count, 0)
        self.assertEqual(kayit["videolar"][0]["ozet"], ["eski"])

    def test_gemini_hatasi_kaydi_bozmaz(self):
        def hata(*a, **kw):
            raise RuntimeError("Gemini basarisiz: HTTP 429")
        http = SahteHttp(rss(("v1", tarih(1)), ("v2", tarih(1))), {"v1": "PT20M", "v2": "PT20M"})
        kayit, g = self.calistir(http, gemini=hata)
        self.assertIn("429", kayit["hata"])
        self.assertEqual(g.call_count, 1)  # 429'da durur
        self.assertEqual(kayit["videolar"], [])  # sonraki calismada yeniden denenir

    def test_anahtarsiz_handle_hata_yazar(self):
        with mock.patch.object(k.yt, "http_get", SahteHttp(rss(), {})):
            kayit = k.kanal_isle(KANAL, {}, "", AYAR)
        self.assertIn("YOUTUBE_API_KEY", kayit["hata"])


if __name__ == "__main__":
    unittest.main()
