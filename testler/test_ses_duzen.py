import pathlib
import sys
import unittest

try:
    import numpy as np
except ImportError:                      # CI'da numpy kurulu değil: bu modül atlanır, diğer testler çalışır
    raise unittest.SkipTest("numpy yok")

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / ".claude" / "skills" / "cinematic-film" / "scripts"))
import ses_duzen as sd  # noqa: E402

SR = 24000


def ton(sn, genlik=0.5, f=180.0):
    t = np.arange(int(sn * SR)) / SR
    return (genlik * np.sin(2 * np.pi * f * t)).astype(np.float32)


def sessiz(sn):
    return np.zeros(int(sn * SR), dtype=np.float32)


class TtsMetni(unittest.TestCase):
    def test_marka_yazimlari_tek_kelime(self):
        self.assertEqual(sd.tts_metni("Yorumlara yaz, KeyfiZar'ı takip et."), "Yorumlara yaz, Keyfizarı takip et.")
        self.assertEqual(sd.tts_metni("Keyfi Zar'ı takip et."), "Keyfizarı takip et.")
        self.assertEqual(sd.tts_metni("KEYFİZAR’ın sesi"), "Keyfizarın sesi")
        self.assertEqual(sd.tts_metni("keyfizar ve KeyfiZar"), "Keyfizar ve Keyfizar")

    def test_siradan_sozlere_dokunmaz(self):
        for s in ("Keyfi zarar verme.", "Keyfine göre zar at.", "keyfi davranma"):
            self.assertEqual(sd.tts_metni(s), s)


class SonKelimeBasi(unittest.TestCase):
    def test_uydurma_ek_kelime_atlanir(self):
        k = [(" Yorumlara", 0.0), (" yaz,", 0.6), (" keyfizarı", 0.9), (" takip", 1.5), (" et", 1.9), (" bil.", 2.2)]
        self.assertEqual(sd.son_kelime_basi("Yorumlara yaz, Keyfizarı takip et.", k), 1.9)

    def test_bulunamazsa_son_duyulan_ve_bos(self):
        self.assertEqual(sd.son_kelime_basi("takip et.", [(" takip", 0.1), (" edin.", 0.5)]), 0.5)
        self.assertEqual(sd.son_kelime_basi("takip et.", []), 0.0)


class KuyrukKes(unittest.TestCase):
    def test_uydurma_hece_kesilir_ve_kirli_sayilir(self):
        # "et" (0.30 sn) + 0.15 sn sessizlik + uydurma "gi" (0.12 sn)
        wav = np.concatenate([sessiz(0.1), ton(0.30), sessiz(0.15), ton(0.12, 0.3), sessiz(0.2)])
        out, artik, bulundu = sd.kuyruk_kes(wav, SR, son_kelime_bas=0.1)
        self.assertTrue(bulundu)
        self.assertAlmostEqual(len(out) / SR, 0.40 + sd.PAY, delta=0.015)
        self.assertGreater(artik, sd.ESIK_DB)          # kesimden sonra ses var → tohum tercih edilmez
        self.assertEqual(out[-1], 0.0)                 # sönümlenmiş, sert kesim yok

    def test_temiz_kuyruk(self):
        wav = np.concatenate([ton(0.4), sessiz(0.5)])
        out, artik, bulundu = sd.kuyruk_kes(wav, SR, son_kelime_bas=0.0)
        self.assertTrue(bulundu)
        self.assertLess(artik, sd.ESIK_DB)
        self.assertLess(len(out) / SR, 0.45)

    def test_kisa_kapanis_kesilmez(self):
        # "et" içindeki t kapanışı (60 ms) sessizlik sayılmaz; t patlaması korunur
        wav = np.concatenate([ton(0.2), sessiz(0.06), ton(0.04, 0.3, 3000.0), sessiz(0.4)])
        out, artik, bulundu = sd.kuyruk_kes(wav, SR, son_kelime_bas=0.0)
        self.assertTrue(bulundu)
        self.assertGreaterEqual(len(out) / SR, 0.30)
        self.assertLess(artik, sd.ESIK_DB)

    def test_sessizlik_yoksa_sona_kadar_ve_bulunamadi(self):
        wav = ton(0.5)
        out, artik, bulundu = sd.kuyruk_kes(wav, SR, son_kelime_bas=0.0)
        self.assertFalse(bulundu)
        self.assertEqual(len(out), len(wav))

    def test_bos_ve_sessiz_girdi(self):
        out, artik, bulundu = sd.kuyruk_kes(np.zeros(0, np.float32), SR, 0.0)
        self.assertEqual(len(out), 0)
        out, artik, bulundu = sd.kuyruk_kes(sessiz(0.3), SR, 0.0)
        self.assertTrue(bulundu)


if __name__ == "__main__":
    unittest.main()
