#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_tarama.py  v2.1  (2026-11-06)
# "Emir Bozkurt | Stratejik Yatirim" (@stratejik.yatirim) kanalinin EN YENI
# videosunu bulur, Turkce transkriptini alir ve data/youtube_emir.json yazar.
#
# v2.0 - neden: v1.2'de (1) YouTube RSS'i bilinen platform-geneli aralikli 404
# veriyor (Dec 2025'ten beri raporlu; User-Agent cozmuyor), (2) Actions IP'leri
# /api/timedtext'te RequestBlocked/429 aliyor. Cozum tek UCRETSIZ Google API
# anahtari ile:
#   VIDEO LISTESI : 1) kanal RSS  2) uploads-playlist RSS  3) YouTube Data API v3
#                   (playlistItems.list, 1 birim/cagri; 10.000 birim/gun ucretsiz)
#   TRANSKRIPT    : Gemini API'ye YouTube URL'si (videoyu Google kendi
#                   sunucusunda isler, IP engeli yok; ucretsiz katman gunde 8 saat video)
# v2.1: youtube-transcript-api + proxy yolu kaldirildi (Actions IP'lerinden her
#       seferinde RequestBlocked/429 veriyordu; 06.11 itibariyla Gemini calisiyor).
# Secret'lar (GitHub -> Settings -> Secrets -> Actions):
#   GOOGLE_API_KEY   : Google AI Studio anahtari (Gemini). Transkript icin ZORUNLU.
#   YOUTUBE_API_KEY  : (opsiyonel) Data API icin ayri anahtar; yoksa
#                      GOOGLE_API_KEY denenir.
#   GEMINI_MODEL     : (opsiyonel) zorla kullanilacak model adi.
# IZOLASYON (v1.2'den korunur): ana taramayi ASLA etkilemez; her yolda JSON
# yazar, basarisizlikta onceki iyi veriyi korur, her zaman exit(0).
import os
import re
import sys
import json
import time
import datetime
import traceback
import urllib.error
import urllib.parse
import urllib.request

SURUM = "2.1"
CHANNEL_ID = "UChiWzAwOe7J67dd5PmmUnnA"
UPLOADS_PLAYLIST = "UU" + CHANNEL_ID[2:]
CHANNEL_ADI = "Emir Bozkurt | Stratejik Yatirim"
TRANSKRIPT_MAX_KARAKTER = 60000
SON_VIDEO_BAGLAM = 8
RSS_DENEME_BEKLEME = [0, 10, 30]  # saniye
HTTP_ZAMAN_ASIMI = 60
GEMINI_ZAMAN_ASIMI = 600
MIN_TRANSKRIPT = 1000  # bundan kisa metin "basarili" sayilmaz

OUT_PATH = os.path.join("data", "youtube_emir.json")
RSS_KANAL = "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL_ID
RSS_PLAYLIST = "https://www.youtube.com/feeds/videos.xml?playlist_id=" + UPLOADS_PLAYLIST
TARAYICI_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
GEMINI_TABAN = "https://generativelanguage.googleapis.com/v1beta"
YT_DATA_TABAN = "https://www.googleapis.com/youtube/v3"
GEMINI_TERCIH = ["gemini-3-flash-preview", "gemini-flash-latest", "gemini-2.5-flash"]

GUNLUK = []  # kisa deneme gunlugu -> JSON "denemeler"


