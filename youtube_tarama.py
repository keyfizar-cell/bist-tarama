#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_tarama.py  v1.0  (2026-11-05)
# "Emir Bozkurt | Stratejik Yatirim" (@stratejik.yatirim) kanalinin EN YENI
# videosunu RSS'ten bulur, Turkce oto-altyazi transkriptini
# (youtube-transcript-api, ucretsiz, anahtarsiz) ceker ve
# data/youtube_emir.json dosyasina yazar.
# IZOLASYON: ana taramayi ASLA etkilemez; her yolda JSON yazar, exit(0).
import os
import re
import sys
import json
import datetime
import traceback
import urllib.request

CHANNEL_ID = "UChiWzAwOe7J67dd5PmmUnnA"
CHANNEL_ADI = "Emir Bozkurt | Stratejik Yatirim"
DIL_ONCELIK = ["tr", "tr-TR", "en"]
TRANSKRIPT_MAX_KARAKTER = 12000
SON_VIDEO_BAGLAM = 8

OUT_PATH = os.path.join("data", "youtube_emir.json")
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL_ID


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _unxml(s):
    if not s:
        return ""
    for a, b in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'")]:
        s = s.replace(a, b)
    return s.strip()


def iskelet(hata, son_videolar=None):
    return {
        "uretim_zamani_utc": now_utc(),
        "kanal": CHANNEL_ADI,
        "channel_id": CHANNEL_ID,
        "en_yeni_video": None,
        "transkript_var": False,
        "son_videolar": son_videolar or [],
        "hata": hata,
    }


def rss_videolar():
    req = urllib.request.Request(
        RSS_URL, headers={"User-Agent": "Mozilla/5.0 (bist-bulten-bot)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        xml = r.read().decode("utf-8", "replace")
    girisler = []
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        blok = m.group(1)
        vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", blok)
        if not vid:
            continue
        bas = re.search(r"<title>(.*?)</title>", blok, re.S)
        pub = re.search(r"<published>(.*?)</published>", blok)
        desc = re.search(r"<media:description>(.*?)</media:description>", blok, re.S)
        vid = vid.group(1)
        girisler.append({
            "video_id": vid,
            "baslik": _unxml(bas.group(1) if bas else ""),
            "yayin_tarihi": (pub.group(1) if pub else ""),
            "url": "https://www.youtube.com/watch?v=" + vid,
            "aciklama": _unxml(desc.group(1) if desc else ""),
        })
    return girisler


def _snippet_metni(snippets):
    parcalar = []
    for s in snippets:
        t = getattr(s, "text", None)
        if t is None and isinstance(s, dict):
            t = s.get("text")
        if t:
            parcalar.append(t)
    metin = " ".join(parcalar)
    return re.sub(r"\s+", " ", metin).strip()


def transkript_cek(video_id):
    from youtube_transcript_api import YouTubeTranscriptApi
    ytt = YouTubeTranscriptApi()
    try:
        fetched = ytt.fetch(video_id, languages=DIL_ONCELIK)
        return _snippet_metni(fetched.snippets), getattr(fetched, "language_code", None)
    except Exception:
        pass
    tl = ytt.list(video_id)
    tr = None
    try:
        tr = tl.find_transcript(DIL_ONCELIK)
    except Exception:
        tr = None
    if tr is None:
        for t in tl:
            tr = t
            break
        if tr is not None and getattr(tr, "is_translatable", False):
            try:
                tr = tr.translate("tr")
            except Exception:
                pass
    if tr is None:
        raise RuntimeError("uygun transkript bulunamadi")
    f = tr.fetch()
    snippets = f.snippets if hasattr(f, "snippets") else f
    return _snippet_metni(snippets), getattr(tr, "language_code", None)


def yaz(cikti):
    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print("YAZILDI:", OUT_PATH,
          "| transkript_var:", cikti.get("transkript_var"),
          "| hata:", cikti.get("hata"))


def main():
    try:
        vids = rss_videolar()
    except Exception as e:
        yaz(iskelet("RSS cekilemedi: %s: %s" % (type(e).__name__, e)))
        return
    if not vids:
        yaz(iskelet("RSS bos / video bulunamadi"))
        return
    son = [{"baslik": v["baslik"], "yayin_tarihi": v["yayin_tarihi"], "url": v["url"]}
           for v in vids[:SON_VIDEO_BAGLAM]]
    en_yeni = vids[0]
    transkript, dil, thata, tvar = "", None, None, False
    try:
        transkript, dil = transkript_cek(en_yeni["video_id"])
        tvar = bool(transkript)
        if not tvar:
            thata = "transkript bos dondu"
    except Exception as e:
        thata = "transkript alinamadi: %s: %s" % (type(e).__name__, e)
    kesildi = False
    if transkript and len(transkript) > TRANSKRIPT_MAX_KARAKTER:
        transkript = transkript[:TRANSKRIPT_MAX_KARAKTER]
        kesildi = True
    yaz({
        "uretim_zamani_utc": now_utc(),
        "kanal": CHANNEL_ADI,
        "channel_id": CHANNEL_ID,
        "en_yeni_video": {
            "video_id": en_yeni["video_id"],
            "baslik": en_yeni["baslik"],
            "yayin_tarihi": en_yeni["yayin_tarihi"],
            "url": en_yeni["url"],
            "aciklama": en_yeni.get("aciklama", ""),
            "transkript_dil": dil,
            "transkript_kesildi": kesildi,
            "transkript": transkript,
        },
        "transkript_var": tvar,
        "son_videolar": son,
        "hata": thata,
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            yaz(iskelet("beklenmeyen hata: " + traceback.format_exc().strip().splitlines()[-1]))
        except Exception:
            pass
    sys.exit(0)
