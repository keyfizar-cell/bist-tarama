#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_konuk.py  v1.0  (2026-11-07)
# Kendi kanali olmayan, baska YouTube kanallarina KONUK olan uzmanlarin son
# videolarini bulur ve Gemini ile transkript + ozet + bahsettigi hisseleri cikarir.
# Liste: konuk_takip.json   Cikti: data/youtube_konuk.json
# Kaynaklar (UCRETSIZ, tek Google API anahtari):
#   - YouTube Data API v3 search.list (100 birim/kisi/gun; gunluk 10.000 birim ucretsiz)
#     + videos.list (sure; 1 birim)
#   - Gemini API, YouTube URL (ucretsiz katman gunde 8 saat video; fps=0.1 ile)
# Secret: GOOGLE_API_KEY (Data API icin YOUTUBE_API_KEY varsa o kullanilir).
# IZOLASYON: her yolda JSON yazar, onceki islenmis videolari korur, exit(0).
import os
import re
import sys
import json
import datetime
import traceback
import urllib.parse

import youtube_tarama as yt

SURUM = "1.0"
LISTE_YOLU = "konuk_takip.json"
OUT_PATH = os.path.join("data", "youtube_konuk.json")
MIN_SURE_DK = 3        # shorts / kirpilmis klipler elenir
MAX_SURE_DK = 240      # 4 saatten uzun canli yayinlar elenir
SAKLA_GUN = 30
TRANSKRIPT_MAX = 40000

KONUK_ISTEM = (
    "Bu YouTube videosunda {ad} konuk olarak konusuyor olabilir. TURKCE yanit ver. "
    "(1) 'kisi_konusuyor': {ad} videoda gercekten konusuyorsa true, yalniz adi geciyorsa veya "
    "yoksa false. (2) 'transkript': videodaki konusmalari oldugu gibi yaziya dok; konusmacilari "
    "'{ad}:' ve 'Sunucu:' / 'Diger:' diye ayir; ozetleme, yorum ekleme, uydurma; hisse kodlarini ve "
    "rakamlari duydugun gibi yaz, emin olmadigini [?] ile isaretle. (3) 'ozet': YALNIZ {ad}'in "
    "soylediklerinin 5-10 maddelik ozeti. (4) 'bahsedilen_hisseler': {ad}'in adini andigi her hisse/"
    "varlik icin kod ve onun bu varlik hakkinda soyledigi (seviye, beklenti, risk) tek cumle. "
    "Yalniz videoda gecenleri yaz.")

KONUK_SEMA = {
    "type": "OBJECT",
    "properties": {
        "kisi_konusuyor": {"type": "BOOLEAN"},
        "transkript": {"type": "STRING"},
        "ozet": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bahsedilen_hisseler": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"kod": {"type": "STRING"}, "ne_dedi": {"type": "STRING"}},
            "required": ["kod", "ne_dedi"]}},
    },
    "required": ["kisi_konusuyor", "transkript", "ozet", "bahsedilen_hisseler"],
}


def tr_kucuk(s):
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def sade(s):
    t = tr_kucuk(s)
    for a, b in (("ı", "i"), ("ö", "o"), ("ü", "u"), ("ş", "s"), ("ç", "c"), ("ğ", "g")):
        t = t.replace(a, b)
    return t


def sure_dk(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return round(d * 1440 + h * 60 + mi + s / 60.0, 1)


def ara(kisi, anahtar, gun):
    sonra = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=gun)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = urllib.parse.urlencode({"part": "snippet", "q": kisi["sorgu"], "type": "video",
                                "order": "date", "publishedAfter": sonra, "maxResults": 15,
                                "regionCode": "TR", "relevanceLanguage": "tr", "key": anahtar})
    _, txt = yt.http_get(yt.YT_DATA_TABAN + "/search?" + q, headers={"Accept": "application/json"})
    adaylar = []
    esles = [sade(e) for e in kisi.get("eslesme") or [kisi["ad"]]]
    for it in json.loads(txt).get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        metin = sade(yt._unxml(sn.get("title", "")) + " " + yt._unxml(sn.get("description", "")))
        if not vid or not any(e in metin for e in esles):
            continue
        adaylar.append({"video_id": vid, "baslik": yt._unxml(sn.get("title", "")),
                        "kanal": sn.get("channelTitle", ""), "yayin_tarihi": sn.get("publishedAt", ""),
                        "url": "https://www.youtube.com/watch?v=" + vid,
                        "canli": sn.get("liveBroadcastContent") not in (None, "", "none")})
    if adaylar:
        q2 = urllib.parse.urlencode({"part": "contentDetails", "id": ",".join(a["video_id"] for a in adaylar),
                                     "key": anahtar})
        _, txt2 = yt.http_get(yt.YT_DATA_TABAN + "/videos?" + q2, headers={"Accept": "application/json"})
        sureler = {i["id"]: sure_dk((i.get("contentDetails") or {}).get("duration"))
                   for i in json.loads(txt2).get("items", [])}
        for a in adaylar:
            a["sure_dk"] = sureler.get(a["video_id"])
    return adaylar


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


