#!/usr/bin/env python3
"""
BIST 100 Emir Bozkurt taramasi — TradingView resmi tarayici API'si uzerinden.
GitHub Actions icinde gunluk calisir, sonucu data/latest.json'a yazar.
Ucretsiz: TradingView hesabi veya API anahtari GEREKMEZ.
"""
import json, os, sys, datetime as dt

import pandas as pd
from tradingview_screener import Query, col

# Pazar taramasi bazi PAY SINIFI kodlarini dondurmuyor (21-22 Eyl'de KRDMD ve ISCTR
# hicbir filtre olmadan da gelmedi; sorun is_primary degil, TradingView'in turkey
# evreninde bu semboller yok). Bunlar ikinci bir sorguda TICKER ile acikca cekilir.
ZORUNLU = [
    # portfoy (BIST)
    "AKBNK","BLUME","CANTE","ENKAI","HEKTS","KRDMD","OBAMS","PAPIL","SOHOE","TTKOM",
    "ULUUN","VAKBN","YIGIT",
    # BIST 30
    "AKSEN","ALARK","ASELS","ASTOR","BIMAS","BRSAN","EKGYO","EREGL","FROTO","GARAN",
    "GUBRF","HALKB","ISCTR","KCHOL","KOZAL","MGROS","OYAKC","PGSUS","SAHOL","SASA",
    "SISE","TCELL","THYAO","TOASO","TUPRS","YKBNK",
]

# --- Alanlar -------------------------------------------------------------
# CEKIRDEK: dokumantasyondan varligi dogrulanmis alanlar
CEKIRDEK = [
    "name", "close", "change", "volume", "average_volume_10d_calc",
    "MACD.macd", "MACD.signal", "BB.lower", "BB.upper",
    "EMA5", "EMA10", "EMA20", "EMA50",
    "Recommend.All", "Recommend.MA",
    "price_52_week_high", "price_52_week_low", "market_cap_basic",
]
# OPSIYONEL: API kabul ederse eklenir, etmezse sessizce dusulur
OPSIYONEL = ["RSI", "SMA50", "SMA20"]

HACIM_KAT = 2.0   # hacim patlamasi esigi (10 gun ort. kaci kati)


def veri_cek():
    """Once opsiyonellerle dene; API reddederse cekirdege dus."""
    for alanlar, etiket in ((CEKIRDEK + OPSIYONEL, "tam"), (CEKIRDEK, "cekirdek")):
        try:
            n, df = (Query()
                     .select(*alanlar)
                     .set_markets("turkey")
                     # NOT: .where(col("is_primary") == True) KULLANMA — bu filtre
                     # pay siniflarini (KRDMD, ISCTR gibi) listeden dusuruyor.
                     .limit(2000)
                     .get_scanner_data())
            print(f"[ok] alan seti='{etiket}' · {len(df)} satir (toplam {n})", file=sys.stderr)
            return df, etiket, alanlar
        except Exception as e:
            print(f"[uyari] alan seti='{etiket}' basarisiz: {e}", file=sys.stderr)
    raise SystemExit("HATA: TradingView tarayicisindan veri alinamadi.")


def eksikleri_tamamla(df, alanlar):
    """Pazar taramasinda cikmayan ZORUNLU sembolleri ticker ile ayrica cek ve birlestir."""
    mevcut = set(df["name"].astype(str))
    eksik = [s for s in ZORUNLU if s not in mevcut]
    if not eksik:
        return df, [], []
    try:
        n, df2 = (Query()
                  .select(*alanlar)
                  .set_tickers(*[f"BIST:{s}" for s in eksik])
                  .get_scanner_data())
        bulunan = set(df2["name"].astype(str))
        hala = [s for s in eksik if s not in bulunan]
        df = pd.concat([df, df2], ignore_index=True)
        print(f"[ok] eksik tamamlama: {len(bulunan)}/{len(eksik)} cekildi "
              f"({', '.join(sorted(bulunan))}); hala eksik: {hala or 'yok'}", file=sys.stderr)
        return df, sorted(bulunan), hala
    except Exception as e:
        print(f"[uyari] eksik tamamlama basarisiz: {e}", file=sys.stderr)
        return df, [], eksik


def sayi(v):
    try:
        f = float(v)
        return None if f != f else f     # NaN -> None
    except (TypeError, ValueError):
        return None


