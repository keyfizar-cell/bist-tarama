#!/usr/bin/env python3
"""
BIST Emir Bozkurt taramasi — TradingView resmi tarayici API'si uzerinden.
GitHub Actions icinde gunluk calisir, sonucu data/latest.json'a yazar.

Tasarim ilkesi: HICBIR ek ozellik ana isi cokertemez.
Oturum cerezi, eksik-sembol tamamlama gibi adimlar basarisiz olursa
sessizce atlanir; ne denendigi ve neden basarisiz oldugu JSON'a yazilir.

--- 23.09.2026 DUZELTMESI (KRDMD kapsam boslugu) ------------------------
SORUN: KRDMD/EKGYO/ISCTR/KOZAL turkey market taramasinda gelmiyor;
`eksikleri_tamamla` bunlari set_tickers ile cekerken .set_markets("turkey")
KULLANMIYORDU. Kanarya testi (THYAO donuyor, digerleri donmuyor) bunu
gosterdi. Bu surumde tamamlama adimi bir DENEME MATRISI calistirir:
  1) turkey market + ticker (tam alan)   <-- en olasi duzeltme
  2) turkey market + ticker (mini alan)
  3) global + ticker + kanarya (eski yol)
  4) global + ticker (tam alan)
Ilk GERCEK eksik dolduran deneme kazanir. Hangisinin ise yaradigi notlara
yazilir; hicbiri getirmezse davranis oncekiyle ayni (hala_eksik dolar,
ana tarama bozulmaz) — bulten o kodlar icin fiyati tekil kaynaktan ceker.
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
OPSIYONEL = ["RSI", "SMA50", "SMA20", "SMA100", "SMA200"]
MINI      = ["name", "close", "change"]

# Taramada cikmazsa ticker ile ayrica denenecek semboller.
ZORUNLU = [
    "AKBNK","BLUME","CANTE","ENKAI","HEKTS","KRDMD","OBAMS","PAPIL","SOHOE","TTKOM",
    "ULUUN","VAKBN","YIGIT",
    "AKSEN","ALARK","ASELS","ASTOR","BIMAS","BRSAN","EKGYO","EREGL","FROTO","GARAN",
    "GUBRF","HALKB","ISCTR","KCHOL","TRALT","MGROS","OYAKC","PGSUS","SAHOL","SASA",
    "SISE","TCELL","THYAO","TOASO","TUPRS","YKBNK","KONTR","DOAS","PETKM",
]
# Portfoydeki BIST hisseleri (detay analizi her gun yapilir).
PORTFOY = ["AKBNK","BLUME","CANTE","ENKAI","HEKTS","KRDMD","OBAMS","PAPIL","SOHOE",
           "TTKOM","ULUUN","VAKBN","YIGIT"]
# Yabanci portfoy hisseleri: Yahoo sembolu .IS'siz. Sadece detay analizi.
YABANCI = ["NVO"]

# EMIR BOZKURT TEMEL WATCHLIST'i. ASIL KAYNAK Claude'un hafizasidir
# (/areas/emir-bozkurt-taramasi.md); bulten yine kendi listesiyle filtreler.
# Burada yalnizca "watchlist disi isim tam kurulum tablosuna girmesin" icin.
WATCHLIST = {
    "A": ["ASELS","ASTOR","TUPRS","EREGL","BRSAN","KCHOL","ENKAI","CCOLA","MPARK",
          "OYAKC","THYAO","EUPWR","GENIL","ENJSA","GESAN","KTLEV","CVKMD","BIMAS"],
    "B": ["AKBNK","GARAN","ISCTR","YKBNK","TCELL","TOASO","DOHOL","PETKM"],
}
def watchlist_grubu(kod):
    for g, liste in WATCHLIST.items():
        if kod in liste:
            return g
    return None
ZORUNLU = list(dict.fromkeys(ZORUNLU + WATCHLIST["A"] + WATCHLIST["B"]))

HACIM_KAT = 2.0

# TradingView oturum cerezi (GitHub Secret -> env). GUVENLIK: asla yazdirilmaz.
# Anonim ~620 sembol; oturumlu ~630 (KRDMD, KRDMB, EKGYO, ISCTR, KOZAL acilir).
_SID = (os.environ.get("TV_SESSIONID") or "").strip().strip('"\'')
COOKIES = {"sessionid": _SID} if _SID else None
# Cerez ONCE denenir, reddedilirse anonime dusulur. Cerez ana isi cokertmez.
CEREZ_MODLARI = ([({"cookies": COOKIES}, "oturumlu"), ({}, "anonim")]
                 if COOKIES else [({}, "anonim")])

KW        = {}            # veri_cek basarili olunca calisan cerez modu buraya
AKTIF_MOD = "belirsiz"
NOTLAR    = []


def not_ekle(m):
    NOTLAR.append(m)
    print("[not] " + m, file=sys.stderr)


# --- Veri cekme ----------------------------------------------------------
def veri_cek():
    """(cerez modu) x (alan seti) sirayla denenir; ilk basarili olan kullanilir."""
    global KW, AKTIF_MOD
    for kw, mod in CEREZ_MODLARI:
        for alanlar, etiket in ((CEKIRDEK + OPSIYONEL, "tam"), (CEKIRDEK, "cekirdek")):
            try:
                n, df = (Query().select(*alanlar).set_markets("turkey")
                         .limit(2000).get_scanner_data(**kw))
                if df is not None and len(df):
                    KW, AKTIF_MOD = kw, mod
                    not_ekle(f"OK [{mod}/{etiket}]: {len(df)} satir / API toplam {n}")
                    if n and len(df) < n:
                        not_ekle(f"DIKKAT: API {n} diyor ama {len(df)} geldi — sayfalama gerekebilir")
                    return df, etiket, alanlar, n
                not_ekle(f"bos [{mod}/{etiket}]")
            except Exception as e:
                not_ekle(f"basarisiz [{mod}/{etiket}]: {type(e).__name__}: {str(e)[:160]}")
    raise SystemExit("HATA: veri alinamadi. " + " | ".join(NOTLAR))


def eksikleri_tamamla(df, alanlar):
    """ZORUNLU'da olup taramada cikmayanlari ticker ile cekmeyi dener.
    Bir DENEME MATRISI calistirir; ilk gercek eksik dolduran kazanir.
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

    tickers = [f"BIST:{x}" for x in eksik]
    kanarya = tickers + ["BIST:THYAO"]   # THYAO taramada KESIN var — endpoint kanaryasi

    # Deneme matrisi. Her biri bagimsiz try; ilk GERCEK eksik dolduran kazanir.
    # DUZELTME: turkey market'e sabitlenmis denemeler EN BASA alindi.
    denemeler = [
        ("turkey+ticker tam",
         lambda: Query().select(*alanlar).set_markets("turkey").set_tickers(*tickers).get_scanner_data(**KW)),
        ("turkey+ticker mini",
         lambda: Query().select(*MINI).set_markets("turkey").set_tickers(*tickers).get_scanner_data(**KW)),
        ("global+kanarya",
         lambda: Query().select(*MINI).set_tickers(*kanarya).get_scanner_data(**KW)),
        ("global+ticker tam",
         lambda: Query().select(*alanlar).set_tickers(*tickers).get_scanner_data(**KW)),
    ]
    for ad, fn in denemeler:
        try:
            n, df2 = fn()
            bulunan = sorted(set(df2["name"].astype(str))) if (df2 is not None and len(df2)) else []
            not_ekle(f"{ad}: {0 if df2 is None else len(df2)} satir, bulunan={bulunan}")
            gercek = [b for b in bulunan if b in eksik]
            if gercek:
                df = pd.concat([df, df2[df2["name"].isin(gercek)]], ignore_index=True)
                kalan = [s for s in eksik if s not in gercek]
                not_ekle(f"{ad} ISE YARADI -> dolduruldu={gercek}; kalan={kalan}")
                return df, gercek, kalan
        except Exception as e:
            not_ekle(f"{ad}: HATA {type(e).__name__}: {str(e)[:160]}")
    not_ekle("tamamlama basarisiz — hicbir deneme eksikleri getirmedi (muhtemelen "
             "TradingView turkey evreni bu kodlari servis etmiyor; bulten fiyati "
             "tekil kaynaktan ceker, teknik gostergeler 'veri yok').")
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
    sma50   = sayi(r.get("SMA50"))
    sma200  = sayi(r.get("SMA200"))
    # Emir Bozkurt "50 gunluk hareketli ortalama" = basit ortalama. SMA50 yoksa EMA50.
    ma50    = sma50 if sma50 is not None else ema50
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
    ema50_uzeri     = (kapanis is not None and ma50 is not None and kapanis > ma50)
    # DUSEN BICAK: MACD 0 ALTINDA *ve sinyalin ALTINDA* *ve* fiyat 50MA altinda.
    dusen_bicak = (macd is not None and macd < 0
                   and sinyal is not None and macd <= sinyal
                   and ma50 is not None and kapanis is not None and kapanis < ma50)
    # DUZELTME (v2): Eskiden (MACD>0 VEYA MACD>sinyal) donus teyidi sayiliyordu.
    # MACD 0 ustunde ama sinyalin ALTINDA = momentum kaybi (Bozkurt: "asagi
    # keserse satim egilimi") -> teyit SAYILMAZ. Teyit = MACD sinyali yukari
    # kesmis olmali. (Detay analizinde pozitif uyumsuzluk da teyit sayilir.)
    donus_teyidi  = macd_yukseliyor and not dusen_bicak
    hacim_elemesi = bool(hacim_orani is not None and not hacim_patlamasi)
    if macd is None or sinyal is None:
        macd_durum = "veri yok"
    elif macd > sinyal and macd > 0:
        macd_durum = "teyitli al (0 ustu, sinyal ustu)"
    elif macd > sinyal:
        macd_durum = "erken donus (0 alti, sinyal ustu)"
    elif macd > 0:
        macd_durum = "zayifliyor (0 ustu, sinyal alti)"
    else:
        macd_durum = "satis baskisi (0 alti, sinyal alti)"
    kod = r.get("name")

    return {
        "kod": kod,
        "kapanis": kapanis, "gunluk_yuzde": gun, "rsi": rsi,
        "macd": macd, "macd_sinyal": sinyal,
        "bb_alt": bb_alt, "bb_ust": sayi(r.get("BB.upper")), "ema50": ema50,
        "sma50": sma50, "ma50": ma50, "sma200": sma200,
        "ma50_uzaklik_yuzde": (round((kapanis / ma50 - 1) * 100, 2)
                               if (kapanis and ma50) else None),
        "sma50_sma200_ustu": (None if (sma50 is None or sma200 is None) else sma50 > sma200),
        "macd_durum": macd_durum,
        "watchlist": watchlist_grubu(kod),
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
        "donus_kaynagi": ("MACD sinyal kesisimi" if donus_teyidi else None),
    }