def kisi_isle(kisi, eski, anahtar_data, ayar):
    kayit = {"ad": kisi["ad"], "not": kisi.get("not", ""), "hata": None,
             "son_basarili_utc": eski.get("son_basarili_utc"), "videolar": []}
    cache = {v["video_id"]: v for v in eski.get("videolar", []) if v.get("video_id")}
    try:
        adaylar = ara(kisi, anahtar_data, ayar["gun_penceresi"])
    except Exception as e:
        kayit["hata"] = "arama: " + yt._hata_metni(e)[:200]
        yt.log("%s arama hatasi: %s" % (kisi["ad"], kayit["hata"]))
        adaylar = []
    yeni_islenen = 0
    for a in sorted(adaylar, key=lambda x: x.get("yayin_tarihi") or "", reverse=True):
        if a["video_id"] in cache:
            continue
        sd = a.get("sure_dk")
        if a.get("canli") or (sd is not None and (sd < MIN_SURE_DK or sd > MAX_SURE_DK)):
            a["atlandi"] = "canli yayin" if a.get("canli") else "sure %.0f dk" % sd
            cache[a["video_id"]] = a
            continue
        if yeni_islenen >= ayar["calisma_basina_en_fazla_yeni_video"]:
            continue  # sonraki calismaya kalir (cache'e girmez)
        yeni_islenen += 1
        try:
            j, kaynak, bitis = yt.gemini_transkript(a["url"], istem=KONUK_ISTEM.format(ad=kisi["ad"]),
                                                    sema=KONUK_SEMA, fps=0.1)
            a.update({"kisi_konusuyor": bool(j.get("kisi_konusuyor")),
                      "transkript": (j.get("transkript") or "")[:TRANSKRIPT_MAX],
                      "transkript_kesildi": bitis == "MAX_TOKENS" or len(j.get("transkript") or "") > TRANSKRIPT_MAX,
                      "ozet": j.get("ozet") or [], "bahsedilen_hisseler": j.get("bahsedilen_hisseler") or [],
                      "transkript_kaynagi": kaynak, "islendi_utc": yt.now_utc()})
            kayit["son_basarili_utc"] = yt.now_utc()
            cache[a["video_id"]] = a
        except Exception as e:
            kayit["hata"] = "gemini: " + yt._hata_metni(e)[:200]
            yt.log("%s / %s Gemini hatasi: %s" % (kisi["ad"], a["video_id"], kayit["hata"]))
            if "429" in kayit["hata"]:
                break
    sinir = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=SAKLA_GUN)).isoformat()
    kayit["videolar"] = sorted([v for v in cache.values() if (v.get("yayin_tarihi") or "") >= sinir[:19]],
                               key=lambda x: x.get("yayin_tarihi") or "", reverse=True)[:15]
    kayit["son_arama_utc"] = yt.now_utc()
    kayit["aday_sayisi"] = len(adaylar)
    return kayit


def main():
    eski = onceki()
    cikti = {"kisiler": {}, "hata": None}
    try:
        with open(LISTE_YOLU, encoding="utf-8") as f:
            liste = json.load(f)
    except Exception as e:
        cikti["hata"] = "konuk_takip.json okunamadi: %s" % e
        cikti["kisiler"] = eski.get("kisiler", {})
        yaz(cikti)
        return
    ayar = {"gun_penceresi": int(liste.get("gun_penceresi", 7)),
            "calisma_basina_en_fazla_yeni_video": int(liste.get("calisma_basina_en_fazla_yeni_video", 2))}
    anahtar_data = os.environ.get("YOUTUBE_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    for kisi in liste.get("kisiler", []):
        e = (eski.get("kisiler") or {}).get(kisi["ad"], {})
        if not anahtar_data:
            e = dict(e, hata="GOOGLE_API_KEY/YOUTUBE_API_KEY yok")
            cikti["kisiler"][kisi["ad"]] = e
            continue
        cikti["kisiler"][kisi["ad"]] = kisi_isle(kisi, e, anahtar_data, ayar)
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
