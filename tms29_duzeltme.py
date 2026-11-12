#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tms29_duzeltme.py  v1.0  (2026-11-12) — 5 faktör modeli için TMS 29 (enflasyon muhasebesi) kısmi arındırma + marj değişimi

Kaynak: İş Yatırım MaliTablo (XI_29 şablonu; kümülatif dönem değerleri). Banka/sigorta/GYO kapsam dışı (faktor_skor ile aynı).
Hesaplanan (son 12 ay = son dönem + önceki yıl 12A − önceki yıl aynı dönem):
  - net_kar_ttm (3Z ana ortaklık), ertelenmis_vergi_ttm (3IC), duz_net_kar_ttm = net kâr − ertelenmiş vergi
    (Emir Bozkurt formülünün ertelenmiş vergi ayağı; "gelir düşülür, gider geri eklenir").
  - bir yıl önceki aynı büyüklükler → duz_net_kar_buyume_yuzde
  - ozkaynak (2O, son dönem) → duz_roe_yuzde
  - brüt marj ve FAVÖK marjı (FAVÖK ≈ faaliyet kârı 3DF + amortisman 4B): yılbaşından bugüne, bu yıl − geçen yıl aynı
    dönem → marj değişimi (puan).
SINIR (dürüstçe): NET PARASAL POZİSYON kazancı/kaybı İş Yatırım şablonunda ayrı satır değildir (başka kalemlere gömülü);
  güvenilir ayrıştırılamadığı için ÇIKARILMAZ. Bu yüzden düzeltme "kısmi"dir (yalnız ertelenmiş vergi).
Önbellek: data/tms29.json → {KOD: {donem, ..., guncelleme}}. Her çalışmada en eski kayıtlardan başlanır ve
  SURE_BUTCE_DK dolunca durulur (kalanlar sonraki çalışmaya); 7 günden taze kayıtlar atlanır.
