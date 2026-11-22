"""Seslendirme yardımcıları (yalnız numpy): TTS'e giden metnin telaffuz düzeltmesi ve take sonundaki uydurma kuyruğun kesilmesi.
xtts_say.py kullanır; testler: testler/test_ses_duzen.py"""
import re

import numpy as np

# "KeyfiZar", "Keyfi Zar", "KEYFİZAR'ı", "keyfizar’ın" … → "Keyfizar", "Keyfizarı", "Keyfizarın" (tek kelime, kesme işaretsiz).
# Yalnız TTS'e giden metne uygulanır; ekran/altyazı/meta yazımı `KeyfiZar` olarak kalır.
# Ayrı yazımda Z büyük olmalı ("keyfi zarar" gibi sıradan sözlere dokunmamak için).
_MARKA = re.compile(r"\b[Kk][Ee][Yy][Ff][İIiı](?:\s+Z|[Zz])[Aa][Rr]['’]?")


def tts_metni(metin):
    """Okunacak metinde kanal adını XTTS'in akıcı ve tutarlı okuduğu biçime çevirir."""
    return _MARKA.sub("Keyfizar", metin)


def _kelimeler(s):
    s = s.replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"[^a-zçğıöşü ]", "", s).split()


def son_kelime_basi(metin, kelimeler):
    """Metnin son kelimesinin duyulduğu yerin başlangıcı (sn). kelimeler: [(söz, başlangıç), ...] (Whisper).
    Whisper uydurma bir ek kelime duymuşsa ("takip et bil") kesimi ona değil, metnin gerçek son kelimesine bağlar;
    bulunamazsa duyulan son kelimeye düşer."""
    if not kelimeler:
        return 0.0
    son = (_kelimeler(metin) or [""])[-1]
    for soz, bas in reversed(kelimeler):
        if _kelimeler(soz) == [son]:
            return bas
    return kelimeler[-1][1]


ESIK_DB = -35.0      # tepeye göre bu seviyenin altı "sessiz" sayılır
MIN_SESSIZ = 0.10    # son kelimeden sonra kesim için gereken en kısa sessizlik (sn); "t/k/p" kapanışından uzun
PAY = 0.03           # sessizlik başlangıcından sonra bırakılan sönüm payı (sn)
FADE = 0.025         # kesimde uygulanan sönümleme (sn)
_PENCERE = 0.01      # zarf penceresi (sn)


def _zarf_db(wav, sr):
    h = max(1, int(_PENCERE * sr))
    n = len(wav) // h
    if n == 0:
        return np.zeros(0), h
    kare = wav[: n * h].astype(np.float64).reshape(n, h)
    rms = np.sqrt((kare ** 2).mean(axis=1))
    tepe = rms.max()
    if tepe <= 0:
        return np.full(n, -120.0), h
    return 20 * np.log10(np.maximum(rms, 1e-12) / tepe), h


def kuyruk_kes(wav, sr, son_kelime_bas):
    """Son kelimenin başından ileri yürüyüp ilk gerçek sessizlikte (>= MIN_SESSIZ) keser, FADE uygular.

    Döner: (kesilmiş ses, artık_db, kesim_bulundu)
      artık_db: kesimden sonra kalan en yüksek seviye (tepeye göre dB). ESIK_DB'den yüksekse son kelimeden sonra
      uydurma bir hece/ses vardır; çağıran o tohumu tercih etmemelidir. Kesimden sonra hiç ses yoksa -120.
      kesim_bulundu: False ise son kelimeden sonra sessizlik bulunamadı (ses dosyanın sonuna kadar sürüyor)."""
    wav = np.asarray(wav, dtype=np.float32)
    db, h = _zarf_db(wav, sr)
    gerek = max(1, int(round(MIN_SESSIZ / _PENCERE)))
    i = min(max(0, int(son_kelime_bas * sr) // h), len(db))
    kesim, sayac = None, 0
    while i < len(db):
        sayac = sayac + 1 if db[i] < ESIK_DB else 0
        if sayac >= gerek:
            kesim = (i - gerek + 1) * h + int(PAY * sr)
            break
        i += 1
    bulundu = kesim is not None
    if kesim is None or kesim >= len(wav):
        kesim = len(wav)
    sonra = db[(kesim + h - 1) // h:]
    artik = float(sonra.max()) if len(sonra) else -120.0
    out = wav[:kesim].copy()
    f = min(len(out), int(FADE * sr))
    if f > 0:
        out[-f:] *= np.linspace(1.0, 0.0, f, dtype=np.float32)
    return out, artik, bulundu
