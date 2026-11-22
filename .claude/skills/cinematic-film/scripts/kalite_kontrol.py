#!/usr/bin/env python3
"""KeyfiZar short'ları için otomatik kalite kontrolü (Claude'un kare incelemesini azaltmak için).

Bir klasör (video.mp4 + meta.json) ya da doğrudan video.mp4 alır; ffmpeg/ffprobe ile ölçer:
  çözünürlük 1080x1920 · süre 20–45 sn · ses −16…−12 LUFS ve true peak ≤ −1 dBTP ·
  sessiz başlangıç/bitiş yok · kenar bantlarında (8 px) kesik yazı izi yok · siyah/donmuş kare yok ·
  son 2 sn imza (kararan zemin + ortada koyu kutu içinde açık yazı) ·
  meta.json alanları ve uzunlukları · başlık/açıklama/etiketlerde sansürsüz küfür yok.

Kullanım:
  python3 kalite_kontrol.py videolar/026-el-gerdek [videolar/027-… …] [--json sonuc.json]
  python3 kalite_kontrol.py video.mp4 --meta meta.json --json -     # JSON'u stdout'a yaz
Çıkış kodu: 0 = tüm kontroller ✓; 1 = en az bir ✗; 2 = girdi/ffmpeg hatası.
(Bu bir doğrulama aracıdır; bilinçli olarak sorun bulunca 0 dışı döner. Veri hattı betiği değildir.)
Sezgisel kontroller (kenar, imza, donma) yanlış alarm verebilir: ✗ görülürse Claude temas kartına bakar.
Yalnız standart kitaplık + ffmpeg kullanır (numpy gerekmez).
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

# ---- eşikler ---------------------------------------------------------------------------------------------
GENISLIK, YUKSEKLIK = 1080, 1920
SURE_MIN, SURE_MAX = 20.0, 45.0
LUFS_MIN, LUFS_MAX = -16.0, -12.0
TP_MAX = -1.0
SESSIZ_DB = -45            # bu seviyenin altı "sessiz" sayılır
SESSIZ_BAS_MAX = 1.0       # baştaki sessizlik en çok (sn)
SESSIZ_SON_MAX = 3.5       # sondaki sessizlik en çok (sn; son cümleden sonra ~1 sn + 2 sn imza normal)
BANT = 8                   # kenar bandı (px)
KENAR_FARK = 60            # komşu piksel parlaklık farkı bu değerden büyükse "keskin kenar"
KENAR_IZ = 6               # bir bantta bandı enine kesen en az bu kadar iz = kesik yazı şüphesi (çerçeve çizgileri ≤ 4 iz bırakır)
KENAR_KARE = 40            # kenar kontrolü için en çok örnek kare (saniyede ~1)
ENINE = 0.6                # bir konumda bandın bu kadarı keskin kenarsa iz bandı "enine kesiyor" sayılır
DONMA_SN = 3.0             # bu süreden uzun tamamen donuk görüntü ✗
SIYAH_SN = 0.5             # bu süreden uzun siyah görüntü ✗ (imzanın kararttığı son 2.2 sn hariç)
BASLIK_MAX = 92
ACIKLAMA_MAX_BAYT = 5000
ETIKET_MIN, ETIKET_MAX, ETIKET_TOPLAM = 8, 10, 500
KATEGORILER = {"egitim", "eglence", "insanlar", "komedi"}
MARKA = "KeyfiZar"

# Sansürsüz küfür kökleri (kelime başında aranır). İstisnalar: aynı harflerle başlayan masum kelimeler.
KUFUR = [
    (r"sik", ("sikke", "siklet", "siklon", "siklo", "sikoz")),
    (r"göt", ("götür",)),
    (r"taşa[kğ]", ()),
    (r"sıç", ("sıçan", "sıçra", "sıçrat")),
    (r"yarra[kğ]", ()), (r"dalyara[kğ]", ()),
    (r"amcı[kğ]", ()), (r"amın", ()), (r"amk$", ()),
    (r"orospu", ()), (r"piç$", ()), (r"piçi", ()),
    (r"pezevenk", ()), (r"kahpe", ()), (r"ibne", ()), (r"yavşa[kğ]", ()), (r"gavat", ()),
]


def tr_kucuk(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def kufur_bul(metin):
    """Metindeki sansürsüz küfürlü kelimeleri döndürür ('s*kiyle' gibi yıldızlılar sayılmaz)."""
    bulunan = []
    for kelime in re.findall(r"[^\W\d_]+", tr_kucuk(metin)):
        for kok, istisna in KUFUR:
            if re.match(kok, kelime) and not kelime.startswith(istisna or ("\0",)):
                bulunan.append(kelime)
                break
    return bulunan


# ---- ffmpeg yardımcıları -----------------------------------------------------------------------------------
def calistir(cmd, ikili=False):
    r = subprocess.run(cmd, capture_output=True, text=not ikili)
    return r


def olc(video):
    r = calistir(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                  "stream=width,height:format=duration", "-of", "json", str(video)])
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe okuyamadı: {r.stderr.strip()[-300:]}")
    j = json.loads(r.stdout)
    s = (j.get("streams") or [{}])[0]
    return int(s.get("width", 0)), int(s.get("height", 0)), float(j.get("format", {}).get("duration", 0))


def ses_var_mi(video):
    r = calistir(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                  "-of", "csv=p=0", str(video)])
    return bool(r.stdout.strip())


def ses_seviyesi(video):
    r = calistir(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn",
                  "-af", "loudnorm=print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise RuntimeError("loudnorm ölçümü okunamadı")
    j = json.loads(m.group(0))
    return float(j["input_i"]), float(j["input_tp"])


def sessizlikler(video, sure):
    r = calistir(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn",
                  "-af", f"silencedetect=noise={SESSIZ_DB}dB:d=0.3", "-f", "null", "-"])
    araliklar, bas = [], None
    for satir in r.stderr.splitlines():
        m = re.search(r"silence_start: (-?[\d.]+)", satir)
        if m:
            bas = max(0.0, float(m.group(1)))
        m = re.search(r"silence_end: ([\d.]+)", satir)
        if m and bas is not None:
            araliklar.append((bas, float(m.group(1))))
            bas = None
    if bas is not None:
        araliklar.append((bas, sure))
    bas_sessiz = next((b - a for a, b in araliklar if a <= 0.05), 0.0)
    son_sessiz = next((b - a for a, b in araliklar if b >= sure - 0.1), 0.0)
    return round(bas_sessiz, 2), round(son_sessiz, 2)


def siyah_donma(video, sure):
    r = calistir(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an", "-vf",
                  f"blackdetect=d={SIYAH_SN}:pic_th=0.995:pix_th=0.03,freezedetect=n=-60dB:d={DONMA_SN}",
                  "-f", "null", "-"])
    siyah = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]
    siyah = [(a, b) for a, b in siyah if a < sure - 2.2]   # imza bölümü bilinçli olarak kararır
    donma = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", r.stderr)]
    if "freeze_start" in r.stderr and len(re.findall(r"freeze_start", r.stderr)) > len(donma):
        donma.append(DONMA_SN)  # sona kadar süren donma
    return siyah, donma


def kare_gri(video, t, w, h):
    """t anındaki kareyi gri (1 bayt/piksel) olarak döndürür."""
    r = calistir(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                  "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], ikili=True)
    if r.returncode != 0 or len(r.stdout) < w * h:
        return None
    return r.stdout[:w * h]


def bant_izleri(px, w, h, bant=BANT, fark=KENAR_FARK):
    """Üst/alt/sol/sağ bantlarda "enine kesen iz" yoğunluğu.

    Kenardan taşan yazının harf gövdeleri bandı enine keser: o konumda bandın (8 px) neredeyse tamamı keskin
    kenardır. Kenara paralel çerçeve/süs çizgileri (hafif eğik olsalar da) bir konumda yalnız 1–3 px kenar
    bırakır; bandı dik kesen bir çizgi ise yalnız 2 iz (üst ve alt kıyısı). Değer = enine kesilen konum sayısı.
    """
    def keskin(x, y):
        p = px[y * w + x]
        d = abs(p - px[y * w + x + 1]) if x + 1 < w else 0
        if y + 1 < h:
            d = max(d, abs(p - px[(y + 1) * w + x]))
        return d > fark

    esik = max(1, round(ENINE * bant))

    def say(boy, kesit, xy):
        return sum(sum(keskin(*xy(i, j)) for j in kesit) >= esik for i in range(boy))
    return {
        "ust": say(w, range(bant), lambda i, j: (i, j)),
        "alt": say(w, range(h - bant - 1, h - 1), lambda i, j: (i, j)),
        "sol": say(h, range(bant), lambda i, j: (j, i)),
        "sag": say(h, range(w - bant - 1, w - 1), lambda i, j: (j, i)),
    }


def kenar_kontrol(video, w, h, sure):
    """Örnek karelerde kenar bantlarını ölçer; ihlal 0.4 sn sonra da aynı bantta sürüyorsa raporlar
    (kamera geçişinde kenardan akıp giden içerik sayılmaz, ekranda duran kesik altyazı/yazı sayılır)."""
    def kotu_bantlar(t):
        px = kare_gri(video, t, w, h)
        if px is None:
            return {}
        return {k: v for k, v in bant_izleri(px, w, h).items() if v >= KENAR_IZ}

    sonuc = []
    son = max(0.5, sure - 2.6)   # imza bölümü hariç
    adet = max(2, min(KENAR_KARE, int(son)))
    for i in range(adet):
        t = 0.5 + (son - 0.5) * i / (adet - 1)
        kotu = kotu_bantlar(t)
        if kotu:
            sonra = kotu_bantlar(t + 0.4)
            kalici = {k: v for k, v in kotu.items() if k in sonra}
            if kalici:
                sonuc.append({"t": round(t, 1), "bantlar": kalici})
    return sonuc


def imza_kontrol(video, w, h, sure):
    """Son 2 sn: tüm kare kararır (black@0.6) ve ortada koyu kutu içinde açık yazı belirir."""
    px_son = kare_gri(video, sure - 0.6, w, h)
    px_once = kare_gri(video, sure - 3.0, w, h)
    if px_son is None or px_once is None:
        return False, {"neden": "kare okunamadı"}
    x0, x1 = int(w * 0.25), int(w * 0.75)
    y0, y1 = int(h * 0.48), int(h * 0.52)
    alan = [px_son[y * w + x] for y in range(y0, y1) for x in range(x0, x1)]
    koyu = sum(p < 50 for p in alan) / len(alan)
    acik = sum(p > 180 for p in alan) / len(alan)
    ort = lambda b: sum(b[::97]) / len(b[::97])  # noqa: E731  seyrek örnekle ortalama parlaklık
    once, sonra = ort(px_once), ort(px_son)
    ayrinti = {"merkez_koyu": round(koyu, 3), "merkez_acik": round(acik, 3),
               "parlaklik_once": round(once, 1), "parlaklik_son": round(sonra, 1)}
    kutu = koyu > 0.4 and acik > 0.02
    kararma = sonra < once * 0.75 or once < 40
    return kutu and kararma, ayrinti


# ---- meta.json ---------------------------------------------------------------------------------------------
def meta_kontrol(meta):
    hatalar = []
    for alan in ("tur", "baslik", "aciklama", "etiketler", "kategori", "gizlilik", "yapay_icerik",
                 "oynatma_listesi", "yorum", "yayin_zamani"):
        if alan not in meta:
            hatalar.append(f"'{alan}' alanı yok")
    baslik, aciklama = meta.get("baslik", ""), meta.get("aciklama", "")
    etiketler = meta.get("etiketler", [])
    if meta.get("tur") != "short":
        hatalar.append("tur 'short' değil")
    if not baslik or len(baslik) > BASLIK_MAX:
        hatalar.append(f"başlık boş ya da {BASLIK_MAX} karakterden uzun ({len(baslik)})")
    if len(baslik) + len(" #shorts") > 100:
        hatalar.append("başlık + ' #shorts' 100 karakteri aşıyor")
    if not aciklama or len(aciklama.encode("utf-8")) > ACIKLAMA_MAX_BAYT:
        hatalar.append("açıklama boş ya da 5000 baytı aşıyor")
    if any(c in baslik + aciklama for c in "<>"):
        hatalar.append("başlık/açıklamada < ya da > var")
    for parca in ("Anlamı:", "KeyfiZar'ı takip et", "yapay zekâ"):
        if parca not in aciklama:
            hatalar.append(f"açıklamada '{parca}' yok")
    if not isinstance(etiketler, list) or not (ETIKET_MIN <= len(etiketler) <= ETIKET_MAX):
        hatalar.append(f"etiket sayısı {ETIKET_MIN}–{ETIKET_MAX} değil")
    elif etiketler[-1] != MARKA:
        hatalar.append("son etiket 'KeyfiZar' değil")
    if sum(len(e) + 2 for e in etiketler) > ETIKET_TOPLAM:
        hatalar.append("etiketlerin toplamı 500 karakteri aşıyor")
    if meta.get("kategori") not in KATEGORILER:
        hatalar.append("kategori geçersiz")
    if meta.get("gizlilik") != "public":
        hatalar.append("gizlilik 'public' değil")
    if meta.get("yapay_icerik") is not True:
        hatalar.append("yapay_icerik true değil")
    yz = meta.get("yayin_zamani", "")
    try:
        z = dt.datetime.fromisoformat(yz)
        if z.utcoffset() != dt.timedelta(hours=3) or (z.hour, z.minute) != (19, 0):
            hatalar.append("yayin_zamani 19:00+03:00 değil")
    except (TypeError, ValueError):
        hatalar.append("yayin_zamani ISO biçiminde değil")
    tum = " ".join([baslik, aciklama, meta.get("yorum", ""), " ".join(map(str, etiketler))])
    for yanlis in re.findall(r"keyfi\s*zar", tum, re.I):
        if yanlis != MARKA:
            hatalar.append(f"marka yanlış yazılmış: '{yanlis}'")
            break
    return hatalar


def kufur_kontrol(meta):
    bulunan = {}
    for alan in ("baslik", "aciklama", "yorum"):
        k = kufur_bul(meta.get(alan, ""))
        if k:
            bulunan[alan] = k
    k = kufur_bul(" ".join(map(str, meta.get("etiketler", []))))
    if k:
        bulunan["etiketler"] = k
    return bulunan


# ---- ana akış ----------------------------------------------------------------------------------------------
def denetle(video, meta_yolu=None):
    video = pathlib.Path(video)
    kontroller = []

    def ekle(ad, gecti, ayrinti=""):
        kontroller.append({"ad": ad, "gecti": bool(gecti), "ayrinti": ayrinti})

    w, h, sure = olc(video)
    ekle("cozunurluk", (w, h) == (GENISLIK, YUKSEKLIK), f"{w}x{h}")
    ekle("sure", SURE_MIN <= sure <= SURE_MAX, f"{sure:.1f} sn")
    if ses_var_mi(video):
        lufs, tp = ses_seviyesi(video)
        ekle("ses_seviyesi", LUFS_MIN <= lufs <= LUFS_MAX, f"{lufs:.1f} LUFS")
        ekle("true_peak", tp <= TP_MAX, f"{tp:.1f} dBTP")
        bs, ss = sessizlikler(video, sure)
        ekle("sessiz_baslangic", bs <= SESSIZ_BAS_MAX, f"{bs:.2f} sn")
        ekle("sessiz_bitis", ss <= SESSIZ_SON_MAX, f"{ss:.2f} sn")
    else:
        ekle("ses_seviyesi", False, "ses akışı yok")
    siyah, donma = siyah_donma(video, sure)
    ekle("siyah_kare", not siyah, f"{len(siyah)} aralık" + (f" (ilk {siyah[0][0]:.1f} sn)" if siyah else ""))
    ekle("donmus_kare", not donma, f"en uzun {max(donma):.1f} sn" if donma else "yok")
    kenar = kenar_kontrol(video, w, h, sure)
    ekle("kenar_kesik_yazi", not kenar, kenar[:4] if kenar else "örnek kareler temiz")
    ok, ayr = imza_kontrol(video, w, h, sure)
    ekle("imza_son_2sn", ok, ayr)

    meta_yolu = pathlib.Path(meta_yolu) if meta_yolu else video.with_name("meta.json")
    if meta_yolu.exists():
        try:
            meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            meta = None
            ekle("meta_alanlari", False, f"meta.json okunamadı: {e}")
        if meta is not None:
            hatalar = meta_kontrol(meta)
            ekle("meta_alanlari", not hatalar, hatalar or "tamam")
            kf = kufur_kontrol(meta)
            ekle("sansursuz_kufur", not kf, kf or "yok")
    else:
        ekle("meta_alanlari", False, "meta.json yok")
    return {"video": str(video), "gecti": all(k["gecti"] for k in kontroller), "kontroller": kontroller}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hedefler", nargs="+", help="video klasörü (video.mp4 + meta.json) ya da video.mp4")
    ap.add_argument("--meta", help="meta.json yolu (tek video verildiğinde)")
    ap.add_argument("--json", help="JSON sonucunu bu dosyaya yaz ('-' = stdout, insan çıktısı stderr'e)")
    a = ap.parse_args(argv)
    insan = sys.stderr if a.json == "-" else sys.stdout
    sonuclar, hata = [], False
    for hedef in a.hedefler:
        p = pathlib.Path(hedef)
        video = p / "video.mp4" if p.is_dir() else p
        try:
            if not video.exists():
                raise RuntimeError(f"{video} yok")
            s = denetle(video, a.meta if len(a.hedefler) == 1 else None)
        except (RuntimeError, OSError) as e:
            hata = True
            print(f"✗ {hedef}: {e}", file=insan)
            sonuclar.append({"video": str(video), "gecti": False, "hata": str(e), "kontroller": []})
            continue
        sonuclar.append(s)
        print(f"{'✓' if s['gecti'] else '✗'} {hedef}", file=insan)
        for k in s["kontroller"]:
            ayr = k["ayrinti"] if isinstance(k["ayrinti"], str) else json.dumps(k["ayrinti"], ensure_ascii=False)
            print(f"   {'✓' if k['gecti'] else '✗'} {k['ad']}: {ayr}", file=insan)
    cikti = {"gecti": not hata and all(s["gecti"] for s in sonuclar), "videolar": sonuclar}
    if a.json == "-":
        print(json.dumps(cikti, ensure_ascii=False, indent=1))
    elif a.json:
        pathlib.Path(a.json).write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")
    if hata:
        return 2
    return 0 if cikti["gecti"] else 1


if __name__ == "__main__":
    sys.exit(main())
