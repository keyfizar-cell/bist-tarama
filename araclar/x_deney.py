#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# araclar/x_deney.py  v1.0  (2026-11-15)
# X/Twitter UCRETSIZ yol yoklamasi (Alpay karari 15.11.2026: "X'i ucretsiz yollarla devam ettirelim").
# Hesap/cerez/ucretli API KULLANMAZ. GitHub Actions'tan su herkese acik uclari dener ve sonucu
# data/x_deney.json'a yazar: X oEmbed (resmi, tek tweet), X embed syndication (tweet + profil zaman
# cizelgesi), Telegram herkese acik kanal onizlemesi (t.me/s/), Bluesky herkese acik arama API'si.
# nitter/xcancel yansilari KULLANILMAZ. Her durumda JSON yazar, exit(0).
import datetime
import json
import os
import re
import sys
import urllib.request

OUT = os.path.join("data", "x_deney.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
ORNEK_TWEET = os.environ.get("X_ORNEK_TWEET", "https://twitter.com/jack/status/20")
ORNEK_HESAP = os.environ.get("X_ORNEK_HESAP", "borsacoo")
ORNEK_TELEGRAM = os.environ.get("X_ORNEK_TELEGRAM", "durov")


def getir(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")[:300]
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def tweet_id(url):
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else ""


def deneyler():
    out = []
    kod, txt = getir("https://publish.twitter.com/oembed?omit_script=1&url=" + ORNEK_TWEET)
    metin = re.sub(r"<[^>]+>", " ", json.loads(txt).get("html", "")) if kod == 200 else ""
    out.append({"ad": "x_oembed", "http": kod, "basarili": bool(metin.strip()), "onizleme": metin[:300] or txt[:300]})
    kod, txt = getir("https://cdn.syndication.twimg.com/tweet-result?lang=tr&token=4&id=" + tweet_id(ORNEK_TWEET))
    ok = kod == 200 and '"text"' in txt
    out.append({"ad": "x_syndication_tweet", "http": kod, "basarili": ok, "onizleme": txt[:300]})
    kod, txt = getir("https://syndication.twitter.com/srv/timeline-profile/screen-name/" + ORNEK_HESAP)
    n = len(re.findall(r'"full_text"', txt)) if kod == 200 else 0
    out.append({"ad": "x_syndication_profil", "http": kod, "basarili": n > 0, "tweet_sayisi": n,
                "onizleme": txt[:300] if n == 0 else ""})
    kod, txt = getir("https://t.me/s/" + ORNEK_TELEGRAM)
    n = len(re.findall(r'tgme_widget_message_text', txt)) if kod == 200 else 0
    out.append({"ad": "telegram_onizleme", "http": kod, "basarili": n > 0, "mesaj_sayisi": n})
    kod, txt = getir("https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?lang=tr&limit=10&q=borsa%20hisse")
    n = len(json.loads(txt).get("posts", [])) if kod == 200 else 0
    out.append({"ad": "bluesky_arama", "http": kod, "basarili": n > 0, "gonderi_sayisi": n,
                "onizleme": "" if n else txt[:300]})
    return out


def main():
    try:
        d = {"surum": "1.0", "uretim_zamani_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "deneyler": deneyler(), "hata": None}
    except Exception as e:
        d = {"surum": "1.0", "deneyler": [], "hata": "%s: %s" % (type(e).__name__, e)}
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    for x in d["deneyler"]:
        print(x["ad"], x["http"], x["basarili"])
    sys.exit(0)


if __name__ == "__main__":
    main()