def tv_etiket(skor):
    if skor is None: return "veri yok"
    if skor >= 0.5:  return "GÜÇLÜ AL"
    if skor >= 0.1:  return "AL"
    if skor > -0.1:  return "NÖTR"
    if skor > -0.5:  return "SAT"
    return "GÜÇLÜ SAT"


# --- Eksik kodlar icin YAHOO gosterge hesabi (23.09.2026 gelistirmesi) ----
# TradingView tarayicisi acmazsa (KRDMD/EKGYO/ISCTR/KOZAL), gostergeler artik
# "veri yok" kalmasin: Yahoo Finance'ten (KOD.IS) ~1 yil OHLCV cekip RSI(14) /
# MACD(12,26,9) / Bollinger(20,2) / EMA50 hesaplariz. Ciktiyi degerlendir()'in
# bekledigi TradingView-tarzi anahtarlara koyariz -> tum kriter mantigi AYNEN
# calisir, tutarli kalir. tv_sinyal Yahoo'da olmadigi icin "veri yok".
# yfinance bu ortamda 403 alir; GitHub Actions'ta acik internetle calisir.
def _gostergeler(c, v=None):
    """Kapanis serisi (c) ve opsiyonel hacim serisi (v) -> degerlendir()'in
    bekledigi TradingView-tarzi anahtar sozlugu. RSI(14)/MACD(12,26,9)/
    Bollinger(20,2)/EMA50 tek yerden hesaplanir -> Yahoo ve Is Yatirim
    yedekleri AYNI matematigi kullanir, tutarli kalir. Recommend.All hesaplanamaz
    (bu kaynaklar TV onerisi vermez) -> tv_sinyal 'veri yok'."""
    c = pd.to_numeric(c, errors="coerce").dropna()
    if len(c) < 30:
        return None
    delta = c.diff()
    up   = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs   = (up.ewm(alpha=1/14, adjust=False).mean()
            / down.ewm(alpha=1/14, adjust=False).mean())
    rsi  = 100 - 100 / (1 + rs)
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig   = macd.ewm(span=9, adjust=False).mean()
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    ema50 = c.ewm(span=50, adjust=False).mean()
    close = float(c.iloc[-1])
    prev  = float(c.iloc[-2])
    v = pd.to_numeric(v, errors="coerce").dropna() if v is not None else None
    return {
        "close": close,
        "change": ((close / prev - 1) * 100) if prev else None,
        "RSI": float(rsi.iloc[-1]),
        "MACD.macd": float(macd.iloc[-1]),
        "MACD.signal": float(sig.iloc[-1]),
        "BB.lower": float(sma20.iloc[-1] - 2 * std20.iloc[-1]),
        "BB.upper": float(sma20.iloc[-1] + 2 * std20.iloc[-1]),
        "EMA50": float(ema50.iloc[-1]),
        "volume": float(v.iloc[-1]) if (v is not None and len(v)) else None,
        "average_volume_10d_calc": (float(v.tail(10).mean())
                                    if (v is not None and len(v) >= 10) else None),
        "price_52_week_high": float(c.tail(252).max()),
        "price_52_week_low": float(c.tail(252).min()),
        "market_cap_basic": None,
        "Recommend.All": None,   # kaynak TV onerisi vermez -> tv_sinyal "veri yok"
    }


