"""Generate the PWA PNG icons (iOS home-screen install needs raster icons).

Draws the same reef motif as assets/icon.svg with Pillow, at 4x supersampling.
Run: python tools/make_icons.py
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "assets")

DEEP = (11, 60, 73)
TEAL = (18, 165, 184)
CORAL = (255, 107, 90)
SUN = (242, 166, 90)
FOAM = (142, 230, 242)


def gradient(size):
    img = Image.new("RGB", (size, size), DEEP)
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2.0 * (size - 1))
            px[x, y] = (
                int(DEEP[0] + (TEAL[0] - DEEP[0]) * t),
                int(DEEP[1] + (TEAL[1] - DEEP[1]) * t),
                int(DEEP[2] + (TEAL[2] - DEEP[2]) * t),
            )
    return img


def branch(d, x, y, scale, color, lean=0.0):
    """A stylised coral branch: trunk + two arms, rounded caps."""
    w = int(22 * scale)
    d.line([(x, y), (x + lean * 26 * scale, y - 86 * scale)], fill=color, width=w, joint="curve")
    tipx = x + lean * 26 * scale
    tipy = y - 86 * scale
    d.line([(tipx, tipy + 30 * scale), (tipx - 44 * scale, tipy - 16 * scale)],
           fill=color, width=int(w * 0.8), joint="curve")
    d.line([(tipx, tipy + 44 * scale), (tipx + 46 * scale, tipy - 4 * scale)],
           fill=color, width=int(w * 0.8), joint="curve")
    for cx, cy, r in [(tipx, tipy, w * 0.62),
                      (tipx - 44 * scale, tipy - 16 * scale, w * 0.5),
                      (tipx + 46 * scale, tipy - 4 * scale, w * 0.5)]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def make(size):
    S = size * 4
    img = gradient(S).convert("RGBA")
    d = ImageDraw.Draw(img)

    cx, base = S * 0.5, S * 0.74
    branch(d, cx - S * 0.20, base, S / 512.0 * 0.86, SUN, lean=-0.30)
    branch(d, cx + S * 0.20, base, S / 512.0 * 0.86, SUN, lean=0.30)
    branch(d, cx, base + S * 0.03, S / 512.0 * 1.20, CORAL, lean=0.0)

    # seabed wave
    wave = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)
    y = S * 0.80
    amp, step = S * 0.028, S / 8.0
    pts = []
    for i in range(9):
        pts.append((i * step, y + (amp if i % 2 else -amp)))
    wd.line(pts, fill=FOAM + (150,), width=int(S * 0.032), joint="curve")
    img.alpha_composite(wave)

    # rounded mask
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.putalpha(mask)

    return img.resize((size, size), Image.LANCZOS)


for s in (180, 192, 512):
    p = os.path.join(OUT, "icon-%d.png" % s)
    make(s).save(p)
    print("wrote", p)
