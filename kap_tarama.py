#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KAP bildirim toplayıcı — keyfizar-cell/bist-tarama  (v3.3)

v3.3: v3.2 ayrıştırıcısı 4 kapsam-içi (portföy+BIST30) geri-alım şirketinden 3'ünü
çözdü; KRDMD çözülemedi. v3.3 yalnızca TANI ekler (ayrıştırma mantığı aynı):
geri_alim.json'a "detay_ornek_basarisiz" (parse edilemeyen ilk kapsam-içi belgenin
metni) + her kapsam-içi şirkete "detay_durum" (ok/satir_yok/indirilemedi). Böylece
KRDMD'nin KAP tablo düzeni görülüp ayrıştırıcı kesinleştirilebilir.

İKİ ÇIKTI, HER İKİSİ DE BAĞIMSIZ VE AYRI DOSYA:
  (1) data/kap.json       — v2 ile AYNI: portföy/ek kodlar için son N günün
                            KAP bildirimleri. Mantık/biçim DEĞİŞTİRİLMEDİ.
  (2) data/geri_alim.json — 01.09.2026'dan bugüne piyasa genelindeki TÜM
                            "Pay Geri Alım" bildirimlerini şirket bazında özetler.

v3.1 YENİLİĞİ — LOT/TUTAR İÇİN İKİNCİ YOL (Tier-2 yeniden yazıldı):
  v3.0'da Tier-2, bildirimin Angular (SPA) sayfasını get_html ile çekip regex
  deniyordu — güvenilmezdi. v3.1 bunun yerine KAP'ın KENDİ BELGE DIŞA-AKTARMA
  uçlarını kullanır (ücretsiz, giriş/anahtar yok):
     PDF :  https://www.kap.org.tr/tr/api/BildirimPdf/{index}
     Word:  https://www.kap.org.tr/tr/api/notification/export/word/{index}
  Bunlar bildirimin GERÇEK BELGESİDİR; "Pay Geri Alım İşlemleri" tablosunu
  (tarih, nominal/lot, fiyat aralığı, işlem tutarı, sermayeye oran) içerir.
  Belge indirilir, önce TABLO olarak (pdfplumber / python-docx), olmazsa düz
  METİN anahtar-kelimesiyle ayrıştırılır. Varsayılan: PDF dene, olmazsa Word.

  ⚠️ Bu uçlar binary döndürür; kap.org.tr buluttan/WebFetch'ten 403 verdiği için
  ayrıştırma YALNIZ GitHub Actions'ta (tam internet) doğrulanır. İlk çalışmada
  geri_alim.json'daki "detay_ornek" alanına ilk belgenin METNİ yazılır → gerçek
  KAP düzenini görüp (gerekirse) ayrıştırmayı kesinleştiririz.

GÜVENLİK TASARIMI:
  • ANA taramadan (tarama.py) TAMAMEN BAĞIMSIZDIR, onu ETKİLEMEZ.
  • İki faz da KENDİ try/except'inde; HER İKİ dosya HER DURUMDA yazılır; betik
    DAİMA sıfır çıkışla (sys.exit(0)) biter → bağlı iş akışını ASLA düşürmez.
  • Tier-2 kapatılabilir (DETAY_DENE=False) ve kibar/sınırlıdır (MAX_DETAY).
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time
import traceback
import urllib.request
from datetime import date, datetime, timedelta, timezone

# ───────────────────────── AYARLAR (düzenlenebilir) ─────────────────────────
PORTFOY: list[str] = [
    "AKBNK", "BLUME", "CANTE", "ENKAI", "HEKTS", "KRDMD", "OBAMS",
    "PAPIL", "SOHOE", "TTKOM", "ULUUN", "VAKBN", "YIGIT",
]
EK_KODLAR: list[str] = []