def yahoo_row(kod):
    import yfinance as yf
    h = yf.Ticker(f"{kod}.IS").history(period="1y", interval="1d", auto_adjust=False)
    if h is None or len(h) < 30:
        return None
    d = _gostergeler(h["Close"], h["Volume"] if "Volume" in h.columns else None)
    if d:
        d["name"] = kod
    return d


def yahoo_ile_kurtar(hala_eksik, kayitlar):
    """hala_eksik kodlari Yahoo gostergeleriyle kayitlara ekler; kurtarilanlari
    hala_eksik'ten duser. Her kod ayri try — hicbiri ana akisi bozamaz."""
    kurtarilan = []
    for kod in list(hala_eksik):
        try:
            row = yahoo_row(kod)
            if not row:
                not_ekle(f"yahoo gosterge: {kod} icin yeterli veri yok")
                continue
            k = degerlendir(row, True)
            k["tv_sinyal"] = "veri yok"
            k["veri_kaynagi"] = "yahoo (gosterge hesabi)"
            kayitlar.append(k)
            kurtarilan.append(kod)
            not_ekle(f"yahoo gosterge: {kod} eklendi "
                     f"(RSI={k['rsi']:.1f} MACD={k['macd']:.3f} kapanis={k['kapanis']})")
        except Exception as e:
            not_ekle(f"yahoo gosterge: {kod} HATA {type(e).__name__}: {str(e)[:120]}")
    return [x for x in hala_eksik if x not in kurtarilan]


