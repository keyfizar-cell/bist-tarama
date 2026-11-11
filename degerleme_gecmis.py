#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
degerleme_gecmis.py  v1.0  (2026-11-11) — BIST100 için 5 yıllık F/K ve PD/DD bandı (haftalık)

Kaynak: İş Yatırım veri servisi (giriş gerekmez)
  - MaliTablo (yıllık, dönem 12): 3Z = ana ortaklık / dönem net kârı, 2O = (ana ortaklık) özkaynak.
    Sanayi şirketleri financialGroup=XI_29, bankalar/finans UFRS (otomatik denenir).
  - HisseTekil: her yılın son işlem günü piyasa değeri (PD).
Her yıl için F/K = PD / net kâr (kâr > 0 ise), PD/DD = PD / özkaynak. Bant: en düşük / ortanca / en yüksek.
NOT: 2023'ten itibaren TMS 29 (enflasyon muhasebesi) uygulandığı için eski yıllar doğrudan kıyaslanamayabilir;
bant bilgi amaçlıdır, adil değer harmanına katılmaz.
Çıktı: data/degerleme_gecmis.json (degerleme.py okur). Hisse listesi data/adil_deger.json'dan alınır.
GÜVENLİK: hata olsa da JSON yazar, eski kayıtları korur, exit(0).
"""
import datetime as dt
import json
import os
import statistics
import sys
import time
import traceback
import urllib.request

SURUM = "1.0"
CIKTI = os.path.join("data", "degerleme_gecmis.json")
GIRDI = os.path.join("data", "adil_deger.json")
TABAN = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/"
YIL_SAYISI = 5
BEKLE = 0.4


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bist-tarama/degerleme_gecmis)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def mali_tablo(kod, yillar, grup):
    q = "&".join("year%d=%d&period%d=12" % (i + 1, y, i + 1) for i, y in enumerate(yillar))
    d = http_json(TABAN + "MaliTablo?companyCode=%s&exchange=TRY&financialGroup=%s&%s" % (kod, grup, q))
    v = d.get("value") or []
    out = {y: {} for y in yillar}
    for r in v:
        k = (r.get("itemCode") or "").strip()
        if k in ("3Z", "2O"):
            for i, y in enumerate(yillar):
                x = r.get("value%d" % (i + 1))
                if x is not None:
                    out[y]["kar" if k == "3Z" else "ozk"] = float(x)
    return out if v else None


def finansallar(kod, yillar):
    sonuc = {}
    for grup in ("XI_29", "UFRS"):
        ok = False
        ys = sorted(yillar, reverse=True)
        # servis her istekte 4 dönem bekliyor: en yeni 4 yıl + (gerekirse) kalanlar eski yıllarla doldurulur
        parcalar = [ys[:4]]
        if len(ys) > 4:
            kalan = ys[4:]
            parcalar.append(kalan + [kalan[-1] - i - 1 for i in range(4 - len(kalan))])
        for parca in parcalar:
            m = mali_tablo(kod, parca, grup)
            time.sleep(BEKLE)
            if m:
                ok = True
                for y, v in m.items():
                    if v and y in yillar:
                        sonuc.setdefault(y, {}).update(v)
        if ok and any(v.get("ozk") for v in sonuc.values()):
            return sonuc, grup
        sonuc = {}
    return {}, None


def yil_sonu_pd(kod, yillar):
    bas, son = "20-12-%d" % min(yillar), "31-12-%d" % max(yillar)
    d = http_json(TABAN + "HisseTekil?hisse=%s&startdate=%s&enddate=%s" % (kod, bas, son))
    son_gun = {}
    for r in d.get("value") or []:
        try:
            t = dt.datetime.strptime(r["HGDG_TARIH"], "%d-%m-%Y")
        except Exception:
            continue
        if t.year in yillar and r.get("PD"):
            if t.year not in son_gun or t > son_gun[t.year][0]:
                son_gun[t.year] = (t, float(r["PD"]))
    return {y: v[1] for y, v in son_gun.items()}


def bant(degerler):
    d = sorted(x for x in degerler if x is not None)
    if len(d) < 3:
        return None
    return {"min": round(d[0], 2), "ortanca": round(statistics.median(d), 2), "max": round(d[-1], 2), "n": len(d)}


def hisse_isle(kod, yillar):
    fin, grup = finansallar(kod, yillar)
    pd = yil_sonu_pd(kod, yillar)
    time.sleep(BEKLE)
    yil = {}
    for y in yillar:
        f, p = fin.get(y) or {}, pd.get(y)
        if not p:
            continue
        fk = p / f["kar"] if f.get("kar") and f["kar"] > 0 else None
        pb = p / f["ozk"] if f.get("ozk") and f["ozk"] > 0 else None
        if fk is not None and not (0 < fk < 200):
            fk = None
        yil[str(y)] = {"fk": round(fk, 2) if fk else None, "pddd": round(pb, 2) if pb else None}
    return {"grup": grup, "yillar": yil,
            "fk_bant": bant([v["fk"] for v in yil.values()]),
            "pddd_bant": bant([v["pddd"] for v in yil.values()])}


def main():
    try:
        with open(CIKTI, encoding="utf-8") as f:
            eski = json.load(f)
    except Exception:
        eski = {}
    cikti = {"surum": SURUM, "uretim_zamani_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "hata": None, "hisseler": dict(eski.get("hisseler") or {}),
             "not": "Yıl sonu PD / yıllık net kâr ve özkaynak (İş Yatırım). 2023+ TMS 29: eski yıllarla kıyas sınırlı."}
    try:
        with open(GIRDI, encoding="utf-8") as f:
            kodlar = [h["kod"] for h in json.load(f).get("hisseler") or [] if h.get("kod")]
        bu_yil = dt.date.today().year
        yillar = list(range(bu_yil - YIL_SAYISI, bu_yil))
        hatalar = 0
        for kod in kodlar:
            try:
                cikti["hisseler"][kod] = hisse_isle(kod, yillar)
            except Exception as e:
                hatalar += 1
                print(kod, "hata:", type(e).__name__, str(e)[:100])
        cikti["yillar"] = yillar
        cikti["basari"] = len(kodlar) - hatalar
        cikti["hata_sayisi"] = hatalar
    except Exception:
        traceback.print_exc()
        cikti["hata"] = traceback.format_exc().strip().splitlines()[-1][:300]
    os.makedirs("data", exist_ok=True)
    with open(CIKTI, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=1)
    print("YAZILDI:", CIKTI, cikti.get("basari"), "hisse")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
    sys.exit(0)
