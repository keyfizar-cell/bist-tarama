#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_arsiv.py  v1.0  (2026-11-14)
# KOC OKUMA PROGRAMI — video arsivi (Alpay karari 14.11.2026: "Koc rahmetli Yasar Erdinc'in yazilarini ve
# video iceriklerini okuyup izleyip ogrensin"). Yeni video beklenmeyen (arsiv) kisilerin YouTube'daki
# eski videolarini tarihten bagimsiz bulur ve her calismada en fazla N tanesini Gemini ile isler:
# transkript YERINE yatirim ILKELERI/YONTEMLERI + ozet + gecen hisseler (dosya boyutu ve kota korunur).
# Liste: arsiv_takip.json   Cikti: data/youtube_arsiv.json (islenenler kalici birikir).
# Aday listesi Data API search.list ile (100 birim) en fazla 7 gunde bir yenilenir.
# IZOLASYON: her yolda JSON yazar, onceki islenmisleri korur, exit(0).
import datetime
import json
import os
import sys
import traceback
import urllib.parse

import youtube_konuk as yk
import youtube_tarama as yt

SURUM = "1.0"
LISTE_YOLU = "arsiv_takip.json"
OUT_PATH = os.path.join("data", "youtube_arsiv.json")
ADAY_YENILE_GUN = 7
MIN_SURE_DK = 5
MAX_SURE_DK = 240

ISTEM = (
    "Bu Turkce YouTube videosunda {ad} konusuyor (konuk, ders, seminer veya roportaj). Videoyu izle ve "
    "TURKCE yaz: (1) 'ilkeler': {ad}'in anlattigi yatirim ILKELERI ve YONTEMLERI (gorus/tahmin degil; "
    "or. 'satis, net kar ve ozkaynagi her donem artan sirkete uzun vadeli ortak ol', 'temettu verimini "
    "mevduatla kiyasla'); her biri tek cumle, en fazla 12 madde; videoda soylenmeyeni yazma. "
    "(2) 'ozet': videonun ana fikirleri 3-6 madde. (3) 'bahsedilen_hisseler': adi gecen hisse/varlik ve "
    "soylenen (tek cumle). (4) 'konusmaci_dogrulandi': videoda gercekten {ad} konusuyor mu (true/false). "
    "(5) 'yaklasik_tarih': videoda gecen ya da anlasilan yil (bilinmiyorsa bos).")

SEMA = {
    "type": "OBJECT",
    "properties": {
        "ilkeler": {"type": "ARRAY", "items": {"type": "STRING"}},
        "ozet": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bahsedilen_hisseler": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"kod": {"type": "STRING"}, "ne_dedi": {"type": "STRING"}},
            "required": ["kod", "ne_dedi"]}},
        "konusmaci_dogrulandi": {"type": "BOOLEAN"},
        "yaklasik_tarih": {"type": "STRING"},
    },
    "required": ["ilkeler", "ozet", "bahsedilen_hisseler", "konusmaci_dogrulandi"],
}


def simdi():
    return datetime.datetime.now(datetime.timezone.utc)


def liste():
    with open(LISTE_YOLU, encoding="utf-8") as f:
        return json.load(f)


def onceki():
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"kisiler": {}}


def ara(kisi, anahtar):
    """Tarih sinirsiz, ilgiye gore arama (en fazla 50) + sure; eslesme baslik/aciklamada aranir."""
    adaylar, sayfa = [], None
    esles = [yk.sade(e) for e in kisi.get("eslesme") or [kisi["ad"]]]
    for _ in range(2):
        p = {"part": "snippet", "q": kisi["sorgu"], "type": "video", "order": "relevance",
             "maxResults": 25, "regionCode": "TR", "relevanceLanguage": "tr", "key": anahtar}
        if sayfa:
            p["pageToken"] = sayfa
        _, txt = yt.http_get(yt.YT_DATA_TABAN + "/search?" + urllib.parse.urlencode(p),
                             headers={"Accept": "application/json"})
        d = json.loads(txt)
        for it in d.get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            sn = it.get("snippet") or {}
            metin = yk.sade(yt._unxml(sn.get("title", "")) + " " + yt._unxml(sn.get("description", "")))
            if vid and any(e in metin for e in esles):
                adaylar.append({"video_id": vid, "baslik": yt._unxml(sn.get("title", "")),
                                "kanal": sn.get("channelTitle", ""), "yayin_tarihi": sn.get("publishedAt", ""),
                                "url": "https://www.youtube.com/watch?v=" + vid})
        sayfa = d.get("nextPageToken")
        if not sayfa:
            break
    if adaylar:
        for i in range(0, len(adaylar), 50):
            parca = adaylar[i:i + 50]
            q2 = urllib.parse.urlencode({"part": "contentDetails", "id": ",".join(a["video_id"] for a in parca),
                                         "key": anahtar})
            _, txt2 = yt.http_get(yt.YT_DATA_TABAN + "/videos?" + q2, headers={"Accept": "application/json"})
            sureler = {x["id"]: yk.sure_dk((x.get("contentDetails") or {}).get("duration"))
                       for x in json.loads(txt2).get("items", [])}
            for a in parca:
                a["sure_dk"] = sureler.get(a["video_id"])
    return [a for a in adaylar if a.get("sure_dk") and MIN_SURE_DK <= a["sure_dk"] <= MAX_SURE_DK]