# --- Eksik kodlar icin IS YATIRIM gosterge hesabi (29.09.2026 gelistirmesi) ---
# UCUNCU yedek: hem TradingView tamamlama hem de Yahoo basarisiz olursa devreye
# girer. Yahoo (ABD) ve TradingView'den TAMAMEN BAGIMSIZ bir kaynaktir (Is
# Yatirim / BIST), boylece kapsam boslugu icin gercek bir cesitlilik saglar.
# isyatirimhisse ucretsiz, API anahtari gerektirmez. Sadece kapanis serisini
# kullaniriz; gostergeler _gostergeler() ile AYNI matematikle hesaplanir.
# NOT: asiri istekte IP engeli riski var -> yalnizca kalan birkac kod icin,
# tek tek denenir; her kod ayri try -> ana akisi asla cokertmez.
def isyatirim_row(kod):
    from isyatirimhisse import fetch_stock_data
    bas = (dt.date.today() - dt.timedelta(days=420)).strftime("%d-%m-%Y")
    df = fetch_stock_data(symbols=kod, start_date=bas)
    if df is None or not len(df):
        return None

    def _col(anahtarlar):
        for c in df.columns:
            u = str(c).upper()
            if any(k in u for k in anahtarlar):
                return c
        return None

    kapanis_col = _col(["KAPANIS", "CLOSING", "CLOSE"])
    if kapanis_col is None:
        not_ekle(f"isyatirim: {kod} kapanis sutunu bulunamadi (sutunlar={list(df.columns)[:8]})")
        return None
    tarih_col = _col(["TARIH", "DATE"])
    hacim_col = _col(["HACIM", "VOLUME", "VOL"])

    d2 = df.copy()
    if tarih_col is not None:
        try:
            d2 = d2.sort_values(tarih_col)
        except Exception:
            pass
    d = _gostergeler(d2[kapanis_col], d2[hacim_col] if hacim_col else None)
    if d:
        d["name"] = kod
    return d


def isyatirim_ile_kurtar(hala_eksik, kayitlar):
    """hala_eksik kodlari Is Yatirim gostergeleriyle kayitlara ekler; kurtarilanlari
    hala_eksik'ten duser. Her kod ayri try — hicbiri ana akisi bozamaz."""
    kurtarilan = []
    for kod in list(hala_eksik):
        try:
            row = isyatirim_row(kod)
            if not row:
                not_ekle(f"isyatirim gosterge: {kod} icin yeterli veri yok")
                continue
            k = degerlendir(row, True)
            k["tv_sinyal"] = "veri yok"
            k["veri_kaynagi"] = "isyatirim (gosterge hesabi)"
            kayitlar.append(k)
            kurtarilan.append(kod)
            not_ekle(f"isyatirim gosterge: {kod} eklendi "
                     f"(RSI={k['rsi']:.1f} MACD={k['macd']:.3f} kapanis={k['kapanis']})")
        except Exception as e:
            not_ekle(f"isyatirim gosterge: {kod} HATA {type(e).__name__}: {str(e)[:120]}")
    return [x for x in hala_eksik if x not in kurtarilan]