GÜVENLİK: her durumda JSON yazar, exit(0).
"""
import datetime as dt
import json
import os
import sys
import time
import traceback
import urllib.request

SURUM = "1.0"
CIKTI = os.path.join("data", "tms29.json")
SKOR = os.path.join("data", "faktor_skor.json")
TABAN = "https://www.isyatirim.com.tr/_layouts/15/IsYatirim.Website/Common/Data.aspx/MaliTablo"
TAZE_GUN = 7
SURE_BUTCE_DK = 70
BEKLE = 0.3
KALEMLER = {"3Z": "net_kar", "3IC": "ert_vergi", "3C": "satis", "3D": "brut", "3DF": "faaliyet", "4B": "amortisman",
            "2O": "ozkaynak"}


def sayi(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def http_json(url, deneme=3):
    son = None
    for i in range(deneme):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bist-tarama/tms29)"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            son = e
            time.sleep(2 * (i + 1))
    raise son


def cek(kod, donemler):
    """donemler: [(yil, ay)] x4 → {(yil, ay): {alan: değer}}"""
    q = "&".join("year%d=%d&period%d=%d" % (i + 1, y, i + 1, a) for i, (y, a) in enumerate(donemler))
    d = http_json("%s?companyCode=%s&exchange=TRY&financialGroup=XI_29&%s" % (TABAN, kod, q))
    out = {p: {} for p in donemler}
    for r in d.get("value") or []:
        alan = KALEMLER.get((r.get("itemCode") or "").strip())
        if not alan:
            continue
        for i, p in enumerate(donemler):
            v = sayi(r.get("value%d" % (i + 1)))
            if v is not None:
                out[p][alan] = v
    return out


def dolu(v):
    return bool(v) and v.get("satis") not in (None, 0)


def ttm(veri, y, a, alan):
    """y/a dönemi için son 12 ay: a=12 ise doğrudan; değilse cur + (y-1,12) − (y-1,a)."""
    try:
        if a == 12:
            return veri[(y, 12)][alan]
        return veri[(y, a)][alan] + veri[(y - 1, 12)][alan] - veri[(y - 1, a)][alan]
    except (KeyError, TypeError):
        return None


def marj(v, pay):
    s = v.get("satis")
    if not s or v.get(pay) is None:
        return None
    return v[pay] / s * 100


def favok(v):
    if v.get("faaliyet") is None:
        return None
    return v["faaliyet"] + abs(v.get("amortisman") or 0)


def hisse_isle(kod, bugun=None):
    bugun = bugun or dt.date.today()
    Y = bugun.year
    v = cek(kod, [(Y, 9), (Y, 6), (Y - 1, 12), (Y - 1, 9)])
    time.sleep(BEKLE)
    if dolu(v.get((Y, 9))):
        y, a = Y, 9
    elif dolu(v.get((Y, 6))):
        y, a = Y, 6
    elif dolu(v.get((Y - 1, 12))):
        y, a = Y - 1, 12
    else:
        return {"hata": "son dönem verisi yok"}
    gerek = set()
    for (yy, aa) in ((y, a), (y - 1, 12), (y - 1, a), (y - 2, 12), (y - 2, a)):
        if (yy, aa) not in v and aa != 0:
            gerek.add((yy, aa))
    gerek = sorted(gerek, reverse=True)
    while gerek:
        parca = gerek[:4]
        gerek = gerek[4:]
        while len(parca) < 4:  # servis 4 dönem bekliyor
            parca.append((parca[-1][0] - 1, parca[-1][1]))
        v.update({k: x for k, x in cek(kod, parca).items() if k not in v})
        time.sleep(BEKLE)
    nk, ev = ttm(v, y, a, "net_kar"), ttm(v, y, a, "ert_vergi")
    nk0, ev0 = ttm(v, y - 1, a, "net_kar"), ttm(v, y - 1, a, "ert_vergi")
    duz = nk - (ev or 0) if nk is not None else None
    duz0 = nk0 - (ev0 or 0) if nk0 is not None else None
    ozk = (v.get((y, a)) or {}).get("ozkaynak")
    cur, once = v.get((y, a)) or {}, v.get((y - 1, a)) or {}
    bm, bm0 = marj(cur, "brut"), marj(once, "brut")
    fv, fv0 = favok(cur), favok(once)
    fm = fv / cur["satis"] * 100 if fv is not None and cur.get("satis") else None
    fm0 = fv0 / once["satis"] * 100 if fv0 is not None and once.get("satis") else None
    return {
        "donem": "%d/%02d" % (y, a), "net_kar_ttm": nk, "ertelenmis_vergi_ttm": ev, "duz_net_kar_ttm": duz,
        "duz_net_kar_ttm_once": duz0,
        "duz_net_kar_buyume_yuzde": round((duz / duz0 - 1) * 100, 1) if duz and duz0 and duz0 > 0 and duz > 0 else None,
        "ozkaynak": ozk, "duz_roe_yuzde": round(duz / ozk * 100, 1) if duz is not None and ozk and ozk > 0 else None,
        "brut_marj": round(bm, 2) if bm is not None else None,
        "brut_marj_degisim_puan": round(bm - bm0, 2) if bm is not None and bm0 is not None else None,
        "favok_marj": round(fm, 2) if fm is not None else None,
        "favok_marj_degisim_puan": round(fm - fm0, 2) if fm is not None and fm0 is not None else None,
        "guncelleme": bugun.isoformat(),
    }


def main():
    try:
        with open(CIKTI, encoding="utf-8") as f:
            eski = json.load(f)
    except Exception:
        eski = {}
    hisseler = dict(eski.get("hisseler") or {})
    cikti = {"surum": SURUM, "hata": None, "not": "Kısmi TMS 29 arındırma: yalnız ertelenmiş vergi çıkarılır; net parasal "
             "pozisyon İş Yatırım şablonunda ayrı satır olmadığı için çıkarılamaz. Marj değişimi: yılbaşından bugüne, yıllık."}
    try:
        with open(SKOR, encoding="utf-8") as f:
            kodlar = list((json.load(f).get("tum") or {}).keys())
        sinir = (dt.date.today() - dt.timedelta(days=TAZE_GUN)).isoformat()
        sira = sorted(kodlar, key=lambda k: (hisseler.get(k) or {}).get("guncelleme") or "")
        bas = time.time()
        islenen = hata = 0
        for kod in sira:
            if ((hisseler.get(kod) or {}).get("guncelleme") or "") >= sinir:
                continue
            if time.time() - bas > SURE_BUTCE_DK * 60:
                break
            try:
                hisseler[kod] = hisse_isle(kod)
                islenen += 1
            except Exception as e:
                hata += 1
                print(kod, "hata:", type(e).__name__, str(e)[:100])
        cikti.update({"islenen": islenen, "hata_sayisi": hata, "kapsam": sum(1 for v in hisseler.values()
                                                                             if v.get("duz_net_kar_ttm") is not None),
                      "evren": len(kodlar)})
    except Exception:
        traceback.print_exc()
        cikti["hata"] = traceback.format_exc().strip().splitlines()[-1][:300]
    cikti["uretim_zamani_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    cikti["hisseler"] = hisseler
    os.makedirs("data", exist_ok=True)
    with open(CIKTI, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=1)
    print("YAZILDI:", CIKTI, cikti.get("islenen"), "işlendi; kapsam", cikti.get("kapsam"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
    sys.exit(0)
