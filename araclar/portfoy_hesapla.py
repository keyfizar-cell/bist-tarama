#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
araclar/portfoy_hesapla.py  v1.0  (2026-11-07)  — Aşama 2 (portföy)

"Alpay - Porfoy Takip" tablosunun xlsx dışa aktarımından portföy hesaplarını yapar.
GİZLİLİK: Bu repo herkese açıktır. Betik YALNIZ zamanlanmış görevin kendi oturumunda,
görevin Drive'dan indirdiği dosya üzerinde çalışır; sonucu yerel bir dosyaya (/tmp)
yazar. Portföy verisi ASLA repoya, data/ klasörüne veya Actions günlüğüne yazılmaz.

Kullanım (bülten görevinde):
  python3 portfoy_hesapla.py --xlsx /tmp/portfoy.xlsx --latest /tmp/bist.json \
      --bulten-girdi /tmp/bg.json --cikti /tmp/portfoy_hesap.json

Sayfa yapısı (07.11.2026 itibarıyla doğrulandı):
  Kar-Zarar : 2. satır başlık; A="İlk Alım" DOLU → açık pozisyon; C=Kod, D=Tür, E=Yatırılan TL
  DB - VEri : 3. satırdan itibaren A=Kod, B=Tür, C=Sektör, D=Maliyet TL, E=Güncel TL, F=K/Z TL,
              I=Kod, J=Pay, K=Ortalama, L=GüncelFiy (bayat olabilir), M=Değişim
  Veri      : işlem defteri; A=Tarih, B=Sahip, D=Durum, E=İşlem(Alış/Satış), F=Kod, G=Tür, H=Adet,
              I=Birim fiyat, J=Top. TL Maliyet (Satış satırında NEGATİF), O=TL K/Z (cari fiyatla;
              KAPALI lotta anlamsız), R=Sonuç (Açık/Kapalı)

