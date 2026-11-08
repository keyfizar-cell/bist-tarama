#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_kanallar.py  v1.1  (2026-11-08)
# Ek YouTube KANALLARININ (Emir Bozkurt disinda) son videolarini bulur ve Gemini ile
# ozet + ana mesaj + bahsedilen hisseler + konusmacinin kendi dile getirdigi riskleri cikarir.
# Liste: kanal_takip.json   Cikti: data/youtube_kanallar.json
# Kaynaklar (UCRETSIZ):
#   - Kanal kimligi: YouTube Data API channels.list?forHandle (1 birim; sonuc JSON'da saklanir)
#   - Video listesi: kanal RSS'i; olmazsa Data API playlistItems (UU...) (1 birim)
#   - Sure/canli: Data API videos.list (1 birim) -> shorts ve canli yayinlar elenir
#   - Gemini API, YouTube URL (fps=0.1)
# BUTCE (v1.1): Gemini ucretsiz katmani (~8 saat video/gun) icin calisma basina TOPLAM en fazla
#   `calisma_basina_toplam_video` video islenir; adaylar kanallar arasi sirayla (her turda kanal basina 1,
#   en yeni once) secilir. Islenemeyenler `bekleyenler` listesinde baslik+link ile durur, sonraki calismada
#   islenir. Kanal videolarinda tam transkript ISTENMEZ (yalniz ozet alanlari) -> daha hizli, kotaya az yuk.
# GUNLUK YUKLEYEN (kullanici karari 08.11.2026): son 7 gunde >= `gunluk_yukleyen_esigi` (varsayilan 5) uzun
#   video (>=3 dk, canli degil) yukleyen kanal 'liste_disi' isaretlenir, islenmez, bultene girmez.
#   kanal_takip.json'daki 'liste_disi' dizisindeki kanallar hic taranmaz. Kanala "zorla_takip": true verilirse muaf.
# Secret: GOOGLE_API_KEY (Gemini), YOUTUBE_API_KEY (Data API; yoksa GOOGLE_API_KEY denenir).
# IZOLASYON: her yolda JSON yazar, onceki islenmis videolari korur, exit(0).
import os
import sys
import json
import datetime
import traceback
import urllib.parse

import youtube_tarama as yt
from youtube_konuk import sure_dk

SURUM = "1.1"
LISTE_YOLU = "kanal_takip.json"
OUT_PATH = os.path.join("data", "youtube_kanallar.json")
MIN_SURE_DK = 3
MAX_SURE_DK = 240
SAKLA_GUN = 30
RSS_TABAN = "https://www.youtube.com/feeds/videos.xml?channel_id="

KANAL_ISTEM = (
    "Bu YouTube videosu '{kanal}' kanalina ait. TURKCE yanit ver. Tam transkript YAZMA; hisse kodlarini ve "
    "rakamlari duydugun gibi yaz, emin olmadigini [?] ile isaretle. "
    "(1) 'ana_mesaj': videonun ana tezi, tek cumle. (2) 'ozet': 5-8 maddelik ozet, yalniz videoda "
    "soylenenler. (3) 'bahsedilen_hisseler': adi gecen her hisse/fon/varlik icin kod (BIST kodu biliniyorsa "
    "o, yoksa varligin adi) ve videoda onun hakkinda soylenen (seviye, beklenti, vade) tek cumle. "
    "(4) 'konusmacinin_riskleri': konusmacinin KENDISININ dile getirdigi riskler/cekinceler; yoksa bos liste. "
    "(5) 'icerik_turu': 'piyasa_yorumu', 'egitim', 'kisisel_finans', 'reklam_sponsorlu' veya 'diger'. "
    "Yalniz videoda gecenleri yaz, uydurma.")

KANAL_SEMA = {
    "type": "OBJECT",
    "properties": {
        "ana_mesaj": {"type": "STRING"},
        "ozet": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bahsedilen_hisseler": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"kod": {"type": "STRING"}, "ne_dedi": {"type": "STRING"}},
            "required": ["kod", "ne_dedi"]}},
        "konusmacinin_riskleri": {"type": "ARRAY", "items": {"type": "STRING"}},
        "icerik_turu": {"type": "STRING"},
    },
    "required": ["ana_mesaj", "ozet", "bahsedilen_hisseler", "konusmacinin_riskleri", "icerik_turu"],
}