def sirala(adaylar, islenen_idler, hatali):
    """Islenmemis adaylar: once uzun (ders/seminer) videolar; 2 kez hata verenler atlanir."""
    kalan = [a for a in adaylar if a["video_id"] not in islenen_idler and hatali.get(a["video_id"], 0) < 2]
    return sorted(kalan, key=lambda a: -(a.get("sure_dk") or 0))


def kisi_isle(kisi, eski, anahtar_data, butce):
    k = dict(eski or {})
    k.setdefault("islenenler", [])
    k.setdefault("hatali", {})
    notlar = []
    son = k.get("aday_guncelleme_utc")
    yenile = not son or (simdi() - datetime.datetime.fromisoformat(son)).days >= ADAY_YENILE_GUN
    if yenile and anahtar_data:
        try:
            k["adaylar"] = ara(kisi, anahtar_data)
            k["aday_guncelleme_utc"] = simdi().isoformat()
        except Exception as e:
            notlar.append("arama: " + yt._hata_metni(e)[:150])
    islenen_idler = {v["video_id"] for v in k["islenenler"]}
    sira = sirala(k.get("adaylar") or [], islenen_idler, k["hatali"])
    for a in sira[:butce]:
        try:
            j, kaynak, _ = yt.gemini_transkript(a["url"], istem=ISTEM.format(ad=kisi["ad"]), sema=SEMA)
            k["islenenler"].append(dict(a, islenme_utc=simdi().isoformat(), kaynak=kaynak,
                                        ilkeler=j.get("ilkeler") or [], ozet=j.get("ozet") or [],
                                        bahsedilen_hisseler=j.get("bahsedilen_hisseler") or [],
                                        konusmaci_dogrulandi=bool(j.get("konusmaci_dogrulandi")),
                                        yaklasik_tarih=j.get("yaklasik_tarih") or ""))
        except Exception as e:
            k["hatali"][a["video_id"]] = k["hatali"].get(a["video_id"], 0) + 1
            notlar.append("%s: %s" % (a["video_id"], yt._hata_metni(e)[:150]))
            if "429" in str(e):
                break
    k["kalan_aday"] = len(sirala(k.get("adaylar") or [], {v["video_id"] for v in k["islenenler"]}, k["hatali"]))
    k["not"] = kisi.get("not", "")
    k["hata"] = "; ".join(notlar) or None
    return k


def main():
    eski = onceki()
    cikti = {"surum": SURUM, "uretim_zamani_utc": simdi().isoformat(), "kisiler": dict(eski.get("kisiler") or {})}
    try:
        ayar = liste()
        anahtar_data = os.environ.get("YOUTUBE_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
        butce = int(ayar.get("calisma_basina_video", 1))
        if not os.environ.get("GOOGLE_API_KEY", "").strip():
            cikti["hata"] = "GOOGLE_API_KEY yok"
        else:
            for kisi in ayar.get("kisiler", []):
                cikti["kisiler"][kisi["ad"]] = kisi_isle(kisi, cikti["kisiler"].get(kisi["ad"]), anahtar_data, butce)
            cikti["hata"] = None
    except Exception:
        traceback.print_exc()
        cikti["hata"] = "beklenmeyen: " + yt.anahtar_gizle(traceback.format_exc().strip().splitlines()[-1])
    try:
        os.makedirs("data", exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(cikti, f, ensure_ascii=False, indent=1)
        for ad, k in cikti["kisiler"].items():
            print(ad, "islenen", len(k.get("islenenler", [])), "kalan", k.get("kalan_aday"), "hata", k.get("hata"))
    except Exception as e:
        print("JSON yazilamadi:", e)
    sys.exit(0)


if __name__ == "__main__":
    main()