def log(msg):
    print(msg)
    GUNLUK.append(str(msg)[:300])


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def anahtar_gizle(s):
    # loglara/JSON'a API anahtari sizmasin
    for k in ("GOOGLE_API_KEY", "YOUTUBE_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            s = s.replace(v, "***")
    return re.sub(r"key=[A-Za-z0-9_\-]+", "key=***", s)


# ── HTTP (tek nokta; testte bu fonksiyon degistirilir) ──
def http_get(url, headers=None, timeout=HTTP_ZAMAN_ASIMI):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": TARAYICI_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def http_post_json(url, govde, timeout=GEMINI_ZAMAN_ASIMI):
    data = json.dumps(govde).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _hata_metni(e):
    if isinstance(e, urllib.error.HTTPError):
        govde = ""
        try:
            govde = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        return anahtar_gizle("HTTP %s %s" % (e.code, govde))
    return anahtar_gizle("%s: %s" % (type(e).__name__, e))


def _unxml(s):
    if not s:
        return ""
    for a, b in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'")]:
        s = s.replace(a, b)
    return s.strip()


# ── 1) VIDEO LISTESI ──
def _rss_ayristir(xml):
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


def rss_dene(url, bekleme):
    for i, bekle in enumerate(bekleme, 1):
        if bekle:
            time.sleep(bekle)
        try:
            _, xml = http_get(url)
            v = _rss_ayristir(xml)
            if v:
                return v
            log("RSS bos dondu (%s)" % url.split("?")[1])
        except Exception as e:
            log("RSS %d/%d basarisiz (%s): %s" % (i, len(bekleme), url.split("?")[1], _hata_metni(e)))
    return []


def data_api_videolar(anahtar):
    q = urllib.parse.urlencode({"part": "snippet,contentDetails", "playlistId": UPLOADS_PLAYLIST,
                                "maxResults": SON_VIDEO_BAGLAM, "key": anahtar})
    _, txt = http_get(YT_DATA_TABAN + "/playlistItems?" + q, headers={"Accept": "application/json"})
    d = json.loads(txt)
    out = []
    for it in d.get("items", []):
        sn = it.get("snippet") or {}
        cd = it.get("contentDetails") or {}
        vid = cd.get("videoId") or (sn.get("resourceId") or {}).get("videoId")
        if not vid:
            continue
        out.append({
            "video_id": vid,
            "baslik": sn.get("title", ""),
            "yayin_tarihi": cd.get("videoPublishedAt") or sn.get("publishedAt", ""),
            "url": "https://www.youtube.com/watch?v=" + vid,
            "aciklama": sn.get("description", ""),
        })
    out.sort(key=lambda x: x.get("yayin_tarihi") or "", reverse=True)
    return out


def video_listesi():
    v = rss_dene(RSS_KANAL, RSS_DENEME_BEKLEME)
    if v:
        return v, "rss_kanal"
    v = rss_dene(RSS_PLAYLIST, [0])
    if v:
        return v, "rss_playlist"
    anahtar = os.environ.get("YOUTUBE_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if anahtar:
        try:
            v = data_api_videolar(anahtar)
            if v:
                return v, "youtube_data_api"
            log("Data API bos liste dondu")
        except Exception as e:
            log("Data API basarisiz: %s" % _hata_metni(e))
    else:
        log("Data API atlandi: GOOGLE_API_KEY/YOUTUBE_API_KEY yok")
    return [], None


# ── 2) TRANSKRIPT: Gemini (YouTube URL) ──
GEMINI_ISTEM = (
    "Bu YouTube videosundaki konusmalari TURKCE olarak yaziya dok. Kurallar: "
    "(1) 'transkript' alanina konusmaciin soylediklerini OLDUGU GIBI yaz; ozetleme, "
    "yorum ekleme, uydurma. Zaman damgasi koyma. Hisse kodlarini (or. THYAO, KRDMD), "
    "fiyat seviyelerini ve rakamlari duydugun gibi aynen yaz; emin olmadigin kelimeyi [?] ile isaretle. "
    "(2) 'ozet' alanina videonun ana fikirlerini 5-10 maddede, yalniz videoda soylenenlere "
    "dayanarak yaz. (3) 'bahsedilen_hisseler' alanina videoda adi gecen her hisse/varlik icin "
    "kod ve konusmacinin o hisse hakkinda soyledigini (seviye, beklenti, risk) tek cumleyle yaz; "
    "yalniz videoda gecenleri yaz.")

GEMINI_SEMA = {
    "type": "OBJECT",
    "properties": {
        "transkript": {"type": "STRING"},
        "ozet": {"type": "ARRAY", "items": {"type": "STRING"}},
        "bahsedilen_hisseler": {"type": "ARRAY", "items": {
            "type": "OBJECT",
            "properties": {"kod": {"type": "STRING"}, "ne_dedi": {"type": "STRING"}},
            "required": ["kod", "ne_dedi"]}},
    },
    "required": ["transkript", "ozet", "bahsedilen_hisseler"],
}


def gemini_modelleri(anahtar):
    zorla = os.environ.get("GEMINI_MODEL", "").strip()
    adaylar = [zorla] if zorla else []
    mevcut = []
    try:
        _, txt = http_get(GEMINI_TABAN + "/models?pageSize=200&key=" + anahtar,
                          headers={"Accept": "application/json"})
        for m in json.loads(txt).get("models", []):
            ad = (m.get("name") or "").replace("models/", "")
            yontem = m.get("supportedGenerationMethods") or []
            if "generateContent" not in yontem:
                continue
            kucuk = ad.lower()
            if "flash" not in kucuk:
                continue
            if any(x in kucuk for x in ("lite", "tts", "live", "image", "audio", "embedding", "transcribe")):
                continue
            mevcut.append(ad)
    except Exception as e:
        log("Gemini model listesi alinamadi: %s" % _hata_metni(e))
    for t in GEMINI_TERCIH:
        if t in mevcut or not mevcut:
            adaylar.append(t)
    for ad in sorted(mevcut, reverse=True):
        adaylar.append(ad)
    goruldu, sira = set(), []
    for a in adaylar:
        if a and a not in goruldu:
            goruldu.add(a)
            sira.append(a)
    return sira[:5]


def _gemini_cevap_metni(txt):
    d = json.loads(txt)
    adaylar = d.get("candidates") or []
    if not adaylar:
        raise RuntimeError("Gemini aday donmedi: %s" % json.dumps(d.get("promptFeedback", {}))[:200])
    c = adaylar[0]
    parcalar = ((c.get("content") or {}).get("parts")) or []
    metin = "".join(p.get("text", "") for p in parcalar)
    return metin, c.get("finishReason")


def gemini_transkript(video_url):
    anahtar = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not anahtar:
        raise RuntimeError("GOOGLE_API_KEY yok")
    son_hata = None
    for model in gemini_modelleri(anahtar):
        govde = {
            "contents": [{"role": "user", "parts": [
                {"file_data": {"file_uri": video_url}},
                {"text": GEMINI_ISTEM}]}],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 32768,
                "mediaResolution": "MEDIA_RESOLUTION_LOW",
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_SEMA,
            },
        }
        url = "%s/models/%s:generateContent?key=%s" % (GEMINI_TABAN, model, anahtar)
        try:
            _, txt = http_post_json(url, govde)
            metin, bitis = _gemini_cevap_metni(txt)
            try:
                j = json.loads(metin)
            except ValueError:
                # JSON yarim kaldiysa (MAX_TOKENS) ham metni transkript say
                j = {"transkript": metin, "ozet": [], "bahsedilen_hisseler": []}
            tr = re.sub(r"\s+", " ", j.get("transkript") or "").strip()
            log("Gemini %s: %d karakter, bitis=%s" % (model, len(tr), bitis))
            return tr, "tr", "gemini:" + model, j.get("ozet") or [], j.get("bahsedilen_hisseler") or [], bitis
        except urllib.error.HTTPError as e:
            son_hata = _hata_metni(e)
            log("Gemini %s hata: %s" % (model, son_hata))
            if e.code == 429:
                break  # kota: baska modelle israf etme
        except Exception as e:
            son_hata = _hata_metni(e)
            log("Gemini %s hata: %s" % (model, son_hata))
    raise RuntimeError("Gemini basarisiz: %s" % son_hata)


# ── 3) YAZMA ──
def onceki_veri():
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def yaz(cikti):
    cikti["surum"] = SURUM
    cikti["denemeler"] = GUNLUK[-40:]
    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print("YAZILDI:", OUT_PATH, "| transkript_var:", cikti.get("transkript_var"),
          "| kaynak:", (cikti.get("en_yeni_video") or {}).get("transkript_kaynagi"),
          "| hata:", cikti.get("hata"))


def iskelet(hata, onceki=None):
    return {
        "uretim_zamani_utc": now_utc(), "kanal": CHANNEL_ADI, "channel_id": CHANNEL_ID,
        "en_yeni_video": None, "transkript_var": False, "son_videolar": [],
        "video_liste_kaynagi": None, "son_basarili_utc": (onceki or {}).get("son_basarili_utc"),
        "hata": hata,
    }


def onceki_ile_yaz(onceki, hata):
    if onceki and onceki.get("en_yeni_video"):
        d = dict(onceki)
        d["hata"] = hata
        d["son_deneme_utc"] = now_utc()
        d["onceki_veri_korundu"] = True
        yaz(d)
    else:
        yaz(iskelet(hata, onceki))


def main():
    onceki = onceki_veri()
    vids, liste_kaynak = video_listesi()
    if not vids:
        onceki_ile_yaz(onceki, "video listesi alinamadi (RSS kanal + RSS playlist + Data API)")
        return
    son = [{"baslik": v["baslik"], "yayin_tarihi": v["yayin_tarihi"], "url": v["url"]}
           for v in vids[:SON_VIDEO_BAGLAM]]
    en_yeni = vids[0]
    onceki_v = (onceki or {}).get("en_yeni_video") or {}

    transkript, dil, kaynak, ozet, hisseler, thata, bitis = "", None, None, [], [], None, None
    ayni_video_hazir = (onceki_v.get("video_id") == en_yeni["video_id"]
                        and len(onceki_v.get("transkript") or "") >= MIN_TRANSKRIPT)
    if ayni_video_hazir:
        # ayni video zaten yazildi: kota/istek harcama, onceki transkripti kullan
        log("Ayni video icin transkript zaten var; yeniden cekilmedi.")
        transkript = onceki_v["transkript"]
        dil = onceki_v.get("transkript_dil")
        kaynak = onceki_v.get("transkript_kaynagi") or "onceki"
        ozet = onceki_v.get("ozet") or []
        hisseler = onceki_v.get("bahsedilen_hisseler") or []
    else:
        hatalar = []
        try:
            transkript, dil, kaynak, ozet, hisseler, bitis = gemini_transkript(en_yeni["url"])
            if len(transkript) < MIN_TRANSKRIPT:
                hatalar.append("gemini kisa/bos (%d)" % len(transkript))
                transkript = ""
        except Exception as e:
            hatalar.append(_hata_metni(e)[:200])
            log(hatalar[-1])
        if not transkript:
            thata = " | ".join(hatalar) or "transkript alinamadi"

    tvar = len(transkript or "") >= MIN_TRANSKRIPT
    kesildi = False
    if transkript and len(transkript) > TRANSKRIPT_MAX_KARAKTER:
        transkript = transkript[:TRANSKRIPT_MAX_KARAKTER]
        kesildi = True
    if bitis == "MAX_TOKENS":
        kesildi = True
    yaz({
        "uretim_zamani_utc": now_utc(),
        "kanal": CHANNEL_ADI,
        "channel_id": CHANNEL_ID,
        "video_liste_kaynagi": liste_kaynak,
        "en_yeni_video": {
            "video_id": en_yeni["video_id"],
            "baslik": en_yeni["baslik"],
            "yayin_tarihi": en_yeni["yayin_tarihi"],
            "url": en_yeni["url"],
            "aciklama": en_yeni.get("aciklama", "")[:2000],
            "transkript_dil": dil,
            "transkript_kaynagi": kaynak,
            "transkript_kesildi": kesildi,
            "transkript": transkript,
            "ozet": ozet,
            "bahsedilen_hisseler": hisseler,
        },
        "transkript_var": tvar,
        "son_basarili_utc": now_utc() if tvar else (onceki or {}).get("son_basarili_utc"),
        "son_videolar": son,
        "hata": thata,
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            yaz(iskelet("beklenmeyen hata: " + anahtar_gizle(traceback.format_exc().strip().splitlines()[-1]),
                        onceki_veri()))
        except Exception:
            pass
    sys.exit(0)
