# -*- coding: utf-8 -*-
"""tms29_duzeltme.py birim testleri (ağ yok)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tms29_duzeltme as t  # noqa: E402


def donem(nk, ev, satis, brut, faal, amort=10.0, ozk=1000.0):
    return {"net_kar": nk, "ert_vergi": ev, "satis": satis, "brut": brut, "faaliyet": faal, "amortisman": amort,
            "ozkaynak": ozk}


VERI = {(2026, 9): donem(90, 30, 900, 270, 150), (2026, 6): donem(60, 20, 600, 180, 100),
        (2025, 12): donem(100, 10, 1000, 250, 150), (2025, 9): donem(70, 5, 700, 175, 100),
        (2024, 12): donem(80, 0, 800, 200, 120), (2024, 9): donem(50, 0, 500, 125, 80)}


def sahte_cek(kod, donemler):
    return {p: dict(VERI.get(p, {})) for p in donemler}


class Hesap(unittest.TestCase):
    def test_ttm_ve_duzeltme(self):
        with mock.patch.object(t, "cek", side_effect=sahte_cek), mock.patch.object(t.time, "sleep"):
            r = t.hisse_isle("X", t.dt.date(2026, 11, 12))
        self.assertEqual(r["donem"], "2026/09")
        self.assertEqual(r["net_kar_ttm"], 120)            # 90 + 100 − 70
        self.assertEqual(r["ertelenmis_vergi_ttm"], 35)    # 30 + 10 − 5
        self.assertEqual(r["duz_net_kar_ttm"], 85)
        self.assertEqual(r["duz_net_kar_ttm_once"], 95)    # (70+80−50) − (5+0−0)
        self.assertAlmostEqual(r["duz_net_kar_buyume_yuzde"], -10.5, places=1)
        self.assertAlmostEqual(r["duz_roe_yuzde"], 8.5)
        self.assertAlmostEqual(r["brut_marj_degisim_puan"], 5.0)   # 30% − 25%
        self.assertAlmostEqual(r["favok_marj_degisim_puan"], 2.06, places=2)  # 17.78 − 15.71

    def test_son_donem_yoksa_altiya_duser(self):
        def cek2(kod, donemler):
            d = sahte_cek(kod, donemler)
            d[(2026, 9)] = {}
            return d
        with mock.patch.object(t, "cek", side_effect=cek2), mock.patch.object(t.time, "sleep"):
            r = t.hisse_isle("X", t.dt.date(2026, 11, 12))
        self.assertEqual(r["donem"], "2026/06")


if __name__ == "__main__":
    unittest.main()
