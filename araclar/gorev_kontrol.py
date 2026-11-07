#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gorevler/*.md talimat dosyalarinin temel butunluk kontrolu.

Zamanlanmis gorevler bu dosyalari her calismada main'den ceker. Bozuk bir
degisiklik (yanlislikla silinen gonderim satiri, kisalan dosya, EK blogunun
dosyaya tasinmasi) bulteni sessizce bozmasin diye her push'ta calisir.
Hata varsa exit(1).
"""
import os
import re
import sys

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gorevler")
EK_BASLIK = "═══ EK ÜCRETSİZ KAYNAK ENTEGRASYONU"

# Repo HERKESE AÇIK: talimat dosyalarında kişisel veri olmamalı (değerler başlatıcıda tutulur).
KISISEL_DESENLER = [
    (re.compile(r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "e-posta adresi"),
    (re.compile(r"(?<![A-Za-z0-9_-])(?!\w*__)(?=[\w-]*\d)(?=[\w-]*[A-Z])(?=[\w-]*[a-z])[A-Za-z0-9_-]{30,50}(?![A-Za-z0-9_-])"),
     "Drive dosya kimliği benzeri dizi"),
    (re.compile(r"\b(?:HİSSE|KRİPTO|FON) \(\d+\)"), "pozisyon listesi"),
]

KURALLAR = {
    "sabah_brifingi.md": {
        "min": 11000,
        "zorunlu": ["TATİL KONTROLÜ", "🌅 Sabah Portföy Brifingi", "mcp__Gmail__send_message",
                    "{E_POSTA}", "Yatırım tavsiyesi değildir", "{PORTFOY_DOSYA_ID}"],
        "ek_yasak": True,
    },
    "aksam_bulteni.md": {
        "min": 25000,
        "zorunlu": ["TATİL KONTROLÜ", "📊 Günlük Portföy Bülteni — <GG.AA.YYYY>", "mcp__Gmail__send_message",
                    "{E_POSTA}", "send_later", "HARD DEADLINE", "7d · 🎥", "7e · 🎙️",
                    "Yatırım tavsiyesi değildir", "{PORTFOY_DOSYA_ID}", "7f · 📺",
                    "KOÇ NOTLARI", "Yatırımcı Profili (Koç)"],
        "ek_yasak": True,
    },
    "saglik_nobeti.md": {
        "min": 6000,
        "zorunlu": ["trig_01UjjJQe3p9x4D5SZc484Ryt", "fire_trigger", "PushNotification",
                    "Portföy Bülteni", "youtube_konuk", "youtube_kanallar"],
        "ek_yasak": False,
    },
    "veri_kaynagi_arastirma.md": {
        "min": 18000,
        "zorunlu": ["KULLANICI YETKİSİ", "İNCE BAŞLATICI", EK_BASLIK, "GÜVENLİK KURALLARI",
                    "{E_POSTA}", "KALDIRILANLAR"],
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
        for desen, aciklama in KISISEL_DESENLER:
            bul = desen.search(metin)
            if bul:
                hatalar.append("%s: kişisel veri olabilir (%s): %r — repo herkese açık; gerçek değer "
                               "başlatıcının GİZLİ PARAMETRELER bloğuna, dosyaya yer tutucu yazılmalı"
                               % (ad, aciklama, bul.group(0)[:40]))
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
