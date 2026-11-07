# -*- coding: utf-8 -*-
"""bulten_hazirla.py birim testleri (yalnız standart kütüphane: python -m unittest)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bulten_hazirla as b  # noqa: E402


def hisse(**kw):
    h = {"kod": "TEST", "kapanis": 10.0, "gunluk_yuzde": 2.0, "bb_alt": 9.0, "piyasa_degeri": 5e9,
         "asiri_satim": True, "donus_teyidi": True, "hacim_patlamasi": True,
         "dusen_bicak": False, "olasi_sermaye_islemi": False, "hacim_ort10": 1e6,
         "h52_dip": 5.0, "h52_zirve": 20.0, "watchlist": None}
    h.update(kw)
    return h


class SinyalKurali(unittest.TestCase):
    def test_tum_kosullar_saglaninca_sinyal(self):
        self.assertTrue(b.sinyal_mi(hisse()))

    def test_her_zorunlu_bayrak_gerekli(self):
        for bayrak in ("asiri_satim", "donus_teyidi", "hacim_patlamasi"):
            self.assertFalse(b.sinyal_mi(hisse(**{bayrak: False})), bayrak)
            self.assertFalse(b.sinyal_mi(hisse(**{bayrak: None})), bayrak + " eksik")

    def test_eleme_bayraklari(self):
        self.assertFalse(b.sinyal_mi(hisse(dusen_bicak=True)))
        self.assertFalse(b.sinyal_mi(hisse(olasi_sermaye_islemi=True)))

    def test_guvenlik_filtreleri(self):
        self.assertFalse(b.sinyal_mi(hisse(bb_alt=0)))
        self.assertFalse(b.sinyal_mi(hisse(bb_alt=-1.2)))
        self.assertFalse(b.sinyal_mi(hisse(gunluk_yuzde=15.0)))
        self.assertFalse(b.sinyal_mi(hisse(gunluk_yuzde=-16.0)))
        self.assertTrue(b.sinyal_mi(hisse(gunluk_yuzde=14.99)))
        self.assertFalse(b.sinyal_mi(hisse(piyasa_degeri=999_999_999)))
        self.assertTrue(b.sinyal_mi(hisse(piyasa_degeri=1_000_000_000)))

    def test_sert_cokus_isareti(self):
        s = b.sinyal_satiri(hisse(kapanis=4.0, h52_zirve=20.0))
        self.assertTrue(s["kap_bedelsiz_kontrolu_gerekli"])
        self.assertFalse(b.sinyal_satiri(hisse(kapanis=10.0, h52_zirve=20.0))["kap_bedelsiz_kontrolu_gerekli"])

    def test_watchlist_grubu(self):
        e = b.emir_bozkurt([hisse(kod="A1", watchlist="A"), hisse(kod="B1", watchlist="B"), hisse(kod="X1")])
        self.assertEqual([s["kod"] for s in e["7a_watchlist"]], ["A1", "B1"])
        self.assertEqual([s["kod"] for s in e["7b_diger"]], ["X1"])


class TeknikPlan(unittest.TestCase):
    def test_standart_seviyeler(self):
        p = b.teknik_plan(hisse(kapanis=100.0, h52_dip=50.0, h52_zirve=200.0))
        self.assertEqual((p["stop"], p["tp1"], p["tp2"]), (93.0, 108.0, 115.0))
        self.assertEqual(p["h52_konum_yuzde"], 33.3)

    def test_dip_daha_yakinsa_stop_dip(self):
        self.assertEqual(b.teknik_plan(hisse(kapanis=100.0, h52_dip=96.0))["stop"], 96.0)

    def test_tp1_zirveyi_asmaz(self):
        self.assertEqual(b.teknik_plan(hisse(kapanis=100.0, h52_zirve=104.0))["tp1"], 104.0)

    def test_gecersiz_kapanis(self):
        self.assertIsNone(b.teknik_plan(hisse(kapanis=None)))


class SinyalGecmisi(unittest.TestCase):
    def test_ilk_tarih_sayac_getiri_ve_tatil(self):
        with tempfile.TemporaryDirectory() as d:
            def dosya(t, liste):
                with open(os.path.join(d, t + ".json"), "w") as f:
                    json.dump({"tarih": t, "tum_hisseler": liste}, f)
            dosya("2026-10-27", [hisse(kod="AAA", kapanis=10.0)])
            dosya("2026-10-28", [hisse(kod="AAA", kapanis=11.0), hisse(kod="BBB", asiri_satim=False)])
            dosya("2026-10-29", [hisse(kod="AAA", kapanis=12.0)])  # tatil → sayılmaz
            dosya("2026-10-30", [hisse(kod="BBB", kapanis=8.0)])
            dosyalar = b.tarihli_dosyalar(b.dt.date(2026, 10, 30), d)
            self.assertNotIn("2026-10-29", [t for t, _ in dosyalar])
            bugun = {"AAA": hisse(kod="AAA", kapanis=12.0), "BBB": hisse(kod="BBB", kapanis=6.0)}
            g = b.sinyal_gecmisi(dosyalar, bugun, "2026-10-30")
            r = {s["kod"]: s for s in g["satirlar"]}
            self.assertEqual(r["AAA"]["ilk_sinyal"], "2026-10-27")
            self.assertEqual(r["AAA"]["sinyal_sayisi"], 2)
            self.assertEqual(r["AAA"]["sinyalden_bu_yana_yuzde"], 20.0)
            self.assertFalse(r["AAA"]["bugun_sinyal"])
            self.assertEqual(r["BBB"]["sinyalden_bu_yana_yuzde"], -25.0)
            self.assertTrue(r["BBB"]["bugun_sinyal"])
            self.assertEqual(g["ozet"]["pozitif"], 1)
            self.assertEqual(g["ozet"]["en_iyi"]["kod"], "AAA")


class GeriAlim(unittest.TestCase):
    def test_kumulatif_yalniz_sirket_beyani(self):
        ga = {"sirketler": {
            "CANTE": {"portfoyde": True, "kumulatif_kaynak": "sirket_beyani", "kumulatif_lot": 25000000.0,
                      "sermaye_orani_yuzde": 0.25, "detay_bildirim_tarih": "2026-10-01"},
            "KRDMD": {"portfoyde": True, "kumulatif_kaynak": "tablo_program", "kumulatif_lot": 1175107.0},
            "XYZ": {"portfoyde": False, "bist30": False}}}
        r = {s["kod"]: s for s in b.geri_alim_ozet(ga)["satirlar"]}
        self.assertEqual(r["CANTE"]["kumulatif_lot"], 25000000.0)
        self.assertIsNone(r["KRDMD"]["kumulatif_lot"])
        self.assertNotIn("XYZ", r)


class GercekVeri(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(os.path.join(b.VERI, "latest.json")), "data/latest.json yok")
    def test_gercek_veriyle_tutarli(self):
        c = b.hazirla()
        self.assertIsNone(c["hata"])
        lt = json.load(open(os.path.join(b.VERI, "latest.json"), encoding="utf-8"))
        beklenen = sum(1 for h in lt["tum_hisseler"] if b.sinyal_mi(h))
        self.assertEqual(c["emir_bozkurt"]["toplam_sinyal"], beklenen)
        self.assertEqual(len(c["bist30"]["satirlar"]), 30)
        # betiğin sinyalleri taramanın kendi listesinin alt kümesi olmalı (bülten ek güvenlik filtreleri uygular)
        tarama = {x["kod"] if isinstance(x, dict) else x
                  for x in (lt.get("tam_kurulum") or []) + (lt.get("tam_kurulum_watchlist_disi") or [])}
        if tarama:
            bizim = {s["kod"] for s in c["emir_bozkurt"]["7a_watchlist"] + c["emir_bozkurt"]["7b_diger"]}
            self.assertTrue(bizim <= tarama, bizim - tarama)


if __name__ == "__main__":
    unittest.main()
