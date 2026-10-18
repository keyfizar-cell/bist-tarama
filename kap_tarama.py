#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KAP bildirim toplayıcı — keyfizar-cell/bist-tarama  (v3.0)

İKİ ÇIKTI ÜRETİR, HER İKİSİ DE BAĞIMSIZ VE AYRI DOSYA:
  (1) data/kap.json       — v2 ile AYNI: portföy/ek kodlar için son N günün
                            KAP bildirimleri (bültenlerin mevcut KAP yedeği).
                            Mantık ve çıktı biçimi v2 ile BİREBİR aynıdır,
                            DEĞİŞTİRİLMEMİŞTİR → mevcut tüketiciler bozulmaz.
  (2) data/geri_alim.json — YENİ: 01.09.2026'dan bugüne piyasa genelindeki
                            TÜM "Pay Geri Alım" bildirimlerini şirket bazında
                            özetler (Kemal Çağlar Demirtaş'ın X'te paylaştığı
                            geri-alım takip tablosunun KENDİ KAP verimizden
                            üretilen, ona bağımlı OLMAYAN karşılığı).

GÜVENLİK TASARIMI (v2'den devralındı, v3'te de geçerli):
  • ANA taramadan (tarama.py) TAMAMEN BAĞIMSIZDIR, onu ETKİLEMEZ.
  • İki faz da KENDİ içinde try/except ile sarılıdır; biri patlasa bile
    diğeri çalışır. HER İKİ dosya HER DURUMDA yazılır; betik DAİMA sıfır
    çıkışla (sys.exit(0)) biter → bağlı iş akışını ASLA düşürmez.

VERİ DÜRÜSTLÜĞÜ (önemli):
  • Piyasa-geneli bildirim LİSTE sorgusu yalnızca başlık verir:
    tarih, tür, konu, özet (ör. "13.10.2026 Tarihli Pay Geri Alım İşlemleri"),
    şirket, kodlar, url. Lot/adet, ortalama fiyat, tutar, program bütçesi ve
    SERMAYEYE ORANI bu listede YOKTUR — bunlar bildirimin DETAY sayfasındadır.
  • Bu yüzden geri_alim.json İKİ KATMANLIDIR:
      TIER-1 (GÜVENİLİR, her zaman çalışır): şirket bazında geri-alım
        bildirimlerinin listesi + sayısı + program/işlem sınıfı + ilk/son
        tarih + KAP linkleri + portföy/BIST30 işareti + piyasa değeri.
      TIER-2 (EN İYİ ÇABA, varsayılan açık ama ASLA zorunlu değil): yalnız
        PORTFÖY+BIST30 şirketlerinin geri-alım bildirim DETAYINI (get_html)
        çekip lot/fiyat/tutar/sermaye-oranını regex ile ayıklamayı dener;
        başarısızsa veya alan yoksa "veri yok" yazar, Tier-1'e düşer.
    ⚠️ KAP detay sayfası Angular SPA'dır; get_html'in kullanılabilir içerik
    döndürüp döndürmediği YALNIZ GitHub Actions'ta (tam internet) doğrulanır.
    Bulut/yerel ortamdan kap.org.tr 403 verir. İlk Actions çalışmasından sonra
    geri_alim.json'da kumulatif_* alanlarının dolu mu "veri yok" mu olduğunu
    KONTROL ET; hep "veri yok" ise DETAY_DENE=False yapıp Tier-1 ile devam et.
