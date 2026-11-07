#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# sosyal_nabiz.py  v1.0  (2026-11-07)
# Kucuk yatirimci nabzi (UCRETSIZ kaynaklar):
#   (1) YouTube yorumlari: takip edilen videolar (youtube_emir/konuk/kanallar.json) + son 2 gunun en cok
#       yorum alan "borsa" videolari -> yorumlarda gecen BIST kodlari sayilir (Data API: ~130 birim/gun).
#   (2) Forum/Reddit/Eksi taramasi: Gemini + Google Search (grounding) ile son 48 saatte konusulan BIST
#       hisseleri ve spekulasyonlar; kaynak linkleri JSON'a yazilir.
#   (3) Ipucu takibi: konusulan hisse + taramadaki hacim -> isaret; 5 ve 20 islem gunu sonraki getiri
#       kaydedilir (hangi kaynak ise yariyor olcumu).
# X/Twitter ve Reddit API kullanilmaz (X ucretli, Reddit API onay istiyor). Kullanici adi SAKLANMAZ.
# Secret: GOOGLE_API_KEY (Gemini), YOUTUBE_API_KEY (Data API).  Cikti: data/sosyal_nabiz.json
# IZOLASYON: her yolda JSON yazar, exit(0).
import os
import re
import sys
import json
import datetime
import traceback
import urllib.parse

import youtube_tarama as yt

SURUM = "1.0"
OUT_PATH = os.path.join("data", "sosyal_nabiz.json")
LATEST = os.path.join("data", "latest.json")
ARAMA_SORGULARI = ["borsa hisse", "bist hisse analiz"]
ARAMA_GUN = 2
EN_FAZLA_ARAMA_VIDEO = 15
YORUM_SAYFA = 100
IPUCU_ESIK_YORUM = 3        # en az bu kadar FARKLI yorumda gecen kod ipucu sayilir
HACIM_ESIK = 2.0            # hacim_orani >= bu -> "konusuluyor+hacim"
ARTIS_KAT = 3.0             # bugunku sayim >= onceki gunler ortalamasi x bu -> ani artis
GECMIS_GUN = 30
TAKIP_GUN = 60
# Gunluk dilde kelime olan kodlar: yalniz #KOD, $KOD veya "KOD hisse" bicimindeyse sayilir.
KELIME_KODLAR = {
    "ADEL", "ALTIN", "ARENA", "ATLAS", "AVOD", "BERA", "BESTE", "BEYAZ", "BIZIM", "CASA", "DAGI",
    "DENGE", "DERIM", "EDIP", "EKIM", "ELITE", "ERSU", "ESEN", "FENER", "GEDIK", "GOODY", "GOZDE",
    "HEDEF", "HUNER", "INFO", "KENT", "KONYA", "LIDER", "LILAK", "LINK", "LOGO", "MANAS", "MARTI",
    "MAVI", "MERIT", "METRO", "ORGE", "ORMA", "OTTO", "QUICK", "SANKO", "SELVA", "SMART", "SONME",
    "TERA", "UFUK", "ULAS", "YAYLA", "YESIL", "YIGIT", "SILVR", "TATEN", "BORSA", "BIST"}

FORUM_ISTEM = (
    "Google aramasini kullan. Son 48 saatte Turkce yatirimci topluluklarinda (Reddit r/Borsa ve r/BorsaIstanbul, "
    "Eksi Sozluk borsa basliklari, hisse.net forum, Investing.com Turkce yorumlar, borsa forumlari ve haber "
    "yorumlari) en cok konusulan Borsa Istanbul hisselerini ve spekulasyonlari bul. YALNIZ aramada gercekten "
    "buldugun icerige dayan; bulamazsan bos liste ver, uydurma. Yanit YALNIZ su JSON olsun (baska metin yok): "
    '{"ozet": ["genel hava, en fazla 3 madde"], "hisseler": [{"kod": "BIST kodu", "ne_konusuluyor": "tek cumle", '
    '"tur": "spekulasyon|haber|analiz|sikayet", "kaynak": "site adi"}]}. En fazla 10 hisse.')


def simdi():
    return datetime.datetime.now(datetime.timezone.utc)


def yukle(yol, varsayilan):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return varsayilan


def data_get(yol, params, anahtar):
    q = urllib.parse.urlencode(dict(params, key=anahtar))
    _, txt = yt.http_get(yt.YT_DATA_TABAN + "/" + yol + "?" + q, headers={"Accept": "application/json"})
    return json.loads(txt)


