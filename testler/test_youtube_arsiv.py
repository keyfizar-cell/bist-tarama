import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import youtube_arsiv as ar  # noqa: E402


class TestArsiv(unittest.TestCase):
    def test_sirala(self):
        ad = [{"video_id": "a", "sure_dk": 10}, {"video_id": "b", "sure_dk": 60},
              {"video_id": "c", "sure_dk": 30}, {"video_id": "d", "sure_dk": 90}]
        s = ar.sirala(ad, {"b"}, {"d": 2})
        self.assertEqual([x["video_id"] for x in s], ["c", "a"])

    def test_kisi_isle_birikir_ve_hata_sayar(self):
        kisi = {"ad": "X", "sorgu": "x"}
        eski = {"aday_guncelleme_utc": ar.simdi().isoformat(),
                "adaylar": [{"video_id": "v1", "url": "u1", "sure_dk": 50}, {"video_id": "v2", "url": "u2", "sure_dk": 20}],
                "islenenler": [], "hatali": {}}
        with mock.patch.object(ar.yt, "gemini_transkript",
                               return_value=({"ilkeler": ["i"], "ozet": ["o"], "bahsedilen_hisseler": [],
                                              "konusmaci_dogrulandi": True}, "gemini:m", "STOP")):
            k = ar.kisi_isle(kisi, eski, "", 1)
        self.assertEqual([v["video_id"] for v in k["islenenler"]], ["v1"])
        self.assertEqual(k["kalan_aday"], 1)
        with mock.patch.object(ar.yt, "gemini_transkript", side_effect=RuntimeError("x")):
            k = ar.kisi_isle(kisi, k, "", 1)
        self.assertEqual(k["hatali"], {"v2": 1})
        self.assertEqual(len(k["islenenler"]), 1)


if __name__ == "__main__":
    unittest.main()
