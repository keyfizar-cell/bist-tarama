# -*- coding: utf-8 -*-
"""faktor_skor.py birim testleri (ağ yok; kurgusal şirketler)."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import faktor_skor as f  # noqa: E402


def sirket(kod, **kw):
    r = {"kod": kod, "description": kod, "close": 10.0, "sector": "Producer Manufacturing", "industry": "X",
         "market_cap_basic": 10e9, "total_revenue_yoy_growth_ttm": 20, "ebitda_yoy_growth_ttm": 20,
         "net_income_yoy_growth_ttm": 20, "return_on_equity": 15, "return_on_invested_capital": 12,
         "cash_f_operating_activities_ttm": 100, "free_cash_flow": 50, "free_cash_flow_fq": 10,
         "total_revenue": 1000, "net_income": 100, "price_earnings_ttm": 10, "enterprise_value_ebitda_ttm": 6,
         "net_debt": 100, "ebitda": 200, "debt_to_equity": 0.5, "Perf.Y": 30, "Perf.6M": 10, "Perf.3M": 5, "Perf.1M": 2}
    r.update(kw)
    return r


class Yuzdelik(unittest.TestCase):
    def test_yon_ve_esitlik(self):
        self.assertEqual(f.yuzdelik({0: 1, 1: 2, 2: 3}, 1), {0: 0.0, 1: 50.0, 2: 100.0})
        self.assertEqual(f.yuzdelik({0: 1, 1: 2, 2: 3}, -1), {0: 100.0, 1: 50.0, 2: 0.0})
        self.assertEqual(f.yuzdelik({0: 5, 1: 5, 2: None}, 1), {0: 50.0, 1: 50.0})


class Skor(unittest.TestCase):
    def test_iyi_sirket_ustte_ve_agirliklar(self):
        evren = [sirket("IYI", total_revenue_yoy_growth_ttm=90, ebitda_yoy_growth_ttm=90, return_on_equity=40,
                        price_earnings_ttm=4, **{"Perf.Y": 90}),
                 sirket("ORTA"), sirket("KOTU", total_revenue_yoy_growth_ttm=-10, price_earnings_ttm=40, **{"Perf.Y": -20})]
        s = f.skorla(evren)
        self.assertEqual([x["kod"] for x in s], ["IYI", "ORTA", "KOTU"])
        x = s[0]
        beklenen = round(sum(f.AGIRLIK[k] * x[k] for k in f.AGIRLIK), 1)
        self.assertAlmostEqual(x["toplam"], beklenen, places=0)

    def test_zarar_edende_fk_ve_net_kar_bos(self):
        m = f.metrikler(sirket("Z", net_income=-5, price_earnings_ttm=8))
        self.assertIsNone(m["degerleme"][0][0])
        self.assertIsNone(m["buyume"][2][0])

    def test_eksik_veri_sifir_puan(self):
        evren = [sirket("A"), sirket("B", **{"Perf.Y": None, "Perf.6M": None, "Perf.3M": None})]
        s = {x["kod"]: x for x in f.skorla(evren)}
        self.assertEqual(s["B"]["momentum"], 0.0)

    def test_ana_liste_esigi_tl(self):
        s = {x["kod"]: x for x in f.skorla([sirket("BUYUK", market_cap_basic=6e9), sirket("KUCUK", market_cap_basic=3e9)])}
        self.assertTrue(s["BUYUK"]["ana_liste"])
        self.assertFalse(s["KUCUK"]["ana_liste"])


class Sepet(unittest.TestCase):
    def skorlar(self):
        out = []
        for i, (kod, sek) in enumerate([("A", "S1"), ("B", "S1"), ("C", "S1"), ("D", "S2"), ("E", "S3"), ("F", "S4"), ("G", "S5")]):
            out.append({"kod": kod, "sektor": sek, "ana_liste": True, "kapanis": 10.0 + i, "toplam": 90 - i, "sira": i + 1})
        return out

    def test_sektor_siniri_ve_kirmizi_haric(self):
        adil = [{"kod": "D", "durum": "🔴 iyimser senaryonun üstünde"}]
        secim = [x["kod"] for x in f.sepet_sec(self.skorlar(), adil)]
        self.assertEqual(secim, ["A", "B", "E", "F", "G"])  # C: S1'de 3. olur; D: 🔴

    def test_haftada_bir_sepet_ve_getiri(self):
        s1 = f.sepet_guncelle({}, self.skorlar(), [], 10000.0)
        s2 = f.sepet_guncelle(s1, self.skorlar(), [], 10000.0)
        self.assertEqual(len(s2["sepetler"]), 1)
        yeni = [dict(x, kapanis=x["kapanis"] * 1.1) for x in self.skorlar()]
        s3 = f.sepet_guncelle(s2, yeni, [], 10500.0)
        sp = s3["sepetler"][0]
        self.assertAlmostEqual(sp["sepet_getiri_yuzde"], 10.0, places=1)
        self.assertAlmostEqual(sp["xu100_getiri_yuzde"], 5.0, places=1)
        self.assertAlmostEqual(sp["fark_puan"], 5.0, places=1)
        self.assertEqual(s3["karne"]["endeksi_gecen"], 1)


if __name__ == "__main__":
    unittest.main()