# BIST30 — YAKLAŞIK, düzenlenebilir; güncel endeks bileşimini teyit et.
BIST30: list[str] = [
    "AKBNK", "AKSEN", "ALARK", "ASELS", "ASTOR", "BIMAS", "EKGYO", "ENKAI",
    "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL", "KONTR",
    "KRDMD", "OYAKC", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TCELL",
    "THYAO", "TOASO", "TRALT", "TUPRS", "VAKBN", "YKBNK",
]

# ── kap.json fazı (v2 ile aynı) ──
GUN_PENCERESI = 4
KOD_BASI_LIMIT = 20
CIKTI = "data/kap.json"

# ── geri_alim.json fazı ──
GERI_ALIM_BASLANGIC = "2026-09-01"
GERI_ALIM_CIKTI = "data/geri_alim.json"
CHUNK_GUN = 7
GA_BILDIRIM_LIMIT = 60

# ── Tier-2 (lot/tutar ikinci yol: KAP belge dışa-aktarma) ──
DETAY_DENE = True                 # kapatmak için False
DETAY_KAPSAM = "portfoy_bist30"   # "portfoy_bist30" | "portfoy" | "yok"
DETAY_FORMAT = "pdf_sonra_word"   # "pdf_sonra_word" | "pdf" | "word"
MAX_DETAY = 80                    # en fazla kaç belge indirilsin (kibar/hızlı)
GA_DETAY_DENEME = 3               # şirket başına en güncelden kaç bildirim denensin (parse olana dek)
DETAY_ORNEK_KAYDET = True         # ilk belgenin metnini (4000 krktr) tanı için kaydet
BELGE_TIMEOUT = 25
BELGE_BEKLE = 0.3                 # belgeler arası kibar bekleme (sn)

TIMEOUT = 30.0
GERI_ALIM_ANAHTAR = ("geri al",)

BASE_KAP = "https://www.kap.org.tr"
PDF_URL = BASE_KAP + "/tr/api/BildirimPdf/{}"
WORD_URL = BASE_KAP + "/tr/api/notification/export/word/{}"
BELGE_BASLIK = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"),
    "Referer": BASE_KAP + "/tr/bildirim-sorgu",
    "Accept": ("application/pdf,application/vnd.openxmlformats-officedocument."
               "wordprocessingml.document,*/*"),
}
# ─────────────────────────────────────────────────────────────────────────────


def _tr_lower(s: str) -> str:
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


_SAYI = r"[0-9][0-9\.]*(?:,[0-9]+)?"