# --- EMIR BOZKURT DETAY ANALIZI (v2, 01.10.2026) --------------------------
# TradingView tarayicisi tek gunluk anlik deger verir; Bozkurt'un su kurallari
# icin FIYAT GECMISI gerekir: 5/8/13 gunluk ortalamalar, 2 gun ust uste 50MA
# ustu kapanis, 50/200 Altin-Olum kesisimi, RSI & MACD uyumsuzluklari,
# Fibonacci seviyeleri. Bunlari Yahoo'dan (~1 yil, bolunme/bedelsiz DUZELTILMIS)
# yalnizca PORTFOY + WATCHLIST + gunun asiri satim adaylari icin hesaplariz.
# Hata olursa ana akis bozulmaz; ilgili alanlar bos kalir.
FIB_ORANLARI = (0.236, 0.382, 0.5, 0.618, 0.786)
DETAY_PENCERE = 40      # uyumsuzluk arama penceresi (is gunu)
FIB_PENCERE = 126       # ~6 ay salinim (swing) araligi


def _rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def _uyumsuzluk(c, gosterge, pencere=DETAY_PENCERE):
    """Pencereyi ikiye boler: eski yari ve yeni yari.
    Pozitif: fiyat yeni yarida DAHA DUSUK dip (veya esit dip) yaparken gosterge
    daha YUKSEK dip yapar. Negatif: fiyat daha yuksek tepe yaparken gosterge
    daha dusuk tepe yapar. Yeni dip/tepe son 10 gun icinde olmali (taze sinyal)."""
    c = c.tail(pencere); g = gosterge.reindex(c.index)
    if len(c) < pencere or g.isna().any():
        return False, False
    yari = pencere // 2
    eski, yeni = c.iloc[:yari], c.iloc[yari:]
    i1, i2 = eski.idxmin(), yeni.idxmin()
    j1, j2 = eski.idxmax(), yeni.idxmax()
    son10 = set(c.index[-10:])
    pozitif = (i2 in son10 and c[i2] <= c[i1] * 1.01 and g[i2] > g[i1])
    negatif = (j2 in son10 and c[j2] >= c[j1] * 0.99 and g[j2] < g[j1])
    return bool(pozitif), bool(negatif)


def _fibonacci(c, kapanis, pencere=FIB_PENCERE):
    w = c.tail(pencere)
    tepe, dip = float(w.max()), float(w.min())
    if tepe <= dip:
        return None
    dusus_trendi = w.idxmax() < w.idxmin()   # once tepe sonra dip -> dusus
    fark = tepe - dip
    if dusus_trendi:   # diptan yukari geri cekilme seviyeleri = direncler
        seviyeler = {f"{int(r*1000)/10}%": round(dip + fark * r, 4) for r in FIB_ORANLARI}
    else:              # tepeden asagi geri cekilme seviyeleri = destekler
        seviyeler = {f"{int(r*1000)/10}%": round(tepe - fark * r, 4) for r in FIB_ORANLARI}
    return {"yon": "dusus (diptan tepki)" if dusus_trendi else "yukselis (tepeden duzeltme)",
            "tepe": round(tepe, 4), "dip": round(dip, 4), "seviyeler": seviyeler}


