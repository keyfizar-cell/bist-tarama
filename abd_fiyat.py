#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# abd_fiyat.py  v1.0  (2026-11-13)
# Twelve Data baglayicisinin yerine (Alpay karari 13.11.2026: baglayici bultenlerde calismiyordu, kaldirildi).
# ABD sembolleri (abd_semboller.json) icin Yahoo chart API'den 1 yillik gunluk veri -> data/abd.json:
# son fiyat, onceki kapanis, gunluk %, 52 hafta zirve/dip, RSI14 (Wilder), MACD(12,26,9), piyasa durumu.
# Bultenler bu dosyayi raw.githubusercontent'ten okur (gorev ortaminin Bash'i Yahoo'ya erisemiyor).
# Hata olan sembolde onceki veri korunur; her durumda JSON yazar ve exit(0).
import datetime
import json
import os
import sys
import time
import urllib.request

SURUM = "1.0"
OUT_PATH = os.path.join("data", "abd.json")
AYAR_PATH = "abd_semboller.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def rsi(kapanislar, n=14):
    if len(kapanislar) <= n:
        return None
    kazanc = kayip = 0.0
    for i in range(1, n + 1):
        d = kapanislar[i] - kapanislar[i - 1]
        kazanc += max(d, 0)
        kayip += max(-d, 0)
    kazanc /= n
    kayip /= n
    for i in range(n + 1, len(kapanislar)):
        d = kapanislar[i] - kapanislar[i - 1]
        kazanc = (kazanc * (n - 1) + max(d, 0)) / n
        kayip = (kayip * (n - 1) + max(-d, 0)) / n
    if kayip == 0:
        return 100.0
    return round(100 - 100 / (1 + kazanc / kayip), 1)


def ema(seri, n):
    k = 2 / (n + 1)
    out, e = [], None
    for x in seri:
        e = x if e is None else x * k + e * (1 - k)
        out.append(e)
    return out


def macd(kapanislar):
    if len(kapanislar) < 35:
        return None
    m = [a - b for a, b in zip(ema(kapanislar, 12), ema(kapanislar, 26))]
    s = ema(m, 9)
    return {"macd": round(m[-1], 3), "sinyal": round(s[-1], 3), "histogram": round(m[-1] - s[-1], 3),
            "yon": "pozitif" if m[-1] > s[-1] else "negatif"}


def piyasa_durumu(meta, simdi=None):
    """Chart API marketState vermiyor: currentTradingPeriod.regular araligina gore REGULAR/KAPALI."""
    if meta.get("marketState"):
        return meta["marketState"]
    reg = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    simdi = simdi if simdi is not None else time.time()
    if reg.get("start") and reg.get("end"):
        return "REGULAR" if reg["start"] <= simdi <= reg["end"] else "KAPALI"
    return ""


def ozet(sembol, d):
    r = d["chart"]["result"][0]
    meta = r.get("meta") or {}
    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    zaman = r.get("timestamp") or []
    satirlar = [(t, c, h, l) for t, c, h, l in zip(zaman, q.get("close") or [], q.get("high") or [], q.get("low") or [])
                if c is not None]
    if not satirlar:
        raise ValueError("bos veri")
    kap = [s[1] for s in satirlar]
    son = meta.get("regularMarketPrice") or kap[-1]
    onceki = kap[-2] if len(kap) >= 2 else None
    # meta fiyati son gunluk mumla ayni gune aitse onceki kapanis bir onceki mum
    yuksek = [s[2] for s in satirlar if s[2] is not None]
    dusuk = [s[3] for s in satirlar if s[3] is not None]
    son_tarih = datetime.datetime.fromtimestamp(satirlar[-1][0], datetime.timezone.utc).date().isoformat()
    return {
        "sembol": sembol,
        "ad": meta.get("longName") or meta.get("shortName") or sembol,
        "para": meta.get("currency"),
        "son": round(son, 2),
        "onceki_kapanis": round(onceki, 2) if onceki else None,
        "gunluk_yuzde": round((son / onceki - 1) * 100, 2) if onceki else None,
        "son_mum_tarihi": son_tarih,
        "h52_zirve": round(max(yuksek), 2) if yuksek else None,
        "h52_dip": round(min(dusuk), 2) if dusuk else None,
        "zirveye_uzaklik_yuzde": round((son / max(yuksek) - 1) * 100, 1) if yuksek else None,
        "rsi14": rsi(kap),
        "macd": macd(kap),
        "piyasa_durumu": piyasa_durumu(meta),
    }


def cek(sembol):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1y&interval=1d" % sembol
    son_hata = None
    for bekle in (0, 5, 15):
        time.sleep(bekle)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return ozet(sembol, json.loads(r.read().decode("utf-8")))
        except Exception as e:
            son_hata = "%s: %s" % (type(e).__name__, e)
    raise RuntimeError(son_hata)


def semboller():
    try:
        with open(AYAR_PATH, encoding="utf-8") as f:
            return json.load(f)["semboller"]
    except Exception:
        return ["NVO", "SPY", "QQQ", "DIA"]


def main():
    simdi = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            eski = json.load(f).get("veriler", {})
    except Exception:
        eski = {}
    veriler, hatalar = {}, {}
    for s in semboller():
        try:
            v = cek(s)
            v["guncelleme_utc"] = simdi
            veriler[s] = v
        except Exception as e:
            hatalar[s] = str(e)[:200]
            if s in eski:
                veriler[s] = dict(eski[s], bayat=True)
    cikti = {"surum": SURUM, "uretim_zamani_utc": simdi, "kaynak": "Yahoo Finance chart API",
             "veriler": veriler, "hatalar": hatalar}
    try:
        os.makedirs("data", exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(cikti, f, ensure_ascii=False, indent=1)
        for s, v in veriler.items():
            print(s, v.get("son"), v.get("gunluk_yuzde"), "RSI", v.get("rsi14"), "bayat" if v.get("bayat") else "")
        if hatalar:
            print("hatalar:", hatalar)
    except Exception as e:
        print("JSON yazilamadi:", e)
    sys.exit(0)


if __name__ == "__main__":
    main()