def degerlendir(r, var_rsi):
    """Emir Bozkurt kriterlerini tek hisse icin hesaplar."""
    kapanis = sayi(r.get("close"))
    bb_alt  = sayi(r.get("BB.lower"))
    macd    = sayi(r.get("MACD.macd"))
    sinyal  = sayi(r.get("MACD.signal"))
    ema50   = sayi(r.get("EMA50"))
    hacim   = sayi(r.get("volume"))
    ort10   = sayi(r.get("average_volume_10d_calc"))
    rsi     = sayi(r.get("RSI")) if var_rsi else None

    # (a) asiri satim: Bollinger alt bandi kirildi/dokunuldu
    asiri_satim = (kapanis is not None and bb_alt is not None and kapanis <= bb_alt)
    if rsi is not None and rsi < 30:
        asiri_satim = True

    # (b) hacim patlamasi
    hacim_orani = (hacim / ort10) if (hacim and ort10) else None
    hacim_patlamasi = (hacim_orani is not None and hacim_orani >= HACIM_KAT)

    # (c) MACD + 50MA donus teyidi
    macd_0_ustu     = (macd is not None and macd > 0)
    macd_yukseliyor = (macd is not None and sinyal is not None and macd > sinyal)
    ema50_uzeri     = (kapanis is not None and ema50 is not None and kapanis > ema50)
    # DUSEN BICAK: MACD 0 ALTINDA *ve DUSUYOR* (sinyalin altinda) *ve* fiyat 50MA altinda.
    # Onemli: gercek diplerde MACD zaten 0 altindadir ve fiyat 50MA altindadir; bunu tek
    # basina eleme olarak kullanmak HER gercek donusu eler. Ayirt edici olan MACD'nin
    # yonudur — sinyalin uzerine cikmissa bu "sifira yakin pozitif egilim" = donus baslangicidir.
    dusen_bicak = (macd is not None and macd < 0
                   and sinyal is not None and macd <= sinyal
                   and ema50 is not None and kapanis is not None and kapanis < ema50)
    donus_teyidi = (macd_0_ustu or macd_yukseliyor) and not dusen_bicak

    # BIST gunluk marj +-%10 (bazi paylarda +-%20). Bunun cok otesindeki bir "dusus"
    # neredeyse her zaman BEDELSIZ/BOLUNME fiyat duzeltmesidir, gercek satis degil.
    # Boyle bir gun sahte "asiri satim + hacim patlamasi" uretir -> aday havuzundan cikar.
    gun_yuzde = sayi(r.get("change"))
    olasi_sermaye_islemi = (gun_yuzde is not None and abs(gun_yuzde) > 15)

    return {
        "kod": r.get("name"),
        "olasi_sermaye_islemi": olasi_sermaye_islemi,
        "kapanis": kapanis,
        "gunluk_yuzde": sayi(r.get("change")),
        "rsi": rsi,
        "macd": macd,
        "macd_sinyal": sinyal,
        "bb_alt": bb_alt,
        "ema50": ema50,
        "hacim": hacim,
        "hacim_ort10": ort10,
        "hacim_orani": round(hacim_orani, 2) if hacim_orani else None,
        "tv_sinyal_skor": sayi(r.get("Recommend.All")),
        "h52_zirve": sayi(r.get("price_52_week_high")),
        "h52_dip": sayi(r.get("price_52_week_low")),
        "piyasa_degeri": sayi(r.get("market_cap_basic")),
        # kriter bayraklari
        "asiri_satim": asiri_satim,
        "hacim_patlamasi": hacim_patlamasi,
        "macd_0_ustu": macd_0_ustu,
        "macd_yukseliyor": macd_yukseliyor,
        "ema50_uzeri": ema50_uzeri,
        "dusen_bicak": dusen_bicak,
        "donus_teyidi": donus_teyidi,
        # Hacim kurali: oran OLCULEBILIYORSA patlama sart (zayif hacimli hareket elenir);
        # olculemiyorsa "hacim: veri yok" notuyla gecer.
        "hacim_elemesi": bool(hacim_orani is not None and not hacim_patlamasi),
        "TAM_KURULUM": bool(asiri_satim and donus_teyidi
                            and not (hacim_orani is not None and not hacim_patlamasi)
                            and not olasi_sermaye_islemi),
    }


def tv_etiket(skor):
    """TradingView Recommend.All skorunu AL/SAT etiketine cevirir."""
    if skor is None: return "veri yok"
    if skor >= 0.5:  return "GÜÇLÜ AL"
    if skor >= 0.1:  return "AL"
    if skor > -0.1:  return "NÖTR"
    if skor > -0.5:  return "SAT"
    return "GÜÇLÜ SAT"


def main():
    df, etiket, alanlar = veri_cek()
    df, tamamlanan, hala_eksik = eksikleri_tamamla(df, alanlar)
    var_rsi = "RSI" in df.columns
    kayitlar = [degerlendir(r, var_rsi) for r in df.to_dict("records")]
    for k in kayitlar:
        k["tv_sinyal"] = tv_etiket(k["tv_sinyal_skor"])

    tam = [k for k in kayitlar if k["TAM_KURULUM"]]
    # tam kurulum yoksa en yakin adaylar: asiri satim var ama donus yok
    yakin = [k for k in kayitlar
             if k["asiri_satim"] and not k["TAM_KURULUM"] and not k["olasi_sermaye_islemi"]]
    tam.sort(key=lambda x: -(x["hacim_orani"] or 0))
    yakin.sort(key=lambda x: -(x["hacim_orani"] or 0))

    cikti = {
        "tarih": dt.date.today().isoformat(),
        "uretim_zamani_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "kaynak": "TradingView scanner API (turkey)",
        "alan_seti": etiket,
        "rsi_mevcut": var_rsi,
        "hisse_sayisi": len(kayitlar),
        "ticker_ile_tamamlanan": tamamlanan,
        "hala_eksik": hala_eksik,
        "sermaye_islemi_elenen": [k["kod"] for k in kayitlar if k["olasi_sermaye_islemi"]],
        "hacim_esigi": HACIM_KAT,
        "tam_kurulum": tam,
        "yakin_adaylar": yakin[:10],
        "tum_hisseler": kayitlar,
    }

    os.makedirs("data", exist_ok=True)
    for yol in ("data/latest.json", f"data/{cikti['tarih']}.json"):
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(cikti, f, ensure_ascii=False, indent=1)

    print(f"[bitti] {len(kayitlar)} hisse · tam kurulum: {len(tam)} · yakin: {len(yakin)} · RSI={'var' if var_rsi else 'yok'}", file=sys.stderr)
    for k in tam[:10]:
        print(f"  ★ {k['kod']:8s} {k['kapanis']}  hacim×{k['hacim_orani']}  MACD={k['macd']}", file=sys.stderr)


if __name__ == "__main__":
    main()