def _tr_sayi(s):
    """ '1.234.567,89' → 1234567.89. Tarih/aralık/yıl gibi değerler None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    # tam hücre tek bir TR sayı mı? (tarih '13.10.2026' ve aralık '41,2-41,5' hariç)
    m = re.fullmatch(r"%?\s*([0-9][0-9\.]*(?:,[0-9]+)?)\s*%?", s)
    if not m:
        return None
    ham = m.group(1)
    # Yalnızca gerçek gg.aa.yyyy tarihi reddet (binlik ayraçlı 4.120.000'ı DEĞİL).
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", ham):
        return None
    try:
        return float(ham.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _satir_son_sayi(satir: str):
    sayilar = re.findall(_SAYI, satir)
    for s in reversed(sayilar):
        v = _tr_sayi(s)
        if v is not None and not (2020 <= v <= 2035 and "," not in s):  # yıl değilse
            return v
    return None


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
                mkkMemberOidList=[],
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
# ║  FAZ 2 — geri_alim.json                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def _ga_yaz(cikti: dict) -> None:
    os.makedirs("data", exist_ok=True)
    with open(GERI_ALIM_CIKTI, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)
    print(
        "data/geri_alim.json yazıldı: "
        f"{cikti.get('sirket_sayisi', '?')} şirkette geri alım, "
        f"{cikti.get('geri_alim_bildirim_sayisi', '?')} bildirim "
        f"(detay: {cikti.get('detay_denendi')}, belge başarı: {cikti.get('detay_basari_sayisi', 0)})"
    )


def _gunluk_islem_mi(konu: str, ozet: str) -> bool:
    blob = f"{konu or ''} {ozet or ''}"
    return bool(re.search(r"\d{1,2}\.\d{2}\.\d{4}\s*Tarihli\s*Pay\s*Geri\s*Al", blob, re.IGNORECASE))


def _program_mi(konu: str, ozet: str) -> bool:
    b = _tr_lower(f"{konu or ''} {ozet or ''}")
    return ("program" in b) or ("geri alım karar" in b) or ("geri alim karar" in b) \
        or ("çerçevesinde" in b and "geri al" in b)


# ── belge ayrıştırma (SAF; ağ yok → gerçek KAP metniyle test edilebilir) ──
# KAP "Geri Alım İşlemlerinin Detayları" tablosu (PDF metin çıktısında) satır biçimi:
#   <işlem tarihi> <nominal/lot TL> <sermayeye oranı %> <işlem fiyatı TL/adet>
#   <program çerçevesinde DAHA ÖNCE geri alınan nominal TL> <imtiyaz>
# ör:  03.07.2026 4.120.000 0,12865 48,81 0 -
# ÖNEMLİ: Tabloda "işlem tutarı (TL)" sütunu YOKTUR → tutar = Σ(nominal × fiyat).
#   Her bildirim programın TÜM geçmişini taşır → şirket başına YALNIZ en güncel
#   bildirim ayrıştırılır (bildirimler arası TOPLAMA YAPILMAZ, çifte sayım olur).
#   Kümülatif lot = son satırın "daha önce" + son satırın nominali (kısmi tabloda
#   bile doğru). Sermaye = nominal ÷ (oran/100); kümülatif oran = 100×küm_lot/sermaye.
_SATIR_DESEN = re.compile(
    r"(\d{2}\.\d{2}\.\d{4})\s+([\d.]+(?:,\d+)?)\s+(\d+,\d+)\s+([\d.]+,\d+)\s+([\d.]+(?:,\d+)?)"
)


def _buyback_detay_parse(metin: str) -> dict:
    """Tek bir geri-alım bildiriminin METNİNDEN kümülatif lot/tutar/sermaye oranı.
    -> {lot, tutar, sermaye_orani, satir, azami_pay, ayrilan_fon} ; satır yoksa lot=None."""
    out = {"lot": None, "tutar": None, "sermaye_orani": None, "satir": 0,
           "azami_pay": None, "ayrilan_fon": None}
    if not metin:
        return out
    satirlar = []  # (nominal, oran, fiyat, daha_once)
    for m in _SATIR_DESEN.finditer(metin):
        nom = _tr_sayi(m.group(2)); oran = _tr_sayi(m.group(3))
        fiyat = _tr_sayi(m.group(4)); daha = _tr_sayi(m.group(5))
        if nom is None:
            continue
        satirlar.append((nom, oran, fiyat, daha))
    if not satirlar:
        return out
    out["satir"] = len(satirlar)
    # tutar = Σ(nominal×fiyat) (gösterilen satırlar)
    tutar = sum(n * f for (n, o, f, d) in satirlar if f is not None)
    out["tutar"] = round(tutar, 2) if tutar else None
    # kümülatif lot = son satırın (daha_önce + nominal); yoksa Σ nominal
    son = satirlar[-1]
    if son[3] is not None:
        out["lot"] = round(son[3] + son[0], 2)
    else:
        out["lot"] = round(sum(n for (n, o, f, d) in satirlar), 2)
    # sermaye = nominal ÷ (oran/100) ilk geçerli satırdan → kümülatif oran
    sermaye = None
    for (n, o, f, d) in satirlar:
        if o and o > 0 and n:
            sermaye = n / (o / 100.0)
            break
    if sermaye and sermaye > 0:
        out["sermaye_orani"] = round(100.0 * out["lot"] / sermaye, 5)
    else:
        toplam_oran = sum(o for (n, o, f, d) in satirlar if o)
        out["sermaye_orani"] = round(toplam_oran, 5) if toplam_oran else None
    # program meta (en iyi çaba): azami pay / ayrılan fon (etiket sonrası ilk büyük sayı)
    def _meta(anahtar):
        i = _tr_lower(metin).find(anahtar)
        if i < 0:
            return None
        for s in re.findall(_SAYI, metin[i:i + 160]):
            v = _tr_sayi(s)
            if v and v >= 1000:
                return v
        return None
    out["azami_pay"] = _meta("azami pay")
    out["ayrilan_fon"] = _meta("ayrılan fon")
    return out


# ── belge indirme + çıkarma (ağ; try/except'le sarılı) ──
def _belge_indir(url: str, http=None) -> bytes | None:
    """Önce kap-client'ın CANLI httpx oturumunu (çerez/başlık hazır) dener —
    Actions'ta KAP'a erişme şansı en yüksek olan budur; olmazsa urllib'e düşer."""
    # 1) kap-client httpx oturumu (byCriteria POST'larından sonra çerezli)
    cli = getattr(http, "_client", None) if http is not None else None
    if cli is not None:
        try:
            resp = cli.get(url, headers=BELGE_BASLIK, timeout=BELGE_TIMEOUT)
            if getattr(resp, "status_code", None) == 200:
                return resp.content
        except Exception:
            pass
    # 2) urllib yedeği
    try:
        req = urllib.request.Request(url, headers=BELGE_BASLIK)
        with urllib.request.urlopen(req, timeout=BELGE_TIMEOUT) as r:
            if getattr(r, "status", 200) not in (200, None):
                return None
            return r.read()
    except Exception:
        return None