def bozkurt_detay(c, v):
    """Kapanis (c) ve hacim (v) serisi -> Bozkurt detay sozlugu."""
    c = pd.to_numeric(c, errors="coerce").dropna()
    if len(c) < 60:
        return None
    kap = float(c.iloc[-1])
    sma = {n: c.rolling(n).mean() for n in (5, 8, 13, 22, 50, 100, 200)}
    son = {n: (float(s.iloc[-1]) if not pd.isna(s.iloc[-1]) else None) for n, s in sma.items()}
    rsi = _rsi(c)
    ema12 = c.ewm(span=12, adjust=False).mean(); ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26; sig = macd.ewm(span=9, adjust=False).mean(); hist = macd - sig
    sma20 = c.rolling(20).mean(); std20 = c.rolling(20).std()
    bb_alt = float(sma20.iloc[-1] - 2 * std20.iloc[-1]); bb_ust = float(sma20.iloc[-1] + 2 * std20.iloc[-1])

    kisa = [n for n in (5, 8, 13) if son[n] is not None and kap > son[n]]
    s50 = sma[50]
    ustu50 = (c > s50)
    iki_gun_50_ustu = bool(ustu50.iloc[-1] and ustu50.iloc[-2])
    taze_50_kirilim = bool(iki_gun_50_ustu and not ustu50.iloc[-6:-2].all())  # son 5 gunde kirdi

    # 50/200 kesisimi (son 10 gun) ve durum
    kesisim, altin_ustu = None, None
    if son[200] is not None:
        fark = (sma[50] - sma[200]).dropna()
        altin_ustu = bool(fark.iloc[-1] > 0)
        if len(fark) > 11:
            isaret = (fark > 0).astype(int).diff().tail(10)
            if (isaret == 1).any():  kesisim = "ALTIN KESISIM (golden cross) son 10 gunde"
            if (isaret == -1).any(): kesisim = "OLUM KESISIMI (death cross) son 10 gunde"

    rsi_poz, rsi_neg = _uyumsuzluk(c, rsi)
    macd_poz, macd_neg = _uyumsuzluk(c, macd)

    hacim_orani = None
    if v is not None:
        v = pd.to_numeric(v, errors="coerce").reindex(c.index)
        if v.notna().sum() >= 21 and v.iloc[-1] == v.iloc[-1]:
            ort = v.iloc[-21:-1].mean()
            hacim_orani = round(float(v.iloc[-1] / ort), 2) if ort else None

    m, s_, r_ = float(macd.iloc[-1]), float(sig.iloc[-1]), float(rsi.iloc[-1])
    yakin_sifir = abs(m) <= kap * 0.005          # MACD fiyatin %0,5'i icinde = "sifira yakin"
    trend_baslangici = bool(taze_50_kirilim and m > s_ and (m > 0 or yakin_sifir)
                            and (hacim_orani is None or hacim_orani >= 1.2))

    # Destek/direnc: Fibonacci + 50/100/200 ortalamalar
    fib = _fibonacci(c, kap)
    adaylar = [x for x in ([son[50], son[100], son[200]] +
                           (list(fib["seviyeler"].values()) + [fib["tepe"], fib["dip"]] if fib else [])) if x]
    destek = max([x for x in adaylar if x < kap * 0.995], default=None)
    direnc = min([x for x in adaylar if x > kap * 1.005], default=None)

    # Bozkurt durum etiketi (oneri DEGIL; kural ozetidir). Asiri satim bolgesi
    # son 5 gune bakar: donus gunu RSI 35'i gecmis olsa bile dip bolgesi sayilir.
    dip_bolgesi = bool((rsi.tail(5) < 35).any() or (c.tail(5) <= (sma20 - 2 * std20).tail(5)).any())
    donus_isareti = bool(m > s_ or rsi_poz or macd_poz)
    if (son[50] and kap < son[50]) and m < 0 and m <= s_ and not (rsi_poz or macd_poz):
        durum = "DUSEN BICAK (50MA alti, MACD 0 ve sinyal alti)"
    elif dip_bolgesi and donus_isareti:
        durum = "DIP DONUSU ADAYI (asiri satim + donus isareti)"
    elif trend_baslangici:
        durum = "TREND BASLANGICI (50MA kirilimi 2 gun + MACD pozitif)"
    elif len(kisa) == 3 and son[50] and kap > son[50] and m > s_ and m > 0:
        durum = "GUCLU TREND (5/8/13 ve 50MA ustu, MACD teyitli)"
    elif son[50] and kap > son[50] and m > 0:
        durum = "YUKSELIS TRENDI (50MA ustu, momentum yavasliyor)"
    elif dip_bolgesi:
        durum = "ASIRI SATIM - DONUS TEYIDI YOK"
    else:
        durum = "NOTR / IZLE"
    uyarilar = []
    if r_ > 70: uyarilar.append("RSI>70 asiri alim")
    if m > 0 and m < s_: uyarilar.append("MACD 0 ustunde sinyalin altina indi (momentum kaybi)")
    if rsi_neg: uyarilar.append("RSI negatif uyumsuzluk")
    if macd_neg: uyarilar.append("MACD negatif uyumsuzluk")
    if (kesisim or "").startswith("OLUM"): uyarilar.append("50/200 olum kesisimi")
    if son[50] and kap < son[50] and ustu50.iloc[-6:-1].any(): uyarilar.append("50MA asagi kirildi (son 5 gun)")
    if son[200] and kap < son[200]: uyarilar.append("200MA altinda (uzun vade zayif)")

    yuv = lambda x, k=4: (round(x, k) if x is not None else None)
    return {
        "kapanis_yahoo": round(kap, 4),
        "sma": {str(n): yuv(son[n]) for n in son},
        "kisa_vade_ustu": kisa, "kisa_vade_guclu": len(kisa) == 3,
        "ma50_uzaklik_yuzde": (round((kap / son[50] - 1) * 100, 2) if son[50] else None),
        "iki_gun_50ma_ustu": iki_gun_50_ustu, "taze_50ma_kirilimi": taze_50_kirilim,
        "sma50_sma200_ustu": altin_ustu, "kesisim_50_200": kesisim,
        "rsi": round(r_, 2), "macd": round(m, 4), "macd_sinyal": round(s_, 4),
        "macd_hist": round(float(hist.iloc[-1]), 4),
        "macd_hist_artiyor": bool(hist.iloc[-1] > hist.iloc[-2]),
        "bb_alt": round(bb_alt, 4), "bb_ust": round(bb_ust, 4),
        "rsi_pozitif_uyumsuzluk": rsi_poz, "rsi_negatif_uyumsuzluk": rsi_neg,
        "macd_pozitif_uyumsuzluk": macd_poz, "macd_negatif_uyumsuzluk": macd_neg,
        "hacim_orani_20g": hacim_orani,
        "trend_baslangici": trend_baslangici,
        "fibonacci": fib, "en_yakin_destek": yuv(destek), "en_yakin_direnc": yuv(direnc),
        "dip_bolgesi_5g": dip_bolgesi,
        "bozkurt_durum": durum, "uyarilar": uyarilar,
    }


