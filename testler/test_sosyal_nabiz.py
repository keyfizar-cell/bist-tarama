# -*- coding: utf-8 -*-
"""sosyal_nabiz.py birim testleri (ag yok)."""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sosyal_nabiz as s  # noqa: E402

KODLAR = {"THYAO", "SASA", "HEDEF", "ALTIN", "ASELS", "KONTR"}


class KodBulma(unittest.TestCase):
    def test_buyuk_harf_ve_kucuk_bes_harf(self):
        self.assertEqual(s.kodlari_bul("THYAO uçar, asels de iyi", KODLAR), {"THYAO", "ASELS"})

    def test_dort_harfli_kucuk_sayilmaz(self):
        self.assertEqual(s.kodlari_bul("sasa gibi", KODLAR), set())
        self.assertEqual(s.kodlari_bul("SASA tavan", KODLAR), {"SASA"})

    def test_kelime_kodlar_yalniz_isaretle(self):
        self.assertEqual(s.kodlari_bul("HEDEF 100 TL, ALTIN pahalı", KODLAR), set())
        self.assertEqual(s.kodlari_bul("#HEDEF ve $ALTIN", KODLAR), {"HEDEF", "ALTIN"})
        self.assertEqual(s.kodlari_bul("hedef hissesi değil HEDEF hisse alınır", KODLAR), {"HEDEF"})

    def test_listede_olmayan_kod_sayilmaz(self):
        self.assertEqual(s.kodlari_bul("ABCDE ve XYZW", KODLAR), set())


class Ipucu(unittest.TestCase):
    def test_isaret_hacime_gore(self):
        yt_s = {"kod_sayim": {"THYAO": {"yorum": 5}, "SASA": {"yorum": 3}, "ASELS": {"yorum": 1}}}
        forum = {"hisseler": [{"kod": "KONTR", "ne_konusuluyor": "bedelsiz söylentisi", "tur": "spekulasyon"},
                              {"kod": "THYAO", "ne_konusuluyor": "x", "tur": "haber"}]}
        hisse = {"THYAO": {"kapanis": 300, "hacim_orani": 2.5}, "SASA": {"kapanis": 3, "hacim_orani": 0.8},
                 "KONTR": {"kapanis": 10, "hacim_orani": 1.0}}
        ip = {i["kod"]: i for i in s.ipuclari(yt_s, forum, hisse)}
        self.assertNotIn("ASELS", ip)  # esik alti
        self.assertEqual(ip["THYAO"]["isaret"], "konusuluyor+hacim")
        self.assertEqual(ip["THYAO"]["kaynaklar"], ["youtube", "forum"])
        self.assertEqual(ip["SASA"]["isaret"], "yalniz_konusma")
        self.assertEqual(ip["KONTR"]["forum_tur"], "spekulasyon")
        self.assertEqual(s.ipuclari(yt_s, forum, hisse)[0]["kod"], "THYAO")  # iki kaynak once

    def test_ani_artis(self):
        g = {"2026-11-03": {"THYAO": 2}, "2026-11-04": {"THYAO": 2}, "2026-11-05": {"THYAO": 7, "SASA": 3}}
        a = {x["kod"]: x for x in s.ani_artis(g, "2026-11-05")}
        self.assertIn("THYAO", a)
        self.assertEqual(a["THYAO"]["onceki_ortalama"], 2.0)
        self.assertIn("SASA", a)  # onceden hic yok, esik 3

    def test_takip_getiri_5g(self):
        with mock.patch.object(s, "TAKIP_GUN", 100000):
            takip = s.takip_guncelle([], [{"kod": "THYAO", "kaynaklar": ["youtube"], "isaret": "yalniz_konusma",
                                           "kapanis": 100.0}], "2026-11-02", {"THYAO": {"kapanis": 100.0}})
            fiyat = [101, 102, 103, 104, 110, 111]
            for g, f in zip(range(3, 9), fiyat):
                takip = s.takip_guncelle(takip, [], "2026-11-%02d" % g, {"THYAO": {"kapanis": f}})
        self.assertEqual(len(takip), 1)
        self.assertEqual(takip[0]["getiri_5g"], 10.0)
        oz = s.takip_ozeti(takip)
        self.assertEqual(oz["youtube"]["ort_getiri_5g"], 10.0)
        self.assertEqual(oz["isaret:yalniz_konusma"]["olculen_5g"], 1)

    def test_ayni_gun_tekrar_eklenmez(self):
        ip = [{"kod": "THYAO", "kaynaklar": ["forum"], "isaret": "yalniz_konusma", "kapanis": 1.0}]
        t = s.takip_guncelle([], ip, "2026-11-02", {})
        t = s.takip_guncelle(t, ip, "2026-11-02", {})
        self.assertEqual(len(t), 1)


class Forum(unittest.TestCase):
    def test_kaynaksiz_sonuc_atilir_ve_gecersiz_kod_suzulur(self):
        def cevap(kaynakli):
            c = {"candidates": [{"content": {"parts": [{"text": '```json\n{"ozet": ["a"], "hisseler": '
                                                                 '[{"kod": "thyao", "ne_konusuluyor": "x"}, '
                                                                 '{"kod": "UYDU", "ne_konusuluyor": "y"}]}\n```'}]}}]}
            if kaynakli:
                c["candidates"][0]["groundingMetadata"] = {"groundingChunks": [{"web": {"uri": "https://u", "title": "t"}}]}
            return 200, json.dumps(c)
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "k"}), \
                mock.patch.object(s.yt, "gemini_modelleri", return_value=["m"]):
            with mock.patch.object(s.yt, "http_post_json", return_value=cevap(True)):
                f = s.forum_nabiz(KODLAR)
            self.assertEqual([h["kod"] for h in f["hisseler"]], ["THYAO"])
            self.assertEqual(f["kaynaklar"][0]["url"], "https://u")
            with mock.patch.object(s.yt, "http_post_json", return_value=cevap(False)):
                f = s.forum_nabiz(KODLAR)
            self.assertEqual(f["hisseler"], [])
            self.assertIn("dogrulanamaz", f["hata"])

    def test_429da_sonraki_model_denenir(self):
        import urllib.error
        cagri = []

        def post(url, govde, timeout=None):
            cagri.append(url.split("/models/")[1].split(":")[0])
            if len(cagri) == 1:
                raise urllib.error.HTTPError(url, 429, "kota", {}, None)
            return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": '{"ozet": [], "hisseler": []}'}]},
                                                    "groundingMetadata": {"groundingChunks": [{"web": {"uri": "https://u"}}]}}]})
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "k"}), \
                mock.patch.object(s.yt, "gemini_modelleri", return_value=["gemini-3-flash-preview"]), \
                mock.patch.object(s.yt, "http_post_json", side_effect=post):
            f = s.forum_nabiz(KODLAR)
        self.assertEqual(cagri[:2], s.FORUM_MODELLERI)
        self.assertIsNone(f["hata"])


if __name__ == "__main__":
    unittest.main()