"""
from __future__ import annotations

import json
import os
import re
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
# İstenirse ek izlenecek kodlar (kap.json fazı için; BIST30 geri_alim fazında
# ayrıca işaretlenir). Boş bırakılabilir.
EK_KODLAR: list[str] = []

# BIST30 — YAKLAŞIK liste, düzenlenebilir; güncel endeks bileşimini teyit et.
# (Koza unvan değişikliği: KOZAL→TRALT) Yalnız geri_alim.json'da "bist30" işareti
# ve Tier-2 detay çekme kapsamı için kullanılır.
BIST30: list[str] = [
    "AKBNK", "AKSEN", "ALARK", "ASELS", "ASTOR", "BIMAS", "EKGYO", "ENKAI",
    "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL", "KONTR",
    "KRDMD", "OYAKC", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TCELL",
    "THYAO", "TOASO", "TRALT", "TUPRS", "VAKBN", "YKBNK",
]

# ── kap.json fazı (v2 ile aynı) ──
GUN_PENCERESI = 4        # son kaç günün bildirimleri (hafta sonu payı)
KOD_BASI_LIMIT = 20      # kod başına en fazla bildirim (en yeniden)
CIKTI = "data/kap.json"

# ── geri_alim.json fazı (yeni) ──
GERI_ALIM_BASLANGIC = "2026-09-01"   # geri-alım takibinin başlangıç günü
GERI_ALIM_CIKTI = "data/geri_alim.json"
CHUNK_GUN = 7            # piyasa sorgusunu kaç günlük parçalara böl (olası satır sınırına karşı)
GA_BILDIRIM_LIMIT = 60   # şirket başına geri_alim.json'a yazılacak en fazla bildirim
DETAY_DENE = True        # Tier-2: detay sayfasından lot/fiyat/tutar ayıklamayı dene
DETAY_KAPSAM = "portfoy_bist30"   # "portfoy_bist30" | "portfoy" | "yok"
MAX_DETAY = 50           # Tier-2'de en fazla kaç detay sayfası çekilsin (kibar/hızlı)
TIMEOUT = 30.0

GERI_ALIM_ANAHTAR = ("geri al",)   # konu/özet/tür içinde aranır (küçük harf, TR)
# ─────────────────────────────────────────────────────────────────────────────


def _tr_lower(s: str) -> str:
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  FAZ 1 — kap.json  (v2 ile BİREBİR AYNI; dokunulmadı)                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def _kap_yaz(cikti: dict) -> None:
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


def _kap_fazi() -> None:
    """v2 davranışı: portföy/ek kodlar için son N gün → data/kap.json."""
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
        _kap_yaz(cikti)
        return

    toplam = 0
    try:
        with KapHttpClient(timeout=TIMEOUT) as http:
            body = MemberDisclosureQueryBody(
                fromDate=baslangic.isoformat(),
                toDate=bugun.isoformat(),
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
    _kap_yaz(cikti)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  FAZ 2 — geri_alim.json  (yeni)                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def _ga_yaz(cikti: dict) -> None:
    os.makedirs("data", exist_ok=True)
    with open(GERI_ALIM_CIKTI, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print(
        "data/geri_alim.json yazıldı: "
        f"{cikti.get('sirket_sayisi', '?')} şirkette geri alım, "
        f"{cikti.get('geri_alim_bildirim_sayisi', '?')} bildirim "
        f"(detay denendi: {cikti.get('detay_denendi')}, başarı: {cikti.get('detay_basari_sayisi', 0)})"
    )


def _gunluk_islem_mi(konu: str, ozet: str) -> bool:
    """ 'GG.AA.YYYY Tarihli Pay Geri Alım İşlemleri' kalıbı = günlük işlem bildirimi."""
    blob = f"{konu or ''} {ozet or ''}"
    return bool(re.search(r"\d{1,2}\.\d{2}\.\d{4}\s*Tarihli\s*Pay\s*Geri\s*Al", blob, re.IGNORECASE))


def _program_mi(konu: str, ozet: str) -> bool:
    b = _tr_lower(f"{konu or ''} {ozet or ''}")
    return ("program" in b) or ("geri alım karar" in b) or ("geri alim karar" in b) \
        or ("çerçevesinde" in b and "geri al" in b)


_SAYI = r"[0-9][0-9\.]*(?:,[0-9]+)?"

def _tr_sayi(s: str):
    """ '1.234.567,89' → 1234567.89 ; başarısızsa None. """
    if not s:
        return None
    s = s.strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _detay_parse_html(html: str) -> dict:
    """KAP geri-alım detay HTML'inden lot/fiyat/tutar/sermaye-oranı ayıklamayı
    DENER. Bulunamayan alan None döner (çağıran 'veri yok' yazar). SPA içeriği
    gelmezse hepsi None olur — bu beklenen bir durumdur, hata değildir."""
    # Not: fiyat/fiyat-aralığı KASITLI çıkarılmıyor — TR binlik ayraçlı sayılar
    # (ör. "648.500,00") naif regex ile fiyat ("500,00") gibi görünüp yanıltıyor.
    # Görevin istediği sayısal alanlar lot/tutar/sermaye oranıdır; fiyat gerekmez.
    out = {"lot": None, "tutar": None, "sermaye_orani": None}
    if not html or len(html) < 40:
        return out
    metin = re.sub(r"<[^>]+>", " ", html)          # etiketleri at
    metin = re.sub(r"\s+", " ", metin)
    d = _tr_lower(metin)

    def yakala(anahtarlar, pencere_boy=120, desen=_SAYI, birden=False):
        for a in anahtarlar:
            i = d.find(a)
            if i < 0:
                continue
            pencere = metin[i + len(a):i + len(a) + pencere_boy]
            sayilar = re.findall(desen, pencere)
            if sayilar:
                return sayilar if birden else sayilar[0]
        return None

    lot = yakala(["nominal", "pay adedi", "nominal tutar", "adet"])
    out["lot"] = _tr_sayi(lot) if lot else None
    tutar = yakala(["işlem tutarı", "toplam tutar", "alım tutarı", "ödenen"])
    out["tutar"] = _tr_sayi(tutar) if tutar else None
    oran = yakala(["sermayeye oran", "sermaye oran", "ödenmiş sermaye"], pencere_boy=90)
    out["sermaye_orani"] = _tr_sayi(oran) if oran else None
    return out


def _piyasa_degeri_haritasi() -> dict:
    """latest.json'dan {KOD: (piyasa_degeri, kapanis)} — yoksa boş."""
    harita: dict = {}
    for yol in ("data/latest.json", "data/latest.json"):
        try:
            with open(yol, encoding="utf-8") as f:
                lt = json.load(f)
            for h in lt.get("tum_hisseler", []) or []:
                kod = (h.get("kod") or "").strip().upper()
                if kod:
                    harita[kod] = (h.get("piyasa_degeri"), h.get("kapanis"))
            break
        except Exception:
            continue
    return harita


