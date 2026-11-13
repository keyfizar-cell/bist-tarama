#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# youtube_deney.py  v1.0  (2026-11-13)
# YouTube transkript DENEY HATTI (Alpay karari 13.11.2026: "cozum bulana kadar ara ara deneyelim,
# Cin modellerini atlama"). Ana hatti (youtube_tarama.py) DEGISTIRMEZ; yalniz ayni videoda farkli
# yollari dener ve sonucu data/youtube_deney.json'a yazar. Her durumda JSON yazar, exit(0).
#
# Denenen yollar (her calismada hepsi; anahtari olmayan "anahtar_yok" diye kaydedilir, ATLANMAZ):
#   gemini_teshis   : tum video, duz metin; kisa yanitin ilk 400 karakteri (modeller neyi goruyor?)
#   gemini_parca    : videoMetadata startOffset/endOffset ile 10'ar dk parcalar, duz metin, birlestirme
#   ytdlp_altyazi   : yt-dlp otomatik Turkce altyazi (cerezsiz; bulut IP engeli olcumu)
#   ytdlp_ses       : yt-dlp ile yalniz ses (cerezsiz) -> ffmpeg ile 5 dk'lik parcalar (ASR icin)
#   qwen_url        : Alibaba DashScope (Singapur) Qwen-Omni, YouTube baglantisi video_url olarak
#   qwen_ses        : DashScope Qwen ASR, ses parcalari (ytdlp_ses basariliysa)
#   glm_url         : Zhipu Z.ai GLM-V (Flash ucretsiz), YouTube baglantisi video_url olarak
#   glm_ses         : Z.ai GLM ASR, ses parcalari
#   siliconflow_ses : SiliconFlow SenseVoice (ucretsiz ASR), ses parcalari
#   kimi_url        : Moonshot Kimi, YouTube baglantisi video_url olarak
#   deepseek        : DeepSeek API video/ses girdisi kabul etmez -> "uygulanamaz" (her calismada
#                     model listesinden yeniden kontrol edilir; anahtar varsa liste cekilir)
# Kanit standardi: Turkce ve >= MIN_TRANSKRIPT karakter. Iki ayri gunde basarili yol "cozum adayi".
# Kisisel veri YOK: yalniz herkese acik video kimligi/basligi, karakter sayilari, kisa onizleme.
import base64
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import youtube_tarama as yt

SURUM = "1.0"
OUT_PATH = os.path.join("data", "youtube_deney.json")
MIN_TRANSKRIPT = yt.MIN_TRANSKRIPT
PARCA_DK = 10
EN_FAZLA_PARCA = 4
SES_PARCA_SN = 300
EN_FAZLA_SES_PARCA = 12
GECMIS_SINIRI = 30
ZAMAN_ASIMI = 300

DASHSCOPE_TABAN = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
ZAI_TABAN = "https://api.z.ai/api/paas/v4"
SILICONFLOW_TABAN = "https://api.siliconflow.com/v1"
MOONSHOT_TABAN = "https://api.moonshot.ai/v1"
DEEPSEEK_TABAN = "https://api.deepseek.com"

ISTEM = ("Bu Turkce YouTube videosundaki konusmanin TAM ve kelimesi kelimesine transkriptini yaz. "
         "Ozetleme, kisaltma, baslik veya yorum ekleme; yalniz konusulan metni duz yazi olarak ver.")

ANAHTARLAR = ("GOOGLE_API_KEY", "YOUTUBE_API_KEY", "DASHSCOPE_API_KEY", "ZAI_API_KEY",
              "SILICONFLOW_API_KEY", "MOONSHOT_API_KEY", "DEEPSEEK_API_KEY")


def gizle(s):
    s = str(s)
    for k in ANAHTARLAR:
        v = os.environ.get(k, "").strip()
        if v:
            s = s.replace(v, "***")
    return yt.anahtar_gizle(s)


def turkce_mu(metin):
    """Turkceye ozgu harf orani ve sik kelimelerle kaba dil kontrolu."""
    if not metin:
        return False
    harf = sum(1 for c in metin if c.isalpha())
    if harf == 0:
        return False
    ozel = sum(1 for c in metin if c in "çğıöşüÇĞİÖŞÜ")
    kelimeler = set(re.findall(r"\w+", metin.lower()))
    sik = {"ve", "bir", "bu", "da", "de", "için", "ama", "çok", "olarak", "ne", "var"}
    return ozel / harf > 0.02 and len(kelimeler & sik) >= 3


