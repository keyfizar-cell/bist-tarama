#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
degerleme.py  v1.3  (2026-11-11)  — BIST100 adil değer (otomatik, manuel dokunuş yok)

Her akşam ana taramadan sonra GitHub Actions'ta çalışır:
  - TradingView tarama API'sinden (tradingview-screener) BIST100 üyeleri + tüm BIST (~620 hisse, eş grup
    ortancaları için) temel verileri çekilir. Tutarlar TradingView'da USD'dir → DCF dolar bazında yapılır
    (TL enflasyonu / TMS 29 bozulmasından arındırılmış); oran yöntemleri para biriminden bağımsızdır.
    Sonuç her zaman TL fiyatına oranla çevrilir: adil_TL = kapanis_TL × (adil_özkaynak / piyasa_değeri).
  - Yöntemler (sektöre göre otomatik ağırlık):
      göreli : F/K, PD/DD, FD/FAVÖK — eş grup = alt sektör (≥5 pozitif örnek) → sektör → piyasa ortancası;
               kötümser/baz/iyimser = eş grubun %25 / %50 / %75 dilimi.
      DCF    : 5 yıl + uç büyüme, USD; özkaynak maliyeti (Damodaran) = ABD 10Y + beta × (olgun piyasa
               primi + ülke hisse primi), ülke primi = (TR USD eurotahvil 10Y − ABD 10Y) × 1,5;
               büyüme senaryoları sektör sınıfına göre otomatik; döngüsellerde zirve FCF %40 kırpılır.
      DDM    : temettü verimi > 0 ise Gordon.
      ROE ayarlı PD/DD : banka/sigorta/aracı için eş grup PD/DD × (ROE / eş grup ROE) — para biriminden
               bağımsız (bankalar TMS 29 uygulamadığı için TL ROE ile USD iskontosu karıştırılmaz).
      Ters DCF : mevcut fiyatın ima ettiği 5 yıllık büyüme.
  - Güven marjı betaya göre otomatik (%15 + 5 puan × max(0, beta − 1), en fazla %30).
  - Uyarılar: değer tuzağı (ucuz + zayıf kalite), döngüsel zirve kârı, negatif FCF, veri eksik.
v1.1: her hisseye "aday" (⭐ inceleme adayı = kapanış ≤ inceleme seviyesi + uyarılarda ⚠ yok + ≥3 yöntem;
  tablodaki Apps Script ile AYNI kural) ve önceki çalışmaya göre "degisimler" listesi (durum/aday değişen
  hisseler) — akşam bülteni ve Koç bunu kullanır.
v1.2: data/degerleme_gecmis.json (haftalık, İş Yatırım) varsa 5 yıllık F/K ve PD/DD bandı eklenir; holdinglerde
  "tarihsel PD/DD" yöntemi (fiyat × 5 yıllık ortanca PD/DD / güncel PD/DD; holding iskontosunun kendi geçmişine
  dönüşü) — TradingView'da PD/DD yoksa İş Yatırım son yıl PD/DD'si kullanılır. Temettü tarihleri (TradingView).
v1.3: "one_cikanlar" — Koç için her akşam en fazla 3 hisse (önce ⭐ adaylar, yetmezse uyarısız 🟢) ve her biri için
  en belirgin 3 "öne çıkan alan" (sektöre/5 yıllık banda göre ucuzluk, kalite, ters DCF, temettü). Sıralama puanı:
  potansiyel (en fazla %100 sayılır) + kalite artıları − döngüsel/düşük güven eksileri; potansiyeli %150'yi aşan
  (aşırı uç, veri hatası şüphesi) seçilmez.