def simdi():
    return datetime.datetime.now(datetime.timezone.utc)


def data_get(yol, params, anahtar):
    q = urllib.parse.urlencode(dict(params, key=anahtar))
    _, txt = yt.http_get(yt.YT_DATA_TABAN + "/" + yol + "?" + q, headers={"Accept": "application/json"})
    return json.loads(txt)


def kanal_kimligi(kanal, eski, anahtar):
    """(channel_id, kanal_adi, kaynak). Sirasi: listede sabit -> onceki JSON -> Data API forHandle."""
    if kanal.get("channel_id"):
        return kanal["channel_id"], eski.get("kanal_adi") or kanal.get("ad"), "liste"
    if eski.get("channel_id"):
        return eski["channel_id"], eski.get("kanal_adi") or kanal.get("ad"), "onbellek"
    if not anahtar:
        raise RuntimeError("kanal kimligi icin YOUTUBE_API_KEY yok")
    d = data_get("channels", {"part": "id,snippet", "forHandle": "@" + kanal["handle"].lstrip("@")}, anahtar)
    items = d.get("items") or []
    if not items:
        raise RuntimeError("handle bulunamadi: @%s" % kanal["handle"].lstrip("@"))
    return items[0]["id"], (items[0].get("snippet") or {}).get("title") or kanal.get("ad"), "data_api"


def videolar(channel_id, anahtar):
    v = yt.rss_dene(RSS_TABAN + channel_id, [0, 5])
    if v:
        return v, "rss"
    if not anahtar:
        return [], None
    d = data_get("playlistItems", {"part": "snippet,contentDetails", "playlistId": "UU" + channel_id[2:],
                                   "maxResults": 10}, anahtar)
    out = []
    for it in d.get("items", []):
        sn = it.get("snippet") or {}
        cd = it.get("contentDetails") or {}
        vid = cd.get("videoId") or (sn.get("resourceId") or {}).get("videoId")
        if vid:
            out.append({"video_id": vid, "baslik": sn.get("title", ""),
                        "yayin_tarihi": cd.get("videoPublishedAt") or sn.get("publishedAt", ""),
                        "url": "https://www.youtube.com/watch?v=" + vid})
    return out, "youtube_data_api"


def sure_ekle(adaylar, anahtar):
    if not adaylar or not anahtar:
        return
    for i in range(0, len(adaylar), 50):
        parca = adaylar[i:i + 50]
        d = data_get("videos", {"part": "contentDetails,snippet",
                                "id": ",".join(a["video_id"] for a in parca)}, anahtar)
        bilgi = {x["id"]: x for x in d.get("items", [])}
        for a in parca:
            b = bilgi.get(a["video_id"]) or {}
            a["sure_dk"] = sure_dk((b.get("contentDetails") or {}).get("duration"))
            a["canli"] = (b.get("snippet") or {}).get("liveBroadcastContent") not in (None, "", "none")


def onceki():
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def yaz(d):
    d["surum"] = SURUM
    d["uretim_zamani_utc"] = yt.now_utc()
    d["denemeler"] = yt.GUNLUK[-80:]
    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("YAZILDI:", OUT_PATH)