def sonuc(ad, durum, metin="", not_="", sure=0.0, ek=None):
    metin = metin or ""
    d = {"ad": ad, "durum": durum, "karakter": len(metin), "turkce": turkce_mu(metin),
         "sure_sn": round(sure, 1), "not": gizle(not_)[:400], "onizleme": metin[:400]}
    if ek:
        d.update(ek)
    if durum == "deneniyor":
        d["durum"] = "basarili" if (len(metin) >= MIN_TRANSKRIPT and d["turkce"]) else "kisa"
    return d


def anahtar(k):
    return os.environ.get(k, "").strip()


def post_json(url, govde, basliklar, timeout=ZAMAN_ASIMI):
    req = urllib.request.Request(url, data=json.dumps(govde).encode("utf-8"), method="POST",
                                 headers=dict({"Content-Type": "application/json"}, **basliklar))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def hata_metni(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            g = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            g = ""
        return gizle("HTTP %s %s" % (e.code, g))
    return gizle("%s: %s" % (type(e).__name__, e))


def openai_sohbet_metni(txt):
    """OpenAI uyumlu yanit: tek JSON ya da SSE akisi (data: ... satirlari)."""
    txt = txt.strip()
    if txt.startswith("{"):
        d = json.loads(txt)
        return ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    parca = []
    for satir in txt.splitlines():
        satir = satir.strip()
        if not satir.startswith("data:"):
            continue
        veri = satir[5:].strip()
        if veri == "[DONE]":
            break
        try:
            d = json.loads(veri)
        except ValueError:
            continue
        for c in d.get("choices") or []:
            parca.append(((c.get("delta") or {}).get("content")) or "")
    return "".join(parca)


# ── Video secimi ──
def video_sec():
    url = anahtar("VIDEO_URL")
    if url:
        return {"url": url, "video_id": url.split("v=")[-1][:11], "baslik": "(elle verilen)"}
    try:
        with open(yt.OUT_PATH, encoding="utf-8") as f:
            v = (json.load(f).get("en_yeni_video") or {})
        if v.get("url"):
            return {"url": v["url"], "video_id": v.get("video_id") or v["url"].split("v=")[-1][:11],
                    "baslik": v.get("baslik", "")}
    except Exception:
        pass
    return None


def sure_iso_sn(s):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", s or "")
    if not m:
        return None
    h, dk, sn = (int(x or 0) for x in m.groups())
    return h * 3600 + dk * 60 + sn


def video_suresi(video_id):
    k = anahtar("YOUTUBE_API_KEY")
    if not k:
        return None
    try:
        _, txt = yt.http_get("%s/videos?part=contentDetails&id=%s&key=%s" % (yt.YT_DATA_TABAN, video_id, k),
                             headers={"Accept": "application/json"})
        items = json.loads(txt).get("items") or []
        return sure_iso_sn(items[0]["contentDetails"]["duration"]) if items else None
    except Exception:
        return None


def parca_planla(sure_sn, parca_dk=PARCA_DK, en_fazla=EN_FAZLA_PARCA):
    if not sure_sn:
        sure_sn = parca_dk * 60 * en_fazla
    adim = parca_dk * 60
    plan, bas = [], 0
    while bas < sure_sn and len(plan) < en_fazla:
        plan.append((bas, min(bas + adim, sure_sn)))
        bas += adim
    return plan


# ── Gemini ──
def gemini_cagir(model, video_url, bas=None, bit=None):
    meta = {"fps": 0.1}
    if bas is not None:
        meta["startOffset"] = "%ds" % bas
        meta["endOffset"] = "%ds" % bit
    govde = {"contents": [{"role": "user", "parts": [
        {"fileData": {"fileUri": video_url}, "videoMetadata": meta}, {"text": ISTEM}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 32768, "responseMimeType": "text/plain"}}
    url = "%s/models/%s:generateContent?key=%s" % (yt.GEMINI_TABAN, model, anahtar("GOOGLE_API_KEY"))
    _, txt = yt.http_post_json(url, govde)
    return yt._gemini_cevap_metni(txt)


def gemini_ilk_calisan(video_url, bas=None, bit=None, notlar=None):
    for model in yt.gemini_modelleri(anahtar("GOOGLE_API_KEY")):
        if model in yt.TUKENEN:
            continue
        try:
            metin, bitis = gemini_cagir(model, video_url, bas, bit)
            return model, metin or "", bitis
        except urllib.error.HTTPError as e:
            m = hata_metni(e)
            if notlar is not None:
                notlar.append("%s: %s" % (model, m[:120]))
            if e.code == 429 and "PerDay" in m:
                yt.TUKENEN.add(model)
        except Exception as e:
            if notlar is not None:
                notlar.append("%s: %s" % (model, hata_metni(e)[:120]))
    return None, "", None


def deney_gemini_teshis(video):
    if not anahtar("GOOGLE_API_KEY"):
        return sonuc("gemini_teshis", "anahtar_yok")
    t0, notlar = time.time(), []
    model, metin, bitis = gemini_ilk_calisan(video["url"], notlar=notlar)
    if model is None:
        return sonuc("gemini_teshis", "hata", not_="; ".join(notlar), sure=time.time() - t0)
    return sonuc("gemini_teshis", "deneniyor", metin, "model=%s bitis=%s" % (model, bitis),
                 time.time() - t0)


def deney_gemini_parca(video, sure_sn):
    if not anahtar("GOOGLE_API_KEY"):
        return sonuc("gemini_parca", "anahtar_yok")
    t0, notlar, parcalar, toplam = time.time(), [], [], []
    for bas, bit in parca_planla(sure_sn):
        model, metin, bitis = gemini_ilk_calisan(video["url"], bas, bit, notlar)
        parcalar.append({"bas": bas, "bit": bit, "model": model, "karakter": len(metin), "bitis": bitis})
        toplam.append(metin)
        if model is None:
            break
    metin = "\n".join(toplam)
    durum = "deneniyor" if any(p["model"] for p in parcalar) else "hata"
    return sonuc("gemini_parca", durum, metin, "; ".join(notlar), time.time() - t0, {"parcalar": parcalar})


# ── yt-dlp ──
def ytdlp_var():
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=30, check=True)
        return True
    except Exception:
        return False


def vtt_metin(vtt):
    satirlar, onceki = [], None
    for s in vtt.splitlines():
        s = s.strip()
        if not s or s.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in s or s.isdigit():
            continue
        s = re.sub(r"<[^>]+>", "", s).strip()
        if s and s != onceki:
            satirlar.append(s)
            onceki = s
    return " ".join(satirlar)


def deney_ytdlp_altyazi(video, klasor):
    if not ytdlp_var():
        return sonuc("ytdlp_altyazi", "hata", not_="yt-dlp kurulu degil")
    t0 = time.time()
    cikti = os.path.join(klasor, "alt")
    p = subprocess.run(["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "tr.*",
                        "--sub-format", "vtt", "-o", cikti, video["url"]],
                       capture_output=True, text=True, timeout=180)
    dosyalar = glob.glob(cikti + "*.vtt")
    if not dosyalar:
        return sonuc("ytdlp_altyazi", "hata", not_=(p.stderr or p.stdout)[-400:], sure=time.time() - t0)
    with open(dosyalar[0], encoding="utf-8", errors="replace") as f:
        metin = vtt_metin(f.read())
    return sonuc("ytdlp_altyazi", "deneniyor", metin, os.path.basename(dosyalar[0]), time.time() - t0)


def deney_ytdlp_ses(video, klasor):
    """Basariliysa (sonuc, [parca_yollari]) doner."""
    if not ytdlp_var():
        return sonuc("ytdlp_ses", "hata", not_="yt-dlp kurulu degil"), []
    t0 = time.time()
    hedef = os.path.join(klasor, "ses.%(ext)s")
    p = subprocess.run(["yt-dlp", "-f", "ba[ext=m4a]/ba/b", "-o", hedef, video["url"]],
                       capture_output=True, text=True, timeout=600)
    dosyalar = [d for d in glob.glob(os.path.join(klasor, "ses.*")) if not d.endswith(".part")]
    if not dosyalar:
        return sonuc("ytdlp_ses", "hata", not_=(p.stderr or p.stdout)[-400:], sure=time.time() - t0), []
    desen = os.path.join(klasor, "parca_%03d.mp3")
    q = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", dosyalar[0], "-vn", "-ac", "1", "-ar", "16000",
                        "-b:a", "32k", "-f", "segment", "-segment_time", str(SES_PARCA_SN), desen],
                       capture_output=True, text=True, timeout=600)
    parcalar = sorted(glob.glob(os.path.join(klasor, "parca_*.mp3")))[:EN_FAZLA_SES_PARCA]
    d = sonuc("ytdlp_ses", "basarili" if parcalar else "hata",
              not_="ses indirildi; %d parca%s" % (len(parcalar), (" ffmpeg: " + q.stderr[-200:]) if q.returncode else ""),
              sure=time.time() - t0)
    return d, parcalar