Kurallar:
  - Kapalı lotların gerçekleşmiş kârı = −Σ J (yalnız Sonuç=Kapalı satırlar). O sütunu KULLANILMAZ.
  - Açık lotların anlık K/Z = Σ O (yalnız Sonuç=Açık ve İşlem=Alış satırları).
  - Aynı kodda hem kapalı hem açık lot varsa ikisi AYRI raporlanır (eski bülten kuralı bunları
    karıştırıp açık alışları da −ΣJ'ye katıyordu).
  - Mantık denetimi: kapalı lotlarda ortalama satış > ortalama alış ise realize kâr POZİTİF olmalı.
"""
import argparse
import datetime as dt
import json
import sys

SURUM = "1.0"
YENI_POZISYON_GUN = 7


def sayi(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def yuv(x, n=2):
    return round(x, n) if sayi(x) else None


def tarih(x):
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    return None


# ── sayfa okuyucular (openpyxl Workbook alır; testler sahte çalışma kitabıyla çağırır) ──
def acik_pozisyonlar(wb, bugun):
    ws = wb["Kar-Zarar"]
    out = []
    for r in ws.iter_rows(min_row=3, max_col=5, values_only=True):
        ilk, _gecen, kod, tur, yatirilan = (list(r) + [None] * 5)[:5]
        if not kod or tarih(ilk) is None:
            continue
        ilk_t = tarih(ilk)
        out.append({"kod": str(kod).strip(), "tur": tur, "ilk_alim": ilk_t.isoformat(),
                    "yeni_pozisyon": (bugun - ilk_t).days <= YENI_POZISYON_GUN,
                    "yatirilan_tl": yuv(yatirilan)})
    return out


def db_veri(wb):
    ws = wb["DB - VEri"]
    out = {}
    for r in ws.iter_rows(min_row=3, max_col=13, values_only=True):
        r = list(r) + [None] * 13
        kod = r[0]
        if not kod:
            continue
        kod = str(kod).strip()
        maliyet, guncel, kz = r[3], r[4], r[5]
        out[kod] = {"tur": r[1], "sektor": r[2], "maliyet_tl": yuv(maliyet), "guncel_tl_dosya": yuv(guncel),
                    "kz_tl_dosya": yuv(kz), "kz_yuzde_dosya": yuv(100.0 * kz / maliyet) if sayi(kz) and sayi(maliyet) and maliyet else None}
    for r in ws.iter_rows(min_row=3, max_col=13, values_only=True):
        r = list(r) + [None] * 13
        kod = r[8]
        if kod and str(kod).strip() in out:
            d = out[str(kod).strip()]
            d["pay_yuzde"] = yuv(100.0 * r[9], 2) if sayi(r[9]) else None
            d["ortalama"] = yuv(r[10], 6)
    return out


def defter(wb):
    ws = wb["Veri"]
    out = []
    for r in ws.iter_rows(min_row=2, max_col=18, values_only=True):
        r = list(r) + [None] * 18
        if not r[5]:
            continue
        out.append({"tarih": tarih(r[0]), "sahip": r[1], "islem": r[4], "kod": str(r[5]).strip(), "tur": r[6],
                    "adet": r[7], "birim": r[8], "j": r[9], "o": r[14], "sonuc": r[17]})
    return out


# ── hesaplar (saf) ──
def kod_kar(satirlar, kod):
    s = [x for x in satirlar if x["kod"] == kod]
    if not s:
        return {"kod": kod, "etiket": "işlem yok"}
    kap = [x for x in s if x["sonuc"] == "Kapalı"]
    acik = [x for x in s if x["sonuc"] == "Açık" and x["islem"] == "Alış"]
    sonuc = {"kod": kod}
    if kap:
        alis = [x for x in kap if x["islem"] == "Alış"]
        satis = [x for x in kap if x["islem"] == "Satış"]
        realize = -sum(x["j"] for x in kap if sayi(x["j"]))
        alis_tl = sum(x["j"] for x in alis if sayi(x["j"]))
        def ort(liste):
            a = sum(x["adet"] for x in liste if sayi(x["adet"]))
            t = sum(abs(x["j"]) for x in liste if sayi(x["j"]))
            return t / a if a else None
        ort_alis, ort_satis = ort(alis), ort(satis)
        mantik = True
        if ort_alis and ort_satis:
            mantik = (ort_satis > ort_alis) == (realize > 0) or abs(realize) < 0.01
        sonuc["kapali"] = {"realize_tl": yuv(realize), "alis_tl": yuv(alis_tl),
                           "kar_yuzde": yuv(100.0 * realize / alis_tl) if alis_tl else None,
                           "ort_alis": yuv(ort_alis, 4), "ort_satis": yuv(ort_satis, 4),
                           "mantik_denetimi_gecti": mantik}
    if acik:
        maliyet = sum(x["j"] for x in acik if sayi(x["j"]))
        kz = sum(x["o"] for x in acik if sayi(x["o"]))
        sonuc["acik"] = {"maliyet_tl": yuv(maliyet), "anlik_kz_tl_dosya": yuv(kz),
                         "kz_yuzde_dosya": yuv(100.0 * kz / maliyet) if maliyet else None,
                         "adet": yuv(sum(x["adet"] for x in acik if sayi(x["adet"])), 4)}
    sonuc["etiket"] = "+".join(e for e, v in (("kapalı", kap), ("açık", acik)) if v) or "işlem yok"
    return sonuc


def defterden_ortalama(satirlar, kod):
    acik = [x for x in satirlar if x["kod"] == kod and x["sonuc"] == "Açık" and x["islem"] == "Alış"]
    a = sum(x["adet"] for x in acik if sayi(x["adet"]))
    t = sum(x["j"] for x in acik if sayi(x["j"]))
    return (t / a if a else None), t


def hesapla(wb, bugun, latest=None, kodlar_7c=None):
    acik = acik_pozisyonlar(wb, bugun)
    db = db_veri(wb)
    satirlar = defter(wb)
    fiyat = {h["kod"]: h for h in (latest or {}).get("tum_hisseler", [])} if latest else {}
    uyarilar = []
    pozisyonlar = []
    for p in acik:
        kod = p["kod"]
        d = dict(db.get(kod) or {})
        if not d:
            ort, maliyet = defterden_ortalama(satirlar, kod)
            d = {"ortalama": yuv(ort, 6), "maliyet_tl": yuv(maliyet), "pay_yuzde": None,
                 "kaynak": "işlem defteri (DB - VEri'de yok)"}
            uyarilar.append("%s: DB - VEri sayfasında yok; ortalama/maliyet işlem defterinden hesaplandı" % kod)
        h = fiyat.get(kod)
        bugunku = None
        if h and sayi(h.get("kapanis")) and sayi(d.get("ortalama")) and d["ortalama"]:
            bugunku = {"kapanis": h["kapanis"], "gunluk_yuzde": yuv(h.get("gunluk_yuzde")),
                       "maliyete_gore_kz_yuzde": yuv(100.0 * (h["kapanis"] / d["ortalama"] - 1))}
        pozisyonlar.append(dict(p, **d, bugun=bugunku))
    sayim = {}
    for p in acik:
        sayim[p["tur"] or "?"] = sayim.get(p["tur"] or "?", 0) + 1
    db_fazla = sorted(set(db) - {p["kod"] for p in acik})
    if db_fazla:
        uyarilar.append("DB - VEri'de olup Kar-Zarar'da açık görünmeyen: " + ", ".join(db_fazla))
    sonuc = {
        "surum": SURUM, "hesap_zamani_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "acik_pozisyon_sayisi": len(acik), "tur_sayilari": sayim,
        "pozisyonlar": pozisyonlar,
        "toplam": {"maliyet_tl": yuv(sum(d["maliyet_tl"] for d in db.values() if sayi(d.get("maliyet_tl")))),
                   "guncel_tl_dosya": yuv(sum(d["guncel_tl_dosya"] for d in db.values() if sayi(d.get("guncel_tl_dosya"))))},
        "sahipler": sorted({x["sahip"] for x in satirlar if x["sahip"]}),
        "uyarilar": uyarilar,
    }
    if kodlar_7c:
        sonuc["kar_7c"] = {k: kod_kar(satirlar, k) for k in kodlar_7c}
        hatali = [k for k, v in sonuc["kar_7c"].items() if v.get("kapali") and not v["kapali"]["mantik_denetimi_gecti"]]
        if hatali:
            uyarilar.append("Mantık denetimi başarısız (kapalı lot): " + ", ".join(hatali))
    return sonuc


def main(argv=None):
    ap = argparse.ArgumentParser(description="Portföy hesapları (yerel; repoya yazmaz)")
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--latest", help="data/latest.json (bugünkü kapanışlar)")
    ap.add_argument("--bulten-girdi", help="data/bulten_girdi.json (7c kodları buradan)")
    ap.add_argument("--kodlar", help="virgülle ayrılmış ek kodlar (7c için)")
    ap.add_argument("--bugun", help="YYYY-AA-GG (varsayılan: bugün)")
    ap.add_argument("--cikti", required=True, help="yerel çıktı yolu (ör. /tmp/portfoy_hesap.json)")
    a = ap.parse_args(argv)
    if a.cikti.startswith("data/") or "/data/" in a.cikti:
        sys.exit("GİZLİLİK: çıktı data/ altına yazılamaz")
    import openpyxl
    wb = openpyxl.load_workbook(a.xlsx, data_only=True)
    bugun = dt.date.fromisoformat(a.bugun) if a.bugun else dt.date.today()
    latest = json.load(open(a.latest, encoding="utf-8")) if a.latest else None
    kodlar = []
    if a.bulten_girdi:
        bg = json.load(open(a.bulten_girdi, encoding="utf-8"))
        kodlar += [s["kod"] for s in (bg.get("sinyal_gecmisi") or {}).get("satirlar", [])]
    if a.kodlar:
        kodlar += [k.strip() for k in a.kodlar.split(",") if k.strip()]
    sonuc = hesapla(wb, bugun, latest, sorted(set(kodlar)) or None)
    with open(a.cikti, "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1, default=str)
    print("YAZILDI:", a.cikti, "| açık pozisyon:", sonuc["acik_pozisyon_sayisi"], sonuc["tur_sayilari"],
          "| uyarı:", len(sonuc["uyarilar"]))


if __name__ == "__main__":
    main()
