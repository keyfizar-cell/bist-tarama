# -*- coding: utf-8 -*-
"""degerleme.py birim testleri (ag yok; kurgusal sirketler)."""
import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import degerleme as d  # noqa: E402

AYAR = d.ayar_oku("/yok.json")


def sirket(kod, sektor="Producer Manufacturing", ind="Industrial Machinery", **kw):
    r = {"kod": kod, "name": kod, "description": kod + " AS", "close": 10.0, "sector": sektor, "industry": ind,
         "market_cap_basic": 1000.0, "price_earnings_ttm": 10.0, "price_book_fq": 2.0,
         "enterprise_value_ebitda_ttm": 6.0, "return_on_equity": 20.0, "debt_to_equity": 0.5,
         "free_cash_flow": 80.0, "net_income": 100.0, "ebitda": 180.0, "net_debt": 80.0, "total_debt": 200.0,
         "dividends_yield_current": 3.0, "beta_1_year": 1.0, "earnings_release_next_date": None}
    r.update(kw)
    return r


def evren():
    tum = []
    for i, (fk, pb, ev, roe) in enumerate([(6, 1, 4, 10), (8, 1.5, 5, 15), (10, 2, 6, 20), (12, 2.5, 7, 25),
                                           (14, 3, 8, 30)]):
        tum.append(sirket("SAN%d" % i, price_earnings_ttm=fk, price_book_fq=pb, enterprise_value_ebitda_ttm=ev,
                          return_on_equity=roe))
    for i, (pb, roe) in enumerate([(0.8, 20), (1.0, 25), (1.2, 30), (1.4, 35), (1.6, 40)]):
        tum.append(sirket("BNK%d" % i, "Finance", "Major Banks", price_book_fq=pb, return_on_equity=roe,
                          price_earnings_ttm=4 + i, enterprise_value_ebitda_ttm=None, ebitda=None,
                          free_cash_flow=None))
    return tum


class EsGrup(unittest.TestCase):
    def test_dilimler_alt_sektor(self):
        t = d.es_grup_tablosu(evren())
        g, kaynak = d.es_grup(t, "fk", sirket("X"))
        self.assertEqual(kaynak, "industry")
        self.assertEqual((g["p25"], g["p50"], g["p75"]), (8, 10, 12))

    def test_az_ornekte_piyasaya_duser(self):
        t = d.es_grup_tablosu(evren())
        _, kaynak = d.es_grup(t, "fk", sirket("Y", "Utilities", "Electric Utilities"))
        self.assertEqual(kaynak, "piyasa")

    def test_uc_degerler_disarida(self):
        tum = evren() + [sirket("UC", price_earnings_ttm=500.0), sirket("NEG", price_earnings_ttm=-3.0)]
        g, _ = d.es_grup(d.es_grup_tablosu(tum), "fk", sirket("X"))
        self.assertEqual(g["n"], 5)


class Yontemler(unittest.TestCase):
    def setUp(self):
        self.t = d.es_grup_tablosu(evren())

    def test_goreli_fk_ortanca_esitse_1(self):
        self.assertAlmostEqual(d.goreli_oran(sirket("X"), self.t, "fk", "p50"), 1.0)
        self.assertAlmostEqual(d.goreli_oran(sirket("X", price_earnings_ttm=5.0), self.t, "fk", "p50"), 2.0)

    def test_zarar_eden_fk_yok(self):
        self.assertIsNone(d.goreli_oran(sirket("X", price_earnings_ttm=None), self.t, "fk", "p50"))

    def test_dcf_buyume_arttikca_deger_artar(self):
        r = sirket("X")
        a, b = d.dcf_oran(r, 0.0, 0.12, 0.025), d.dcf_oran(r, 0.08, 0.12, 0.025)
        self.assertTrue(a and b and b > a)

    def test_dcf_negatif_fcf_yok(self):
        self.assertIsNone(d.dcf_oran(sirket("X", free_cash_flow=-5.0), 0.04, 0.12, 0.025))

    def test_ters_dcf_tutarli(self):
        r = sirket("X")
        g = d.ters_dcf(r, 0.12, 0.025)
        self.assertIsNotNone(g)
        self.assertAlmostEqual(d.dcf_oran(r, g, 0.12, 0.025), 1.0, places=3)

    def test_roe_ayarli_pddd(self):
        b = sirket("B", "Finance", "Major Banks", price_book_fq=1.0, return_on_equity=60.0)
        self.assertAlmostEqual(d.roe_pddd_oran(b, self.t, "p50"), 1.2 * 2.0)  # ROE oranı 2'de sınırlanır

    def test_yalniz_ddm_ise_deger_yok(self):
        self.assertIsNone(d.harmanla({"ddm": 1.5}, d.AGIRLIK["holding"]))
        self.assertAlmostEqual(d.harmanla({"pddd": 1.0, "ddm": 2.0}, {"pddd": 0.5, "ddm": 0.5}), 1.5)

    def test_tek_yontem_ust_siniri(self):
        self.assertAlmostEqual(d.harmanla({"pddd": 10.0}, {"pddd": 1.0}, 3.0), 3.0)