# ── Cin modelleri ──
def url_video_deneyi(ad, anahtar_adi, taban, model_env, varsayilan_model, akis=False):
    k = anahtar(anahtar_adi)
    if not k:
        return lambda video: sonuc(ad, "anahtar_yok", not_="%s secret'i tanimli degil" % anahtar_adi)

    def calis(video):
        model = anahtar(model_env) or varsayilan_model
        t0 = time.time()
        govde = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
            {"type": "video_url", "video_url": {"url": video["url"]}}, {"type": "text", "text": ISTEM}]}]}
        if akis:
            govde["stream"] = True
            govde["modalities"] = ["text"]
        try:
            txt = post_json(taban + "/chat/completions", govde, {"Authorization": "Bearer " + k})
            return sonuc(ad, "deneniyor", openai_sohbet_metni(txt), "model=" + model, time.time() - t0)
        except Exception as e:
            return sonuc(ad, "hata", not_="model=%s %s" % (model, hata_metni(e)), sure=time.time() - t0)
    return calis


def multipart(alanlar, dosya_alani, dosya_yolu):
    sinir = "----bistdeney%d" % int(time.time() * 1000)
    govde = bytearray()
    for a, v in alanlar.items():
        govde += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (sinir, a, v)).encode()
    with open(dosya_yolu, "rb") as f:
        veri = f.read()
    govde += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
              "Content-Type: audio/mpeg\r\n\r\n" % (sinir, dosya_alani, os.path.basename(dosya_yolu))).encode()
    govde += veri + ("\r\n--%s--\r\n" % sinir).encode()
    return bytes(govde), "multipart/form-data; boundary=" + sinir


