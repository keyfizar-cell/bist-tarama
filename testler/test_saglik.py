"""araclar/saglik.py: iş günü farkı ve bayatlık kararı (kurgusal veri)."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "araclar"))
import saglik  # noqa: E402

D = dt.date


class IsGunu(unittest.TestCase):
    def test_hafta_sonu_ve_tatil_sayilmaz(self):
        self.assertEqual(saglik.is_gunu_farki(D(2026, 11, 20), D(2026, 11, 23)), 1)   # Cuma → Pazartesi
        self.assertEqual(saglik.is_gunu_farki(D(2026, 10, 28), D(2026, 10, 30)), 1)   # 29 Ekim tatil


class Denetim(unittest.TestCase):
    def kur(self, dosyalar):
        d = tempfile.TemporaryDirectory(); self.addCleanup(d.cleanup)
        for ad, v in dosyalar.items():
            (pathlib.Path(d.name) / f"{ad}.json").write_text(json.dumps(v))
        eski = saglik.VERI; saglik.VERI = pathlib.Path(d.name); self.addCleanup(setattr, saglik, "VERI", eski)

    def taze(self, t="2026-11-24"):
        z = t + "T15:21:00+00:00"
        return {"latest": {"tarih": t, "uretim_zamani_utc": z, "aktif_mod": "oturumlu", "rsi_mevcut": True,
                           "hisse_sayisi": 620, "alan_seti": "tam"},
                "status": {"sonuc": "success", "zaman_utc": z},
                **{k: {"uretim_zamani_utc": z} for k in ("kap", "geri_alim", "fon", "bulten_girdi")}}

    def test_saglikli(self):
        self.kur(self.taze())
        self.assertEqual(saglik.denetle(D(2026, 11, 24)), [])

    def test_bayat_tarama_ve_yan_dosya(self):
        v = self.taze("2026-11-19")
        self.kur(v)
        s = " ".join(saglik.denetle(D(2026, 11, 24)))
        self.assertIn("KRONİK", s)
        self.assertIn("bulten_girdi", s)


if __name__ == "__main__":
    unittest.main()