class Butun(unittest.TestCase):
    def test_siniflar_ve_sira(self):
        self.assertEqual(d.sinif(sirket("AKBNK", "Finance", "Major Banks")), "banka")
        self.assertEqual(d.sinif(sirket("KCHOL")), "holding")
        self.assertEqual(d.sinif(sirket("SAHOL", "Finance", "Major Banks")), "holding")
        self.assertEqual(d.sinif(sirket("EKGYO")), "gyo")
        self.assertEqual(d.sinif(sirket("EREGL", "Non-Energy Minerals", "Steel")), "dongusel")
        satir = d.degerle([sirket("SAN2"), sirket("BNK1", "Finance", "Major Banks", price_book_fq=1.0,
                                                   return_on_equity=25, free_cash_flow=None)], evren(), AYAR)
        for s in satir:
            self.assertLessEqual(s["adil_kotumser"], s["adil_baz"])
            self.assertLessEqual(s["adil_baz"], s["adil_iyimser"])
            self.assertAlmostEqual(s["inceleme_seviyesi"], round(s["adil_baz"] * 0.85, 2), places=1)

    def test_durum(self):
        self.assertTrue(d.durum(8, 10, 8.5, 12).startswith("🟢"))
        self.assertTrue(d.durum(9, 10, 8.5, 12).startswith("🟡"))
        self.assertTrue(d.durum(13, 10, 8.5, 12).startswith("🔴"))
        self.assertTrue(d.durum(11, 10, 8.5, 12).startswith("⚪"))

    def test_deger_tuzagi(self):
        t = d.es_grup_tablosu(evren())
        r = sirket("TZK", price_earnings_ttm=3.0, return_on_equity=4.0, free_cash_flow=-10.0)
        dd = d.hisse_degerle(r, t, AYAR)
        self.assertTrue(any("Değer tuzağı" in u for u in d.uyarilar(r, dd, t)))

    def test_csv_tamsayi(self):
        satir = d.degerle([sirket("SAN2")], evren(), AYAR)
        with tempfile.TemporaryDirectory() as k:
            yol = os.path.join(k, "a.csv")
            d.csv_yaz(satir, yol)
            with open(yol, encoding="utf-8") as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows[0][0], "kod")
        self.assertEqual(rows[1][rows[0].index("kapanis_x100")], "1000")
        for h, v in zip(rows[0], rows[1]):
            if h.endswith("_x100") and v:
                int(v)


class Gecmis(unittest.TestCase):
    G = {"KCHOL": {"pddd_bant": {"min": 0.5, "ortanca": 0.6, "max": 1.1}, "yillar": {"2024": {"pddd": 0.8}, "2025": {"pddd": 0.5}}}}

    def test_tarihsel_pddd_tv_varsa(self):
        r = sirket("KCHOL", price_book_fq=0.4)
        self.assertAlmostEqual(d.tarihsel_pddd_oran(r, self.G), 1.5)

    def test_tarihsel_pddd_tv_yoksa_son_yil(self):
        r = sirket("KCHOL", price_book_fq=None)
        self.assertAlmostEqual(d.tarihsel_pddd_oran(r, self.G), 1.2)  # 0.6 / 0.5 (2025)

    def test_holding_tv_verisi_eksikken_deger_uretir(self):
        r = sirket("KCHOL", price_book_fq=None, price_earnings_ttm=None, ebitda=None,
                   enterprise_value_ebitda_ttm=None, free_cash_flow=None, dividends_yield_current=0)
        s = d.degerle([r], evren(), AYAR, self.G)[0]
        self.assertEqual(s["sinif"], "holding")
        self.assertAlmostEqual(s["adil_baz"], 12.0, places=1)  # yalnız tarihsel PD/DD → 10 × 1.2
        self.assertEqual(s["pddd_5y_ortanca"], 0.6)

    def test_bant_notu(self):
        b = {"min": 3.0, "ortanca": 6.0, "max": 9.0}
        self.assertIn("altında", d.bant_notu(2.0, b, "F/K"))
        self.assertIn("üstünde", d.bant_notu(12.0, b, "F/K"))
        self.assertIsNone(d.bant_notu(5.0, b, "F/K"))


