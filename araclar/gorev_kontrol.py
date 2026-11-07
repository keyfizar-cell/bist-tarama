#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gorevler/*.md talimat dosyalarinin temel butunluk kontrolu.

Zamanlanmis gorevler bu dosyalari her calismada main'den ceker. Bozuk bir
degisiklik (yanlislikla silinen gonderim satiri, kisalan dosya, EK blogunun
dosyaya tasinmasi) bulteni sessizce bozmasin diye her push'ta calisir.
Hata varsa exit(1).
"""
import os
import sys

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gorevler")
EK_BASLIK = "═══ EK ÜCRETSİZ KAYNAK ENTEGRASYONU"

KURALLAR = {
    "sabah_brifingi.md": {
        "min": 11000,
        "zorunlu": ["TATİL KONTROLÜ", "🌅 Sabah Portföy Brifingi", "mcp__Gmail__send_message",
                    "alpayaydemir@gmail.com", "Yatırım tavsiyesi değildir", "10_TjaYt3hZA57kLTFYFyR6t7zdwOlnzls_yfzuYsUjY"],
        "ek_yasak": True,
    },
    "aksam_bulteni.md": {
        "min": 25000,
        "zorunlu": ["TATİL KONTROLÜ", "📊 Günlük Portföy Bülteni — <GG.AA.YYYY>", "mcp__Gmail__send_message",
                    "alpayaydemir@gmail.com", "send_later", "HARD DEADLINE", "7d · 🎥", "7e · 🎙️",
                    "Yatırım tavsiyesi değildir", "10_TjaYt3hZA57kLTFYFyR6t7zdwOlnzls_yfzuYsUjY"],
        "ek_yasak": True,
    },
    "saglik_nobeti.md": {
        "min": 6000,
        "zorunlu": ["trig_01UjjJQe3p9x4D5SZc484Ryt", "fire_trigger", "PushNotification",
                    "Portföy Bülteni", "youtube_konuk"],
        "ek_yasak": False,
    },
    "veri_kaynagi_arastirma.md": {
        "min": 18000,
        "zorunlu": ["KULLANICI YETKİSİ", "İNCE BAŞLATICI", EK_BASLIK, "GÜVENLİK KURALLARI",
                    "alpayaydemir@gmail.com", "KALDIRILANLAR"],
        "ek_yasak": False,
    },
}


def main():
    hatalar = []
    for ad, k in KURALLAR.items():
        yol = os.path.join(KOK, ad)
        try:
            with open(yol, encoding="utf-8") as f:
                metin = f.read()
        except Exception as e:
            hatalar.append("%s okunamadi: %s" % (ad, e))
            continue
        if len(metin) < k["min"]:
            hatalar.append("%s cok kisa: %d < %d karakter" % (ad, len(metin), k["min"]))
        for z in k["zorunlu"]:
            if z not in metin:
                hatalar.append("%s icinde zorunlu ifade yok: %r" % (ad, z))
        if k["ek_yasak"] and (EK_BASLIK + " (") in metin:
            hatalar.append("%s: EK blogu dosyaya tasinmis; EK blogu zamanlanmis gorevde kalmali" % ad)
        print("%-28s %6d karakter" % (ad, len(metin)))
    if hatalar:
        print("\nHATALAR:")
        for h in hatalar:
            print(" -", h)
        sys.exit(1)
    print("\nTum gorev talimatlari kontrolden gecti.")


if __name__ == "__main__":
    main()
