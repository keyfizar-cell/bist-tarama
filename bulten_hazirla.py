#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bulten_hazirla.py  v1.0  (2026-11-07)  — Aşama 2: hesaplar koda, yorum yapay zekâya

Akşam bülteninin kurallı (deterministik) hesaplarını GitHub Actions'ta yapar ve
data/bulten_girdi.json dosyasına yazar. Bülten görevi bu hesapları her akşam
yeniden yapmak yerine bu dosyayı okuyabilir (görev talimatı ancak bu dosya en az
bir gerçek akşam doğru üretildikten sonra değiştirilir).

Hesaplananlar (gorevler/aksam_bulteni.md'deki kuralların birebir kodu):
  - emir_bozkurt   : Bölüm 7 sinyali (7a watchlist A/B, 7b diğer) + en yakın adaylar
  - sinyal_gecmisi : Bölüm 7c, son 30 takvim günü tarihli taramalardan aynı filtre
  - bist30         : Bölüm 6 tablo verisi (endekse göre farkı için BIST100 % bültende)
  - teknik_plan    : Bölüm 4 mekanik seviyeler (tüm hisseler; bülten portföy kodlarını seçer)
  - retail_radar   : Bölüm 8.5(1)
  - geri_alim      : portföy + BIST30 özet; kümülatif YALNIZ şirket beyanıysa

Yapmadıkları (bültende kalır): portföy dosyası (Google Drive) ve "Portföy Kâr" sütunu,
BIST100/kur/kripto/haber, yorum ve e-posta.

GÜVENLİK: ana taramayı etkilemez; her durumda JSON yazar (hata alanıyla) ve exit(0).
"""
import datetime as dt
import glob
import json
import os
import sys
import traceback

SURUM = "1.0"
VERI = "data"
CIKTI = os.path.join(VERI, "bulten_girdi.json")

GECMIS_GUN = 30
GECMIS_EN_ESKI = "2026-09-22"
PIYASA_DEGERI_ESIK = 1_000_000_000
GUNLUK_SERMAYE_ESIK = 15.0
SERT_COKUS_ORAN = 5.0
RADAR_HACIM_ORANI = 3.0
RADAR_GUNLUK = 9.0
RADAR_ADET = 10
KAPANIS_SAATI_UTC = dt.time(15, 15)

# BIST tam gün tatilleri (görev talimatlarıyla aynı liste)
TATILLER = {"2026-10-29", "2027-01-01", "2027-03-10", "2027-03-11", "2027-03-12", "2027-04-23",
            "2027-05-17", "2027-05-18", "2027-05-19", "2027-07-15", "2027-08-30", "2027-10-29"}

# BIST30 — kap_tarama.py ile aynı yaklaşık liste (KOZAL yerine TRALT)
BIST30 = ["AKBNK", "AKSEN", "ALARK", "ASELS", "ASTOR", "BIMAS", "EKGYO", "ENKAI",
          "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL", "KONTR",
          "KRDMD", "OYAKC", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TCELL",
          "THYAO", "TOASO", "TRALT", "TUPRS", "VAKBN", "YKBNK"]

SINYAL_BAYRAKLARI = ["asiri_satim", "donus_teyidi", "hacim_patlamasi"]
ELEME_BAYRAKLARI = ["dusen_bicak", "olasi_sermaye_islemi"]

KURAL_METNI = ("SİNYAL = asiri_satim VE donus_teyidi VE hacim_patlamasi VE düşen bıçak değil VE "
               "sermaye işlemi değil; güvenlik: bb_alt > 0, |günlük %| < 15, piyasa değeri ≥ 1 mlr TL. "
               "h52_zirve/kapanış ≥ 5 ise bülten son 60 gün KAP bedelsiz/bölünme kontrolü yapar.")


def simdi():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sayi(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def yuvarla(x, n=2):
    return round(x, n) if sayi(x) else None


# ── kurallar (saf fonksiyonlar; testler bunları doğrudan çağırır) ──
def guvenlik_eksikleri(h):
    eksik = []
    if not (sayi(h.get("bb_alt")) and h["bb_alt"] > 0):
        eksik.append("bb_alt>0")
    g = h.get("gunluk_yuzde")
    if not (sayi(g) and abs(g) < GUNLUK_SERMAYE_ESIK):
        eksik.append("|günlük%|<15")
    pd = h.get("piyasa_degeri")
    if not (sayi(pd) and pd >= PIYASA_DEGERI_ESIK):
        eksik.append("piyasa değeri ≥1 mlr TL")
    return eksik


def sinyal_eksikleri(h):
    """Sinyal için eksik kriterlerin listesi; boşsa hisse sinyal verir."""
    eksik = [b for b in SINYAL_BAYRAKLARI if h.get(b) is not True]
    eksik += ["NOT " + b for b in ELEME_BAYRAKLARI if h.get(b) is True]
    return eksik + guvenlik_eksikleri(h)


def sinyal_mi(h):
    return not sinyal_eksikleri(h)


def watchlist_grubu(h):
    w = h.get("watchlist")
    return w if w in ("A", "B") else None


def hacim_mn_tl(h):
    if sayi(h.get("hacim_ort10")) and sayi(h.get("kapanis")):
        return round(h["hacim_ort10"] * h["kapanis"] / 1e6, 1)
    return None


def teknik_plan(h):
    """Bölüm 4 mekanik seviyeler: Stop −%7 (52H dip daha yakınsa o), TP1 +%8 (52H zirveyi aşmaz), TP2 +%15."""
    k = h.get("kapanis")
    if not sayi(k) or k <= 0:
        return None
    dip, zirve = h.get("h52_dip"), h.get("h52_zirve")
    stop = k * 0.93
    if sayi(dip) and stop < dip < k:
        stop = dip
    tp1 = k * 1.08
    if sayi(zirve) and k < zirve < tp1:
        tp1 = zirve
    konum = None
    if sayi(dip) and sayi(zirve) and zirve > dip:
        konum = round(100.0 * (k - dip) / (zirve - dip), 1)
    return {"giris": yuvarla(k, 4), "stop": yuvarla(stop, 4), "tp1": yuvarla(tp1, 4),
            "tp2": yuvarla(k * 1.15, 4), "h52_konum_yuzde": konum,
            "rsi": yuvarla(h.get("rsi"), 1), "macd": yuvarla(h.get("macd"), 4),
            "macd_sinyal": yuvarla(h.get("macd_sinyal"), 4), "macd_durum": h.get("macd_durum"),
            "tv_sinyal": h.get("tv_sinyal"), "tv_sinyal_skor": yuvarla(h.get("tv_sinyal_skor"), 3)}


def sinyal_satiri(h):
    k = h.get("kapanis")
    zirve = h.get("h52_zirve")
    sert = bool(sayi(zirve) and sayi(k) and k > 0 and zirve / k >= SERT_COKUS_ORAN)
    return {
        "kod": h.get("kod"), "watchlist": watchlist_grubu(h),
        "kapanis": yuvarla(k, 4), "gunluk_yuzde": yuvarla(h.get("gunluk_yuzde")),
        "rsi": yuvarla(h.get("rsi"), 1), "bb_alt": yuvarla(h.get("bb_alt"), 4),
        "hacim_orani": yuvarla(h.get("hacim_orani")), "hacim_ort10_mn_tl": hacim_mn_tl(h),
        "donus_kaynagi": h.get("donus_kaynagi"), "macd_durum": h.get("macd_durum"),
        "ema50_uzeri": h.get("ema50_uzeri"),
        "h52_dip": yuvarla(h.get("h52_dip"), 4), "h52_zirve": yuvarla(zirve, 4),
        "piyasa_degeri": h.get("piyasa_degeri"),
        "kap_bedelsiz_kontrolu_gerekli": sert,
        "not": "sert çöküş sonrası tepki, yüksek risk — bülten son 60 gün KAP bedelsiz/bölünme kontrolü yapmalı" if sert else None,
    }


# ── veri yükleme ──
def yukle(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def kapanis_verisi_mi(d):
    """Seans sonu kuralı: tarih dosyanın kendi tarihi VE üretim ≥ 15:15 UTC aynı gün."""
    try:
        u = dt.datetime.fromisoformat(d["uretim_zamani_utc"].replace("Z", "+00:00"))
        return u.date().isoformat() == d["tarih"] and u.time() >= KAPANIS_SAATI_UTC
    except Exception:
        return False


def tarihli_dosyalar(bugun, klasor=VERI):
    """bugun dahil son GECMIS_GUN takvim günündeki tarihli taramalar (tatiller hariç), eskiden yeniye."""
    alt = max((bugun - dt.timedelta(days=GECMIS_GUN)).isoformat(), GECMIS_EN_ESKI)
    sonuc = []
    for yol in sorted(glob.glob(os.path.join(klasor, "20??-??-??.json"))):
        t = os.path.basename(yol)[:10]
        if alt <= t <= bugun.isoformat() and t not in TATILLER:
            sonuc.append((t, yol))
    return sonuc


# ── bölümler ──
def emir_bozkurt(tum):
    sinyaller = [sinyal_satiri(h) for h in tum if sinyal_mi(h)]
    sinyaller.sort(key=lambda s: -(s["hacim_orani"] or 0))
    return {
        "kural": KURAL_METNI,
        "toplam_sinyal": len(sinyaller),
        "7a_watchlist": [s for s in sinyaller if s["watchlist"]],
        "7b_diger": [s for s in sinyaller if not s["watchlist"]],
    }


def yakin_adaylar(lt, tum_harita, adet=2):
    out = []
    for a in (lt.get("yakin_adaylar") or []):
        h = tum_harita.get(a.get("kod")) or a
        eksik = sinyal_eksikleri(h)
        if not eksik:
            continue  # zaten sinyal; tabloda
        out.append({"kod": h.get("kod"), "rsi": yuvarla(h.get("rsi"), 1),
                    "gunluk_yuzde": yuvarla(h.get("gunluk_yuzde")), "eksik": eksik})
        if len(out) >= adet:
            break
    return out


def sinyal_gecmisi(dosyalar, tum_harita, bugun_tarih):
    kayit = {}
    for t, yol in dosyalar:
        try:
            d = yukle(yol)
        except Exception:
            continue
        for h in d.get("tum_hisseler") or []:
            if not sinyal_mi(h):
                continue
            r = kayit.setdefault(h["kod"], {"ilk_sinyal": t, "ilk_kapanis": h.get("kapanis"), "gunler": set()})
            r["gunler"].add(t)
    satirlar = []
    for kod, r in kayit.items():
        bugun = tum_harita.get(kod) or {}
        k0, k1 = r["ilk_kapanis"], bugun.get("kapanis")
        getiri = round(100.0 * (k1 - k0) / k0, 2) if sayi(k0) and sayi(k1) and k0 > 0 else None
        satirlar.append({
            "kod": kod, "ilk_sinyal": r["ilk_sinyal"],
            "grup": watchlist_grubu(bugun) or "watchlist dışı",
            "sinyal_gunu_kapanis": yuvarla(k0, 4), "bugun_kapanis": yuvarla(k1, 4),
            "sinyalden_bu_yana_yuzde": getiri,
            "hacim_ort10_mn_tl": hacim_mn_tl(bugun),
            "hacim_ort10_mn_lot": round(bugun["hacim_ort10"] / 1e6, 2) if sayi(bugun.get("hacim_ort10")) else None,
            "sinyal_sayisi": len(r["gunler"]),
            "bugun_sinyal": bugun_tarih in r["gunler"],
        })
    satirlar.sort(key=lambda s: s["ilk_sinyal"])
    g = [s["sinyalden_bu_yana_yuzde"] for s in satirlar if s["sinyalden_bu_yana_yuzde"] is not None]
    en_iyi = max((s for s in satirlar if s["sinyalden_bu_yana_yuzde"] is not None),
                 key=lambda s: s["sinyalden_bu_yana_yuzde"], default=None)
    return {
        "pencere": {"en_eski": dosyalar[0][0] if dosyalar else None,
                    "en_yeni": dosyalar[-1][0] if dosyalar else None,
                    "dosya_sayisi": len(dosyalar), "tatiller_haric": True},
        "satirlar": satirlar,
        "ozet": {"toplam": len(satirlar), "pozitif": sum(1 for x in g if x > 0),
                 "negatif": sum(1 for x in g if x < 0),
                 "ortalama_getiri_yuzde": round(sum(g) / len(g), 2) if g else None,
                 "en_iyi": {"kod": en_iyi["kod"], "ilk_sinyal": en_iyi["ilk_sinyal"],
                            "getiri_yuzde": en_iyi["sinyalden_bu_yana_yuzde"]} if en_iyi else None},
        "not": "Portföy Kâr % / TL sütunu portföy dosyasından (Drive) bültende hesaplanır.",
    }


def bist30(tum_harita, hala_eksik):
    satirlar = []
    for kod in BIST30:
        h = tum_harita.get(kod)
        satirlar.append({
            "kod": kod, "veri_var": h is not None,
            "kapanis": yuvarla((h or {}).get("kapanis"), 4),
            "gunluk_yuzde": yuvarla((h or {}).get("gunluk_yuzde")),
            "tv_sinyal": (h or {}).get("tv_sinyal"),
            "tv_sinyal_skor": yuvarla((h or {}).get("tv_sinyal_skor"), 3),
            "rsi": yuvarla((h or {}).get("rsi"), 1),
            "tarayici_disi": kod in (hala_eksik or []),
        })
    return {"satirlar": satirlar, "dolu": sum(1 for s in satirlar if s["veri_var"]),
            "not": "Endekse göre = günlük % − BIST100 günlük % (BIST100 bültende bulunur)."}


def retail_radar(tum):
    aday = [h for h in tum if (sayi(h.get("hacim_orani")) and h["hacim_orani"] >= RADAR_HACIM_ORANI)
            or (sayi(h.get("gunluk_yuzde")) and abs(h["gunluk_yuzde"]) >= RADAR_GUNLUK)]
    aday.sort(key=lambda h: -((h.get("hacim") or 0) * (h.get("kapanis") or 0)))
    return [{"kod": h["kod"], "gunluk_yuzde": yuvarla(h.get("gunluk_yuzde")),
             "hacim_orani": yuvarla(h.get("hacim_orani")),
             "hacim_mn_tl": round((h.get("hacim") or 0) * (h.get("kapanis") or 0) / 1e6, 1),
             "piyasa_degeri": h.get("piyasa_degeri"),
             "olasi_sermaye_islemi": h.get("olasi_sermaye_islemi") is True}
            for h in aday[:RADAR_ADET]]


def geri_alim_ozet(ga):
    if not ga:
        return {"var": False}
    sirketler = ga.get("sirketler") or {}
    satirlar = []
    for kod, s in sorted(sirketler.items()):
        if not (s.get("portfoyde") or s.get("bist30")):
            continue
        beyan = s.get("kumulatif_kaynak") == "sirket_beyani"
        satirlar.append({
            "kod": kod, "portfoyde": bool(s.get("portfoyde")), "bist30": bool(s.get("bist30")),
            "toplam_bildirim": s.get("toplam_bildirim"), "islem_bildirim_sayisi": s.get("islem_bildirim_sayisi"),
            "son_bildirim_tarih": s.get("son_bildirim_tarih"),
            "kumulatif_lot": s.get("kumulatif_lot") if beyan else None,
            "sermaye_orani_yuzde": s.get("sermaye_orani_yuzde") if beyan else None,
            "kumulatif_etiket": ("%s itibarıyla, şirket beyanı (KAP)" % s.get("detay_bildirim_tarih")) if beyan else None,
            "kumulatif_yazilmaz_neden": None if beyan else ("kaynak=%s (yalnız sirket_beyani yazılır)" % s.get("kumulatif_kaynak", "yok")),
        })
    return {"var": True, "uretim_zamani_utc": ga.get("uretim_zamani_utc"), "satirlar": satirlar}


def hazirla(klasor=VERI):
    lt = yukle(os.path.join(klasor, "latest.json"))
    tum = lt.get("tum_hisseler") or []
    harita = {h["kod"]: h for h in tum if h.get("kod")}
    bugun = dt.date.fromisoformat(lt["tarih"])
    try:
        ga = yukle(os.path.join(klasor, "geri_alim.json"))
    except Exception:
        ga = None
    return {
        "surum": SURUM,
        "uretim_zamani_utc": simdi(),
        "kaynak": {"tarih": lt.get("tarih"), "uretim_zamani_utc": lt.get("uretim_zamani_utc"),
                   "kapanis_verisi": kapanis_verisi_mi(lt), "hisse_sayisi": lt.get("hisse_sayisi"),
                   "aktif_mod": lt.get("aktif_mod"), "rsi_mevcut": lt.get("rsi_mevcut"),
                   "hala_eksik": lt.get("hala_eksik") or []},
        "emir_bozkurt": dict(emir_bozkurt(tum), yakin_adaylar=yakin_adaylar(lt, harita)),
        "sinyal_gecmisi": sinyal_gecmisi(tarihli_dosyalar(bugun, klasor), harita, lt["tarih"]),
        "bist30": bist30(harita, lt.get("hala_eksik")),
        "teknik_plan": {kod: teknik_plan(h) for kod, h in harita.items()},
        "retail_radar": retail_radar(tum),
        "geri_alim": geri_alim_ozet(ga),
        "hata": None,
    }


def yaz(cikti, yol=CIKTI):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=1)


def main():
    try:
        cikti = hazirla()
    except Exception:
        traceback.print_exc()
        cikti = {"surum": SURUM, "uretim_zamani_utc": simdi(),
                 "hata": traceback.format_exc().strip().splitlines()[-1]}
    yaz(cikti)
    eb = cikti.get("emir_bozkurt") or {}
    print("YAZILDI:", CIKTI, "| kaynak:", (cikti.get("kaynak") or {}).get("tarih"),
          "| sinyal:", eb.get("toplam_sinyal"), "| hata:", cikti.get("hata"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
    sys.exit(0)
