# -*- coding: utf-8 -*-
"""youtube_kanallar.py v1.1 birim testleri (ag yok; http ve Gemini sahte)."""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import youtube_kanallar as k  # noqa: E402


def tarih(gun_once, saat=0):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=gun_once, hours=saat)
            ).strftime("%Y-%m-%dT%H:%M:%S+00:00")


class SahteYouTube:
    """kanallar: {handle: [(video_id, gun_once, iso_sure, canli?)]}"""

    def __init__(self, kanallar):
        self.k = kanallar
        self.sure = {v[0]: v for vs in kanallar.values() for v in vs}
        self.cagrilar = []

    def __call__(self, url, headers=None, timeout=None):
        self.cagrilar.append(url)
        if "/channels?" in url:
            h = url.split("forHandle=%40")[1].split("&")[0]
            return 200, json.dumps({"items": [{"id": "UC" + h, "snippet": {"title": h.upper() + " TV"}}]})
        if "feeds/videos.xml" in url:
            h = url.split("channel_id=UC")[1]
            g = "".join("<entry><yt:videoId>%s</yt:videoId><title>B %s</title><published>%s</published></entry>"
                        % (v[0], v[0], tarih(v[1], 1)) for v in self.k.get(h, []))
            return 200, "<feed>%s</feed>" % g
        if "/videos?" in url:
            ids = urllib_ids(url)
            return 200, json.dumps({"items": [
                {"id": i, "contentDetails": {"duration": self.sure[i][2]},
                 "snippet": {"liveBroadcastContent": "live" if len(self.sure[i]) > 3 else "none"}}
                for i in ids if i in self.sure]})
        raise AssertionError("beklenmeyen url " + url)


def urllib_ids(url):
    import urllib.parse
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["id"][0].split(",")


def gemini(url, istem=None, sema=None, fps=0.1):
    return ({"ana_mesaj": "tez " + url[-3:], "ozet": ["m"], "bahsedilen_hisseler": [],
             "konusmacinin_riskleri": [], "icerik_turu": "piyasa_yorumu"}, "gemini:m", "STOP")