# ── 1) YOUTUBE YORUMLARI ──
def takip_videolari(gun=7):
    sinir = (simdi() - datetime.timedelta(days=gun)).isoformat()[:19]
    out = {}
    emir = yukle(os.path.join("data", "youtube_emir.json"), {}).get("en_yeni_video") or {}
    if emir.get("video_id") and (emir.get("yayin_tarihi") or "")[:19] >= sinir:
        out[emir["video_id"]] = {"baslik": emir.get("baslik", ""), "kanal": "Emir Bozkurt", "kaynak": "takip"}
    for dosya, anahtar in (("youtube_konuk.json", "kisiler"), ("youtube_kanallar.json", "kanallar")):
        for ad, k in (yukle(os.path.join("data", dosya), {}).get(anahtar) or {}).items():
            for v in k.get("videolar") or []:
                if v.get("video_id") and not v.get("atlandi") and (v.get("yayin_tarihi") or "")[:19] >= sinir:
                    out[v["video_id"]] = {"baslik": v.get("baslik", ""), "kanal": v.get("kanal") or ad,
                                          "kaynak": "takip"}
    return out


def arama_videolari(anahtar):
    sonra = (simdi() - datetime.timedelta(days=ARAMA_GUN)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aday = {}
    for q in ARAMA_SORGULARI:
        d = data_get("search", {"part": "snippet", "q": q, "type": "video", "order": "viewCount",
                                "publishedAfter": sonra, "maxResults": 25, "regionCode": "TR",
                                "relevanceLanguage": "tr"}, anahtar)
        for it in d.get("items", []):
            vid = (it.get("id") or {}).get("videoId")
            sn = it.get("snippet") or {}
            if vid:
                aday[vid] = {"baslik": yt._unxml(sn.get("title", "")), "kanal": sn.get("channelTitle", ""),
                             "kaynak": "arama"}
    if not aday:
        return {}
    d = data_get("videos", {"part": "statistics", "id": ",".join(list(aday)[:50])}, anahtar)
    yorum = {i["id"]: int((i.get("statistics") or {}).get("commentCount") or 0) for i in d.get("items", [])}
    secilen = sorted((v for v in aday if yorum.get(v, 0) > 0), key=lambda v: -yorum[v])[:EN_FAZLA_ARAMA_VIDEO]
    return {v: aday[v] for v in secilen}


def yorumlar(video_id, anahtar):
    d = data_get("commentThreads", {"part": "snippet", "videoId": video_id, "maxResults": YORUM_SAYFA,
                                    "order": "relevance", "textFormat": "plainText"}, anahtar)
    out = []
    for it in d.get("items", []):
        s = ((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
        if s.get("textDisplay"):
            out.append(s["textDisplay"])
    return out


def kodlari_bul(metin, kodlar):
    bulunan = set()
    for m in re.finditer(r"([#$]?)\b([A-Za-z0-9ÇĞİÖŞÜçğıöşü]{4,6})\b(\s+hisse)?", metin):
        on, kelime, hisse = m.group(1), m.group(2), m.group(3)
        kod = kelime.upper().replace("İ", "I")
        if kod not in kodlar:
            continue
        if kod in KELIME_KODLAR:
            if on or hisse:
                bulunan.add(kod)
        elif kelime.isupper() or on or hisse or len(kod) >= 5:
            bulunan.add(kod)
    return bulunan


def youtube_nabiz(anahtar, kodlar):
    sonuc = {"videolar": [], "yorum_sayisi": 0, "kod_sayim": {}, "hata": None}
    try:
        videolar = takip_videolari()
        videolar.update({k: v for k, v in arama_videolari(anahtar).items() if k not in videolar})
    except Exception as e:
        sonuc["hata"] = "video listesi: " + yt._hata_metni(e)[:200]
        videolar = takip_videolari()
    for vid, bilgi in videolar.items():
        try:
            yl = yorumlar(vid, anahtar)
        except Exception as e:
            yl = []
            bilgi["hata"] = yt._hata_metni(e)[:120]  # yorumlar kapali olabilir
        sonuc["videolar"].append(dict(bilgi, video_id=vid, alinan_yorum=len(yl)))
        sonuc["yorum_sayisi"] += len(yl)
        for y in yl:
            for kod in kodlari_bul(y, kodlar):
                k = sonuc["kod_sayim"].setdefault(kod, {"yorum": 0, "videolar": set(), "ornekler": []})
                k["yorum"] += 1
                k["videolar"].add(vid)
                if len(k["ornekler"]) < 2:
                    k["ornekler"].append(re.sub(r"\s+", " ", y)[:160])
    for k in sonuc["kod_sayim"].values():
        k["video"] = len(k.pop("videolar"))
    sonuc["kod_sayim"] = dict(sorted(sonuc["kod_sayim"].items(), key=lambda x: -x[1]["yorum"]))
    return sonuc


# ── 2) FORUM / REDDIT / EKSI (Gemini + Google Search) ──
def forum_nabiz(kodlar):
    anahtar = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not anahtar:
        return {"hata": "GOOGLE_API_KEY yok", "ozet": [], "hisseler": [], "kaynaklar": []}
    son_hata = None
    for model in yt.gemini_modelleri(anahtar):
        govde = {"contents": [{"role": "user", "parts": [{"text": FORUM_ISTEM}]}],
                 "tools": [{"google_search": {}}],
                 "generationConfig": {"temperature": 0, "maxOutputTokens": 4096}}
        url = "%s/models/%s:generateContent?key=%s" % (yt.GEMINI_TABAN, model, anahtar)
        try:
            _, txt = yt.http_post_json(url, govde, timeout=180)
            cevap = json.loads(txt)
            aday = (cevap.get("candidates") or [{}])[0]
            metin = "".join(p.get("text", "") for p in (aday.get("content") or {}).get("parts", []))
            m = re.search(r"\{.*\}", metin, re.S)
            j = json.loads(m.group(0)) if m else {}
            kaynaklar = []
            for c in (aday.get("groundingMetadata") or {}).get("groundingChunks", []) or []:
                w = c.get("web") or {}
                if w.get("uri"):
                    kaynaklar.append({"baslik": w.get("title", ""), "url": w["uri"]})
            hisseler = [h for h in (j.get("hisseler") or [])
                        if isinstance(h, dict) and str(h.get("kod", "")).upper() in kodlar]
            for h in hisseler:
                h["kod"] = h["kod"].upper()
            yt.log("Forum taramasi %s: %d hisse, %d kaynak" % (model, len(hisseler), len(kaynaklar)))
            return {"hata": None if kaynaklar else "arama kaynagi donmedi (sonuc dogrulanamaz)",
                    "model": model, "ozet": (j.get("ozet") or [])[:3] if kaynaklar else [],
                    "hisseler": hisseler if kaynaklar else [], "kaynaklar": kaynaklar[:15]}
        except Exception as e:
            son_hata = yt._hata_metni(e)
            yt.log("Forum taramasi %s hata: %s" % (model, son_hata))
            if "429" in son_hata:
                break
    return {"hata": "Gemini arama basarisiz: %s" % (son_hata or "")[:200], "ozet": [], "hisseler": [],
            "kaynaklar": []}


# ── 3) IPUCU + TAKIP ──
def ipuclari(yt_sonuc, forum, hisse):
    out = {}
    for kod, s in yt_sonuc.get("kod_sayim", {}).items():
        if s["yorum"] >= IPUCU_ESIK_YORUM:
            out.setdefault(kod, {"kod": kod, "kaynaklar": []})["kaynaklar"].append("youtube")
            out[kod]["youtube_yorum"] = s["yorum"]
    for h in forum.get("hisseler", []):
        out.setdefault(h["kod"], {"kod": h["kod"], "kaynaklar": []})["kaynaklar"].append("forum")
        out[h["kod"]]["forum"] = h.get("ne_konusuluyor", "")
        out[h["kod"]]["forum_tur"] = h.get("tur", "")
    for kod, i in out.items():
        t = hisse.get(kod) or {}
        i.update(kapanis=t.get("kapanis"), gunluk_yuzde=t.get("gunluk_yuzde"), hacim_orani=t.get("hacim_orani"))
        i["isaret"] = ("konusuluyor+hacim" if (t.get("hacim_orani") or 0) >= HACIM_ESIK else "yalniz_konusma")
    return sorted(out.values(), key=lambda x: (-len(x["kaynaklar"]), -(x.get("youtube_yorum") or 0)))


def ani_artis(gecmis, tarih):
    bugun = gecmis.get(tarih) or {}
    onceki = [g for t, g in gecmis.items() if t < tarih]
    out = []
    for kod, n in bugun.items():
        ort = sum(g.get(kod, 0) for g in onceki) / len(onceki) if onceki else 0
        if n >= IPUCU_ESIK_YORUM and n >= ARTIS_KAT * max(ort, 1):
            out.append({"kod": kod, "bugun": n, "onceki_ortalama": round(ort, 1)})
    return sorted(out, key=lambda x: -x["bugun"])


def takip_guncelle(takip, ipucu, tarih, hisse):
    var = {(t["tarih"], t["kod"]) for t in takip}
    for i in ipucu:
        if (tarih, i["kod"]) not in var and i.get("kapanis"):
            takip.append({"tarih": tarih, "kod": i["kod"], "kaynaklar": i["kaynaklar"], "isaret": i["isaret"],
                          "ilk_kapanis": i["kapanis"], "izleme": {}})
    for t in takip:
        k = (hisse.get(t["kod"]) or {}).get("kapanis")
        if k and tarih > t["tarih"]:
            t["izleme"][tarih] = k
        gunler = sorted(t["izleme"])
        for n, alan in ((5, "getiri_5g"), (20, "getiri_20g")):
            if len(gunler) >= n and t.get(alan) is None:
                t[alan] = round((t["izleme"][gunler[n - 1]] / t["ilk_kapanis"] - 1) * 100, 2)
        if len(gunler) > 20:
            t["izleme"] = {g: t["izleme"][g] for g in gunler[:20]}
    sinir = (simdi() - datetime.timedelta(days=TAKIP_GUN)).strftime("%Y-%m-%d")
    return [t for t in takip if t["tarih"] >= sinir]


def takip_ozeti(takip):
    oz = {}
    for t in takip:
        for kaynak in t["kaynaklar"] + ["isaret:" + t["isaret"]]:
            o = oz.setdefault(kaynak, {"ipucu": 0, "olculen_5g": 0, "ort_getiri_5g": None, "_t": 0.0})
            o["ipucu"] += 1
            if t.get("getiri_5g") is not None:
                o["olculen_5g"] += 1
                o["_t"] += t["getiri_5g"]
    for o in oz.values():
        if o["olculen_5g"]:
            o["ort_getiri_5g"] = round(o["_t"] / o["olculen_5g"], 2)
        o.pop("_t")
    return oz


def main():
    eski = yukle(OUT_PATH, {})
    latest = yukle(LATEST, {})
    tarih = latest.get("tarih") or simdi().strftime("%Y-%m-%d")
    hisse = {h["kod"]: h for h in latest.get("tum_hisseler") or [] if h.get("kod")}
    kodlar = set(hisse)
    cikti = {"tarih": tarih, "hata": None}
    if not kodlar:
        cikti["hata"] = "latest.json okunamadi (kod listesi yok)"
    anahtar = os.environ.get("YOUTUBE_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if anahtar and kodlar:
        cikti["youtube"] = youtube_nabiz(anahtar, kodlar)
    else:
        cikti["youtube"] = {"hata": "YOUTUBE_API_KEY yok" if not anahtar else cikti["hata"], "kod_sayim": {}}
    cikti["forum"] = forum_nabiz(kodlar) if kodlar else {"hata": cikti["hata"], "hisseler": []}
    gecmis = eski.get("gecmis_sayim") or {}
    gecmis[tarih] = {k: v["yorum"] for k, v in cikti["youtube"].get("kod_sayim", {}).items()}
    sinir = (simdi() - datetime.timedelta(days=GECMIS_GUN)).strftime("%Y-%m-%d")
    cikti["gecmis_sayim"] = {t: g for t, g in sorted(gecmis.items()) if t >= sinir}
    cikti["ani_artis"] = ani_artis(cikti["gecmis_sayim"], tarih)
    cikti["ipuclari"] = ipuclari(cikti["youtube"], cikti["forum"], hisse)
    cikti["ipucu_takip"] = takip_guncelle(eski.get("ipucu_takip") or [], cikti["ipuclari"], tarih, hisse)
    cikti["takip_ozeti"] = takip_ozeti(cikti["ipucu_takip"])
    yaz(cikti)


def yaz(d):
    d["surum"] = SURUM
    d["uretim_zamani_utc"] = yt.now_utc()
    d["denemeler"] = yt.GUNLUK[-40:]
    os.makedirs("data", exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print("YAZILDI:", OUT_PATH)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        try:
            d = yukle(OUT_PATH, {})
            d["hata"] = "beklenmeyen hata: " + yt.anahtar_gizle(traceback.format_exc().strip().splitlines()[-1])
            yaz(d)
        except Exception:
            pass
    sys.exit(0)