def detay_analiz(kodlar):
    """Yahoo'dan toplu indirir; {kod: detay} dondurur. Hata -> bos sozluk."""
    sonuc = {}
    try:
        import yfinance as yf
    except Exception as e:
        not_ekle(f"detay: yfinance yok ({e})"); return sonuc
    semboller = {k: (k if k in YABANCI else f"{k}.IS") for k in kodlar}
    try:
        df = yf.download(" ".join(semboller.values()), period="1y", interval="1d",
                         group_by="ticker", auto_adjust=True, threads=True, progress=False)
    except Exception as e:
        not_ekle(f"detay: toplu indirme HATA {type(e).__name__}: {str(e)[:120]}"); return sonuc
    for kod, sem in semboller.items():
        try:
            h = df[sem] if isinstance(df.columns, pd.MultiIndex) else df
            h = h.dropna(subset=["Close"])
            d = bozkurt_detay(h["Close"], h["Volume"] if "Volume" in h.columns else None)
            if d:
                sonuc[kod] = d
        except Exception as e:
            not_ekle(f"detay: {kod} HATA {type(e).__name__}: {str(e)[:80]}")
    not_ekle(f"detay analizi: {len(sonuc)}/{len(semboller)} sembol hesaplandi")
    return sonuc



def main():
    not_ekle("TV oturum cerezi: " + ("tanimli" if COOKIES else "tanimsiz"))
    df, etiket, alanlar, api_toplam = veri_cek()
    df, tamamlanan, hala_eksik = eksikleri_tamamla(df, alanlar)

    var_rsi = "RSI" in df.columns
    kayitlar, gorulen = [], set()
    for r in df.to_dict("records"):
        k = degerlendir(r, var_rsi)
        if k["kod"] in gorulen:
            continue
        gorulen.add(k["kod"])
        k["tv_sinyal"] = tv_etiket(k["tv_sinyal_skor"])
        kayitlar.append(k)

    # Tamamlama adimi acamadiysa: kalan eksikleri Yahoo gostergeleriyle kurtar.
    if hala_eksik:
        hala_eksik = yahoo_ile_kurtar(hala_eksik, kayitlar)
    # Yahoo da getiremediyse: bagimsiz ucuncu kaynak Is Yatirim ile son bir dene.
    if hala_eksik:
        hala_eksik = isyatirim_ile_kurtar(hala_eksik, kayitlar)

    # --- v2: Bozkurt detay analizi (portfoy + watchlist + gunun adaylari) ---
    by = {k["kod"]: k for k in kayitlar}
    adaylar = [k["kod"] for k in sorted(
        [k for k in kayitlar if k["asiri_satim"] and not k["olasi_sermaye_islemi"]],
        key=lambda x: -(x["hacim_orani"] or 0))][:30]
    detay_set = list(dict.fromkeys(PORTFOY + WATCHLIST["A"] + WATCHLIST["B"] + adaylar))
    detaylar = detay_analiz(detay_set + YABANCI)
    for kod, d in detaylar.items():
        k = by.get(kod)
        if k is None:
            continue
        k["detay"] = d
        # Pozitif uyumsuzluk (RSI veya MACD) da donus teyidi sayilir (kural 5).
        if not k["donus_teyidi"] and (d["rsi_pozitif_uyumsuzluk"] or d["macd_pozitif_uyumsuzluk"]):
            k["donus_teyidi"] = True
            k["donus_kaynagi"] = "pozitif uyumsuzluk (" + ("RSI" if d["rsi_pozitif_uyumsuzluk"] else "MACD") + ")"
            k["TAM_KURULUM"] = bool(k["asiri_satim"] and not k["hacim_elemesi"]
                                    and not k["olasi_sermaye_islemi"])
        if k.get("sma50") is None and d["sma"].get("50"):
            k["ma50"] = d["sma"]["50"]

    teknik_tam = sorted([k for k in kayitlar if k["TAM_KURULUM"]],
                        key=lambda x: -(x["hacim_orani"] or 0))
    # Temel filtre: tabloya YALNIZCA watchlist (A/B) girer. Digerleri ayri listede
    # (bedelsiz-bozulmus seriler, temeli dogrulanmamis isimler buraya duser).
    tam   = [k for k in teknik_tam if k["watchlist"]]
    tam_disi = [k["kod"] for k in teknik_tam if not k["watchlist"]]
    yakin = sorted([k for k in kayitlar if k["asiri_satim"] and not k["TAM_KURULUM"]
                    and not k["olasi_sermaye_islemi"]],
                   key=lambda x: (0 if x["watchlist"] else 1, -(x["hacim_orani"] or 0)))
    trend_bas = [k for k in kayitlar if k.get("watchlist") and k.get("detay")
                 and k["detay"]["trend_baslangici"]]
    ozet = lambda k: {"kod": k["kod"], "kapanis": k["kapanis"], "gunluk_yuzde": k["gunluk_yuzde"],
                      "rsi": k["rsi"], "macd_durum": k["macd_durum"], "ma50": k.get("ma50"),
                      "watchlist": k.get("watchlist"), "detay": k.get("detay")}
    portfoy_bozkurt = {kod: ozet(by[kod]) for kod in PORTFOY if kod in by}
    for kod in YABANCI:
        if kod in detaylar:
            portfoy_bozkurt[kod] = {"kod": kod, "detay": detaylar[kod]}
    watchlist_durum = {kod: ozet(by[kod]) for kod in WATCHLIST["A"] + WATCHLIST["B"] if kod in by}

    cikti = {
        "tarih": dt.date.today().isoformat(),
        "uretim_zamani_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "kaynak": "TradingView scanner API (turkey)",
        "alan_seti": etiket,
        "aktif_mod": AKTIF_MOD,
        "oturum_cerezi_tanimli": bool(COOKIES),
        "rsi_mevcut": var_rsi,
        "hisse_sayisi": len(kayitlar),
        "api_toplam": api_toplam,
        "ticker_ile_tamamlanan": tamamlanan,
        "hala_eksik": hala_eksik,
        "sermaye_islemi_elenen": [k["kod"] for k in kayitlar if k["olasi_sermaye_islemi"]],
        "hacim_esigi": HACIM_KAT,
        "notlar": NOTLAR,
        "surum": "v2-bozkurt (01.10.2026)",
        "kural_ozeti": ("TAM KURULUM = watchlist(A/B) + asiri satim (BB alt bandi alti VEYA RSI<30) "
                        "+ donus teyidi (MACD sinyali yukari kesmis VEYA RSI/MACD pozitif uyumsuzluk) "
                        "+ hacim >= 2x 10g ort + sermaye islemi degil. Dusen bicak elenir."),
        "detay_kapsami": sorted(detaylar.keys()),
        "tam_kurulum": tam,
        "tam_kurulum_watchlist_disi": tam_disi,
        "trend_baslangici": [ozet(k) for k in trend_bas],
        "portfoy_bozkurt": portfoy_bozkurt,
        "watchlist_durum": watchlist_durum,
        "yakin_adaylar": yakin[:10],
        "tum_hisseler": kayitlar,
    }

    os.makedirs("data", exist_ok=True)
    for yol in ("data/latest.json", f"data/{cikti['tarih']}.json"):
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(cikti, f, ensure_ascii=False, indent=1)

    print(f"[bitti] mod={AKTIF_MOD} · {len(kayitlar)} hisse · tam kurulum {len(tam)} · "
          f"yakin {len(yakin)} · RSI={'var' if var_rsi else 'yok'} · hala_eksik={hala_eksik}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