Çıktılar: data/adil_deger.json (bülten) ve data/adil_deger.csv (Google Sheets IMPORTDATA; sayılar ×100
TAMSAYI → yerel ayar ondalık ayıracından etkilenmez).
Ayarlar: degerleme_ayar.json (yalnız piyasa varsayımları; kişisel veri yok).
GÜVENLİK: ana taramayı etkilemez; her durumda JSON yazar ve exit(0). Yatırım tavsiyesi değildir.
"""
import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
import traceback
import urllib.request

SURUM = "1.3"
VERI = "data"
JSON_YOL = os.path.join(VERI, "adil_deger.json")
CSV_YOL = os.path.join(VERI, "adil_deger.csv")
AYAR_YOL = "degerleme_ayar.json"
GECMIS_YOL = os.path.join(VERI, "degerleme_gecmis.json")

ALANLAR = ["name", "description", "close", "sector", "industry", "market_cap_basic", "price_earnings_ttm",
           "price_book_fq", "enterprise_value_ebitda_ttm", "return_on_equity", "debt_to_equity",
           "free_cash_flow", "net_income", "ebitda", "net_debt", "total_debt", "dividends_yield_current",
           "dividend_payout_ratio_ttm", "beta_1_year", "earnings_release_next_date",
           "ex_dividend_date_upcoming", "dividend_payment_date_upcoming"]

SEKTOR_TR = {
    "Communications": "İletişim", "Consumer Durables": "Dayanıklı Tüketim",
    "Consumer Non-Durables": "Dayanıksız Tüketim", "Consumer Services": "Tüketici Hizmetleri",
    "Electronic Technology": "Elektronik Teknoloji", "Energy Minerals": "Enerji / Rafineri",
    "Finance": "Finans", "Health Services": "Sağlık Hizmetleri", "Health Technology": "Sağlık Teknolojisi",
    "Industrial Services": "Endüstriyel Hizmetler", "Miscellaneous": "Diğer",
    "Non-Energy Minerals": "Metal / Maden / Çimento", "Process Industries": "Proses Sanayi",
    "Producer Manufacturing": "İmalat", "Retail Trade": "Perakende", "Technology Services": "Teknoloji Hizmetleri",
    "Transportation": "Ulaştırma", "Utilities": "Enerji Dağıtım / Üretim",
    "Commercial Services": "Ticari Hizmetler", "Distribution Services": "Dağıtım",
}
BANKA = {"Major Banks", "Regional Banks"}
SIGORTA = {"Life/Health Insurance", "Multi-Line Insurance", "Property/Casualty Insurance"}
ARACI = {"Investment Banks/Brokers", "Finance/Rental/Leasing"}
HOLDING = {"Financial Conglomerates", "Industrial Conglomerates"}
GYO = {"Real Estate Investment Trusts"}
DONGUSEL_SEKTOR = {"Non-Energy Minerals", "Energy Minerals", "Process Industries", "Transportation"}
BUYUME_SEKTOR = {"Electronic Technology", "Technology Services", "Health Technology", "Health Services"}
SAVUNMACI_SEKTOR = {"Utilities", "Consumer Non-Durables", "Communications", "Retail Trade"}

# Yöntem ağırlıkları (eksik yöntem çıkarılır, kalanlar yeniden ölçeklenir)
AGIRLIK = {
    "banka":    {"roe_pddd": 0.4, "pddd": 0.3, "fk": 0.2, "ddm": 0.1},
    "sigorta":  {"roe_pddd": 0.3, "pddd": 0.3, "fk": 0.3, "ddm": 0.1},
    "araci":    {"roe_pddd": 0.3, "pddd": 0.3, "fk": 0.3, "ddm": 0.1},
    "holding":  {"tarihsel_pddd": 0.35, "pddd": 0.3, "fk": 0.2, "ddm": 0.15},
    "gyo":      {"pddd": 0.8, "ddm": 0.2},
    "dongusel": {"dcf": 0.3, "fd_favok": 0.3, "pddd": 0.25, "fk": 0.15},
    "sanayi":   {"dcf": 0.4, "fd_favok": 0.2, "fk": 0.2, "pddd": 0.1, "ddm": 0.1},
}
SINIR = {"fk": (0.5, 100.0), "pddd": (0.05, 30.0), "fd_favok": (0.5, 60.0)}

VARSAYILAN_AYAR = {
    "tr_usd_10y_yuzde": 7.64, "tr_usd_10y_kaynak": "Bondscovery TR USD eurotahvil 10Y (26.10.2026)",
    "abd_10y_yuzde": 4.5, "abd_10y_kaynak": "varsayılan",
    "olgun_piyasa_primi_yuzde": 4.5, "ulke_primi_carpani": 1.5, "uc_buyume_yuzde": 2.5,
    "dongusel_fcf_kirpma": 0.6, "tek_yontem_ust_sinir": 3.0, "borc_maliyeti_ek_yuzde": 2.0,
    "vergi_orani_yuzde": 25.0,
    "senaryo_buyume_yuzde": {"buyume": [2.0, 7.0, 12.0], "savunmaci": [0.0, 3.0, 6.0],
                              "dongusel": [-3.0, 2.0, 6.0], "normal": [0.0, 4.0, 8.0]},
}


def simdi():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sayi(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if x != x or x in (float("inf"), float("-inf")) else x


def ayar_oku(yol=AYAR_YOL):
    a = json.loads(json.dumps(VARSAYILAN_AYAR))
    try:
        with open(yol, encoding="utf-8") as f:
            a.update({k: v for k, v in json.load(f).items() if not k.startswith("_")})
    except Exception:
        pass
    return a


def tr_usd_10y_guncelle(ayar):
    """Bondscovery'den TR USD eurotahvil 10Y getirisini dener; olmazsa ayar dosyasındaki değer kalır."""
    try:
        req = urllib.request.Request("https://bondscovery.com/tr/yield-curve/turkey-usd-bonds",
                                     headers={"User-Agent": "bist-tarama/degerleme"})
        with urllib.request.urlopen(req, timeout=30) as r:
            t = r.read().decode("utf-8", "replace")
        m = re.search(r"10Y[^0-9%]{0,80}?(\d{1,2}[.,]\d{1,2})\s*%", t)
        if m:
            v = float(m.group(1).replace(",", "."))
            if 3.0 < v < 20.0:
                ayar["tr_usd_10y_yuzde"] = v
                ayar["tr_usd_10y_kaynak"] = "Bondscovery TR USD eurotahvil 10Y (%s, otomatik)" % dt.date.today()
                return True
    except Exception as e:
        print("Bondscovery okunamadi:", type(e).__name__, str(e)[:120])
    return False


