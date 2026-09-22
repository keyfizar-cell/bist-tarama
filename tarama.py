#!/usr/bin/env python3
"""
BIST Emir Bozkurt taramasi — TradingView resmi tarayici API'si uzerinden.
GitHub Actions icinde gunluk calisir, sonucu data/latest.json'a yazar.
Ucretsiz: TradingView hesabi veya API anahtari GEREKMEZ.

Tasarim ilkesi: HICBIR ek ozellik ana isi cokertemez. Sayfalama, eksik-sembol
tamamlama gibi adimlar basarisiz olursa sessizce atlanir ve durumu JSON'a yazilir.
"""
import json, os, sys, datetime as dt

import pandas as pd
from tradingview_screener import Query

# --- Alanlar -------------------------------------------------------------
CEKIRDEK = [
    "name", "close", "change", "volume", "average_volume_10d_calc",
    "MACD.macd", "MACD.signal", "BB.lower", "BB.upper",
    "EMA5", "EMA10", "EMA20", "EMA50",
    "Recommend.All", "Recommend.MA",
    "price_52_week_high", "price_52_week_low", "market_cap_basic",
]
OPSIYONEL = ["RSI", "SMA50", "SMA20"]          # API kabul ederse eklenir
MINI      = ["name", "close", "change"]

# Pazar taramasinda cikmayan semboller ticker ile ayrica denenir.
ZORUNLU = [
    "AKBNK","BLUME","CANTE","ENKAI","HEKTS","KRDMD","OBAMS","PAPIL","SOHOE","TTKOM",
    "ULUUN","VAKBN","YIGIT",
    "AKSEN","ALARK","ASELS","ASTOR","BIMAS","BRSAN","EKGYO","EREGL","FROTO","GARAN",
    "GUBRF","HALKB","ISCTR","KCHOL","KOZAL","MGROS","OYAKC","PGSUS","SAHOL","SASA",
    "SISE","TCELL","THYAO","TOASO","TUPRS","YKBNK",
]

HACIM_KAT = 2.0          # hacim patlamasi esigi (10 gun ort. kaci kati)
NOTLAR    = []           # her adimin sonucu; JSON'a yazilir


def not_ekle(m):
    NOTLAR.append(m)
    print("[not] " + m, file=sys.stderr)


# --- Veri cekme ----------------------------------------------------------
def _sorgu(alanlar, limit, offset=0):
    q = Query().select(*alanlar).set_markets("turkey").limit(limit)
    if offset:
        q = q.offset(offset)
    return q.get_scanner_data()


def _sayfalayarak(alanlar, etiket):
    parcalar, offset, toplam = [], 0, None
    while True:
        n, df = _sorgu(alanlar, 500, offset)
        toplam = n
        if df is None or len(df) == 0:
            break
        parcalar.append(df)
        offset += len(df)
        if offset >= n or offset > 5000:
            break
    if not parcalar:
        raise RuntimeError("sayfalama bos sonuc dondu")
    return pd.concat(parcalar, ignore_index=True), toplam


def veri_cek():
    """Sirayla: (tam alanlar, cekirdek alanlar) x (sayfalama, tek istek).
    Ilk basarili olan kullanilir; her deneme NOTLAR'a yazilir."""
    for alanlar, etiket in ((CEKIRDEK + OPSIYONEL, "tam"), (CEKIRDEK, "cekirdek")):
        try:
            df, toplam = _sayfalayarak(alanlar, etiket)
            not_ekle(f"sayfalama OK (alan={etiket}): {len(df)} satir / API toplam {toplam}")
            return df, etiket, alanlar, toplam
        except Exception as e:
            not_ekle(f"sayfalama basarisiz (alan={etiket}): {type(e).__name__}: {str(e)[:200]}")
        try:
            n, df = _sorgu(alanlar, 2000)
            if df is not None and len(df):
                not_ekle(f"tek istek OK (alan={etiket}): {len(df)} satir / API toplam {n}")
                return df, etiket, alanlar, n
            not_ekle(f"tek istek bos (alan={etiket})")
        except Exception as e:
            not_ekle(f"tek istek basarisiz (alan={etiket}): {type(e).__name__}: {str(e)[:200]}")
    raise SystemExit("HATA: veri alinamadi. " + " | ".join(NOTLAR))


