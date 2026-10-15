#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KAP bildirim toplayıcı — keyfizar-cell/bist-tarama

Portföy (ve istenirse ek) BIST kodları için son N günün KAP bildirimlerini
kap-client (ücretsiz, MIT lisanslı, API anahtarı/giriş GEREKTİRMEZ) ile çeker
ve data/kap.json dosyasına yazar. Sabah/akşam bültenleri bu dosyayı
raw.githubusercontent.com üzerinden okuyabilir (KAP'a WebFetch-okunur yedek).

GÜVENLİK TASARIMI (önemli):
  • Bu script ANA taramadan (tarama.py) TAMAMEN BAĞIMSIZDIR ve onu ETKİLEMEZ.
  • Hata olsa bile HER ZAMAN data/kap.json yazar (boş da olsa) ve SIFIR çıkışla
    biter — bağlı olduğu iş akışını (workflow) asla düşürmez.
  • Her kod ayrı try/except içinde; bir kodun hatası diğerlerini etkilemez.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

# ───────────────────────── AYARLAR (düzenlenebilir) ─────────────────────────
# Portföy BIST kodları. NVO (NYSE) KAP kapsamında olmadığı için HARİÇ.
# Drive'daki portföyle ELLE eşitlenir; kod eklemek/çıkarmak için bu listeyi
# düzenle. (Koza unvan değişikliği: KOZAL→TRALT, KOZAA→TRMET, IPEKE→TRENJ —
# portföyde varsa YENİ kodu yaz.)
PORTFOY: list[str] = [
    "AKBNK", "BLUME", "CANTE", "ENKAI", "HEKTS", "KRDMD", "OBAMS",
    "PAPIL", "SOHOE", "TTKOM", "ULUUN", "VAKBN", "YIGIT",
]

# İstenirse ek izlenecek kodlar (ör. BIST30 üyeleri). Boş bırakılabilir.
# Örnek: EK_KODLAR = ["THYAO", "GARAN", "ASELS", "EREGL", "KCHOL", "SISE"]
EK_KODLAR: list[str] = []

GUN_PENCERESI = 4        # son kaç günün bildirimleri taransın (hafta sonu payı)
KOD_BASI_LIMIT = 15      # kod başına en fazla bildirim (en yeniden)
TIMEOUT = 30.0           # kap-client istek zaman aşımı (saniye)
CIKTI = "data/kap.json"
# ─────────────────────────────────────────────────────────────────────────────


def _yaz(cikti: dict) -> None:
    os.makedirs("data", exist_ok=True)
    with open(CIKTI, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print(
        "data/kap.json yazıldı: "
        f"{cikti.get('bildirimli_kod_sayisi', '?')}/{cikti.get('hisse_sayisi', '?')} "
        "kodda bildirim var"
    )


def main() -> None:
    # Benzersiz, sırayı koruyan kod listesi
    kodlar: list[str] = []
    for k in PORTFOY + EK_KODLAR:
        k = (k or "").strip().upper()
        if k and k not in kodlar:
            kodlar.append(k)

    bugun = date.today()
    baslangic = bugun - timedelta(days=GUN_PENCERESI)

    cikti: dict = {
        "uretim_zamani_utc": datetime.now(timezone.utc).isoformat(),
        "tarih": bugun.isoformat(),
        "gun_penceresi_gun": GUN_PENCERESI,
        "baslangic": baslangic.isoformat(),
        "kaynak": "KAP (kap-client)",
        "kodlar": {},
        "notlar": [],
    }

    try:
        from kap_client import (
            Kap,
            EmptyResponseError,
            CompanyNotFoundError,
            RateLimitError,
            KapError,
        )
    except Exception as e:  # kütüphane yoksa bile dosya yaz
        cikti["notlar"].append(f"kap-client import edilemedi: {e!r}")
        cikti["hisse_sayisi"] = 0
        cikti["bildirimli_kod_sayisi"] = 0
        _yaz(cikti)
        return

    try:
        with Kap(timeout=TIMEOUT) as kap:
            for kod in kodlar:
                try:
                    diz = kap.fetch_disclosures(kod, baslangic, bugun)
                    kayitlar = []
                    for d in diz[:KOD_BASI_LIMIT]:
                        pz = getattr(d, "publish_datetime", None)
                        kayitlar.append({
                            "no": getattr(d, "index", None),
                            "zaman": pz.isoformat() if pz else None,
                            "tur": getattr(d, "disclosure_type", None),
                            "konu": getattr(d, "subject", None),
                            "ozet": (getattr(d, "summary", None) or None),
                            "sirket": getattr(d, "company_name", None),
                            "gecikmeli": bool(getattr(d, "is_late", False)),
                            "duzeltme": bool(getattr(d, "is_corrective", False)),
                            "ek_var": bool(getattr(d, "has_attachment", False)),
                            "url": getattr(d, "url", None),
                        })
                    cikti["kodlar"][kod] = kayitlar
                except EmptyResponseError:
                    cikti["kodlar"][kod] = []  # pencerede bildirim yok (normal)
                except CompanyNotFoundError:
                    cikti["kodlar"][kod] = []
                    cikti["notlar"].append(
                        f"{kod}: KAP'ta bulunamadı (kod değişmiş/delist olabilir)"
                    )
                except RateLimitError as e:
                    cikti["kodlar"][kod] = []
                    cikti["notlar"].append(f"{kod}: hız sınırı — {e!r}")
                except Exception as e:  # tek kod hatası diğerlerini durdurmaz
                    cikti["kodlar"][kod] = []
                    cikti["notlar"].append(f"{kod}: hata {e!r}")
    except Exception as e:
        cikti["notlar"].append(
            f"KAP oturumu genel hata: {e!r} :: {traceback.format_exc(limit=2)}"
        )

    cikti["hisse_sayisi"] = len(cikti["kodlar"])
    cikti["bildirimli_kod_sayisi"] = sum(1 for v in cikti["kodlar"].values() if v)
    _yaz(cikti)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # son güvenlik ağı — yine de dosya yaz, sıfır çık
        try:
            _yaz({
                "uretim_zamani_utc": datetime.now(timezone.utc).isoformat(),
                "hata": repr(e),
                "kodlar": {},
                "hisse_sayisi": 0,
                "bildirimli_kod_sayisi": 0,
            })
        except Exception:
            pass
        print("kap_tarama beklenmedik hata:", e, file=sys.stderr)
    # İş akışını ASLA düşürme: her durumda 0 ile çık.
    sys.exit(0)
