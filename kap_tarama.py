#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KAP bildirim toplayıcı — keyfizar-cell/bist-tarama  (v2)

Portföy (ve istenirse ek) BIST kodları için son N günün KAP bildirimlerini
kap-client (ücretsiz, MIT, API anahtarı/giriş GEREKTİRMEZ) ile çeker ve
data/kap.json dosyasına yazar. Sabah/akşam bültenleri bu dosyayı
raw.githubusercontent.com üzerinden okuyabilir (KAP'a WebFetch-okunur yedek).

YÖNTEM (v2 — neden değişti):
  v1 her kod için fetch_disclosures(ticker) çağırıyordu; bu kütüphanede
  ticker→şirket çözümlemesi (company/items uç noktası) halka açık hisseleri
  getirmediği için TÜM kodlar "bulunamadı" dönüyordu. v2 bunu bypass eder:
  tarih aralığı için TEK bir piyasa-geneli bildirim sorgusu yapar
  (mkkMemberOidList boş = tüm şirketler), dönen satırları stockCodes alanına
  göre izleme listemizle EŞLEŞTİRİR. Çözümleme uç noktasına hiç bağımlı değil.

GÜVENLİK TASARIMI:
  • ANA taramadan (tarama.py) TAMAMEN BAĞIMSIZDIR, onu ETKİLEMEZ.
  • Hata olsa bile HER ZAMAN data/kap.json yazar ve SIFIR çıkışla biter —
    bağlı iş akışını asla düşürmez.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta, timezone

# ───────────────────────── AYARLAR (düzenlenebilir) ─────────────────────────
# Portföy BIST kodları. NVO (NYSE) KAP kapsamında olmadığı için HARİÇ.
# Drive portföyüyle ELLE eşitlenir. (Koza: KOZAL→TRALT, KOZAA→TRMET, IPEKE→TRENJ)
PORTFOY: list[str] = [
    "AKBNK", "BLUME", "CANTE", "ENKAI", "HEKTS", "KRDMD", "OBAMS",
    "PAPIL", "SOHOE", "TTKOM", "ULUUN", "VAKBN", "YIGIT",
]
# İstenirse ek izlenecek kodlar (ör. BIST30). Boş bırakılabilir.
EK_KODLAR: list[str] = []

GUN_PENCERESI = 4        # son kaç günün bildirimleri (hafta sonu payı)
KOD_BASI_LIMIT = 20      # kod başına en fazla bildirim (en yeniden)
TIMEOUT = 30.0
CIKTI = "data/kap.json"
# ─────────────────────────────────────────────────────────────────────────────


def _yaz(cikti: dict) -> None:
    os.makedirs("data", exist_ok=True)
    with open(CIKTI, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print(
        "data/kap.json yazıldı: "
        f"{cikti.get('bildirimli_kod_sayisi', '?')}/{cikti.get('hisse_sayisi', '?')} kodda bildirim "
        f"(piyasa satırı: {cikti.get('toplam_piyasa_satiri', '?')})"
    )


def _kayit(d) -> dict:
    pz = getattr(d, "publish_datetime", None)
    return {
        "no": getattr(d, "index", None),
        "zaman": pz.isoformat() if pz else None,
        "tur": getattr(d, "disclosure_type", None) or None,
        "konu": getattr(d, "subject", None) or None,
        "ozet": (getattr(d, "summary", None) or None),
        "sirket": getattr(d, "company_name", None) or None,
        "kodlar": getattr(d, "stock_codes", None) or None,
        "gecikmeli": bool(getattr(d, "is_late", False)),
        "duzeltme": bool(getattr(d, "is_corrective", False)),
        "ek_var": bool(getattr(d, "has_attachment", False)),
        "url": getattr(d, "url", None),
    }


def main() -> None:
    izleme: list[str] = []
    for k in PORTFOY + EK_KODLAR:
        k = (k or "").strip().upper()
        if k and k not in izleme:
            izleme.append(k)
    izleme_set = set(izleme)

    bugun = date.today()
    baslangic = bugun - timedelta(days=GUN_PENCERESI)

    cikti: dict = {
        "uretim_zamani_utc": datetime.now(timezone.utc).isoformat(),
        "tarih": bugun.isoformat(),
        "gun_penceresi_gun": GUN_PENCERESI,
        "baslangic": baslangic.isoformat(),
        "kaynak": "KAP (kap-client, piyasa-geneli sorgu + stockCodes filtresi)",
        "kodlar": {k: [] for k in izleme},
        "notlar": [],
    }

    try:
        from kap_client._client import KapHttpClient
        from kap_client._endpoints import (
            MemberDisclosureQueryBody,
            MEMBER_DISCLOSURE_QUERY_URL,
            DisclosureRow,
        )
        from kap_client import Disclosure
    except Exception as e:
        cikti["notlar"].append(f"kap-client import edilemedi: {e!r}")
        cikti["hisse_sayisi"] = len(izleme)
        cikti["bildirimli_kod_sayisi"] = 0
        cikti["toplam_piyasa_satiri"] = 0
        _yaz(cikti)
        return

    def _ds(d: date) -> str:
        return d.isoformat()

    toplam = 0
    try:
        with KapHttpClient(timeout=TIMEOUT) as http:
            body = MemberDisclosureQueryBody(
                fromDate=_ds(baslangic),
                toDate=_ds(bugun),
                mkkMemberOidList=[],   # boş = piyasa geneli (tüm şirketler)
            )
            rows = http.post(MEMBER_DISCLOSURE_QUERY_URL, body)
            toplam = len(rows)
            for raw in rows:
                try:
                    d = Disclosure.from_row(DisclosureRow.model_validate(raw))
                except Exception:
                    continue
                kodlar = [c.strip().upper() for c in (d.stock_codes or "").split(",") if c.strip()]
                for kod in kodlar:
                    if kod in izleme_set:
                        cikti["kodlar"][kod].append(_kayit(d))
        # her kod için en yeniden eskiye sırala + limit
        for kod, lst in cikti["kodlar"].items():
            lst.sort(key=lambda x: (x.get("zaman") or ""), reverse=True)
            cikti["kodlar"][kod] = lst[:KOD_BASI_LIMIT]
    except Exception as e:
        cikti["notlar"].append(
            f"KAP sorgu hatası: {e!r} :: {traceback.format_exc(limit=2)}"
        )

    cikti["toplam_piyasa_satiri"] = toplam
    if toplam == 0:
        cikti["notlar"].append(
            "Piyasa-geneli sorgu 0 satır döndü — tarih aralığı/endpoint kontrol edilmeli."
        )
    cikti["hisse_sayisi"] = len(cikti["kodlar"])
    cikti["bildirimli_kod_sayisi"] = sum(1 for v in cikti["kodlar"].values() if v)
    _yaz(cikti)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            _yaz({
                "uretim_zamani_utc": datetime.now(timezone.utc).isoformat(),
                "hata": repr(e),
                "kodlar": {},
                "hisse_sayisi": 0,
                "bildirimli_kod_sayisi": 0,
                "toplam_piyasa_satiri": 0,
            })
        except Exception:
            pass
        print("kap_tarama beklenmedik hata:", e, file=sys.stderr)
    sys.exit(0)
