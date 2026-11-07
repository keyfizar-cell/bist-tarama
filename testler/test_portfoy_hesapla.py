# -*- coding: utf-8 -*-
"""araclar/portfoy_hesapla.py testleri — SAHTE çalışma kitabıyla (gerçek portföy verisi repoya girmez)."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "araclar"))
try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None
import portfoy_hesapla as p  # noqa: E402

D = dt.datetime


def sahte_kitap():
    wb = openpyxl.Workbook()
    kz = wb.active
    kz.title = "Kar-Zarar"
    kz.append([None, "Sonuçlanan K/Z"])
    kz.append(["İlk Alım", "Geçen Gün", "Hisse Kodu", "Tür", "Yatırılan TL"])
    kz.append([D(2026, 2, 1), "9 ay", "KARMA", "Hisse", 1000])     # açık + kapalı lot
    kz.append([D(2026, 11, 3), "4 gün", "YENI", "Hisse", 500])     # yeni pozisyon
    kz.append([D(2020, 6, 7), "6 yıl", "COIN", "Kripto", 300])     # DB'de yok
    kz.append([None, None, "KAPANDI", "Hisse", 900])               # kapalı pozisyon
    db = wb.create_sheet("DB - VEri")
    db.append(["Hisse Adları", "Tür", "Sektör", "Maliyet TL Toplam", "Güncel TL Toplam", "Kar / Zarar",
               None, None, "Hisse Adları", "Pay", "Ortalama", "GüncelFİy", "Değişim"])
    db.append([])
    db.append(["KARMA", "Hisse", "Banka", 1000, 900, -100, None, None, "KARMA", 0.6, 10.0, 9.0, -0.1])
    db.append(["YENI", "Hisse", "Enerji", 500, 550, 50, None, None, "YENI", 0.4, 5.0, 5.5, 0.1])
    v = wb.create_sheet("Veri")
    v.append(["Tarih", "Sahip", "Aracı Kurum", "Durum", "İşlem", "Hisse Kodu", "Tür", "Adet", "Maliyet",
              "Top. TL MAliyet", "Top. $ Maliyet", "$ Kuru", "Güncel Fiyat", "Toplam Güncel", "TL K/Z",
              "$ Toplam Güncel", "$ K/Z", "Sonuç"])
    def satir(t, islem, kod, tur, adet, birim, j, o, sonuc, sahip="Alpay"):
        v.append([t, sahip, "X", "Giriş" if islem == "Alış" else "Çıkış", islem, kod, tur, adet, birim, j,
                  None, None, None, None, o, None, None, sonuc])
    # Aynı gün al-sat (kurgusal): 100 @ 40 al, 100 @ 45 sat → +500; O sütunu cari fiyatla yanıltıcı zarar gösterir
    satir(D(2026, 10, 9), "Alış", "GUNICI", "Hisse", 100, 40.0, 4000.0, -1500.0, "Kapalı")
    satir(D(2026, 10, 9), "Satış", "GUNICI", "Hisse", 100, 45.0, -4500.0, -2000.0, "Kapalı")
    # KARMA: kapalı lot +100 kâr, açık lot 100 adet @ 10
    satir(D(2026, 1, 5), "Alış", "KARMA", "Hisse", 50, 20.0, 1000.0, -5.0, "Kapalı")
    satir(D(2026, 1, 9), "Satış", "KARMA", "Hisse", 50, 22.0, -1100.0, -5.0, "Kapalı")
    satir(D(2026, 2, 1), "Alış", "KARMA", "Hisse", 100, 10.0, 1000.0, -100.0, "Açık")
    satir(D(2026, 11, 3), "Alış", "YENI", "Hisse", 100, 5.0, 500.0, 50.0, "Açık", sahip="Diger")
    satir(D(2020, 6, 7), "Alış", "COIN", "Kripto", 10, 30.0, 300.0, 4000.0, "Açık")
    # HATALI: satış satırı yanlış işaretle girilmiş (J pozitif) → mantık denetimi düşmeli
    satir(D(2026, 3, 1), "Alış", "HATALI", "Hisse", 10, 50.0, 500.0, 0.0, "Kapalı")
    satir(D(2026, 3, 2), "Satış", "HATALI", "Hisse", 10, 52.0, 520.0, 0.0, "Kapalı")
    return wb


@unittest.skipIf(openpyxl is None, "openpyxl yok")
class PortfoyHesapla(unittest.TestCase):
    def setUp(self):
        self.wb = sahte_kitap()
        self.latest = {"tum_hisseler": [{"kod": "KARMA", "kapanis": 12.0, "gunluk_yuzde": 1.5}]}
        self.s = p.hesapla(self.wb, dt.date(2026, 11, 7), self.latest,
                           ["GUNICI", "KARMA", "HATALI", "YOKKOD"])

    def test_acik_pozisyonlar_ve_sayim(self):
        self.assertEqual(self.s["acik_pozisyon_sayisi"], 3)
        self.assertEqual(self.s["tur_sayilari"], {"Hisse": 2, "Kripto": 1})
        kodlar = {x["kod"] for x in self.s["pozisyonlar"]}
        self.assertNotIn("KAPANDI", kodlar)

    def test_yeni_pozisyon_isareti(self):
        poz = {x["kod"]: x for x in self.s["pozisyonlar"]}
        self.assertTrue(poz["YENI"]["yeni_pozisyon"])
        self.assertFalse(poz["KARMA"]["yeni_pozisyon"])

    def test_bugunku_kz_ortalamadan(self):
        poz = {x["kod"]: x for x in self.s["pozisyonlar"]}
        self.assertEqual(poz["KARMA"]["bugun"]["maliyete_gore_kz_yuzde"], 20.0)
        self.assertEqual(poz["KARMA"]["pay_yuzde"], 60.0)

    def test_db_de_olmayan_defterden(self):
        poz = {x["kod"]: x for x in self.s["pozisyonlar"]}
        self.assertEqual(poz["COIN"]["ortalama"], 30.0)
        self.assertTrue(any("COIN" in u for u in self.s["uyarilar"]))

    def test_gunici_realize_kar_O_sutunu_kullanilmaz(self):
        k = self.s["kar_7c"]["GUNICI"]["kapali"]
        self.assertEqual(k["realize_tl"], 500.0)
        self.assertEqual(k["kar_yuzde"], 12.5)
        self.assertTrue(k["mantik_denetimi_gecti"])

    def test_karisik_lotlar_ayri(self):
        k = self.s["kar_7c"]["KARMA"]
        self.assertEqual(k["etiket"], "kapalı+açık")
        self.assertEqual(k["kapali"]["realize_tl"], 100.0)
        self.assertEqual(k["acik"]["maliyet_tl"], 1000.0)

    def test_mantik_denetimi_hatali_kayit(self):
        self.assertFalse(self.s["kar_7c"]["HATALI"]["kapali"]["mantik_denetimi_gecti"])
        self.assertTrue(any("HATALI" in u for u in self.s["uyarilar"]))

    def test_islem_yok(self):
        self.assertEqual(self.s["kar_7c"]["YOKKOD"]["etiket"], "işlem yok")

    def test_gizlilik_korumasi(self):
        with self.assertRaises(SystemExit):
            p.main(["--xlsx", "x.xlsx", "--cikti", "data/portfoy.json"])


if __name__ == "__main__":
    unittest.main()
