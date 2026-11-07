#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_kanallar.py  v1.0  (2026-11-07)
# Ek YouTube KANALLARININ (Emir Bozkurt disinda) son videolarini bulur ve Gemini ile
# transkript + ozet + bahsedilen hisseler + konusmacinin kendi dile getirdigi riskleri cikarir.
# Liste: kanal_takip.json   Cikti: data/youtube_kanallar.json
# Kaynaklar (UCRETSIZ):
#   - Kanal kimligi: YouTube Data API channels.list?forHandle (1 birim; sonuc JSON'da saklanir)
#   - Video listesi: kanal RSS'i; olmazsa Data API playlistItems (UU...) (1 birim)
#   - Sure/canli: Data API videos.list (1 birim) -> shorts ve canli yayinlar elenir
#   - Gemini API, YouTube URL (fps=0.1)
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

SURUM = "1.0"
LISTE_YOLU = "kanal_takip.json"
OUT_PATH = os.path.join("data", "youtube_kanallar.json")
MIN_SURE_DK = 3
MAX_SURE_DK = 240
SAKLA_GUN = 30
TRANSKRIPT_MAX = 40000
RSS_TABAN = "https://www.youtube.com/feeds/videos.xml?channel_id="

KANAL_ISTEM = (
    "Bu YouTube videosu '{kanal}' kanalina ait. TURKCE yanit ver. "
    "(1) 'transkript': videodaki konusmalari oldugu gibi yaziya dok; birden fazla konusmaci varsa "
    "ayir; ozetleme, yorum ekleme, uydurma; hisse kodlarini ve rakamlari duydugun gibi yaz, emin "
    "olmadigini [?] ile isaretle. (2) 'ana_mesaj': videonun ana tezi, tek cumle. (3) 'ozet': 5-10 "
    "maddelik ozet, yalniz videoda soylenenler. (4) 'bahsedilen_hisseler': adi gecen her hisse/fon/"
    "varlik icin kod (BIST kodu biliniyorsa o, yoksa varligin adi) ve videoda onun hakkinda "
    "soylenen (seviye, beklenti, vade) tek cumle. (5) 'konusmacinin_riskleri': konusmacinin KENDISININ "
    "dile getirdigi riskler/cekinceler; hic yoksa bos liste. (6) 'icerik_turu': 'piyasa_yorumu', "
    "'egitim', 'kisisel_finans', 'reklam_sponsorlu' veya 'diger'. Yalniz videoda gecenleri yaz.")

KANAL_SEMA = {
    "type": "OBJECT",
    "properties": {
        "transkript": {"type": "STRING"},
        "ana_mesaj": {"type": "STRING"},
        "ozet": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bahsedilen_hisseler": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"kod": {"type": "STRING"}, "ne_dedi": {"type": "STRING"}},
            "required": ["kod", "ne_dedi"]}},
        "konusmacinin_riskleri": {"type": "ARRAY", "items": {"type": "STRING"}},
        "icerik_turu": {"type": "STRING"},
    },
    "required": ["transkript", "ana_mesaj", "ozet", "bahsedilen_hisseler",
                 "konusmacinin_riskleri", "icerik_turu"],
}


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
    v = yt.rss_dene(RSS_TABAN + channel_id, [0, 10])
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
    d = data_get("videos", {"part": "contentDetails,snippet",
                            "id": ",".join(a["video_id"] for a in adaylar)}, anahtar)
    bilgi = {i["id"]: i for i in d.get("items", [])}
    for a in adaylar:
        i = bilgi.get(a["video_id"]) or {}
        a["sure_dk"] = sure_dk((i.get("contentDetails") or {}).get("duration"))
        a["canli"] = (i.get("snippet") or {}).get("liveBroadcastContent") not in (None, "", "none")


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
    d["denemeler"] = yt.GUNLUK[-60:]
    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("YAZILDI:", OUT_PATH)


