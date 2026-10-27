#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fon_tarama.py  (v1.0)  —  BIST portföy/eurobond/TL-borçlanma fonları için
TEFAS'tan YAPILANDIRILMIŞ fon verisi üretir -> data/fon.json

TASARIM (kap_tarama.py ile aynı disiplin):
  - Ana tarama (tarama.py / bist-tarama.yml) HİÇBİR ŞEKİLDE DEĞİŞMEZ.
  - Bu script AYRI/İZOLE çalışır; her fon kendi try/except'inde; HER DURUMDA
    data/fon.json yazar ve sys.exit(0) ile biter -> iş akışını ASLA düşürmez.
  - Birincil kaynak: tefasmak (login/anahtar YOK, curl_cffi ile Akamai bypass).
    Yedek: pytefas (resmi JSON endpoint). İkisi de yoksa fon.json'a hata yazar.
  - TEFAS cloud/sandbox Bash'ten 403; bu yüzden CANLI veri YALNIZCA GitHub
    Actions'ta (tam internet) test edilebilir. Yerel test mock iledir.

KULLANIM: python3 fon_tarama.py   (repo kökünde; data/ klasörüne yazar)
"""
import os, sys, json, datetime, traceback

# ---- DÜZENLENEBİLİR FON LİSTESİ (Alpay elle günceller) ----
# Portföy fonları + sabah bülteni 7.5c eurobond/TL-borçlanma fonları.
FON_KODLARI = [
    # portföy
    "IAM", "IBB", "IJC", "TI2", "ZBJ",
    # eurobond (USD) fonları
    "DBH", "FPE", "GPA", "YBE", "FUB", "AKE", "IPV", "TPL",
    # TL borçlanma araçları
    "TZV", "TSI",
]

ICERIK_ISTENEN = True   # portföy dağılımı da çekilsin mi (biraz daha yavaş)


def _tefasmak_cek(kod):
    """tefasmak ile tek fon: anlık bilgi + 1a/1y getiri + içerik dağılımı."""
    from tefasmak import fon_anlik_bilgi, fon_5y_fiyat
    info = fon_anlik_bilgi(kod)
    kayit = {
        "fon_kodu": info.get("fonKodu", kod),
        "fon_unvan": info.get("fonUnvan"),
        "son_fiyat": info.get("sonFiyat"),
        "gunluk_getiri": info.get("gunlukGetiri"),
        "kategori": info.get("fonKategori"),
        "kategori_derece": info.get("kategoriDerece"),
        "kategori_fon_say": info.get("kategoriFonSay"),
        "buyukluk_tl": info.get("portBuyukluk"),
        "yatirimci_sayi": info.get("yatirimciSayi"),
        "kaynak": "tefasmak",
    }
    # 1 ay / 1 yıl getiriyi 5 yıllık seriden hesapla (işlem günü bazlı yaklaşık)
    try:
        seri = fon_5y_fiyat(kod)  # [{tarih, fiyat}, ...] kronolojik
        if seri and len(seri) >= 2:
            son = float(seri[-1]["fiyat"])
            kayit["fiyat_tarih"] = seri[-1].get("tarih")
            def getiri(gun):
                if len(seri) > gun and float(seri[-1 - gun]["fiyat"]):
                    return round((son / float(seri[-1 - gun]["fiyat"]) - 1) * 100, 2)
                return None
            kayit["getiri_1a"] = getiri(21)    # ~1 ay
            kayit["getiri_1y"] = getiri(252)   # ~1 yıl
    except Exception as e:
        kayit["getiri_hata"] = str(e)[:120]
    # içerik dağılımı
    if ICERIK_ISTENEN:
        try:
            from tefasmak import fon_portfoy_dagilimi, portfoy_dagilimi_normalize
            ham = fon_portfoy_dagilimi(kod)
            dag = portfoy_dagilimi_normalize(ham)
            # yalnız anlamlı (>=0.5%) kalemleri tut, büyükten küçüğe
            kayit["icerik"] = {k: v for k, v in sorted(
                dag.items(), key=lambda x: -x[1]) if v and v >= 0.5}
        except Exception as e:
            kayit["icerik_hata"] = str(e)[:120]
    return kayit


def _pytefas_cek(kod):
    """Yedek: pytefas ile anlık bilgi (API farklı olabilir; savunmacı)."""
    import pytefas
    # pytefas API'si sürümle değişebilir; en yaygın giriş noktalarını dene.
    for fn_adi in ("fund_info", "get_fund", "info", "fon"):
        fn = getattr(pytefas, fn_adi, None)
        if callable(fn):
            d = fn(kod)
            if isinstance(d, dict):
                return {"fon_kodu": kod, "ham": d, "kaynak": "pytefas"}
    raise RuntimeError("pytefas uygun fonksiyon bulunamadı")


def fon_cek(kod):
    """Önce tefasmak, olmazsa pytefas; ikisi de patlarsa hata kaydı döndür."""
    try:
        return _tefasmak_cek(kod)
    except Exception as e1:
        try:
            r = _pytefas_cek(kod)
            r["tefasmak_hata"] = str(e1)[:120]
            return r
        except Exception as e2:
            return {"fon_kodu": kod, "hata": f"tefasmak: {str(e1)[:90]} | pytefas: {str(e2)[:90]}"}


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    cikti = {
        "uretim_zamani_utc": now.isoformat(),
        "tarih": now.date().isoformat(),
        "kaynak": "tefasmak>pytefas",
        "aciklama": "BIST portföy + eurobond + TL borçlanma fonları (TEFAS). Ana taramadan bağımsız üretilir.",
        "fonlar": {},
    }
    basari = hata = 0
    for kod in FON_KODLARI:
        try:
            kayit = fon_cek(kod)
        except Exception as e:
            kayit = {"fon_kodu": kod, "hata": "beklenmedik: " + str(e)[:100]}
        cikti["fonlar"][kod] = kayit
        if kayit.get("hata"):
            hata += 1
        else:
            basari += 1
    cikti["basari_sayisi"] = basari
    cikti["hata_sayisi"] = hata

    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", "fon.json"), "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print(f"fon.json yazıldı: {basari} başarı / {hata} hata / {len(FON_KODLARI)} fon")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # her ihtimale karşı: fon.json yine de yazılsın, iş akışı düşmesin
        traceback.print_exc()
        try:
            os.makedirs("data", exist_ok=True)
            with open(os.path.join("data", "fon.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "uretim_zamani_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "tarih": datetime.date.today().isoformat(),
                    "fonlar": {}, "basari_sayisi": 0, "hata_sayisi": len(FON_KODLARI),
                    "genel_hata": "main() çöktü",
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    sys.exit(0)   # ASLA non-zero dönme