# ── 1. ASAMA: her kanal icin adaylari topla (Gemini yok) ──
def kanal_hazirla(kanal, eski, anahtar_data, ayar):
    kayit = {"ad": kanal["ad"], "handle": kanal.get("handle", ""), "not": kanal.get("not", ""),
             "channel_id": eski.get("channel_id"), "kanal_adi": eski.get("kanal_adi"), "hata": None,
             "son_basarili_utc": eski.get("son_basarili_utc"), "videolar": [], "bekleyenler": []}
    cache = {v["video_id"]: v for v in eski.get("videolar", []) if v.get("video_id")}
    adaylar = []
    try:
        cid, kadi, kkaynak = kanal_kimligi(kanal, eski, anahtar_data)
        kayit.update(channel_id=cid, kanal_adi=kadi, kimlik_kaynagi=kkaynak)
        liste, kaynak = videolar(cid, anahtar_data)
        kayit["liste_kaynagi"] = kaynak
        sinir = (simdi() - datetime.timedelta(days=ayar["gun_penceresi"])).isoformat()[:19]
        sinir7 = (simdi() - datetime.timedelta(days=7)).isoformat()[:19]
        kayit["_son7"] = [dict(a) for a in liste if (a.get("yayin_tarihi") or "")[:19] >= sinir7]
        adaylar = [dict(a, kanal_adi=kadi) for a in liste
                   if (a.get("yayin_tarihi") or "")[:19] >= sinir and a["video_id"] not in cache]
        for a in adaylar:
            a.pop("aciklama", None)
    except Exception as e:
        kayit["hata"] = "liste: " + yt._hata_metni(e)[:200]
        yt.log("%s liste hatasi: %s" % (kanal["ad"], kayit["hata"]))
    kayit["aday_sayisi"] = len(adaylar)
    return kayit, cache, adaylar


def gunluk_mu(kayit, esik, sureler):
    """Son 7 gundeki uzun video sayisi esigi gecerse True. Sure bilinmeyen video uzun sayilmaz."""
    uzun = [a for a in kayit.pop("_son7", [])
            if (sureler.get(a["video_id"]) or {}).get("sure_dk") is not None
            and sureler[a["video_id"]]["sure_dk"] >= MIN_SURE_DK and not sureler[a["video_id"]].get("canli")]
    kayit["son7_uzun_video"] = len(uzun)
    return len(uzun) >= esik


def ele(adaylar, cache):
    """Shorts / canli / cok uzun videolari cache'e 'atlandi' ile yazar; islenebilir olanlari dondurur."""
    kalan = []
    for a in adaylar:
        sd = a.get("sure_dk")
        if a.get("canli") or (sd is not None and (sd < MIN_SURE_DK or sd > MAX_SURE_DK)):
            a["atlandi"] = "canli yayin" if a.get("canli") else "sure %.0f dk" % sd
            cache[a["video_id"]] = a
        else:
            kalan.append(a)
    return sorted(kalan, key=lambda x: x.get("yayin_tarihi") or "", reverse=True)


def sirala(kuyruklar, kanal_basina, toplam):
    """Kanallar arasi sirali secim: her turda her kanaldan en yeni 1 video; turlar icinde en yeni once."""
    secim, tur = [], 0
    while len(secim) < toplam and tur < kanal_basina:
        tur_listesi = [(ad, q[tur]) for ad, q in kuyruklar.items() if len(q) > tur]
        if not tur_listesi:
            break
        tur_listesi.sort(key=lambda x: x[1].get("yayin_tarihi") or "", reverse=True)
        secim.extend(tur_listesi[:toplam - len(secim)])
        tur += 1
    return secim


def isle(a, kanal_adi):
    j, kaynak, _ = yt.gemini_transkript(a["url"], istem=KANAL_ISTEM.format(kanal=kanal_adi), sema=KANAL_SEMA,
                                        fps=0.1)
    a.update({"ana_mesaj": j.get("ana_mesaj") or "", "ozet": j.get("ozet") or [],
              "bahsedilen_hisseler": j.get("bahsedilen_hisseler") or [],
              "konusmacinin_riskleri": j.get("konusmacinin_riskleri") or [],
              "icerik_turu": j.get("icerik_turu") or "", "transkript_kaynagi": kaynak,
              "islendi_utc": yt.now_utc()})
    return a


