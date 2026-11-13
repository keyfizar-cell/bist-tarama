import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import abd_fiyat as a  # noqa: E402


class TestAbdFiyat(unittest.TestCase):
    def test_rsi_uclar(self):
        self.assertEqual(a.rsi(list(range(1, 40))), 100.0)
        self.assertLess(a.rsi(list(range(40, 1, -1))), 1)
        self.assertIsNone(a.rsi([1, 2, 3]))

    def test_macd_yon(self):
        self.assertEqual(a.macd([float(i) for i in range(60)])["yon"], "pozitif")
        self.assertIsNone(a.macd([1.0] * 10))

    def test_ozet(self):
        kap = [100 + i for i in range(40)]
        d = {"chart": {"result": [{"meta": {"regularMarketPrice": 140, "currency": "USD", "shortName": "X",
                                            "marketState": "CLOSED"},
                                   "timestamp": [1700000000 + 86400 * i for i in range(40)],
                                   "indicators": {"quote": [{"close": kap, "high": [k + 1 for k in kap],
                                                             "low": [k - 1 for k in kap]}]}}]}}
        o = a.ozet("X", d)
        self.assertEqual(o["son"], 140)
        self.assertEqual(o["onceki_kapanis"], 138)
        self.assertEqual(o["h52_zirve"], 140)
        self.assertEqual(o["h52_dip"], 99)
        self.assertAlmostEqual(o["gunluk_yuzde"], 1.45, places=2)


if __name__ == "__main__":
    unittest.main()