def _pdf_coz(data: bytes):
    """-> (tablolar, metin) ; pdfplumber yoksa (None, '')."""
    try:
        import pdfplumber
    except Exception:
        return None, ""
    tablolar = []
    metin = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for p in pdf.pages:
            try:
                for t in (p.extract_tables() or []):
                    tablolar.append(t)
            except Exception:
                pass
            try:
                metin.append(p.extract_text() or "")
            except Exception:
                pass
    return tablolar, "\n".join(metin)


def _docx_coz(data: bytes):
    """-> (tablolar, metin) ; python-docx yoksa (None, '')."""
    try:
        import docx
    except Exception:
        return None, ""
    doc = docx.Document(io.BytesIO(data))
    metin = [p.text for p in doc.paragraphs]
    tablolar = []
    for t in doc.tables:
        tbl = []
        for row in t.rows:
            hucreler = [c.text for c in row.cells]
            tbl.append(hucreler)
            metin.append(" | ".join(hucreler))
        tablolar.append(tbl)
    return tablolar, "\n".join(metin)


def _detay_getir(index, http=None) -> tuple:
    """index için KAP belgesini (PDF/Word) indirip DÜZ METNİNİ döndürür.
    Ayrıştırma çağırana aittir (_buyback_detay_parse).
    -> (metin_str, kaynak_str | None)."""
    if index is None:
        return "", None
    sira = {"pdf_sonra_word": ("pdf", "word"), "pdf": ("pdf",), "word": ("word",)}.get(
        DETAY_FORMAT, ("pdf", "word"))
    for fmt in sira:
        url = (PDF_URL if fmt == "pdf" else WORD_URL).format(index)
        try:
            data = _belge_indir(url, http)
        except Exception:
            data = None
        if not data or len(data) < 200:
            continue
        try:
            _tbl, metin = (_pdf_coz(data) if fmt == "pdf" else _docx_coz(data))
        except Exception:
            metin = ""
        if metin:
            return metin, fmt
    return "", None