def transkripsiyon_post(url, k, model, yol, ek_alan=None):
    alanlar = {"model": model}
    alanlar.update(ek_alan or {})
    govde, tur = multipart(alanlar, "file", yol)
    req = urllib.request.Request(url, data=govde, method="POST",
                                 headers={"Authorization": "Bearer " + k, "Content-Type": tur})
    with urllib.request.urlopen(req, timeout=ZAMAN_ASIMI) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    return d.get("text") or ""


def qwen_ses_parca(k, model, yol):
    with open(yol, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    govde = {"model": model, "stream": True, "messages": [{"role": "user", "content": [
        {"type": "input_audio", "input_audio": {"data": "data:audio/mpeg;base64," + b64}}]}],
        "asr_options": {"language": "tr", "enable_itn": False}}
    return openai_sohbet_metni(post_json(DASHSCOPE_TABAN + "/chat/completions", govde,
                                         {"Authorization": "Bearer " + k}))


def ses_deneyi(ad, anahtar_adi, model_env, varsayilan_model, parca_fonk):
    def calis(parcalar):
        k = anahtar(anahtar_adi)
        if not k:
            return sonuc(ad, "anahtar_yok", not_="%s secret'i tanimli degil" % anahtar_adi)
        if not parcalar:
            return sonuc(ad, "ses_yok", not_="ytdlp_ses basarisiz; ses parcasi olmadan denenemedi")
        model = anahtar(model_env) or varsayilan_model
        t0, metinler, notlar = time.time(), [], []
        for yol in parcalar:
            try:
                metinler.append(parca_fonk(k, model, yol))
            except Exception as e:
                notlar.append(hata_metni(e)[:150])
                if len(notlar) >= 2 and not any(metinler):
                    break
        durum = "deneniyor" if any(metinler) else "hata"
        return sonuc(ad, durum, "\n".join(metinler), "model=%s %s" % (model, "; ".join(notlar)),
                     time.time() - t0)
    return calis


def deney_deepseek():
    k = anahtar("DEEPSEEK_API_KEY")
    gerekce = "DeepSeek API yalniz metin kabul ediyor (video/ses girdisi yok)"
    if not k:
        return sonuc("deepseek", "uygulanamaz", not_=gerekce + "; anahtar da yok")
    try:
        req = urllib.request.Request(DEEPSEEK_TABAN + "/models", headers={"Authorization": "Bearer " + k})
        with urllib.request.urlopen(req, timeout=60) as r:
            modeller = [m.get("id") for m in json.loads(r.read().decode()).get("data", [])]
        cok = [m for m in modeller if re.search(r"vl|vision|omni|audio|asr", m or "", re.I)]
        if cok:
            return sonuc("deepseek", "aday", not_="cok kipli model goruldu: %s" % ", ".join(cok))
        return sonuc("deepseek", "uygulanamaz", not_=gerekce + "; modeller: " + ", ".join(modeller))
    except Exception as e:
        return sonuc("deepseek", "hata", not_=hata_metni(e))


# ── Gecmis ve cikti ──
def onceki():
    try:
        with open(OUT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def gecmis_guncelle(gecmis, deneyler, tarih):
    gecmis = dict(gecmis or {})
    for d in deneyler:
        g = gecmis.setdefault(d["ad"], [])
        g.append({"tarih": tarih, "durum": d["durum"], "karakter": d["karakter"]})
        del g[:-GECMIS_SINIRI]
    return gecmis


def cozum_adaylari(gecmis):
    adaylar = []
    for ad, g in gecmis.items():
        gunler = {x["tarih"][:10] for x in g if x["durum"] == "basarili"}
        if len(gunler) >= 2:
            adaylar.append(ad)
    return sorted(adaylar)


def calistir():
    simdi = datetime.datetime.now(datetime.timezone.utc).isoformat()
    eski = onceki()
    video = video_sec()
    if not video:
        return {"surum": SURUM, "uretim_zamani_utc": simdi, "hata": "video bulunamadi",
                "deneyler": [], "gecmis": eski.get("gecmis", {}), "cozum_adaylari": eski.get("cozum_adaylari", [])}
    sure_sn = video_suresi(video["video_id"])
    deneyler = []

    def guvenli(fonk, *a):
        try:
            return fonk(*a)
        except Exception as e:
            ad = getattr(fonk, "__name__", "deney").replace("deney_", "")
            return sonuc(ad, "hata", not_="beklenmeyen: " + hata_metni(e))

    with tempfile.TemporaryDirectory() as klasor:
        deneyler.append(guvenli(deney_gemini_teshis, video))
        deneyler.append(guvenli(deney_gemini_parca, video, sure_sn))
        deneyler.append(guvenli(deney_ytdlp_altyazi, video, klasor))
        try:
            ses_sonuc, parcalar = deney_ytdlp_ses(video, klasor)
        except Exception as e:
            ses_sonuc, parcalar = sonuc("ytdlp_ses", "hata", not_=hata_metni(e)), []
        deneyler.append(ses_sonuc)
        deneyler.append(guvenli(url_video_deneyi("qwen_url", "DASHSCOPE_API_KEY", DASHSCOPE_TABAN,
                                                 "QWEN_VIDEO_MODEL", "qwen3.5-omni-plus", akis=True), video))
        deneyler.append(guvenli(ses_deneyi("qwen_ses", "DASHSCOPE_API_KEY", "QWEN_ASR_MODEL",
                                           "qwen3-asr-flash", qwen_ses_parca), parcalar))
        deneyler.append(guvenli(url_video_deneyi("glm_url", "ZAI_API_KEY", ZAI_TABAN,
                                                 "GLM_VIDEO_MODEL", "glm-4.6v-flash"), video))
        deneyler.append(guvenli(ses_deneyi(
            "glm_ses", "ZAI_API_KEY", "GLM_ASR_MODEL", "glm-asr",
            lambda k, m, y: transkripsiyon_post(ZAI_TABAN + "/audio/transcriptions", k, m, y)), parcalar))
        deneyler.append(guvenli(ses_deneyi(
            "siliconflow_ses", "SILICONFLOW_API_KEY", "SILICONFLOW_ASR_MODEL", "FunAudioLLM/SenseVoiceSmall",
            lambda k, m, y: transkripsiyon_post(SILICONFLOW_TABAN + "/audio/transcriptions", k, m, y)), parcalar))
        deneyler.append(guvenli(url_video_deneyi("kimi_url", "MOONSHOT_API_KEY", MOONSHOT_TABAN,
                                                 "KIMI_VIDEO_MODEL", "kimi-k2.5"), video))
        deneyler.append(guvenli(deney_deepseek))

    gecmis = gecmis_guncelle(eski.get("gecmis"), deneyler, simdi)
    return {"surum": SURUM, "uretim_zamani_utc": simdi,
            "video": {"video_id": video["video_id"], "baslik": video.get("baslik", ""), "sure_sn": sure_sn},
            "deneyler": deneyler, "basarili_yollar": [d["ad"] for d in deneyler if d["durum"] == "basarili"],
            "gecmis": gecmis, "cozum_adaylari": cozum_adaylari(gecmis), "hata": None}


def main():
    try:
        cikti = calistir()
    except Exception as e:
        cikti = dict(onceki(), surum=SURUM, uretim_zamani_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     hata="beklenmeyen: " + hata_metni(e))
    try:
        os.makedirs("data", exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(cikti, f, ensure_ascii=False, indent=1)
        for d in cikti.get("deneyler", []):
            print("%-16s %-12s %6d krk  %s" % (d["ad"], d["durum"], d["karakter"], d["not"][:150]))
        print("cozum_adaylari:", cikti.get("cozum_adaylari"))
    except Exception as e:
        print("JSON yazilamadi:", e)
    sys.exit(0)


if __name__ == "__main__":
    main()