def kanal_isle(kanal, eski, anahtar_data, ayar):
    kayit = {"ad": kanal["ad"], "handle": kanal.get("handle", ""), "not": kanal.get("not", ""),
             "channel_id": eski.get("channel_id"), "kanal_adi": eski.get("kanal_adi"), "hata": None,
             "son_basarili_utc": eski.get("son_basarili_utc"), "videolar": []}
    cache = {v["video_id"]: v for v in eski.get("videolar", []) if v.get("video_id")}
    adaylar = []
    try:
        cid, kadi, kkaynak = kanal_kimligi(kanal, eski, anahtar_data)
        kayit.update(channel_id=cid, kanal_adi=kadi, kimlik_kaynagi=kkaynak)
        liste, kaynak = videolar(cid, anahtar_data)
        kayit["liste_kaynagi"] = kaynak
        sinir = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(days=ayar["gun_penceresi"])).isoformat()[:19]
        adaylar = [a for a in liste if (a.get("yayin_tarihi") or "")[:19] >= sinir
                   and a["video_id"] not in cache]
        sure_ekle(adaylar, anahtar_data)
    except Exception as e:
        kayit["hata"] = "liste: " + yt._hata_metni(e)[:200]
        yt.log("%s liste hatasi: %s" % (kanal["ad"], kayit["hata"]))
    yeni = 0
    for a in sorted(adaylar, key=lambda x: x.get("yayin_tarihi") or "", reverse=True):
        a.pop("aciklama", None)
        sd = a.get("sure_dk")
        if a.get("canli") or (sd is not None and (sd < MIN_SURE_DK or sd > MAX_SURE_DK)):
            a["atlandi"] = "canli yayin" if a.get("canli") else "sure %.0f dk" % sd
            cache[a["video_id"]] = a
            continue
        if yeni >= ayar["calisma_basina_en_fazla_yeni_video"]:
            continue  # sonraki calismaya kalir
        yeni += 1
        try:
            j, kaynak, bitis = yt.gemini_transkript(
                a["url"], istem=KANAL_ISTEM.format(kanal=kayit["kanal_adi"] or kanal["ad"]),
                sema=KANAL_SEMA, fps=0.1)
            tr = j.get("transkript") or ""
            a.update({"transkript": tr[:TRANSKRIPT_MAX],
                      "transkript_kesildi": bitis == "MAX_TOKENS" or len(tr) > TRANSKRIPT_MAX,
                      "ana_mesaj": j.get("ana_mesaj") or "", "ozet": j.get("ozet") or [],
                      "bahsedilen_hisseler": j.get("bahsedilen_hisseler") or [],
                      "konusmacinin_riskleri": j.get("konusmacinin_riskleri") or [],
                      "icerik_turu": j.get("icerik_turu") or "", "transkript_kaynagi": kaynak,
                      "islendi_utc": yt.now_utc()})
            kayit["son_basarili_utc"] = yt.now_utc()
            cache[a["video_id"]] = a
        except Exception as e:
            kayit["hata"] = "gemini: " + yt._hata_metni(e)[:200]
            yt.log("%s / %s Gemini hatasi: %s" % (kanal["ad"], a["video_id"], kayit["hata"]))
            if "429" in kayit["hata"]:
                break
    sinir30 = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=SAKLA_GUN)).isoformat()
    kayit["videolar"] = sorted([v for v in cache.values() if (v.get("yayin_tarihi") or "")[:19] >= sinir30[:19]],
                               key=lambda x: x.get("yayin_tarihi") or "", reverse=True)[:15]
    kayit["son_kontrol_utc"] = yt.now_utc()
    kayit["aday_sayisi"] = len(adaylar)
    return kayit


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
    ayar = {"gun_penceresi": int(liste.get("gun_penceresi", 7)),
            "calisma_basina_en_fazla_yeni_video": int(liste.get("calisma_basina_en_fazla_yeni_video", 2))}
    anahtar_data = os.environ.get("YOUTUBE_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    for kanal in liste.get("kanallar", []):
        e = (eski.get("kanallar") or {}).get(kanal["ad"], {})
        cikti["kanallar"][kanal["ad"]] = kanal_isle(kanal, e, anahtar_data, ayar)
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