def _piyasa_degeri_haritasi() -> dict:
    harita: dict = {}
    try:
        with open("data/latest.json", encoding="utf-8") as f:
            lt = json.load(f)
        for h in lt.get("tum_hisseler", []) or []:
            kod = (h.get("kod") or "").strip().upper()
            if kod:
                harita[kod] = (h.get("piyasa_degeri"), h.get("kapanis"))
    except Exception:
        pass
    return harita


def _ga_derle(kayitlar: list, pd_harita: dict, portfoy_set: set, bist30_set: set) -> dict:
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
                "bildirimler": [], "islem_bildirim_sayisi": 0, "program_bildirim_sayisi": 0,
            })
            if not s.get("sirket"):
                s["sirket"] = r.get("sirket")
            s["bildirimler"].append({
                "no": r.get("no"), "tarih": (r.get("zaman") or "")[:10], "zaman": r.get("zaman"),
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
        "kaynak": "KAP (kap-client liste + BildirimPdf/Word belge dışa-aktarma)",
        "aciklama": ("Tier-1 (güvenilir): bildirim listesi/sayısı/sınıfı/link. "
                     "Tier-2 (ikinci yol): her 'işlem' bildiriminin KAP PDF/Word "
                     "belgesinden lot/tutar/sermaye oranı; yalnız Actions'ta doğrulanır. "
                     "İlk belgenin metni 'detay_ornek'te (tanı/ince ayar)."),
        "detay_denendi": False, "detay_basari_sayisi": 0, "detay_kaynak_sayisi": {},
        "detay_ornek": None, "detay_ornek_basarisiz": None,
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

    ga_kayitlar: list = []
    gorulen_no: set = set()
    toplam_satir = 0

    try:
        with KapHttpClient(timeout=TIMEOUT) as http:
            p0 = baslangic
            while p0 <= bugun:
                p1 = min(p0 + timedelta(days=CHUNK_GUN - 1), bugun)
                try:
                    body = MemberDisclosureQueryBody(
                        fromDate=p0.isoformat(), toDate=p1.isoformat(), mkkMemberOidList=[])
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
    except Exception as e:
        cikti["notlar"].append(f"geri alım sorgu hatası: {e!r} :: {traceback.format_exc(limit=2)}")

    cikti["toplam_piyasa_satiri"] = toplam_satir
    cikti["geri_alim_bildirim_sayisi"] = len(ga_kayitlar)
    sirketler = _ga_derle(ga_kayitlar, pd_harita, portfoy_set, bist30_set)

    # ── Tier-2: KAP belge dışa-aktarma (ikinci yol) ──
    # Belge GET'leri için CANLI bir KAP oturumu (hdoc) açılır: önce bildirim-sorgu
    # sayfası ısıtılıp çerez alınır (KAP bot kontrolü), sonra PDF/Word indirilir.
    # Her şey try/except'le sarılı → bu faz patlasa bile dosya yine yazılır.
    if DETAY_DENE and DETAY_KAPSAM != "yok":
        cikti["detay_denendi"] = True
        kapsam = portfoy_set if DETAY_KAPSAM == "portfoy" else (portfoy_set | bist30_set)
        basari = 0
        cekilen = 0
        kaynak_say: dict = {"pdf": 0, "word": 0}
        ornek_kaydedildi = False
        basarisiz_kaydedildi = [False]  # ilk başarısız kapsam-içi belge tanısı
        try:
            with KapHttpClient(timeout=TIMEOUT) as hdoc:
                try:   # oturum/çerez ısıtma
                    hdoc.get_html(BASE_KAP + "/tr/bildirim-sorgu")
                except Exception:
                    pass
                for kod, s in sirketler.items():
                    if kod not in kapsam:
                        continue
                    # İşlem bildirimleri (en yeni → eski; _ga_derle zaten sıraladı).
                    # Her bildirim programın TÜM geçmişini taşıdığından YALNIZ en güncel
                    # (parse edilebilen ilk) bildirim kullanılır — TOPLAMA YOK.
                    islemler = [b for b in s["bildirimler"]
                                if b.get("sinif") == "işlem" and b.get("no") is not None]
                    parse = None
                    indi = False  # en az bir belge metni geldi mi
                    for b in islemler[:GA_DETAY_DENEME]:
                        if cekilen >= MAX_DETAY:
                            break
                        cekilen += 1
                        try:
                            metin, kaynak = _detay_getir(b["no"], hdoc)
                        except Exception:
                            metin, kaynak = "", None
                        if BELGE_BEKLE:
                            time.sleep(BELGE_BEKLE)
                        if metin:
                            indi = True
                        if DETAY_ORNEK_KAYDET and not ornek_kaydedildi and metin:
                            cikti["detay_ornek"] = {"kod": kod, "no": b["no"],
                                                    "kaynak": kaynak, "metin": metin[:4000]}
                            ornek_kaydedildi = True
                        p = _buyback_detay_parse(metin)
                        # TANI: indi ama satır çıkmadı → ilk başarısız kapsam-içi belgenin
                        # metnini ayrı kaydet (farklı KAP tablo düzenini görüp düzeltmek için)
                        if (DETAY_ORNEK_KAYDET and not basarisiz_kaydedildi[0]
                                and metin and p.get("lot") is None):
                            cikti["detay_ornek_basarisiz"] = {"kod": kod, "no": b["no"],
                                                              "kaynak": kaynak, "metin": metin[:4000]}
                            basarisiz_kaydedildi[0] = True
                        if p.get("lot") is not None:
                            if kaynak in kaynak_say:
                                kaynak_say[kaynak] += 1
                            p["kaynak"] = kaynak
                            p["bildirim_no"] = b["no"]
                            p["bildirim_tarih"] = b["tarih"]
                            b["detay"] = p
                            parse = p
                            break
                    s["detay_durum"] = ("ok" if parse else ("satir_yok" if indi else "indirilemedi"))
                    if parse:
                        basari += 1
                        s["kumulatif_lot"] = parse["lot"]
                        if parse.get("tutar") is not None:
                            s["kumulatif_tutar_tl"] = parse["tutar"]
                            pd = s.get("piyasa_degeri")
                            if isinstance(pd, (int, float)) and pd:
                                s["piyasa_degeri_orani_yuzde"] = round(100.0 * parse["tutar"] / pd, 4)
                        if parse.get("sermaye_orani") is not None:
                            s["sermaye_orani_yuzde"] = parse["sermaye_orani"]
        except Exception as e:
            cikti["notlar"].append(f"Tier-2 belge fazı hatası: {e!r}")
        cikti["detay_basari_sayisi"] = basari
        cikti["detay_kaynak_sayisi"] = kaynak_say
        if basari == 0:
            cikti["notlar"].append(
                "Tier-2 hiçbir belgeden lot/tutar ayıklayamadı. 'detay_ornek' alanına "
                "bakıp (varsa) ayrıştırma kesinleştirilebilir; ya da DETAY_DENE=False "
                "yapılıp Tier-1 (liste/sayı/link) ile devam edilebilir.")

    cikti["sirketler"] = sirketler
    cikti["sirket_sayisi"] = len(sirketler)
    cikti["portfoy_ozet"] = {
        k: {"toplam_bildirim": s["toplam_bildirim"], "islem_bildirim_sayisi": s["islem_bildirim_sayisi"],
            "son_bildirim_tarih": s["son_bildirim_tarih"], "kumulatif_lot": s["kumulatif_lot"],
            "kumulatif_tutar_tl": s["kumulatif_tutar_tl"], "sermaye_orani_yuzde": s["sermaye_orani_yuzde"]}
        for k, s in sirketler.items() if s["portfoyde"]
    }
    if toplam_satir == 0:
        cikti["notlar"].append("Piyasa-geneli sorgu 0 satır — tarih aralığı/endpoint kontrol et.")
    _ga_yaz(cikti)


def main() -> None:
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