def abd_10y_guncelle(ayar):
    try:
        req = urllib.request.Request("https://query1.finance.yahoo.com/v8/finance/chart/%5ETNX?range=5d&interval=1d",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            v = json.loads(r.read().decode())["chart"]["result"][0]["meta"]["regularMarketPrice"]
        if 1.0 < float(v) < 10.0:
            ayar["abd_10y_yuzde"] = round(float(v), 3)
            ayar["abd_10y_kaynak"] = "Yahoo ^TNX (%s, otomatik)" % dt.date.today()
            return True
    except Exception as e:
        print("ABD 10Y okunamadi:", type(e).__name__, str(e)[:120])
    return False


# ── VERİ ──
def tv_cek(endeks=None):
    from tradingview_screener import Query
    q = Query().select(*ALANLAR).set_markets("turkey").limit(3000)
    if endeks:
        q = q.set_index(endeks)
    _, df = q.get_scanner_data()
    kayitlar = []
    for r in df.to_dict("records"):
        r = {k: (sayi(v) if k not in ("ticker", "name", "description", "sector", "industry") else v)
             for k, v in r.items()}
        r["kod"] = str(r.get("name") or "").upper()
        kayitlar.append(r)
    return kayitlar


# ── EŞ GRUP ──
def dilimler(degerler):
    d = sorted(degerler)
    if len(d) < 3:
        return None
    q = statistics.quantiles(d, n=4, method="inclusive")
    return {"p25": q[0], "p50": q[1], "p75": q[2], "n": len(d)}


def es_grup_tablosu(tum):
    """{alan: {('industry', ad)|('sector', ad)|('piyasa',''): dilimler}}"""
    tablo = {}
    kaynak = {"fk": "price_earnings_ttm", "pddd": "price_book_fq", "fd_favok": "enterprise_value_ebitda_ttm",
              "roe": "return_on_equity", "borc_ozk": "debt_to_equity"}
    for alan, tv in kaynak.items():
        alt, sek, hepsi = {}, {}, []
        lo, hi = SINIR.get(alan, (-1e9, 1e9))
        for r in tum:
            v = r.get(tv)
            if v is None or not (lo < v < hi):
                continue
            alt.setdefault(r.get("industry"), []).append(v)
            sek.setdefault(r.get("sector"), []).append(v)
            hepsi.append(v)
        t = {}
        for k, vs in alt.items():
            if len(vs) >= 5:
                t[("industry", k)] = dilimler(vs)
        for k, vs in sek.items():
            if len(vs) >= 5:
                t[("sector", k)] = dilimler(vs)
        t[("piyasa", "")] = dilimler(hepsi)
        tablo[alan] = t
    return tablo


def es_grup(tablo, alan, r):
    t = tablo.get(alan) or {}
    for anahtar in (("industry", r.get("industry")), ("sector", r.get("sector")), ("piyasa", "")):
        if t.get(anahtar):
            return t[anahtar], anahtar[0]
    return None, None


# ── SINIF ──
def sinif(r):
    ind, sek, kod = r.get("industry"), r.get("sector"), r.get("kod", "")
    if kod.endswith("HOL"):  # SAHOL gibi bankayı konsolide eden holdingler de holding sayılır
        return "holding"
    if ind in BANKA:
        return "banka"
    if ind in SIGORTA:
        return "sigorta"
    if ind in ARACI:
        return "araci"
    if ind in GYO or kod.endswith("GYO"):
        return "gyo"
    if ind in HOLDING or kod.endswith("HOL"):
        return "holding"
    if sek in DONGUSEL_SEKTOR:
        return "dongusel"
    return "sanayi"


def senaryo_sinifi(r):
    s = r.get("sector")
    if s in BUYUME_SEKTOR:
        return "buyume"
    if s in SAVUNMACI_SEKTOR:
        return "savunmaci"
    if s in DONGUSEL_SEKTOR:
        return "dongusel"
    return "normal"


# ── YÖNTEMLER (hepsi "adil özkaynak / piyasa değeri" oranı döndürür) ──
def ke_hesapla(r, ayar, kayma=0.0):
    beta = r.get("beta_1_year")
    # BIST'te seyrek işlem betayı düşük gösterir → alt sınır 0,7 (risk eksik fiyatlanmasın)
    beta = 1.0 if beta is None else max(0.7, min(2.0, beta))
    beta = 0.67 * beta + 0.33  # Blume düzeltmesi
    spread = max(0.0, ayar["tr_usd_10y_yuzde"] - ayar["abd_10y_yuzde"])
    crp = spread * ayar["ulke_primi_carpani"]
    return (ayar["abd_10y_yuzde"] + beta * (ayar["olgun_piyasa_primi_yuzde"] + crp) + kayma) / 100.0, beta


def wacc_hesapla(r, ke, ayar):
    mc, borc = r.get("market_cap_basic"), r.get("total_debt") or 0.0
    if not mc or mc <= 0:
        return ke
    kd = (ayar["tr_usd_10y_yuzde"] + ayar["borc_maliyeti_ek_yuzde"]) / 100.0 * (1 - ayar["vergi_orani_yuzde"] / 100.0)
    return (mc * ke + borc * kd) / (mc + borc)


def dcf_oran(r, g1, wacc, g_uc, fcf_carpan=1.0):
    """FCF (firma) 5 yıl g1, sonra g_uc büyür; özkaynak = EV − net borç; oran = özkaynak / piyasa değeri."""
    fcf, mc = r.get("free_cash_flow"), r.get("market_cap_basic")
    fcf = fcf * fcf_carpan if fcf else fcf
    if not fcf or fcf <= 0 or not mc or mc <= 0 or wacc <= g_uc + 0.005:
        return None
    pv, f = 0.0, fcf
    for t in range(1, 6):
        f *= 1 + g1
        pv += f / (1 + wacc) ** t
    pv += f * (1 + g_uc) / (wacc - g_uc) / (1 + wacc) ** 5
    ozk = pv - (r.get("net_debt") or 0.0)
    return ozk / mc if ozk > 0 else None


def ters_dcf(r, wacc, g_uc):
    """Mevcut piyasa değerini veren 5 yıllık büyüme (−30%…+60%); bulunamazsa None."""
    if dcf_oran(r, 0.6, wacc, g_uc) is None:
        return None
    lo, hi = -0.30, 0.60
    f = lambda g: (dcf_oran(r, g, wacc, g_uc) or 0.0) - 1.0
    if f(hi) < 0:
        return hi  # %60'tan bile fazla büyüme fiyatlanıyor
    if f(lo) > 0:
        return lo
    for _ in range(60):
        m = (lo + hi) / 2
        if f(m) > 0:
            hi = m
        else:
            lo = m
    return (lo + hi) / 2


def goreli_oran(r, tablo, alan, dilim):
    tv = {"fk": "price_earnings_ttm", "pddd": "price_book_fq"}.get(alan)
    grup, _ = es_grup(tablo, alan, r)
    if not grup:
        return None
    if alan == "fd_favok":
        eb, mc, ev_m = r.get("ebitda"), r.get("market_cap_basic"), r.get("enterprise_value_ebitda_ttm")
        if not eb or eb <= 0 or not mc or mc <= 0 or ev_m is None or ev_m <= 0:
            return None
        ozk = grup[dilim] * eb - (r.get("net_debt") or 0.0)
        return ozk / mc if ozk > 0 else None
    v = r.get(tv)
    lo, hi = SINIR[alan]
    if v is None or not (lo < v < hi):
        return None
    return grup[dilim] / v


def ddm_oran(r, ke, g):
    d = r.get("dividends_yield_current")
    if not d or d <= 0 or ke <= g + 0.005:
        return None
    return (d / 100.0) * (1 + g) / (ke - g)


def roe_pddd_oran(r, tablo, dilim):
    roe, pb = r.get("return_on_equity"), r.get("price_book_fq")
    pb_g, _ = es_grup(tablo, "pddd", r)
    roe_g, _ = es_grup(tablo, "roe", r)
    if roe is None or roe <= 0 or not pb or pb <= 0 or not pb_g or not roe_g or roe_g["p50"] <= 0:
        return None
    hedef = pb_g[dilim] * max(0.5, min(2.0, roe / roe_g["p50"]))
    return hedef / pb


def tarihsel_pddd_oran(r, gecmis):
    """Güncel PD/DD'nin 5 yıllık ortancaya dönüşü: hedef / güncel."""
    g = (gecmis or {}).get(r.get("kod")) or {}
    bant = g.get("pddd_bant")
    if not bant or not bant.get("ortanca"):
        return None
    pb = r.get("price_book_fq")
    if not pb or pb <= 0:
        yillar = g.get("yillar") or {}
        son = yillar.get(max(yillar)) if yillar else None
        pb = (son or {}).get("pddd")
    if not pb or pb <= 0:
        return None
    return bant["ortanca"] / pb


def harmanla(oranlar, agirlik, ust=3.0):
    # Yalnız temettü modeli kalan hisse (ör. TradingView'da bilanço verisi eksik) için değer üretme
    if not any(oranlar.get(k) for k in agirlik if k != "ddm"):
        return None
    toplam, w = 0.0, 0.0
    for k, a in agirlik.items():
        v = oranlar.get(k)
        if v is not None and v > 0:
            toplam += a * min(v, ust)  # tek yöntemin uçması sonucu bozmasın
            w += a
    return (toplam / w) if w > 0 else None


def hisse_degerle(r, tablo, ayar, gecmis=None):
    s = sinif(r)
    g_uc = ayar["uc_buyume_yuzde"] / 100.0
    ke, beta = ke_hesapla(r, ayar)
    wacc = wacc_hesapla(r, ke, ayar)
    sen = [x / 100.0 for x in ayar["senaryo_buyume_yuzde"][senaryo_sinifi(r)]]
    agirlik = AGIRLIK[s]
    ust = ayar["tek_yontem_ust_sinir"]
    roe_g, _ = es_grup(tablo, "roe", r)
    zirve = (s == "dongusel" and r.get("return_on_equity") is not None and roe_g
             and r["return_on_equity"] > roe_g["p75"])
    fcf_c = ayar["dongusel_fcf_kirpma"] if zirve else 1.0
    sonuc = {}
    kullanilan = set()
    for i, (ad, dilim) in enumerate((("kotumser", "p25"), ("baz", "p50"), ("iyimser", "p75"))):
        o = {"fk": goreli_oran(r, tablo, "fk", dilim), "pddd": goreli_oran(r, tablo, "pddd", dilim),
             "fd_favok": goreli_oran(r, tablo, "fd_favok", dilim),
             "dcf": dcf_oran(r, sen[i], wacc, g_uc, fcf_c), "ddm": ddm_oran(r, ke, min(sen[i], g_uc)),
             "roe_pddd": roe_pddd_oran(r, tablo, dilim), "tarihsel_pddd": tarihsel_pddd_oran(r, gecmis)}
        sonuc[ad] = harmanla(o, agirlik, ust)
        if ad == "baz":
            kullanilan = {k for k in agirlik if o.get(k)}
            sonuc["yontem_oranlari"] = {k: round(v, 3) for k, v in o.items() if v}
    # sıralı olsun (kötümser ≤ baz ≤ iyimser)
    seri = sorted(x for x in (sonuc["kotumser"], sonuc["baz"], sonuc["iyimser"]) if x)
    if len(seri) == 3:
        sonuc["kotumser"], sonuc["baz"], sonuc["iyimser"] = seri
    # duyarlılık: özkaynak maliyeti ±2 puan (yalnız DCF/DDM/gerekçeli PD/DD etkilenir)
    duy = {}
    for etiket, kayma in (("ke_eksi2", -2.0), ("ke_arti2", 2.0)):
        ke2, _ = ke_hesapla(r, ayar, kayma)
        w2 = wacc_hesapla(r, ke2, ayar)
        o2 = {"fk": goreli_oran(r, tablo, "fk", "p50"), "pddd": goreli_oran(r, tablo, "pddd", "p50"),
              "fd_favok": goreli_oran(r, tablo, "fd_favok", "p50"), "dcf": dcf_oran(r, sen[1], w2, g_uc, fcf_c),
              "ddm": ddm_oran(r, ke2, min(sen[1], g_uc)), "roe_pddd": roe_pddd_oran(r, tablo, "p50"),
              "tarihsel_pddd": tarihsel_pddd_oran(r, gecmis)}
        duy[etiket] = harmanla(o2, agirlik, ust)
    gm = min(0.30, 0.15 + 0.05 * max(0.0, (r.get("beta_1_year") or 1.0) - 1.0))
    ters = ters_dcf(r, wacc, g_uc) if s in ("sanayi", "dongusel") else None
    return {"sinif": s, "zirve_fcf_kirpildi": bool(zirve), "ke": ke, "beta_duz": beta, "wacc": wacc, "senaryo": sen, "agirlik": agirlik,
            "kullanilan": sorted(kullanilan), "guven_marji": gm, "ters_dcf": ters, "duyarlilik": duy, **sonuc}


def uyarilar(r, d, tablo):
    u = []
    roe_g, _ = es_grup(tablo, "roe", r)
    borc_g, _ = es_grup(tablo, "borc_ozk", r)
    roe, fcf, ni, borc = r.get("return_on_equity"), r.get("free_cash_flow"), r.get("net_income"), r.get("debt_to_equity")
    ucuz = d.get("baz") and d["baz"] > 1.15
    zayif = []
    if roe is not None and roe_g and roe < roe_g["p50"] / 2:
        zayif.append("ROE sektörün yarısından düşük")
    if fcf is not None and fcf < 0 and d["sinif"] not in ("banka", "sigorta", "araci"):
        zayif.append("serbest nakit akışı negatif")
    if borc is not None and borc_g and borc > 2 * borc_g["p50"] and d["sinif"] not in ("banka", "sigorta", "araci"):
        zayif.append("borç/özkaynak sektörün 2 katından fazla")
    if ucuz and zayif:
        u.append("⚠️ Değer tuzağı riski: ucuz görünüyor ama " + ", ".join(zayif))
    elif zayif:
        u.append("Kalite: " + ", ".join(zayif))
    if d["sinif"] == "dongusel" and roe is not None and roe_g and roe > 1.5 * roe_g["p75"]:
        u.append("⚠️ Döngüsel sektörde zirve kârı olabilir: düşük F/K yanıltıcı")
    if d.get("zirve_fcf_kirpildi"):
        u.append("DCF'de zirve nakit akışı %40 kırpıldı")
    if d.get("ters_dcf") is not None and d["ters_dcf"] >= 0.6:
        u.append("Fiyat yıllık %60'tan fazla büyüme varsayıyor (ters DCF)")
    if ni is not None and ni <= 0:
        u.append("Son 12 ay zarar: F/K kullanılamadı")
    if len(d.get("kullanilan") or []) <= 1:
        u.append("Veri az: tek yöntemle hesaplandı, güven düşük")
    if d["sinif"] == "holding":
        u.append("Holding: tarihsel PD/DD (kendi holding iskontosu) ağırlıklı; iştirak bazlı net varlık değeri yok")
    return u


def durum(kapanis, baz, inceleme, iyimser):
    if not baz:
        return "⚪ veri yok"
    if kapanis <= inceleme:
        return "🟢 güven marjının altında"
    if kapanis <= baz:
        return "🟡 adil değerin altında"
    if iyimser and kapanis > iyimser:
        return "🔴 iyimser senaryonun üstünde"
    return "⚪ adil değer bandında"


def aday_mi(s):
    return bool(s.get("adil_baz") and s.get("inceleme_seviyesi") and s["kapanis"] <= s["inceleme_seviyesi"]
                and not any("⚠" in u for u in s.get("uyarilar") or [])
                and (s.get("yontemler") or "").count("%") >= 3)


def _oran(a, b):
    return a / b if a is not None and b not in (None, 0) and a > 0 and b > 0 else None


def one_cikan_alanlar(s):
    """(önem, metin) listesi → en belirgin 3 metin."""
    a = []
    for alan, sek, ad in (("fk", "fk_sektor", "F/K"), ("pddd", "pddd_sektor", "PD/DD"),
                          ("fd_favok", "fd_favok_sektor", "FD/FAVÖK")):
        o = _oran(s.get(alan), s.get(sek))
        if o and o < 0.75:
            a.append((1 - o, "%s %.1f, sektör ortancası %.1f (%%%d daha düşük)" % (ad, s[alan], s[sek], round((1 - o) * 100))))
    for alan, ort, ad in (("fk", "fk_5y_ortanca", "F/K"), ("pddd", "pddd_5y_ortanca", "PD/DD")):
        o = _oran(s.get(alan), s.get(ort))
        if o and o < 0.8:
            a.append((0.8 * (1 - o), "%s kendi 5 yıllık ortancasının altında (%.1f / %.1f)" % (ad, s[alan], s[ort])))
    o = _oran(s.get("roe_yuzde"), s.get("roe_sektor"))
    if o and o > 1.3:
        a.append((min(o - 1, 1.0) * 0.9, "ROE %%%.1f, sektörün %.1f katı" % (s["roe_yuzde"], o)))
    t = s.get("ters_dcf_buyume_yuzde")
    if t is not None and t <= 2:
        a.append((0.6 + max(0, -t) / 50, ("fiyat yıllık %%%.0f küçülme varsayıyor (ters DCF)" % -t) if t < 0
                  else ("fiyat yalnız yıllık %%%.1f büyüme varsayıyor (ters DCF)" % t)))
    tv = s.get("temettu_verimi_yuzde")
    if tv and tv >= 5:
        a.append((tv / 20, "temettü verimi %%%.1f" % tv))
    fc = s.get("fcf_kar_donusum")
    if fc and fc >= 0.8 and s.get("sinif") not in ("banka", "sigorta", "araci"):
        a.append((0.4, "kârın nakde dönüşümü güçlü (FCF/kâr %.2f)" % fc))
    a.sort(key=lambda x: -x[0])
    return [m for _, m in a[:3]]


def one_cikanlar(satirlar, n=3):
    def puan(s):
        p = min(s.get("potansiyel_yuzde") or 0, 100)
        if (s.get("roe_yuzde") or 0) > (s.get("roe_sektor") or 1e9):
            p += 10
        if (s.get("fcf_kar_donusum") or 0) >= 0.7:
            p += 5
        if s.get("sinif") == "dongusel":
            p -= 10
        p += 3 * (s.get("yontemler") or "").count("%")
        return p
    uygun = [s for s in satirlar if s.get("adil_baz") and (s.get("potansiyel_yuzde") or 0) <= 150]
    adaylar = sorted([s for s in uygun if s.get("aday")], key=lambda s: -puan(s))
    yedek = sorted([s for s in uygun if not s.get("aday") and (s.get("durum") or "").startswith("🟢")
                    and not any("⚠" in u for u in s.get("uyarilar") or [])], key=lambda s: -puan(s))
    out = []
    for s in (adaylar + yedek)[:n]:
        out.append({"kod": s["kod"], "ad": s.get("ad"), "sektor": s.get("sektor"), "sinif": s.get("sinif"),
                    "aday": bool(s.get("aday")), "kapanis": s.get("kapanis"), "adil_kotumser": s.get("adil_kotumser"),
                    "adil_baz": s.get("adil_baz"), "adil_iyimser": s.get("adil_iyimser"),
                    "potansiyel_yuzde": s.get("potansiyel_yuzde"), "inceleme_seviyesi": s.get("inceleme_seviyesi"),
                    "one_cikan_alanlar": one_cikan_alanlar(s), "uyarilar": s.get("uyarilar") or [],
                    "sonraki_bilanco": s.get("sonraki_bilanco"), "sonraki_temettu": s.get("sonraki_temettu"),
                    "puan": round(puan(s), 1)})
    return out


def degisimler(yeni, eski):
    """Önceki çalışmaya göre durum veya aday bilgisi değişen hisseler."""
    once = {h.get("kod"): h for h in eski or [] if h.get("kod")}
    out = []
    for h in yeni:
        o = once.get(h.get("kod"))
        if not o or h.get("hata"):
            continue
        e_d, y_d = (o.get("durum") or "")[:1], (h.get("durum") or "")[:1]
        if bool(o.get("aday")) != bool(h.get("aday")) or e_d != y_d:
            out.append({"kod": h["kod"], "eski_durum": o.get("durum"), "yeni_durum": h.get("durum"),
                        "eski_aday": bool(o.get("aday")), "yeni_aday": bool(h.get("aday")),
                        "kapanis": h.get("kapanis"), "adil_baz": h.get("adil_baz")})
    return out


def tarih(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d") if ts else None


def bant_notu(guncel, bant, ad):
    if guncel is None or not bant or guncel <= 0:
        return None
    if guncel < bant["min"]:
        return "%s 5 yıllık bandının altında (%.2f < en düşük %.2f)" % (ad, guncel, bant["min"])
    if guncel > bant["max"]:
        return "%s 5 yıllık bandının üstünde (%.2f > en yüksek %.2f)" % (ad, guncel, bant["max"])
    return None


def degerle(bist100, tum, ayar, gecmis=None):
    tablo = es_grup_tablosu(tum)
    satirlar = []
    for r in sorted(bist100, key=lambda x: x["kod"]):
        kap = r.get("close")
        if not kap:
            continue
        try:
            d = hisse_degerle(r, tablo, ayar, gecmis)
        except Exception as e:
            satirlar.append({"kod": r["kod"], "hata": str(e)[:120]})
            continue
        tl = lambda o: round(kap * o, 2) if o else None
        baz = tl(d["baz"])
        inceleme = round(baz * (1 - d["guven_marji"]), 2) if baz else None
        gruplar = {a: es_grup(tablo, a, r) for a in ("fk", "pddd", "fd_favok", "roe")}
        nxt = r.get("earnings_release_next_date")
        satirlar.append({
            "kod": r["kod"], "ad": r.get("description"), "sektor": SEKTOR_TR.get(r.get("sector"), r.get("sector")),
            "alt_sektor": r.get("industry"), "sinif": d["sinif"], "kapanis": kap,
            "adil_kotumser": tl(d["kotumser"]), "adil_baz": baz, "adil_iyimser": tl(d["iyimser"]),
            "inceleme_seviyesi": inceleme, "guven_marji_yuzde": round(d["guven_marji"] * 100, 1),
            "potansiyel_yuzde": round((baz / kap - 1) * 100, 1) if baz else None,
            "duyarlilik_ke_eksi2": tl(d["duyarlilik"]["ke_eksi2"]), "duyarlilik_ke_arti2": tl(d["duyarlilik"]["ke_arti2"]),
            "ters_dcf_buyume_yuzde": round(d["ters_dcf"] * 100, 1) if d["ters_dcf"] is not None else None,
            "fk": r.get("price_earnings_ttm"), "fk_sektor": (gruplar["fk"][0] or {}).get("p50"),
            "pddd": r.get("price_book_fq"), "pddd_sektor": (gruplar["pddd"][0] or {}).get("p50"),
            "fd_favok": r.get("enterprise_value_ebitda_ttm"), "fd_favok_sektor": (gruplar["fd_favok"][0] or {}).get("p50"),
            "roe_yuzde": r.get("return_on_equity"), "roe_sektor": (gruplar["roe"][0] or {}).get("p50"),
            "borc_ozk": r.get("debt_to_equity"),
            "fcf_kar_donusum": (r["free_cash_flow"] / r["net_income"]) if r.get("free_cash_flow") is not None
            and r.get("net_income") and r["net_income"] > 0 else None,
            "temettu_verimi_yuzde": r.get("dividends_yield_current"), "beta": r.get("beta_1_year"),
            "ozkaynak_maliyeti_usd_yuzde": round(d["ke"] * 100, 2),
            "es_grup": gruplar["fk"][1] or gruplar["pddd"][1],
            "yontemler": ", ".join("%s %%%d" % (k, round(d["agirlik"][k] * 100)) for k in d["kullanilan"]),
            "sonraki_bilanco": dt.datetime.fromtimestamp(nxt, dt.timezone.utc).strftime("%Y-%m-%d") if nxt else None,
            "durum": durum(kap, baz, inceleme, tl(d["iyimser"])),
            "uyarilar": uyarilar(r, d, tablo),
            "sonraki_temettu": tarih(r.get("ex_dividend_date_upcoming")),
            "temettu_odeme": tarih(r.get("dividend_payment_date_upcoming")),
        })
        g = (gecmis or {}).get(r["kod"]) or {}
        fb, pb = g.get("fk_bant"), g.get("pddd_bant")
        satirlar[-1].update({"fk_5y_ortanca": (fb or {}).get("ortanca"), "pddd_5y_ortanca": (pb or {}).get("ortanca"),
                             "fk_5y_bant": fb, "pddd_5y_bant": pb})
        for n_ in (bant_notu(r.get("price_earnings_ttm"), fb, "F/K"), bant_notu(r.get("price_book_fq"), pb, "PD/DD")):
            if n_:
                satirlar[-1]["uyarilar"].append(n_)
        satirlar[-1]["aday"] = aday_mi(satirlar[-1])
    return satirlar


CSV_SAYI = ["kapanis", "adil_kotumser", "adil_baz", "adil_iyimser", "inceleme_seviyesi", "guven_marji_yuzde",
            "potansiyel_yuzde", "duyarlilik_ke_eksi2", "duyarlilik_ke_arti2", "ters_dcf_buyume_yuzde", "fk",
            "fk_sektor", "pddd", "pddd_sektor", "fd_favok", "fd_favok_sektor", "roe_yuzde", "roe_sektor",
            "borc_ozk", "fcf_kar_donusum", "temettu_verimi_yuzde", "beta", "ozkaynak_maliyeti_usd_yuzde",
            "fk_5y_ortanca", "pddd_5y_ortanca"]
CSV_METIN = ["kod", "ad", "sektor", "alt_sektor", "sinif", "durum", "yontemler", "sonraki_bilanco", "uyari",
             "sonraki_temettu"]


def csv_yaz(satirlar, yol=CSV_YOL):
    """Sayılar ×100 tamsayı (boş = veri yok). Sütun sırası DEĞİŞTİRİLMEZ: tablo formülleri buna bağlı."""
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_METIN[:5] + [c + "_x100" for c in CSV_SAYI] + CSV_METIN[5:])
        for s in satirlar:
            if s.get("hata"):
                continue
            sayilar = ["" if s.get(c) is None else str(int(round(s[c] * 100))) for c in CSV_SAYI]
            metin2 = [s.get("durum") or "", s.get("yontemler") or "", s.get("sonraki_bilanco") or "",
                      " | ".join(s.get("uyarilar") or []), s.get("sonraki_temettu") or ""]
            w.writerow([s.get(c) or "" for c in CSV_METIN[:5]] + sayilar + metin2)


def yaz_json(d, yol=JSON_YOL):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def main():
    cikti = {"surum": SURUM, "uretim_zamani_utc": simdi(), "hata": None,
             "not": "Otomatik model çıktısıdır; yatırım tavsiyesi değildir. Tutarlar TL; DCF USD bazlı yapılıp TL fiyata oranlanır."}
    try:
        with open(JSON_YOL, encoding="utf-8") as f:
            eski_hisseler = json.load(f).get("hisseler") or []
    except Exception:
        eski_hisseler = []
    try:
        ayar = ayar_oku()
        tr_usd_10y_guncelle(ayar)
        abd_10y_guncelle(ayar)
        tum = tv_cek()
        bist100 = tv_cek("SYML:BIST;XU100")
        try:
            with open(GECMIS_YOL, encoding="utf-8") as f:
                gecmis = json.load(f).get("hisseler") or {}
        except Exception:
            gecmis = {}
        satirlar = degerle(bist100, tum, ayar, gecmis)
        cikti.update({"ayar": ayar, "evren": {"bist100": len(bist100), "es_grup_evreni": len(tum)},
                      "hisseler": satirlar, "adaylar": [x["kod"] for x in satirlar if x.get("aday")],
                      "one_cikanlar": one_cikanlar(satirlar),
                      "degisimler": degisimler(satirlar, eski_hisseler)})
        csv_yaz(satirlar)
        print("YAZILDI:", JSON_YOL, CSV_YOL, len(satirlar), "hisse")
    except Exception:
        traceback.print_exc()
        cikti["hata"] = traceback.format_exc().strip().splitlines()[-1][:300]
        try:
            with open(JSON_YOL, encoding="utf-8") as f:
                eski = json.load(f)
            cikti["hisseler"] = eski.get("hisseler", [])
            cikti["ayar"] = eski.get("ayar")
            cikti["onceki_uretim_utc"] = eski.get("uretim_zamani_utc")
        except Exception:
            pass
    yaz_json(cikti)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
    sys.exit(0)