def _ga_derle(kayitlar: list[dict], pd_harita: dict,
              portfoy_set: set, bist30_set: set) -> dict:
    """Geri-alım bildirim kayıtlarını (dict listesi) şirket bazında özetler.
    SAF fonksiyon (ağ yok) → mock ile test edilebilir. Her kayıt:
      {no, zaman, tur, konu, ozet, sirket, kodlar(str), url}
    """
    sirketler: dict = {}
    for r in kayitlar:
        kodlar = [c.strip().upper() for c in (r.get("kodlar") or "").split(",") if c.strip()]
        if not kodlar:
            continue
        konu, ozet = r.get("konu") or "", r.get("ozet") or ""
        gunluk = _gunluk_islem_mi(konu, ozet)
        program = _program_mi(konu, ozet) and not gunluk
        for kod in kodlar:
            s = sirketler.setdefault(kod, {
                "kod": kod, "sirket": r.get("sirket"),
                "portfoyde": kod in portfoy_set, "bist30": kod in bist30_set,
                "bildirimler": [], "islem_bildirim_sayisi": 0,
                "program_bildirim_sayisi": 0,
            })
            if not s.get("sirket"):
                s["sirket"] = r.get("sirket")
            s["bildirimler"].append({
                "tarih": (r.get("zaman") or "")[:10], "zaman": r.get("zaman"),
                "tur": r.get("tur"), "konu": konu, "ozet": ozet,
                "sinif": "program/karar" if program else ("işlem" if gunluk else "diğer"),
                "url": r.get("url"),
            })
            if gunluk:
                s["islem_bildirim_sayisi"] += 1
            if program:
                s["program_bildirim_sayisi"] += 1

    for kod, s in sirketler.items():
        s["bildirimler"].sort(key=lambda x: (x.get("zaman") or ""), reverse=True)
        tarihler = [b["zaman"] for b in s["bildirimler"] if b.get("zaman")]
        s["son_bildirim_tarih"] = (max(tarihler) or "")[:10] if tarihler else None
        s["ilk_bildirim_tarih"] = (min(tarihler) or "")[:10] if tarihler else None
        s["toplam_bildirim"] = len(s["bildirimler"])
        pd, kap = pd_harita.get(kod, (None, None))
        s["piyasa_degeri"] = pd
        s["kapanis"] = kap
        # Tier-2 alanları (varsayılan "veri yok"; detay fazı doldurur)
        s["kumulatif_lot"] = "veri yok"
        s["kumulatif_tutar_tl"] = "veri yok"
        s["sermaye_orani_yuzde"] = "veri yok"
        s["piyasa_degeri_orani_yuzde"] = "veri yok"
        s["bildirimler"] = s["bildirimler"][:GA_BILDIRIM_LIMIT]

    return sirketler