def main():
    eski = onceki()
    cikti = {"kanallar": {}, "hata": None}
    try:
        with open(LISTE_YOLU, encoding="utf-8") as f:
            liste = json.load(f)
    except Exception as e:
        cikti["hata"] = "kanal_takip.json okunamadi: %s" % e
        cikti["kanallar"] = eski.get("kanallar", {})
        yaz(cikti)
        return
    ayar = {"gun_penceresi": int(liste.get("gun_penceresi", 4)),
            "kanal_basina": int(liste.get("calisma_basina_en_fazla_yeni_video", 2)),
            "toplam": int(liste.get("calisma_basina_toplam_video", 10)),
            "gunluk_esik": int(liste.get("gunluk_yukleyen_esigi", 5))}
    anahtar_data = os.environ.get("YOUTUBE_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    kayitlar, cacheler, tum_adaylar = {}, {}, []
    for kanal in liste.get("kanallar", []):
        e = (eski.get("kanallar") or {}).get(kanal["ad"], {})
        kayitlar[kanal["ad"]], cacheler[kanal["ad"]], ad_ = kanal_hazirla(kanal, e, anahtar_data, ayar)
        for a in ad_:
            a["_kanal"] = kanal["ad"]
        tum_adaylar.extend(ad_)
    son7 = {a["video_id"]: a for k in kayitlar.values() for a in k.get("_son7", [])}
    for a in tum_adaylar:
        son7.setdefault(a["video_id"], a)
    try:
        sure_ekle(list(son7.values()), anahtar_data)
    except Exception as e:
        yt.log("sure bilgisi alinamadi: %s" % yt._hata_metni(e))
    for a in tum_adaylar:
        if a["video_id"] in son7:
            a["sure_dk"], a["canli"] = son7[a["video_id"]].get("sure_dk"), son7[a["video_id"]].get("canli")
    zorla = {k["ad"] for k in liste.get("kanallar", []) if k.get("zorla_takip")}
    kuyruklar = {}
    for ad, kayit in kayitlar.items():
        if gunluk_mu(kayit, ayar["gunluk_esik"], son7) and ad not in zorla:
            kayit["liste_disi"] = "her gun video yukluyor (son 7 gunde %d uzun video)" % kayit["son7_uzun_video"]
            kuyruklar[ad] = []
            continue
        kuyruklar[ad] = ele([a for a in tum_adaylar if a["_kanal"] == ad], cacheler[ad])
    secim = sirala(kuyruklar, ayar["kanal_basina"], ayar["toplam"])
    secilen_idler = set()
    kota_bitti = False
    for ad, a in secim:
        if kota_bitti:
            break
        secilen_idler.add(a["video_id"])
        try:
            isle(a, kayitlar[ad]["kanal_adi"] or ad)
            kayitlar[ad]["son_basarili_utc"] = yt.now_utc()
            cacheler[ad][a["video_id"]] = a
        except Exception as e:
            secilen_idler.discard(a["video_id"])
            kayitlar[ad]["hata"] = "gemini: " + yt._hata_metni(e)[:200]
            yt.log("%s / %s Gemini hatasi: %s" % (ad, a["video_id"], kayitlar[ad]["hata"]))
            kota_bitti = "429" in kayitlar[ad]["hata"]
    sinir30 = (simdi() - datetime.timedelta(days=SAKLA_GUN)).isoformat()[:19]
    for ad, kayit in kayitlar.items():
        kayit["videolar"] = sorted(
            [{k: v for k, v in x.items() if k != "_kanal"} for x in cacheler[ad].values()
             if (x.get("yayin_tarihi") or "")[:19] >= sinir30],
            key=lambda x: x.get("yayin_tarihi") or "", reverse=True)[:15]
        kayit["bekleyenler"] = [{k: a.get(k) for k in ("video_id", "baslik", "url", "yayin_tarihi", "sure_dk")}
                                for a in kuyruklar[ad] if a["video_id"] not in cacheler[ad]]
        kayit["son_kontrol_utc"] = yt.now_utc()
        cikti["kanallar"][ad] = kayit
    cikti["liste_disi"] = [{"ad": k.get("ad"), "handle": k.get("handle"), "neden": k.get("neden", "")}
                           for k in liste.get("liste_disi", [])]
    cikti["butce"] = {"toplam_sinir": ayar["toplam"], "islenen": len(secilen_idler),
                      "bekleyen": sum(len(k["bekleyenler"]) for k in kayitlar.values()), "kota_bitti": kota_bitti}
    yaz(cikti)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            d = onceki()
            d["hata"] = "beklenmeyen hata: " + yt.anahtar_gizle(traceback.format_exc().strip().splitlines()[-1])
            yaz(d)
        except Exception:
            pass
    sys.exit(0)
