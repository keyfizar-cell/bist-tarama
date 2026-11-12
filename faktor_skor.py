#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
faktor_skor.py  v1.1  (2026-11-12) — 5 faktörlü skor modeli + örnek model sepet (eğitim amaçlı)

Yöntem (Alpay'ın paylaştığı Emir Bozkurt "Gelişmiş Model" videosundan uyarlandı, 12.11.2026):
  Büyüme %40   : satış, FAVÖK ve net kâr büyümesi (yıllık, son 12 ay), ROE, ROIC
  Nakit %20    : işletme nakit akışı / net kâr, serbest nakit akışı / satış, son çeyrek SNA yönü (+/−)
  Değerleme %20: F/K ve FD/FAVÖK (düşük = iyi; negatif/zarar = boş)
  Borç %10     : net borç / FAVÖK (düşük/negatif = iyi), borç / özkaynak (düşük = iyi)
  Momentum %10 : 12−1 ay getirisi, 6 ay ve 3 ay getirisi
  Her metrik evren içinde 0–100 yüzdelik sıraya çevrilir; eksik veri o metrikte 0 puan (Emir'in kuralı);
  son 12 ayda zarar edende F/K ve net kâr büyümesi boş kalır.
  Kapsam: banka, sigorta, aracı kurum, GYO ve gayrimenkul geliştirme HARİÇ tüm BIST (Emir: modele uymuyor).
  Ana liste: piyasa değeri ≥ 5 mlr TL (~100 mn USD); küçük ölçek ayrı listelenir (sığ tahta uyarısı).
  NOT: TradingView toplu (set_markets) sorgusu tutarları TL verir; oranlar para biriminden bağımsızdır.
v1.1 TMS 29 (KISMİ) + MARJ: data/tms29.json (tms29_duzeltme.py, haftalık, İş Yatırım) varsa o şirket için
  net kâr = ertelenmiş vergiden arındırılmış son 12 ay kârı → F/K, ROE, net kâr büyümesi ve İşletme nakit/net kâr
  bu düzeltilmiş kârla hesaplanır; büyüme faktörüne brüt marj ve FAVÖK marjı değişimi (yıllık, puan) eklenir.
  Net parasal pozisyon İş Yatırım şablonunda ayrı satır olmadığından ÇIKARILMAZ → "kısmi arındırma".
  Düzeltme verisi olmayan şirket TradingView rakamlarıyla (enflasyon dahil) değerlenir; marj metrikleri 0 puan.
Sıra değişimi: haftalık anlık görüntüler saklanır; ~90 gün önceki (yoksa en eski) sırayla kıyaslanır.

ÖRNEK MODEL SEPET (yatırım tavsiyesi DEĞİLDİR; Koç'un eğitim/izleme amaçlı kâğıt portföyü):
  Haftada bir (haftanın ilk çalışmasında) ana listenin en iyi skorlularından 5 hisse, sektör başına en fazla 2,
  adil değer modeli "🔴 iyimser senaryonun üstünde" diyenler hariç; eşit ağırlık. Giriş fiyatı kaydedilir,
  tüm geçmiş sepetlerin getirisi BIST100'e karşı her gün güncellenir (dürüst karne).
Çıktılar: data/faktor_skor.json, data/model_sepet.json. Her durumda JSON yazar ve exit(0).
"""
import datetime as dt
import json
import os
import statistics
import sys
import traceback

SURUM = "1.1"
VERI = "data"
SKOR_YOL = os.path.join(VERI, "faktor_skor.json")
SEPET_YOL = os.path.join(VERI, "model_sepet.json")
ADIL_YOL = os.path.join(VERI, "adil_deger.json")
TMS_YOL = os.path.join(VERI, "tms29.json")

AGIRLIK = {"buyume": 0.40, "nakit": 0.20, "degerleme": 0.20, "borc": 0.10, "momentum": 0.10}
ANA_LISTE_TL = 5e9  # TradingView toplu sorgu tutarları TL döndürür
HARIC_ALT = {"Major Banks", "Regional Banks", "Life/Health Insurance", "Multi-Line Insurance",
             "Property/Casualty Insurance", "Investment Banks/Brokers", "Finance/Rental/Leasing",
             "Real Estate Investment Trusts", "Real Estate Development"}
SEPET_BOYUT = 5
SEKTOR_SINIR = 2
ANLIK_SAKLA_GUN = 400

ALANLAR = ["name", "description", "close", "sector", "industry", "market_cap_basic",
           "total_revenue_yoy_growth_ttm", "ebitda_yoy_growth_ttm", "net_income_yoy_growth_ttm",
           "return_on_equity", "return_on_invested_capital", "cash_f_operating_activities_ttm",
           "free_cash_flow", "free_cash_flow_fq", "total_revenue", "net_income", "price_earnings_ttm",
           "enterprise_value_ebitda_ttm", "net_debt", "ebitda", "debt_to_equity",
           "Perf.Y", "Perf.6M", "Perf.3M", "Perf.1M"]

SEKTOR_TR = {
    "Communications": "İletişim", "Consumer Durables": "Dayanıklı Tüketim", "Consumer Non-Durables": "Dayanıksız Tüketim",
    "Consumer Services": "Tüketici Hizmetleri", "Electronic Technology": "Elektronik Teknoloji",
    "Energy Minerals": "Enerji / Rafineri", "Finance": "Finans", "Health Services": "Sağlık Hizmetleri",
    "Health Technology": "Sağlık Teknolojisi", "Industrial Services": "Endüstriyel Hizmetler", "Miscellaneous": "Diğer",
    "Non-Energy Minerals": "Metal / Maden / Çimento", "Process Industries": "Proses Sanayi",
    "Producer Manufacturing": "İmalat", "Retail Trade": "Perakende", "Technology Services": "Teknoloji Hizmetleri",
    "Transportation": "Ulaştırma", "Utilities": "Enerji Dağıtım / Üretim", "Commercial Services": "Ticari Hizmetler",
    "Distribution Services": "Dağıtım",
}


def bugun():
    return dt.date.today().isoformat()


def sayi(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if x != x or x in (float("inf"), float("-inf")) else x


def yukle(yol, varsayilan):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return varsayilan


def yaz(yol, d):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def tv_cek():
    from tradingview_screener import Query
    _, df = Query().select(*ALANLAR).set_markets("turkey").limit(3000).get_scanner_data()
    out = []
    for r in df.to_dict("records"):
        r = {k: (v if k in ("ticker", "name", "description", "sector", "industry") else sayi(v)) for k, v in r.items()}
        r["kod"] = str(r.get("name") or "").upper()
        out.append(r)
    return out


def bist100_kapanis():
    """BIST100 endeks değeri (Yahoo XU100.IS; TradingView taraması endeksi döndürmüyor)."""
    import urllib.request
    try:
        req = urllib.request.Request("https://query1.finance.yahoo.com/v8/finance/chart/XU100.IS?range=5d&interval=1d",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return sayi(json.loads(r.read().decode())["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except Exception as e:
        print("XU100 okunamadi:", type(e).__name__, str(e)[:100])
        return None


# ── METRİKLER ──
def bol(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def metrikler(r, t=None):
    """(değer, yön) — yön +1: büyük iyi, −1: küçük iyi. None = eksik (0 puan). t: tms29.json kaydı (varsa)."""
    t = t if t and t.get("duz_net_kar_ttm") is not None else None
    ni = t["duz_net_kar_ttm"] if t else r.get("net_income")
    zarar = ni is None or ni <= 0
    pe = (r["market_cap_basic"] / ni if not zarar and r.get("market_cap_basic") else None) if t \
        else r.get("price_earnings_ttm")
    ev = r.get("enterprise_value_ebitda_ttm")
    eb = r.get("ebitda")
    nd = r.get("net_debt")
    py, p1 = r.get("Perf.Y"), r.get("Perf.1M")
    mom12_1 = ((1 + py / 100) / (1 + p1 / 100) - 1) * 100 if py is not None and p1 is not None and p1 > -100 else None
    sfq = r.get("free_cash_flow_fq")
    return {
        "buyume": [(r.get("total_revenue_yoy_growth_ttm"), 1), (r.get("ebitda_yoy_growth_ttm"), 1),
                   (None if zarar else (t.get("duz_net_kar_buyume_yuzde") if t else r.get("net_income_yoy_growth_ttm")), 1),
                   ((t.get("duz_roe_yuzde") if t else r.get("return_on_equity")), 1),
                   (r.get("return_on_invested_capital"), 1),
                   ((t or {}).get("brut_marj_degisim_puan"), 1), ((t or {}).get("favok_marj_degisim_puan"), 1)],
        "nakit": [(None if zarar else bol(r.get("cash_f_operating_activities_ttm"), ni), 1),
                  (bol(r.get("free_cash_flow"), r.get("total_revenue")), 1),
                  (None if sfq is None else (1.0 if sfq > 0 else 0.0), 1)],
        "degerleme": [(pe if pe and pe > 0 and not zarar else None, -1), (ev if ev and ev > 0 else None, -1)],
        "borc": [(bol(nd, eb) if eb and eb > 0 else (None if nd is None or nd > 0 else -1.0), -1),
                 (r.get("debt_to_equity"), -1)],
        "momentum": [(mom12_1, 1), (r.get("Perf.6M"), 1), (r.get("Perf.3M"), 1)],
    }


def yuzdelik(degerler, yon):
    """{i: 0–100}; eşitlerde ortalama sıra. yon −1 ise küçük değer yüksek puan."""
    dolu = sorted([(v * yon, i) for i, v in degerler.items() if v is not None])
    n = len(dolu)
    out = {}
    if n == 0:
        return out
    j = 0
    while j < n:
        k = j
        while k + 1 < n and dolu[k + 1][0] == dolu[j][0]:
            k += 1
        p = 100.0 * ((j + k) / 2) / (n - 1) if n > 1 else 100.0
        for t in range(j, k + 1):
            out[dolu[t][1]] = p
        j = k + 1
    return out


def skorla(evren, tms=None):
    tms = tms or {}
    m = [metrikler(r, tms.get(r["kod"])) for r in evren]
    faktor = {f: [0.0] * len(evren) for f in AGIRLIK}
    for f in AGIRLIK:
        alt_sayi = len(m[0][f]) if m else 0
        for a in range(alt_sayi):
            deg = {i: m[i][f][a][0] for i in range(len(evren))}
            yon = m[0][f][a][1]
            p = yuzdelik(deg, yon)
            for i in range(len(evren)):
                faktor[f][i] += p.get(i, 0.0) / alt_sayi  # eksik → 0 puan
    sonuc = []
    for i, r in enumerate(evren):
        fs = {f: round(faktor[f][i], 1) for f in AGIRLIK}
        toplam = round(sum(AGIRLIK[f] * fs[f] for f in AGIRLIK), 1)
        sonuc.append({"kod": r["kod"], "ad": r.get("description"), "sektor": SEKTOR_TR.get(r.get("sector"), r.get("sector")),
                      "kapanis": r.get("close"), "pd_mlr_tl": round((r.get("market_cap_basic") or 0) / 1e9, 2),
                      "ana_liste": (r.get("market_cap_basic") or 0) >= ANA_LISTE_TL, **fs, "toplam": toplam,
                      "tms29_duzeltildi": bool((tms.get(r["kod"]) or {}).get("duz_net_kar_ttm") is not None)})
    sonuc.sort(key=lambda x: -x["toplam"])
    for s, x in enumerate(sonuc, 1):
        x["sira"] = s
    return sonuc


def eski_sira(anliklar, hedef_gun=90):
    """~90 gün önceki (yoksa en eski) anlık görüntü → ({kod: sıra}, tarih)."""
    if not anliklar:
        return {}, None
    hedef = (dt.date.today() - dt.timedelta(days=hedef_gun)).isoformat()
    tarihler = sorted(anliklar)
    once = [t for t in tarihler if t <= hedef]
    t = once[-1] if once else tarihler[0]
    if t == bugun():
        return {}, None
    return anliklar[t], t


# ── MODEL SEPET ──
def hafta_anahtari(gun=None):
    y, w, _ = (gun or dt.date.today()).isocalendar()
    return "%d-H%02d" % (y, w)


def sepet_sec(skorlar, adil):
    durum = {h.get("kod"): (h.get("durum") or "") for h in adil}
    secim, sektor_say = [], {}
    for x in skorlar:
        if not x["ana_liste"] or x["kapanis"] is None:
            continue
        if durum.get(x["kod"], "").startswith("🔴"):
            continue
        if sektor_say.get(x["sektor"], 0) >= SEKTOR_SINIR:
            continue
        secim.append(x)
        sektor_say[x["sektor"]] = sektor_say.get(x["sektor"], 0) + 1
        if len(secim) == SEPET_BOYUT:
            break
    return secim


def sepet_guncelle(sepet_d, skorlar, adil, xu100):
    fiyat = {x["kod"]: x["kapanis"] for x in skorlar}
    sepetler = sepet_d.get("sepetler") or []
    hk = hafta_anahtari()
    if xu100 and not any(s.get("hafta") == hk for s in sepetler):
        secim = sepet_sec(skorlar, adil)
        if secim:
            sepetler.append({"hafta": hk, "tarih": bugun(), "xu100_giris": xu100,
                             "hisseler": [{"kod": x["kod"], "sektor": x["sektor"], "giris": x["kapanis"],
                                           "skor": x["toplam"], "sira": x["sira"], "agirlik_yuzde": 100 / len(secim)}
                                          for x in secim]})
    for s in sepetler:
        getiriler = []
        for h in s["hisseler"]:
            f = fiyat.get(h["kod"])
            if f and h.get("giris"):
                h["guncel"] = f
                h["getiri_yuzde"] = round((f / h["giris"] - 1) * 100, 2)
            if h.get("getiri_yuzde") is not None:
                getiriler.append(h["getiri_yuzde"])
        s["sepet_getiri_yuzde"] = round(statistics.mean(getiriler), 2) if getiriler else None
        if xu100 and s.get("xu100_giris"):
            s["xu100_getiri_yuzde"] = round((xu100 / s["xu100_giris"] - 1) * 100, 2)
            if s["sepet_getiri_yuzde"] is not None:
                s["fark_puan"] = round(s["sepet_getiri_yuzde"] - s["xu100_getiri_yuzde"], 2)
    farklar = [s["fark_puan"] for s in sepetler if s.get("fark_puan") is not None]
    return {"surum": SURUM, "guncelleme": bugun(), "sepetler": sepetler[-52:],
            "karne": {"sepet_sayisi": len(sepetler), "endeksi_gecen": sum(1 for f in farklar if f > 0),
                      "ort_fark_puan": round(statistics.mean(farklar), 2) if farklar else None},
            "not": "Örnek model sepet — eğitim/izleme amaçlı kâğıt portföy; yatırım tavsiyesi değildir."}


def main():
    eski = yukle(SKOR_YOL, {})
    cikti = {"surum": SURUM, "tarih": bugun(), "hata": None, "agirlik": AGIRLIK,
             "not": "Emir Bozkurt 5 faktör yönteminden uyarlandı. TMS 29 KISMİ arındırma (ertelenmiş vergi çıkarıldı; "
                    "net parasal pozisyon çıkarılamadı) + marj değişimi; düzeltme verisi olmayan şirketler enflasyon dahil."}
    try:
        tum = tv_cek()
        evren = [r for r in tum if r.get("industry") not in HARIC_ALT and not r["kod"].endswith("GYO")
                 and r.get("market_cap_basic") and r.get("close")]
        tms = (yukle(TMS_YOL, {}).get("hisseler") or {})
        skorlar = skorla(evren, tms)
        cikti["tms29_kapsam"] = sum(1 for x in skorlar if x.get("tms29_duzeltildi"))
        anliklar = dict(eski.get("anliklar") or {})
        once, once_t = eski_sira(anliklar)
        for x in skorlar:
            o = once.get(x["kod"])
            x["onceki_sira"] = o
            x["sira_degisim"] = (o - x["sira"]) if o else None
        # haftalık anlık görüntü (haftanın ilk çalışması)
        if not any(hafta_anahtari(dt.date.fromisoformat(t)) == hafta_anahtari() for t in anliklar):
            anliklar[bugun()] = {x["kod"]: x["sira"] for x in skorlar}
        sinir = (dt.date.today() - dt.timedelta(days=ANLIK_SAKLA_GUN)).isoformat()
        anliklar = {t: v for t, v in anliklar.items() if t >= sinir}
        ana = [x for x in skorlar if x["ana_liste"]]
        kucuk = [x for x in skorlar if not x["ana_liste"]]
        liderler = {f: [{"kod": x["kod"], "sektor": x["sektor"], "puan": x[f]}
                        for x in sorted(ana, key=lambda y: -y[f])[:3]] for f in AGIRLIK}
        degisen = [x for x in ana if x.get("sira_degisim") is not None]
        cikti.update({
            "evren": len(skorlar), "ana_liste_sayisi": len(ana), "karsilastirma_tarihi": once_t,
            "ana_ilk20": ana[:20], "kucuk_ilk10": kucuk[:10], "faktor_liderleri": liderler,
            "en_cok_yukselen": sorted(degisen, key=lambda x: -x["sira_degisim"])[:10],
            "en_cok_gerileyen": sorted(degisen, key=lambda x: x["sira_degisim"])[:10],
            "tum": {x["kod"]: {k: x[k] for k in ("sira", "toplam", "buyume", "nakit", "degerleme", "borc",
                                                  "momentum", "ana_liste", "sira_degisim", "tms29_duzeltildi")}
                    for x in skorlar},
            "anliklar": anliklar,
        })
        adil = yukle(ADIL_YOL, {}).get("hisseler") or []
        yaz(SEPET_YOL, sepet_guncelle(yukle(SEPET_YOL, {}), skorlar, adil, bist100_kapanis()))
        print("YAZILDI:", SKOR_YOL, len(skorlar), "şirket;", SEPET_YOL)
    except Exception:
        traceback.print_exc()
        cikti["hata"] = traceback.format_exc().strip().splitlines()[-1][:300]
        for k in ("ana_ilk20", "kucuk_ilk10", "faktor_liderleri", "tum", "anliklar"):
            if k in eski:
                cikti[k] = eski[k]
    yaz(SKOR_YOL, cikti)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
    sys.exit(0)
