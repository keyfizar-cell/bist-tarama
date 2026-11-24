#!/usr/bin/env python3
"""Sağlık Denetimi (Actions) — gorevler/saglik_nobeti.md'nin (A) tazelik, (B) kalite, (D) Actions sonucu ve
(E) yan dosya maddelerinin kodu (24.11.2026; kullanım limitini azaltmak için Claude görevinden taşındı).

Repodaki data/ dosyalarını okur; sorun varsa GitHub adım özetine yazar ve exit(1) verir → iş kırmızı olur
ve GitHub sahibine e-posta gider. Sorun yoksa sessizce exit(0). Veri dosyası YAZMAZ (bilinçli istisna:
diğer betiklerin "her durumda exit(0)" kuralı veri üreticiler içindir; bu bir alarm).
(C) "bülten gitti mi" Gmail ister → Claude'daki kısa Sağlık Nöbeti görevinde kaldı.

  python araclar/saglik.py [--bugun 2026-11-24]
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
VERI = KOK / "data"
TATIL = {"2026-10-29", "2027-01-01", "2027-03-10", "2027-03-11", "2027-03-12", "2027-04-23",
         "2027-05-17", "2027-05-18", "2027-05-19", "2027-07-15", "2027-08-30", "2027-10-29"}


def is_gunu(g):
    return g.weekday() < 5 and g.isoformat() not in TATIL


def is_gunu_farki(eski, bugun):
    """eski'den bugüne kaç iş günü geçti (eski hariç, bugün dahil)."""
    n, g = 0, eski
    while g < bugun:
        g += dt.timedelta(days=1)
        n += is_gunu(g)
    return n


def oku(ad):
    p = VERI / f"{ad}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return "BOZUK"


def tarih(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def denetle(bugun):
    s = []
    lt = oku("latest")
    if lt in (None, "BOZUK"):
        return [f"ERİŞİM: data/latest.json {'yok' if lt is None else 'bozuk'}"]
    # (A) tazelik: son GEÇERLİ kapanış verisi (≥15:15 UTC üretilmiş)
    td = oku(bugun.isoformat())
    d = td if isinstance(td, dict) else lt
    t, u = tarih(d.get("tarih")), str(d.get("uretim_zamani_utc", ""))
    if t == bugun and u[11:16] < "15:15":
        t = bugun - dt.timedelta(days=1)          # gün içi elle çalışma: bugün için veri yok say
    fark = is_gunu_farki(t, bugun) if t else 99
    if fark >= 2:
        s.append(f"KRONİK: BIST taraması {fark} iş günüdür üretilmedi (son veri: {t})")
    # (B) kalite
    if t and is_gunu_farki(t, bugun) <= 1:
        k = []
        if d.get("aktif_mod") != "oturumlu" or d.get("oturum_cerezi_tanimli") is False:
            k.append(f"aktif_mod={d.get('aktif_mod')} (TV_SESSIONID yenilenmeli olabilir)")
        if d.get("rsi_mevcut") is False:
            k.append("rsi_mevcut=false")
        if (d.get("hisse_sayisi") or 0) < 550:
            k.append(f"hisse_sayisi={d.get('hisse_sayisi')}")
        if d.get("alan_seti") not in (None, "tam"):
            k.append(f"alan_seti={d.get('alan_seti')}")
        if k:
            s.append("KALİTE: " + ", ".join(k))
    # (D) Actions sonucu
    st = oku("status")
    if isinstance(st, dict) and st.get("sonuc") != "success":
        z = tarih(st.get("zaman_utc"))
        if z and (bugun - z).days <= 1:
            s.append(f"ACTIONS HATASI: {st.get('sonuc')} {st.get('zaman_utc')} {st.get('url')}")
    # (E) yan dosyalar: (ad, zaman alanı, yoksa arıza mı)
    for ad, alan, zorunlu in [("kap", "uretim_zamani_utc", True), ("geri_alim", "uretim_zamani_utc", True),
                              ("fon", "uretim_zamani_utc", True), ("bulten_girdi", "uretim_zamani_utc", True),
                              ("youtube_emir", "uretim_zamani_utc", False), ("youtube_konuk", "uretim_zamani_utc", False),
                              ("youtube_kanallar", "uretim_zamani_utc", False), ("sosyal_nabiz", "uretim_zamani_utc", False),
                              ("adil_deger", "uretim_zamani_utc", False), ("faktor_skor", "tarih", False),
                              ("abd", "uretim_zamani_utc", False)]:
        v = oku(ad)
        if v is None:
            if zorunlu:
                s.append(f"YAN DOSYA YOK: {ad}.json")
            continue
        if v == "BOZUK":
            s.append(f"YAN DOSYA BOZUK: {ad}.json")
            continue
        z = tarih(v.get(alan))
        if z and is_gunu_farki(z, bugun) >= 2:
            s.append(f"YAN DOSYA BAYAT: {ad}.json (son: {v.get(alan)})")
        if v.get("hata") and ad in ("adil_deger", "faktor_skor", "bulten_girdi"):
            s.append(f"YAN DOSYA HATALI: {ad}.json — {str(v.get('hata'))[:80]}")
    fon = oku("fon")
    if isinstance(fon, dict) and (fon.get("hata_sayisi") or 0) > (fon.get("basari_sayisi") or 0):
        s.append(f"YAN DOSYA HATALI: fon.json ({fon.get('hata_sayisi')} hata / {fon.get('basari_sayisi')} başarı)")
    ye = oku("youtube_emir")
    if isinstance(ye, dict) and ye.get("son_basarili_utc"):
        z = tarih(ye["son_basarili_utc"])
        if z and is_gunu_farki(z, bugun) >= 2:
            s.append(f"YOUTUBE TRANSKRİPT YOK: son başarılı {ye['son_basarili_utc']}; hata: {str(ye.get('hata'))[:120]}")
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bugun")
    a = ap.parse_args()
    bugun = dt.date.fromisoformat(a.bugun) if a.bugun else dt.datetime.now(dt.timezone.utc).date()
    if not is_gunu(bugun):
        print("Hafta sonu / tatil: denetim yok.")
        return 0
    sorun = denetle(bugun)
    ozet = os.environ.get("GITHUB_STEP_SUMMARY")
    metin = "## Sağlık Denetimi " + bugun.isoformat() + "\n" + ("\n".join(f"- ❌ {x}" for x in sorun) if sorun else "- ✅ Sorun yok")
    print(metin)
    if ozet:
        with open(ozet, "a", encoding="utf-8") as f:
            f.write(metin + "\n")
    return 1 if sorun else 0


if __name__ == "__main__":
    sys.exit(main())