class OneCikanlar(unittest.TestCase):
    def s(self, kod, **kw):
        x = {"kod": kod, "adil_baz": 12, "kapanis": 10, "potansiyel_yuzde": 20, "aday": True, "durum": "🟢 x",
             "uyarilar": [], "yontemler": "dcf %40, fk %20, pddd %10", "sinif": "sanayi", "fk": 5, "fk_sektor": 10,
             "pddd": 1, "pddd_sektor": 1.1, "roe_yuzde": 30, "roe_sektor": 15, "fcf_kar_donusum": 0.9,
             "temettu_verimi_yuzde": 6, "ters_dcf_buyume_yuzde": -5, "fk_5y_ortanca": 8, "pddd_5y_ortanca": 1.0}
        x.update(kw)
        return x

    def test_en_fazla_uc_ve_once_aday(self):
        ss = [self.s("A", potansiyel_yuzde=30), self.s("B", potansiyel_yuzde=50), self.s("C", aday=False, potansiyel_yuzde=90),
              self.s("D", potansiyel_yuzde=10), self.s("E", potansiyel_yuzde=200)]
        o = [x["kod"] for x in d.one_cikanlar(ss)]
        self.assertEqual(o, ["B", "A", "D"])  # E aşırı uç → dışarıda; C aday değil, adaylar yetince girmez

    def test_aday_yetmezse_uyarisiz_yesil(self):
        ss = [self.s("A"), self.s("B", aday=False), self.s("C", aday=False, uyarilar=["⚠️ x"])]
        self.assertEqual([x["kod"] for x in d.one_cikanlar(ss)], ["A", "B"])

    def test_alanlar(self):
        al = d.one_cikan_alanlar(self.s("A"))
        self.assertEqual(len(al), 3)
        self.assertTrue(any("F/K" in a and "sektör" in a for a in al))


class AdayVeDegisim(unittest.TestCase):
    def test_aday_kurali(self):
        s = {"kapanis": 8, "adil_baz": 10, "inceleme_seviyesi": 8.5, "uyarilar": [], "yontemler": "dcf %40, fk %20, pddd %10"}
        self.assertTrue(d.aday_mi(s))
        self.assertFalse(d.aday_mi(dict(s, uyarilar=["⚠️ Değer tuzağı riski: x"])))
        self.assertFalse(d.aday_mi(dict(s, yontemler="pddd %25")))
        self.assertFalse(d.aday_mi(dict(s, kapanis=9)))
        self.assertTrue(d.aday_mi(dict(s, uyarilar=["Kalite: ROE düşük"])))  # ⚠ olmayan not engel değil

    def test_degisimler(self):
        eski = [{"kod": "A", "durum": "⚪ bant", "aday": False}, {"kod": "B", "durum": "🟢 x", "aday": True},
                {"kod": "C", "durum": "🟡 y", "aday": False}]
        yeni = [{"kod": "A", "durum": "🟢 x", "aday": True}, {"kod": "B", "durum": "🟢 x", "aday": True},
                {"kod": "C", "durum": "🔴 z", "aday": False}, {"kod": "D", "durum": "🟢", "aday": True}]
        dd = {x["kod"]: x for x in d.degisimler(yeni, eski)}
        self.assertEqual(set(dd), {"A", "C"})  # B değişmedi, D'nin öncesi yok
        self.assertTrue(dd["A"]["yeni_aday"])


if __name__ == "__main__":
    unittest.main()
