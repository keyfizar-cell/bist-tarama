#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_tarama.py  v1.2  (2026-11-05)  proxy + RSS tekrar deneme + onceki veriyi koruma
# "Emir Bozkurt | Stratejik Yatirim" (@stratejik.yatirim) kanalinin EN YENI
# videosunu RSS'ten bulur, Turkce oto-altyazi transkriptini
# (youtube-transcript-api, ucretsiz, anahtarsiz) ceker ve
# data/youtube_emir.json dosyasina yazar.
# IZOLASYON: ana taramayi ASLA etkilemez; her yolda JSON yazar, exit(0).
import os
import re
import sys
import json
import time
import datetime
import traceback
import urllib.error
import urllib.request

CHANNEL_ID = "UChiWzAwOe7J67dd5PmmUnnA"
CHANNEL_ADI = "Emir Bozkurt | Stratejik Yatirim"
DIL_ONCELIK = ["tr", "tr-TR", "en"]
TRANSKRIPT_MAX_KARAKTER = 12000
SON_VIDEO_BAGLAM = 8
RSS_DENEME_BEKLEME = [0, 5, 15, 30]  # saniye; 4 deneme

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


def onceki_veri():
    # Bir onceki calismanin JSON'u; yoksa / bozuksa None.
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def rss_xml():
    # YouTube RSS ara sira gecici 404/5xx veriyor: birkac kez tekrar dene.
    son_hata = None
    for i, bekle in enumerate(RSS_DENEME_BEKLEME, 1):
        if bekle:
            time.sleep(bekle)
        try:
            req = urllib.request.Request(
                RSS_URL, headers={"User-Agent": "Mozilla/5.0 (bist-bulten-bot)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                xml = r.read().decode("utf-8", "replace")
            if "<entry>" in xml:
                return xml
            son_hata = RuntimeError("RSS bos dondu")
        except (urllib.error.URLError, OSError) as e:
            son_hata = e
        print("RSS deneme %d/%d basarisiz: %s: %s"
              % (i, len(RSS_DENEME_BEKLEME), type(son_hata).__name__, son_hata))
    raise son_hata


def rss_videolar():
    xml = rss_xml()
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


def proxy_ayari():
    # Proxy, GitHub secret'larindan ortam degiskeni olarak gelir.
    # 1) WEBSHARE_PROXY_USERNAME + WEBSHARE_PROXY_PASSWORD -> Webshare konut proxy
    # 2) YT_PROXY_URL (ornek: http://kullanici:sifre@host:port) -> genel proxy
    # Hicbiri yoksa proxy kullanilmaz.
    ws_user = os.environ.get("WEBSHARE_PROXY_USERNAME", "").strip()
    ws_pass = os.environ.get("WEBSHARE_PROXY_PASSWORD", "").strip()
    if ws_user and ws_pass:
        from youtube_transcript_api.proxies import WebshareProxyConfig
        return WebshareProxyConfig(proxy_username=ws_user, proxy_password=ws_pass), "webshare"
    url = os.environ.get("YT_PROXY_URL", "").strip()
    if url:
        from youtube_transcript_api.proxies import GenericProxyConfig
        return GenericProxyConfig(http_url=url, https_url=url), "genel"
    return None, None


def transkript_cek(video_id):
    from youtube_transcript_api import YouTubeTranscriptApi
    pcfg, ptur = proxy_ayari()
    print("Proxy:", ptur or "yok")
    ytt = YouTubeTranscriptApi(proxy_config=pcfg)
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


def onceki_ile_yaz(onceki, hata):
    # Calisma basarisizsa onceki iyi veriyi silme: aynen koru, sadece
    # hata ve son deneme bilgisini ekle. Onceki veri yoksa iskelet yaz.
    if onceki and onceki.get("en_yeni_video"):
        d = dict(onceki)
        d["hata"] = hata
        d["son_deneme_utc"] = now_utc()
        d["onceki_veri_korundu"] = True
        yaz(d)
    else:
        yaz(iskelet(hata))


def main():
    onceki = onceki_veri()
    try:
        vids = rss_videolar()
    except Exception as e:
        onceki_ile_yaz(onceki, "RSS cekilemedi: %s: %s" % (type(e).__name__, e))
        return
    if not vids:
        onceki_ile_yaz(onceki, "RSS bos / video bulunamadi")
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
    # Transkript alinamadiysa ama ayni videonun transkripti onceki
    # calismada alinmissa onu koru.
    onceki_v = (onceki or {}).get("en_yeni_video") or {}
    if (not tvar and onceki_v.get("video_id") == en_yeni["video_id"]
            and onceki_v.get("transkript")):
        print("Transkript alinamadi; ayni videonun onceki transkripti korunuyor.")
        transkript = onceki_v["transkript"]
        dil = onceki_v.get("transkript_dil")
        tvar = True
        thata = "onceki transkript korundu; bu calismada: %s" % thata
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
