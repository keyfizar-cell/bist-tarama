"""tarama.degerlendir: tam kurulum kuralı (kurgusal satırlar; ağ ve TradingView gerekmez)."""
import os
import sys
import types
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
for ad in ("pandas", "tradingview_screener"):            # CI'da kurulu değil; degerlendir bunları kullanmaz
    if ad not in sys.modules:
        try:
            __import__(ad)
        except ImportError:
            m = types.ModuleType(ad)
            m.Query = object
            sys.modules[ad] = m
import tarama  # noqa: E402

# Aşırı satım (BB altı) + MACD sinyali yukarı kesmiş + hacim 3x + fiyat 50MA üstü
TAM = {"name": "AAAAA", "close": 10.0, "BB.lower": 10.5, "MACD.macd": -0.1, "MACD.signal": -0.2,
       "SMA50": 9.5, "volume": 3_000_000, "average_volume_10d_calc": 1_000_000, "RSI": 35, "change": -2.0}


def satir(**ek):
    return {**TAM, **ek}


class TamKurulum(unittest.TestCase):
    def test_tum_kosullar_saglaninca_tam_kurulum(self):
        k = tarama.degerlendir(satir(), True)
        self.assertTrue(k["TAM_KURULUM"])
        self.assertEqual(k["hacim_orani"], 3.0)

    def test_hacim_yetersizse_elenir(self):
        self.assertFalse(tarama.degerlendir(satir(volume=1_500_000), True)["TAM_KURULUM"])

    def test_hacim_verisi_yoksa_elenir(self):
        for ek in ({"volume": None}, {"average_volume_10d_calc": 0}):
            k = tarama.degerlendir(satir(**ek), True)
            self.assertTrue(k["hacim_elemesi"])
            self.assertFalse(k["TAM_KURULUM"])

    def test_dusen_bicak_teyit_sayilmaz(self):
        # MACD 0 altı ve sinyalin altında + fiyat 50MA altında
        k = tarama.degerlendir(satir(**{"MACD.macd": -0.3, "MACD.signal": -0.2, "SMA50": 11.0}), True)
        self.assertTrue(k["dusen_bicak"])
        self.assertFalse(k["TAM_KURULUM"])

    def test_sermaye_islemi_elenir(self):
        k = tarama.degerlendir(satir(change=-40.0), True)
        self.assertTrue(k["olasi_sermaye_islemi"])
        self.assertFalse(k["TAM_KURULUM"])

    def test_rsi_30_alti_bb_ustunde_de_asiri_satim(self):
        self.assertTrue(tarama.degerlendir(satir(**{"BB.lower": 9.0, "RSI": 25}), True)["asiri_satim"])
        self.assertFalse(tarama.degerlendir(satir(**{"BB.lower": 9.0, "RSI": 25}), False)["asiri_satim"])


if __name__ == "__main__":
    unittest.main()