def eksikleri_tamamla(df, alanlar):
    """ZORUNLU listesinde olup taramada cikmayanlari ticker ile cekmeyi dener.
    Basarisiz olursa sadece not duser — ana akisi bozmaz."""
    try:
        mevcut = set(df["name"].astype(str))
    except Exception as e:
        not_ekle(f"eksik kontrolu yapilamadi: {e}")
        return df, [], []
    eksik = [s for s in ZORUNLU if s not in mevcut]
    if not eksik:
        not_ekle("eksik sembol yok")
        return df, [], []
    not_ekle(f"taramada cikmayanlar ({len(eksik)}): {', '.join(eksik)}")

    # KANARYA: THYAO taramada KESIN var. set_tickers ile de gelirse sorun sembol
    # adlarindadir; gelmezse o uc BIST sembollerini hic servis etmiyordur.
    denemeler = [
        ("ticker+kanarya", [f"BIST:{x}" for x in eksik + ["THYAO"]], MINI),
        ("ticker tam",     [f"BIST:{x}" for x in eksik],             alanlar),
        ("ticker minimal", [f"BIST:{x}" for x in eksik],             MINI),
        ("oneksiz",        list(eksik),                              MINI),
    ]
    for ad, tickers, alan in denemeler:
        try:
            n, df2 = Query().select(*alan).set_tickers(*tickers).get_scanner_data()
            bulunan = sorted(set(df2["name"].astype(str))) if (df2 is not None and len(df2)) else []
            not_ekle(f"{ad}: {len(df2) if df2 is not None else 0} satir, bulunan={bulunan}")
            gercek = [b for b in bulunan if b in eksik]
            if gercek:
                df = pd.concat([df, df2[df2["name"].isin(gercek)]], ignore_index=True)
                return df, gercek, [s for s in eksik if s not in gercek]
        except Exception as e:
            not_ekle(f"{ad}: HATA {type(e).__name__}: {str(e)[:200]}")
    return df, [], eksik


# --- Hesap ---------------------------------------------------------------
def sayi(v):
    try:
        f = float(v)
        return None if f != f else f      # NaN -> None
    except (TypeError, ValueError):
        return None


def degerlendir(r, var_rsi):
    kapanis = sayi(r.get("close"))
    bb_alt  = sayi(r.get("BB.lower"))
    macd    = sayi(r.get("MACD.macd"))
    sinyal  = sayi(r.get("MACD.signal"))
    ema50   = sayi(r.get("EMA50"))
    hacim   = sayi(r.get("volume"))
    ort10   = sayi(r.get("average_volume_10d_calc"))
    rsi     = sayi(r.get("RSI")) if var_rsi else None
    gun     = sayi(r.get("change"))

    # BIST gunluk marj +-%10. Bunun cok otesi neredeyse her zaman BEDELSIZ/BOLUNME
    # fiyat duzeltmesidir; sahte "asiri satim + hacim patlamasi" uretir -> ele.
    olasi_sermaye_islemi = (gun is not None and abs(gun) > 15)

    asiri_satim = (kapanis is not None and bb_alt is not None and kapanis <= bb_alt)
    if rsi is not None and rsi < 30:
        asiri_satim = True

    hacim_orani = (hacim / ort10) if (hacim and ort10) else None
    hacim_patlamasi = (hacim_orani is not None and hacim_orani >= HACIM_KAT)

    macd_0_ustu     = (macd is not None and macd > 0)
    macd_yukseliyor = (macd is not None and sinyal is not None and macd > sinyal)
    ema50_uzeri     = (kapanis is not None and ema50 is not None and kapanis > ema50)
    # DUSEN BICAK: MACD 0 ALTINDA *ve DUSUYOR* *ve* fiyat 50MA altinda.
    # Gercek diplerde MACD zaten 0 altindadir ve fiyat 50MA altindadir; bunu tek
    # basina eleme saymak HER gercek donusu eler. Ayirt edici MACD'nin YONUDUR.
    dusen_bicak = (macd is not None and macd < 0
                   and sinyal is not None and macd <= sinyal
                   and ema50 is not None and kapanis is not None and kapanis < ema50)
    donus_teyidi = (macd_0_ustu or macd_yukseliyor) and not dusen_bicak
    hacim_elemesi = bool(hacim_orani is not None and not hacim_patlamasi)

    return {
        "kod": r.get("name"),
        "kapanis": kapanis, "gunluk_yuzde": gun, "rsi": rsi,
        "macd": macd, "macd_sinyal": sinyal,
        "bb_alt": bb_alt, "bb_ust": sayi(r.get("BB.upper")), "ema50": ema50,
        "hacim": hacim, "hacim_ort10": ort10,
        "hacim_orani": round(hacim_orani, 2) if hacim_orani else None,
        "tv_sinyal_skor": sayi(r.get("Recommend.All")),
        "h52_zirve": sayi(r.get("price_52_week_high")),
        "h52_dip": sayi(r.get("price_52_week_low")),
        "piyasa_degeri": sayi(r.get("market_cap_basic")),
        "asiri_satim": asiri_satim, "hacim_patlamasi": hacim_patlamasi,
        "macd_0_ustu": macd_0_ustu, "macd_yukseliyor": macd_yukseliyor,
        "ema50_uzeri": ema50_uzeri, "dusen_bicak": dusen_bicak,
        "donus_teyidi": donus_teyidi, "hacim_elemesi": hacim_elemesi,
        "olasi_sermaye_islemi": olasi_sermaye_islemi,
        "TAM_KURULUM": bool(asiri_satim and donus_teyidi
                            and not hacim_elemesi and not olasi_sermaye_islemi),
    }


