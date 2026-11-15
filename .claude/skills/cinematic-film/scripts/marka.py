#!/usr/bin/env python3
"""Kanal markası "KeyfiZar"ı bitmiş videoya işler: köşe filigranı + son saniyelerde imza.

  python3 marka.py --video out/altyazili.mp4 --out out/markali.mp4
  python3 marka.py --video ... --out ... --imza 0        # yalnız filigran (ciddi içerik)

Filigran görüntünün parçasıdır; video indirilip başka yerde paylaşılsa da kalır (YouTube Studio
filigranı yalnız YouTube oynatıcısında görünür). Konum: dikey (Shorts) sol üst — sağ kenar ve alt
Shorts arayüzünün altında kalır; yatay sağ üst. Yazım her zaman "KeyfiZar" (Alpay kararı 15.11.2026);
Bebas/cond yazı tipi küçük harf basmadığı için Inter ExtraBold kullanılır.
"""
import argparse
import pathlib
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

MARKA = "KeyfiZar"
FONTLAR = ["/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(px):
    for f in FONTLAR:
        if pathlib.Path(f).exists():
            return ImageFont.truetype(f, px)
    return ImageFont.load_default()


def yazi_png(yol, yukseklik, opak, golge=True, zemin=None):
    """Saydam PNG: 'KeyfiZar' (beyaz, yumuşak gölgeli; isteğe bağlı koyu hap zemin)."""
    f = font(yukseklik)
    x0, y0, x1, y1 = f.getbbox(MARKA)
    pad = int(yukseklik * (0.55 if zemin else 0.25))
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if zemin:
        ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, h - 1], radius=h // 2, fill=zemin)
    if golge:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((pad - x0 + 2, pad - y0 + 3), MARKA, font=f, fill=(0, 0, 0, int(160 * opak)))
        im = Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(max(1, yukseklik // 14))))
    ImageDraw.Draw(im).text((pad - x0, pad - y0), MARKA, font=f, fill=(255, 255, 255, int(255 * opak)))
    im.save(yol)
    return w, h


def olc(video):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video)],
                       capture_output=True, text=True, check=True).stdout.split()
    return int(o[0]), int(o[1]), float(o[2])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--imza", type=float, default=2.0, help="sondaki imzanın süresi (sn); 0 = imza yok")
    ap.add_argument("--opaklik", type=float, default=0.7, help="filigran opaklığı")
    ap.add_argument("--crf", type=int, default=18)
    a = ap.parse_args()

    W, H, dur = olc(a.video)
    dikey = H > W
    with tempfile.TemporaryDirectory() as tmp:
        fil = pathlib.Path(tmp) / "filigran.png"
        fh = int(H * (0.024 if dikey else 0.034))
        fw, _ = yazi_png(fil, fh, a.opaklik)
        mx = int(W * 0.045)
        fx = mx if dikey else W - fw - mx
        fy = int(H * (0.055 if dikey else 0.05))
        girdiler = ["-i", str(a.video), "-loop", "1", "-i", str(fil)]
        filtre = f"[0:v][1:v]overlay={fx}:{fy}:shortest=1[v1]"
        son = "[v1]"
        if a.imza > 0:
            imz = pathlib.Path(tmp) / "imza.png"
            iw, ih = yazi_png(imz, int(H * (0.05 if dikey else 0.075)), 1.0, zemin=(12, 12, 14, 205))
            t0 = max(0.0, dur - a.imza)
            girdiler += ["-loop", "1", "-i", str(imz)]
            filtre += (f";[2:v]format=rgba,fade=t=in:st={t0:.2f}:d=0.4:alpha=1[im];"
                       f"[v1]drawbox=x=0:y=0:w=iw:h=ih:color=black@0.6:t=fill:enable='gte(t,{t0:.2f})'[vk];"
                       f"[vk][im]overlay=(W-w)/2:(H-h)/2:enable='gte(t,{t0:.2f})':shortest=1[v2]")
            son = "[v2]"
        cmd = ["ffmpeg", "-v", "error", "-y", *girdiler, "-filter_complex", filtre, "-map", son, "-map", "0:a?",
               "-c:v", "libx264", "-crf", str(a.crf), "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy",
               "-movflags", "+faststart", str(a.out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"ffmpeg hatası:\n{r.stderr[-1500:]}")
    print(f"marka işlendi: {a.out}  ({'dikey, sol üst' if dikey else 'yatay, sağ üst'}; imza {a.imza:g} sn)")


if __name__ == "__main__":
    main()