class Calistir(unittest.TestCase):
    def setUp(self):
        self.eski = os.getcwd()
        self.d = tempfile.mkdtemp()
        os.chdir(self.d)

    def tearDown(self):
        os.chdir(self.eski)
        shutil.rmtree(self.d)

    def kos(self, kanallar, yt_veri, toplam=10, gemini_fn=gemini, ekstra=None):
        liste = {"gun_penceresi": 4, "calisma_basina_en_fazla_yeni_video": 2, "calisma_basina_toplam_video": toplam,
                 "gunluk_yukleyen_esigi": 5, "kanallar": kanallar, "liste_disi": []}
        liste.update(ekstra or {})
        with open("kanal_takip.json", "w") as f:
            json.dump(liste, f)
        http = SahteYouTube(yt_veri)
        with mock.patch.object(k.yt, "http_get", http), \
                mock.patch.object(k.yt, "gemini_transkript", side_effect=gemini_fn) as g, \
                mock.patch.object(k.yt.time, "sleep"), \
                mock.patch.dict(os.environ, {"YOUTUBE_API_KEY": "A"}):
            k.main()
        with open(k.OUT_PATH) as f:
            return json.load(f), g, http

    def test_handle_cozulur_ve_islenir(self):
        d, g, http = self.kos([{"ad": "A", "handle": "aa"}], {"aa": [("a01", 1, "PT20M")]})
        a = d["kanallar"]["A"]
        self.assertEqual((a["channel_id"], a["kanal_adi"]), ("UCaa", "AA TV"))
        self.assertEqual(a["videolar"][0]["ana_mesaj"], "tez a01")
        self.assertNotIn("transkript", a["videolar"][0])
        self.assertEqual(g.call_count, 1)

    def test_shorts_canli_ve_pencere_disi_elenir(self):
        d, g, _ = self.kos([{"ad": "A", "handle": "aa"}],
                           {"aa": [("kis", 1, "PT50S"), ("cnl", 1, "PT0S", True), ("esk", 6, "PT20M"), ("iyi", 2, "PT9M")]})
        durum = {v["video_id"]: v.get("atlandi") for v in d["kanallar"]["A"]["videolar"]}
        self.assertEqual(durum, {"kis": "sure 1 dk", "cnl": "canli yayin", "iyi": None})
        self.assertEqual(g.call_count, 1)

    def test_toplam_butce_kanallar_arasi_sirali(self):
        veri = {"aa": [("a1", 0, "PT20M"), ("a2", 1, "PT20M"), ("a3", 2, "PT20M")],
                "bb": [("b1", 1, "PT20M"), ("b2", 2, "PT20M")], "cc": [("c1", 3, "PT20M")]}
        kanallar = [{"ad": x.upper(), "handle": x} for x in ("aa", "bb", "cc")]
        d, g, _ = self.kos(kanallar, veri, toplam=4)
        islenen = [c.args[0][-2:] for c in g.call_args_list]
        self.assertEqual(islenen, ["a1", "b1", "c1", "a2"])  # once her kanaldan 1, sonra 2. tur
        self.assertEqual([b["video_id"] for b in d["kanallar"]["AA"]["bekleyenler"]], ["a3"])
        self.assertEqual([b["video_id"] for b in d["kanallar"]["BB"]["bekleyenler"]], ["b2"])
        self.assertEqual(d["butce"]["islenen"], 4)
        self.assertEqual(d["butce"]["bekleyen"], 2)

    def test_gunluk_yukleyen_liste_disi(self):
        veri = {"gg": [("g%d" % i, i, "PT15M") for i in range(6)], "hh": [("h1", 1, "PT15M")]}
        d, g, _ = self.kos([{"ad": "G", "handle": "gg"}, {"ad": "H", "handle": "hh"}], veri)
        self.assertIn("her gun", d["kanallar"]["G"]["liste_disi"])
        self.assertEqual(d["kanallar"]["G"]["son7_uzun_video"], 6)
        self.assertEqual(d["kanallar"]["G"]["bekleyenler"], [])
        self.assertNotIn("liste_disi", d["kanallar"]["H"])
        self.assertEqual([c.args[0][-2:] for c in g.call_args_list], ["h1"])

    def test_gunluk_shorts_sayilmaz_ve_zorla_takip(self):
        veri = {"ss": [("s%d" % i, i, "PT40S") for i in range(6)] + [("s9", 1, "PT20M")]}
        d, _, _ = self.kos([{"ad": "S", "handle": "ss"}], veri)
        self.assertNotIn("liste_disi", d["kanallar"]["S"])  # shorts gunluk sayilmaz
        veri = {"gg": [("g%d" % i, i, "PT15M") for i in range(6)]}
        d, g, _ = self.kos([{"ad": "G", "handle": "gg", "zorla_takip": True}], veri)
        self.assertNotIn("liste_disi", d["kanallar"]["G"])
        self.assertEqual(g.call_count, 2)

    def test_liste_disi_dizisi_taranmaz(self):
        d, _, http = self.kos([], {"zz": [("z1", 1, "PT20M")]},
                              ekstra={"liste_disi": [{"ad": "Z", "handle": "zz", "neden": "her gun"}]})
        self.assertEqual(d["liste_disi"][0]["ad"], "Z")
        self.assertEqual(http.cagrilar, [])

    def test_429_kalan_isleri_birakir_ve_tekrar_dener(self):
        def hata(*a, **kw):
            raise RuntimeError("Gemini basarisiz: HTTP 429")
        d, g, _ = self.kos([{"ad": "A", "handle": "aa"}, {"ad": "B", "handle": "bb"}],
                           {"aa": [("a1", 1, "PT20M")], "bb": [("b1", 1, "PT20M")]}, gemini_fn=hata)
        self.assertEqual(g.call_count, 1)
        self.assertTrue(d["butce"]["kota_bitti"])
        self.assertEqual(len(d["kanallar"]["A"]["bekleyenler"]) + len(d["kanallar"]["B"]["bekleyenler"]), 2)

    def test_onceki_islenen_tekrar_islenmez(self):
        d, g, _ = self.kos([{"ad": "A", "handle": "aa"}], {"aa": [("a01", 1, "PT20M")]})
        with mock.patch.object(k.yt, "GUNLUK", []):
            d2, g2, http = self.kos([{"ad": "A", "handle": "aa"}], {"aa": [("a01", 1, "PT20M")]})
        self.assertEqual(g2.call_count, 0)
        self.assertFalse(any("/channels?" in u for u in http.cagrilar))  # kimlik onbellekten
        self.assertEqual(d2["kanallar"]["A"]["videolar"][0]["ana_mesaj"], "tez a01")


if __name__ == "__main__":
    unittest.main()