def _ga_fazi() -> None:
    bugun = date.today()
    try:
        baslangic = datetime.strptime(GERI_ALIM_BASLANGIC, "%Y-%m-%d").date()
    except Exception:
        baslangic = bugun - timedelta(days=45)

    cikti: dict = {
        "uretim_zamani_utc": datetime.now(timezone.utc).isoformat(),
        "tarih": bugun.isoformat(),
        "baslangic": baslangic.isoformat(),
        "kaynak": "KAP (kap-client, piyasa-geneli 'Pay Geri Alım' bildirimleri)",
        "aciklama": ("Tier-1 (güvenilir): bildirim listesi/sayısı/sınıfı/link. "
                     "Tier-2 (en iyi çaba): detaydan lot/fiyat/tutar/sermaye oranı "
                     "— SPA nedeniyle 'veri yok' olabilir, yalnız Actions'ta doğrulanır."),
        "detay_denendi": False, "detay_basari_sayisi": 0,
        "toplam_piyasa_satiri": 0, "geri_alim_bildirim_sayisi": 0,
        "sirket_sayisi": 0, "sirketler": {}, "portfoy_ozet": {}, "notlar": [],
    }

    try:
        from kap_client._client import KapHttpClient
        from kap_client._endpoints import (
            MemberDisclosureQueryBody, MEMBER_DISCLOSURE_QUERY_URL, DisclosureRow,
        )
        from kap_client import Disclosure
    except Exception as e:
        cikti["notlar"].append(f"kap-client import edilemedi: {e!r}")
        _ga_yaz(cikti)
        return

    portfoy_set = {k.strip().upper() for k in PORTFOY}
    bist30_set = {k.strip().upper() for k in BIST30}
    pd_harita = _piyasa_degeri_haritasi()
    if not pd_harita:
        cikti["notlar"].append("latest.json okunamadı → piyasa değeri oranları 'veri yok'.")

    ga_kayitlar: list[dict] = []
    gorulen_no: set = set()
    toplam_satir = 0

    try:
        with KapHttpClient(timeout=TIMEOUT) as http:
            # tarih aralığını CHUNK_GUN'lük parçalara böl (olası satır sınırına karşı)
            p0 = baslangic
            while p0 <= bugun:
                p1 = min(p0 + timedelta(days=CHUNK_GUN - 1), bugun)
                try:
                    body = MemberDisclosureQueryBody(
                        fromDate=p0.isoformat(), toDate=p1.isoformat(),
                        mkkMemberOidList=[],
                    )
                    rows = http.post(MEMBER_DISCLOSURE_QUERY_URL, body)
                    toplam_satir += len(rows)
                    for raw in rows:
                        try:
                            d = Disclosure.from_row(DisclosureRow.model_validate(raw))
                        except Exception:
                            continue
                        blob = _tr_lower(f"{d.disclosure_type or ''} {d.subject or ''} {d.summary or ''}")
                        if not any(a in blob for a in GERI_ALIM_ANAHTAR):
                            continue
                        no = getattr(d, "index", None)
                        if no in gorulen_no:
                            continue
                        gorulen_no.add(no)
                        ga_kayitlar.append(_kayit(d))
                except Exception as e:
                    cikti["notlar"].append(f"parça {p0}..{p1} hatası: {e!r}")
                p0 = p1 + timedelta(days=1)

            cikti["toplam_piyasa_satiri"] = toplam_satir
            cikti["geri_alim_bildirim_sayisi"] = len(ga_kayitlar)

            sirketler = _ga_derle(ga_kayitlar, pd_harita, portfoy_set, bist30_set)

            # ── Tier-2: detay sayfasından sayısal ayıklama (en iyi çaba) ──
            if DETAY_DENE and DETAY_KAPSAM != "yok":
                cikti["detay_denendi"] = True
                if DETAY_KAPSAM == "portfoy":
                    kapsam = portfoy_set
                else:
                    kapsam = portfoy_set | bist30_set
                basari = 0
                cekilen = 0
                for kod, s in sirketler.items():
                    if kod not in kapsam:
                        continue
                    kum_lot = 0.0
                    kum_tutar = 0.0
                    lot_var = tutar_var = oran_son = False
                    son_oran = None
                    for b in s["bildirimler"]:
                        if b.get("sinif") != "işlem" or not b.get("url"):
                            continue
                        if cekilen >= MAX_DETAY:
                            break
                        cekilen += 1
                        try:
                            html = http.get_html(b["url"])
                            p = _detay_parse_html(html)
                        except Exception:
                            p = None
                        if not p:
                            continue
                        if p.get("lot") is not None:
                            kum_lot += p["lot"]; lot_var = True
                        if p.get("tutar") is not None:
                            kum_tutar += p["tutar"]; tutar_var = True
                        if p.get("sermaye_orani") is not None:
                            son_oran = p["sermaye_orani"]; oran_son = True
                        b["detay"] = p
                    if lot_var:
                        s["kumulatif_lot"] = round(kum_lot, 2); basari += 1
                    if tutar_var:
                        s["kumulatif_tutar_tl"] = round(kum_tutar, 2)
                        pd = s.get("piyasa_degeri")
                        if isinstance(pd, (int, float)) and pd:
                            s["piyasa_degeri_orani_yuzde"] = round(100.0 * kum_tutar / pd, 4)
                    if oran_son and son_oran is not None:
                        s["sermaye_orani_yuzde"] = son_oran
                cikti["detay_basari_sayisi"] = basari
                if basari == 0:
                    cikti["notlar"].append(
                        "Tier-2 hiçbir detaydan sayı ayıklayamadı (KAP SPA içeriği "
                        "gelmemiş olabilir). Tier-1 (liste/sayı/link) geçerli; "
                        "istenirse DETAY_DENE=False yapılabilir.")

            cikti["sirketler"] = sirketler
            cikti["sirket_sayisi"] = len(sirketler)
            cikti["portfoy_ozet"] = {
                k: {
                    "toplam_bildirim": s["toplam_bildirim"],
                    "islem_bildirim_sayisi": s["islem_bildirim_sayisi"],
                    "son_bildirim_tarih": s["son_bildirim_tarih"],
                    "kumulatif_lot": s["kumulatif_lot"],
                    "kumulatif_tutar_tl": s["kumulatif_tutar_tl"],
                }
                for k, s in sirketler.items() if s["portfoyde"]
            }
    except Exception as e:
        cikti["notlar"].append(
            f"geri alım sorgu hatası: {e!r} :: {traceback.format_exc(limit=2)}")

    if toplam_satir == 0:
        cikti["notlar"].append("Piyasa-geneli sorgu 0 satır — tarih aralığı/endpoint kontrol et.")
    _ga_yaz(cikti)


def main() -> None:
    # İki faz birbirinden bağımsız; biri patlasa diğeri yine çalışır.
    try:
        _kap_fazi()
    except Exception as e:
        try:
            _kap_yaz({"uretim_zamani_utc": datetime.now(timezone.utc).isoformat(),
                      "hata": repr(e), "kodlar": {}, "hisse_sayisi": 0,
                      "bildirimli_kod_sayisi": 0, "toplam_piyasa_satiri": 0})
        except Exception:
            pass
        print("kap fazı beklenmedik hata:", e, file=sys.stderr)
    try:
        _ga_fazi()
    except Exception as e:
        try:
            _ga_yaz({"uretim_zamani_utc": datetime.now(timezone.utc).isoformat(),
                     "hata": repr(e), "sirketler": {}, "sirket_sayisi": 0,
                     "geri_alim_bildirim_sayisi": 0, "toplam_piyasa_satiri": 0,
                     "detay_denendi": False, "detay_basari_sayisi": 0})
        except Exception:
            pass
        print("geri alım fazı beklenmedik hata:", e, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("kap_tarama beklenmedik hata:", e, file=sys.stderr)
    sys.exit(0)