def tv_etiket(skor):
    if skor is None: return "veri yok"
    if skor >= 0.5:  return "GÜÇLÜ AL"
    if skor >= 0.1:  return "AL"
    if skor > -0.1:  return "NÖTR"
    if skor > -0.5:  return "SAT"
    return "GÜÇLÜ SAT"


def main():
    df, etiket, alanlar, api_toplam = veri_cek()
    df, tamamlanan, hala_eksik = eksikleri_tamamla(df, alanlar)

    var_rsi = "RSI" in df.columns
    kayitlar = [degerlendir(r, var_rsi) for r in df.to_dict("records")]
    # ayni kod birden fazla kez gelirse tekille
    gorulen, tekil = set(), []
    for k in kayitlar:
        if k["kod"] in gorulen:
            continue
        gorulen.add(k["kod"]); tekil.append(k)
    kayitlar = tekil
    for k in kayitlar:
        k["tv_sinyal"] = tv_etiket(k["tv_sinyal_skor"])

    tam   = sorted([k for k in kayitlar if k["TAM_KURULUM"]], key=lambda x: -(x["hacim_orani"] or 0))
    yakin = sorted([k for k in kayitlar
                    if k["asiri_satim"] and not k["TAM_KURULUM"] and not k["olasi_sermaye_islemi"]],
                   key=lambda x: -(x["hacim_orani"] or 0))

    cikti = {
        "tarih": dt.date.today().isoformat(),
        "uretim_zamani_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "kaynak": "TradingView scanner API (turkey)",
        "alan_seti": etiket,
        "rsi_mevcut": var_rsi,
        "hisse_sayisi": len(kayitlar),
        "api_toplam": api_toplam,
        "ticker_ile_tamamlanan": tamamlanan,
        "hala_eksik": hala_eksik,
        "sermaye_islemi_elenen": [k["kod"] for k in kayitlar if k["olasi_sermaye_islemi"]],
        "hacim_esigi": HACIM_KAT,
        "notlar": NOTLAR,
        "tam_kurulum": tam,
        "yakin_adaylar": yakin[:10],
        "tum_hisseler": kayitlar,
    }

    os.makedirs("data", exist_ok=True)
    for yol in ("data/latest.json", f"data/{cikti['tarih']}.json"):
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(cikti, f, ensure_ascii=False, indent=1)

    print(f"[bitti] {len(kayitlar)} hisse · tam kurulum {len(tam)} · yakin {len(yakin)} · "
          f"RSI={'var' if var_rsi else 'yok'} · hala_eksik={hala_eksik}", file=sys.stderr)


if __name__ == "__main__":
    main()
