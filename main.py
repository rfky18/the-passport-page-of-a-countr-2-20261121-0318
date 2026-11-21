#!/usr/bin/env python3
"""The Passport Page of a Country That Isn't There.
Republic of Tefraya — passport spread of Mara Ilse Velkora,
Ashfall Observer (ST-2). Pure stdlib: reads atlas.bin/atlas.json
(bitmap font atlas rendered at build time from real TTFs) and
portrait.bin (raw RGB photo), draws the whole 1024x1024 spread,
writes a PNG with zlib. Deterministic, no network, no time, no RNG.
"""
import json
import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
W = 1024
H = 1024

PAPER = (247, 243, 230)
PAPER2 = (250, 246, 236)
INK = (32, 32, 30)
NAVY = (28, 44, 74)
RED = (122, 30, 35)
GREY = (112, 106, 96)
GREEN_D = (38, 96, 58)
BLUE_D = (36, 68, 140)
PURPLE_D = (110, 52, 130)
STAMP_RED = (178, 44, 38)
STAMP_BLUE = (52, 84, 160)
STAMP_GREEN = (46, 120, 74)
STAMP_PURPLE = (128, 62, 148)
YELLOW = (233, 196, 90)

# ---------------------------------------------------------------- canvas
canvas = bytearray([0]) * (W * H * 3)


def set_px(x, y, rgb, a=1.0):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        if a >= 1.0:
            canvas[i] = rgb[0]
            canvas[i + 1] = rgb[1]
            canvas[i + 2] = rgb[2]
        elif a > 0:
            canvas[i] = int(canvas[i] * (1 - a) + rgb[0] * a)
            canvas[i + 1] = int(canvas[i + 1] * (1 - a) + rgb[1] * a)
            canvas[i + 2] = int(canvas[i + 2] * (1 - a) + rgb[2] * a)


def fill_rect(x, y, w, h, rgb, a=1.0):
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(W, x + w)
    y1 = min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    if a >= 1.0:
        row = bytes(rgb) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * W + x0) * 3
            canvas[i:i + len(row)] = row
    else:
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                set_px(xx, yy, rgb, a)


def rect_outline(x, y, w, h, rgb, t=1, a=1.0):
    for k in range(t):
        for xx in range(x + k, x + w - k):
            set_px(xx, y + k, rgb, a)
            set_px(xx, y + h - 1 - k, rgb, a)
        for yy in range(y + k, y + h - k):
            set_px(x + k, yy, rgb, a)
            set_px(x + w - 1 - k, yy, rgb, a)


def hline(x, y, w, rgb, t=1, a=1.0):
    for k in range(t):
        for xx in range(x, x + w):
            set_px(xx, y + k, rgb, a)


def vline(x, y, h, rgb, t=1, a=1.0):
    for k in range(t):
        for yy in range(y, y + h):
            set_px(x + k, yy, rgb, a)


def line(x0, y0, x1, y1, rgb, a=1.0):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        set_px(x0, y0, rgb, a)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def circle(cx, cy, r, rgb, a=1.0, fill=False):
    if fill:
        for yy in range(cy - r, cy + r + 1):
            dx = int(math.sqrt(max(0, r * r - (yy - cy) ** 2)))
            for xx in range(cx - dx, cx + dx + 1):
                set_px(xx, yy, rgb, a)
        return
    x = r
    y = 0
    err = 0
    while x >= y:
        for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                       (x, -y), (y, -x), (-x, -y), (-y, -x)):
            set_px(cx + sx, cy + sy, rgb, a)
        y += 1
        err += 1 + 2 * y
        if 2 * (err - x) + 1 > 0:
            x -= 1
            err += 1 - 2 * x


def poly_fill(points, rgb, a=1.0):
    ys = [p[1] for p in points]
    for yy in range(min(ys), max(ys) + 1):
        nodes = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= yy < y1) or (y1 <= yy < y0):
                xi = x0 + (yy - y0) * (x1 - x0) / (y1 - y0)
                nodes.append(xi)
        nodes.sort()
        for k in range(0, len(nodes) - 1, 2):
            for xx in range(int(nodes[k]), int(nodes[k + 1]) + 1):
                set_px(xx, yy, rgb, a)


# ---------------------------------------------------------------- atlas text
with open(os.path.join(HERE, "atlas.json")) as f:
    _ATLAS = json.load(f)
_ATLAS_W = _ATLAS["width"]
_ATLAS_H = _ATLAS["height"]
with open(os.path.join(HERE, "atlas.bin"), "rb") as f:
    _ATLAS_RAW = f.read()
_GLYPHS = _ATLAS["glyphs"]


def _glyph(fid, size, ch):
    return _GLYPHS.get("%s|%d|%s" % (fid, size, ch))


def text_width(fid, size, s, spacing=0):
    w = 0
    for ch in s:
        g = _glyph(fid, size, ch)
        if g is None:
            continue
        w += g["adv"] + spacing
    return w - spacing if s else 0


def draw_text(x, y, fid, size, s, rgb, spacing=0, alpha=1.0):
    """Draw text; y is the top of the em box approx (baseline offset
    handled per glyph via by). Returns width drawn."""
    cx = x
    for ch in s:
        g = _glyph(fid, size, ch)
        if g is None:
            cx += size // 2
            continue
        gw, gh = g["w"], g["h"]
        gx, gy = g["x"], g["y"]
        for row in range(gh):
            src = (gy + row) * _ATLAS_W + gx
            for col in range(gw):
                v = _ATLAS_RAW[src + col]
                if v:
                    set_px(cx + g["bx"] + col, y + g["by"] + row,
                           rgb, alpha * v / 255.0)
        cx += g["adv"] + spacing
    return cx - x - (spacing if s else 0)


def draw_text_c(cx, y, fid, size, s, rgb, spacing=0, alpha=1.0):
    w = text_width(fid, size, s, spacing)
    return draw_text(cx - w // 2, y, fid, size, s, rgb, spacing, alpha)


def wrap_text(fid, size, s, maxw, spacing=0):
    words = s.split(" ")
    lines = []
    cur = ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_width(fid, size, trial, spacing) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- ICAO MRZ
def _mrz_val(c):
    if c == "<":
        return 0
    if c.isdigit():
        return int(c)
    return ord(c) - 55


def mrz_check(s):
    w = (7, 3, 1)
    return str(sum(_mrz_val(c) * w[i % 3] for i, c in enumerate(s)) % 10)


DOC_NO = "TF284917"
DOB = "810312"       # 12 MAR 1981
EXP = "330213"       # 13 FEB 2033
PERSONAL = "8103124471<<<<"
_doc = DOC_NO + "<"
MRZ2 = (_doc + mrz_check(_doc) + "TEF" + DOB + mrz_check(DOB) + "F"
        + EXP + mrz_check(EXP) + PERSONAL + mrz_check(PERSONAL))
MRZ2 += mrz_check(_doc + mrz_check(_doc) + DOB + mrz_check(DOB)
                  + EXP + mrz_check(EXP) + PERSONAL + mrz_check(PERSONAL))
MRZ1 = "P<TEFVELKORA<<MARA<ILSE" + "<" * (44 - len("P<TEFVELKORA<<MARA<ILSE"))
assert len(MRZ1) == 44 and len(MRZ2) == 44, (MRZ1, MRZ2)

# ---------------------------------------------------------------- portrait
with open(os.path.join(HERE, "portrait.bin"), "rb") as f:
    _PORTRAIT = f.read()  # 180x225 RGB
PW, PH = 180, 225


def blit_portrait(x, y, w, h, alpha=1.0, grey=False):
    for yy in range(h):
        sy = yy * PH // h
        for xx in range(w):
            sx = xx * PW // w
            i = (sy * PW + sx) * 3
            r, g, b = _PORTRAIT[i], _PORTRAIT[i + 1], _PORTRAIT[i + 2]
            if grey:
                v = (r * 3 + g * 6 + b) // 10
                r = g = b = v
            set_px(x + xx, y + yy, (r, g, b), alpha)


# ---------------------------------------------------------------- stamps
def _stamp_canvas(w, h):
    return bytearray([255]) * (w * h * 3), bytearray(w * h)


def _stamp_px(rgb_buf, mask, w, x, y, rgb):
    if 0 <= x < w and 0 <= y < len(mask) // w:
        i = (y * w + x) * 3
        rgb_buf[i] = rgb[0]
        rgb_buf[i + 1] = rgb[1]
        rgb_buf[i + 2] = rgb[2]
        mask[y * w + x] = 255


def _stamp_rect(rgb_buf, mask, w, x, y, rw, rh, rgb, t=2):
    for k in range(t):
        for xx in range(x + k, x + rw - k):
            _stamp_px(rgb_buf, mask, w, xx, y + k, rgb)
            _stamp_px(rgb_buf, mask, w, xx, y + rh - 1 - k, rgb)
        for yy in range(y + k, y + rh - k):
            _stamp_px(rgb_buf, mask, w, x + k, yy, rgb)
            _stamp_px(rgb_buf, mask, w, x + rw - 1 - k, yy, rgb)


def _stamp_circle(rgb_buf, mask, w, cx, cy, r, rgb):
    x = r
    y = 0
    err = 0
    while x >= y:
        for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                       (x, -y), (y, -x), (-x, -y), (-y, -x)):
            _stamp_px(rgb_buf, mask, w, cx + sx, cy + sy, rgb)
        y += 1
        err += 1 + 2 * y
        if 2 * (err - x) + 1 > 0:
            x -= 1
            err += 1 - 2 * x


def _stamp_text(rgb_buf, mask, w, h, cx, y, fid, size, s, rgb, spacing=0):
    tw = text_width(fid, size, s, spacing)
    x = cx - tw // 2
    for ch in s:
        g = _glyph(fid, size, ch)
        if g is None:
            x += size // 2
            continue
        for row in range(g["h"]):
            src = (g["y"] + row) * _ATLAS_W + g["x"]
            for col in range(g["w"]):
                v = _ATLAS_RAW[src + col]
                if v > 40:
                    _stamp_px(rgb_buf, mask, w, x + g["bx"] + col,
                              y + g["by"] + row, rgb)
        x += g["adv"] + spacing


def _composite_stamp(rgb_buf, mask, w, h, cx, cy, angle_deg, alpha=0.9):
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    hw, hh = w / 2.0, h / 2.0
    rad = int(math.hypot(hw, hh)) + 2
    for yy in range(cy - rad, cy + rad + 1):
        for xx in range(cx - rad, cx + rad + 1):
            dx, dy = xx - cx, yy - cy
            sx = int(dx * ca + dy * sa + hw)
            sy = int(-dx * sa + dy * ca + hh)
            if 0 <= sx < w and 0 <= sy < h and mask[sy * w + sx]:
                i = (sy * w + sx) * 3
                set_px(xx, yy, (rgb_buf[i], rgb_buf[i + 1], rgb_buf[i + 2]),
                       alpha)


def stamp_rect(cx, cy, lines, rgb, angle=0, w=150, h=104):
    buf, mask = _stamp_canvas(w, h)
    _stamp_rect(buf, mask, w, 2, 2, w - 4, h - 4, rgb, 3)
    _stamp_rect(buf, mask, w, 8, 8, w - 16, h - 16, rgb, 1)
    y = 16
    for fid, size, s in lines:
        _stamp_text(buf, mask, w, h, w // 2, y, fid, size, s, rgb)
        y += size + 5
    _composite_stamp(buf, mask, w, h, cx, cy, angle)


def stamp_circle(cx, cy, lines, rgb, angle=0, d=132):
    buf, mask = _stamp_canvas(d, d)
    _stamp_circle(buf, mask, d, d // 2, d // 2, d // 2 - 3, rgb)
    _stamp_circle(buf, mask, d, d // 2, d // 2, d // 2 - 9, rgb)
    y = d // 2 - (len(lines) * 17) // 2 + 4
    for fid, size, s in lines:
        _stamp_text(buf, mask, d, d, d // 2, y, fid, size, s, rgb)
        y += size + 5
    _composite_stamp(buf, mask, d, d, cx, cy, angle)


# ---------------------------------------------------------------- background
fill_rect(0, 0, W, H, (12, 12, 12))
fill_rect(12, 12, 1000, 1000, PAPER)
# spine
fill_rect(504, 12, 16, 1000, (214, 206, 188))
vline(511, 12, 1000, (168, 160, 140), 2)
# guilloche: faint concentric arcs, both pages
for r in range(60, 460, 26):
    circle(262, 760, r, NAVY, a=0.05)
    circle(766, 300, r, NAVY, a=0.05)
for yy in range(30, 1010, 14):
    for xx in range(20, 500, 4):
        if int(math.sin((xx + yy) * 0.05) * 3 + yy) == yy:
            set_px(xx, yy + int(math.sin(xx * 0.03) * 2), NAVY, 0.03)

# ================================================================ LEFT PAGE
# emblem: volcano in a circle
EX, EY = 262, 66
circle(EX, EY, 32, NAVY, a=1.0)
circle(EX, EY, 28, NAVY, a=1.0)
poly_fill([(EX, EY - 20), (EX - 19, EY + 22), (EX + 19, EY + 22)], NAVY)
poly_fill([(EX - 5, EY - 20), (EX + 5, EY - 20), (EX + 2, EY - 12),
           (EX - 2, EY - 12)], RED)
circle(EX - 7, EY - 26, 3, GREY, a=0.9, fill=True)
circle(EX + 2, EY - 30, 4, GREY, a=0.9, fill=True)
circle(EX + 9, EY - 25, 2, GREY, a=0.9, fill=True)
for k, wy in enumerate((EY + 14, EY + 19)):
    for xx in range(EX - 16, EX + 17, 2):
        set_px(xx, wy + int(math.sin((xx - EX) * 0.35) * 2), NAVY, 0.9)

draw_text_c(262, 108, "serif_b", 30, "REPUBLIC OF TEFRAYA", NAVY)
draw_text_c(262, 144, "sans", 11, "T E F R A Y A   R E P U B L I K A", RED)
draw_text_c(262, 162, "sans_b", 13, "P A S S P O R T", INK)
hline(32, 186, 460, NAVY, 2)
hline(32, 190, 460, NAVY, 1)

# photo
rect_outline(31, 201, 182, 227, NAVY, 2)
blit_portrait(32, 202, PW, PH)
draw_text(32, 432, "sans", 10, "PHOTOGRAPH", GREY)
# signature
draw_text(32, 448, "serif_i", 26, "Mara Ilse Velkora", (38, 52, 96))
hline(32, 478, 180, INK, 1)
draw_text(32, 484, "sans", 10, "HOLDER'S SIGNATURE", GREY)

# fields, right column
FX = 232


def field(x, y, label, value, vsize=15, vfont="sans_b"):
    draw_text(x, y, "sans", 10, label, GREY)
    draw_text(x, y + 12, vfont, vsize, value, INK)
    return y + 34


y = 202
draw_text(FX, y, "sans", 10, "Type / Type", GREY)
draw_text(FX, y + 12, "sans_b", 17, "P", INK)
draw_text(FX + 62, y, "sans", 10, "Code / Code", GREY)
draw_text(FX + 62, y + 12, "sans_b", 17, "TEF", INK)
draw_text(FX + 132, y, "sans", 10, "Passport No. / No.", GREY)
draw_text(FX + 132, y + 12, "sans_b", 17, DOC_NO, INK)
y += 40
y = field(FX, y, "Surname / Nom", "VELKORA", 17)
y = field(FX, y, "Given names / Prenoms", "MARA ILSE", 17)
y = field(FX, y, "Nationality / Nationalite", "TEFRAYAN", 15)
draw_text(FX, y, "sans", 10, "Date of birth / Ne(e) le", GREY)
draw_text(FX, y + 12, "sans_b", 15, "12 MAR 1981", INK)
draw_text(FX + 150, y, "sans", 10, "Sex / Sexe", GREY)
draw_text(FX + 150, y + 12, "sans_b", 15, "F", INK)
y += 34
y = field(FX, y, "Place of birth / Lieu de naissance", "PORT CALDERA", 15)
y = field(FX, y, "Personal No. / No. personnel", "810312-4471", 15)
draw_text(FX, y, "sans", 10, "Date of issue / Delivre le", GREY)
draw_text(FX, y + 12, "sans_b", 15, "14 FEB 2023", INK)
draw_text(FX + 150, y, "sans", 10, "Date of expiry / Expire le", GREY)
draw_text(FX + 150, y + 12, "sans_b", 15, "13 FEB 2033", INK)
y += 34
y = field(FX, y, "Authority / Autorite", "PASSPORT OFFICE, PORT CALDERA", 13)

# observations box + ghost image
OY = 560
rect_outline(32, OY, 460, 96, NAVY, 1)
draw_text(44, OY + 8, "sans_b", 11, "OBSERVATIONS", NAVY)
obs = [
    "Registered Ashfall Observer (ST-2).",
    "Crater road closed during eruption alerts;",
    "see endorsement on page 3.",
]
yy = OY + 26
for ln in obs:
    draw_text(44, yy, "serif", 13, ln, INK)
    yy += 17
blit_portrait(398, OY + 6, 84, 84, alpha=0.22, grey=True)
rect_outline(397, OY + 5, 86, 86, GREY, 1)

# faint large passport number (watermark)
draw_text_c(262, 700, "serif_b", 30, "T F 2 8 4 9 1 7", (200, 192, 172),
            alpha=0.55)
draw_text_c(262, 736, "sans", 11,
            "ASHFALL OBSERVER  -  ST-2  -  PORT CALDERA", GREY, alpha=0.7)

# MRZ
hline(32, 852, 460, NAVY, 1)
draw_text(32, 866, "mono_b", 15, MRZ1, INK)
draw_text(32, 890, "mono_b", 15, MRZ2, INK)
hline(32, 916, 460, NAVY, 1)
draw_text_c(262, 968, "sans", 12, "2", GREY)

# ================================================================ RIGHT PAGE
RX = 540
draw_text(RX, 34, "serif_b", 24, "VISAS", RED)
draw_text(RX + 92, 44, "sans", 11, "/ VIZE", GREY)
draw_text(986, 40, "sans", 12, "3", GREY)
hline(RX, 66, 450, RED, 2)

# endorsement box
EB_Y = 82
rect_outline(RX, EB_Y, 450, 128, NAVY, 2)
draw_text(RX + 12, EB_Y + 10, "sans_b", 12,
          "ENDORSEMENT 1 / 2023  -  ASHFALL ADVISORY", NAVY)
draw_text(RX + 12, EB_Y + 28, "sans", 10, "Port Caldera, 14 FEB 2023", GREY)
endorse = [
    "The holder is a registered Ashfall Observer (ST-2).",
    "Landing permitted only while the ash advisory is GREEN;",
    "crater road closed during eruption alerts.",
    "The ashfall levy must be paid before departure.",
]
yy = EB_Y + 48
for ln in endorse:
    draw_text(RX + 12, yy, "serif", 13, ln, INK)
    yy += 17

# visa sticker — Republic of Selmara
VY = 240
fill_rect(RX, VY, 450, 164, (233, 240, 228))
rect_outline(RX, VY, 450, 164, GREEN_D, 2)
rect_outline(RX + 5, VY + 5, 440, 154, GREEN_D, 1)
draw_text(RX + 12, VY + 12, "serif_b", 17, "REPUBLIC OF SELMARA", GREEN_D)
draw_text(RX + 330, VY + 14, "sans_b", 15, "VISA C", GREEN_D)
draw_text(RX + 12, VY + 34, "sans", 11, "SHORT-STAY VISA", GREY)
draw_text(RX + 330, VY + 34, "sans", 11, "No. SEL 552 091", INK)
draw_text(RX + 12, VY + 56, "sans", 10, "VALID FROM / DU", GREY)
draw_text(RX + 12, VY + 68, "sans_b", 12, "01 AUG 2024", INK)
draw_text(RX + 170, VY + 56, "sans", 10, "UNTIL / AU", GREY)
draw_text(RX + 170, VY + 68, "sans_b", 12, "31 AUG 2024", INK)
draw_text(RX + 330, VY + 56, "sans", 10, "STAY / SEJOUR", GREY)
draw_text(RX + 330, VY + 68, "sans_b", 12, "15 DAYS", INK)
draw_text(RX + 12, VY + 90, "sans", 10, "ENTRIES", GREY)
draw_text(RX + 12, VY + 102, "sans_b", 12, "1 - SINGLE", INK)
draw_text(RX + 170, VY + 90, "sans", 10, "ISSUED AT / DELIVRE A", GREY)
draw_text(RX + 170, VY + 102, "sans_b", 12, "CONSULATE, PORT CALDERA", INK)
draw_text(RX + 12, VY + 122, "sans", 10, "PASSPORT", GREY)
draw_text(RX + 12, VY + 134, "sans_b", 12, DOC_NO, INK)
draw_text(RX + 170, VY + 122, "sans", 10, "REMARKS", GREY)
draw_text(RX + 170, VY + 134, "sans_b", 11, "ENTRY BY FERRY ONLY", INK)
draw_text(RX + 170, VY + 147, "sans_b", 11, "FEE 35 SEL PAID", INK)
# barcode
_bx = RX + 330
for k, wd in enumerate([3, 1, 2, 1, 4, 2, 1, 3, 1, 2, 2, 1, 3, 1, 2, 4,
                        1, 1, 2, 3, 1, 2, 1, 4, 2, 1, 3, 2]):
    if k % 2 == 0:
        fill_rect(_bx, VY + 122, wd, 28, INK)
    _bx += wd + 1

# fee stamp overlapping endorsement corner (drawn AFTER the visa
# sticker so nothing covers it)
_fbuf, _fmask = _stamp_canvas(140, 84)
_stamp_rect(_fbuf, _fmask, 140, 2, 2, 136, 80, (146, 110, 20), 3)
_stamp_text(_fbuf, _fmask, 140, 84, 70, 10, "sans_b", 12, "TEFRAYA",
            (146, 110, 20))
_stamp_text(_fbuf, _fmask, 140, 84, 70, 27, "sans_b", 12, "ASHFALL LEVY",
            (146, 110, 20))
_stamp_text(_fbuf, _fmask, 140, 84, 70, 44, "sans_b", 15, "PAID",
            (146, 110, 20))
_stamp_text(_fbuf, _fmask, 140, 84, 70, 63, "sans_b", 11, "12 TEF",
            (146, 110, 20))
# yellow wash behind fee stamp
fill_rect(838, 160, 140, 84, YELLOW, a=0.35)
_composite_stamp(_fbuf, _fmask, 140, 84, 908, 202, -8)


draw_text(RX, 414, "sans_b", 11, "ENTRY AND EXIT  -  TRAVEL HISTORY", NAVY)

# stamps grid 3x3
SB = "sans_b"
stamps = [
    ("rect", 615, 480, STAMP_RED, -4,
     [(SB, 13, "TEFRAYA"), (SB, 12, "DEPARTURE"), (SB, 11, "02 MAR 2023"),
      (SB, 10, "PORT CALDERA")]),
    ("circ", 765, 480, STAMP_PURPLE, 3,
     [(SB, 12, "SELMARA"), (SB, 13, "ENTRY"), (SB, 11, "03 MAR 2023"),
      (SB, 10, "FERRY TERMINAL")]),
    ("rect", 915, 480, STAMP_PURPLE, -3,
     [(SB, 13, "SELMARA"), (SB, 12, "EXIT"), (SB, 11, "17 MAR 2023"),
      (SB, 10, "FERRY TERMINAL")]),
    ("rect", 615, 612, STAMP_BLUE, 4,
     [(SB, 13, "TEFRAYA"), (SB, 12, "ARRIVAL"), (SB, 11, "18 MAR 2023"),
      (SB, 10, "PORT CALDERA")]),
    ("circ", 765, 612, STAMP_GREEN, -4,
     [(SB, 12, "ORVIND"), (SB, 13, "ENTRY"), (SB, 11, "02 AUG 2024"),
      (SB, 10, "HARBOUR GATE 3")]),
    ("rect", 915, 612, STAMP_GREEN, 3,
     [(SB, 13, "ORVIND"), (SB, 12, "EXIT"), (SB, 11, "16 AUG 2024"),
      (SB, 10, "HARBOUR GATE 3")]),
    ("circ", 615, 744, STAMP_BLUE, -3,
     [(SB, 13, "TEFRAYA"), (SB, 12, "ARRIVAL"), (SB, 11, "17 AUG 2024"),
      (SB, 10, "PORT CALDERA")]),
    ("rect", 765, 744, STAMP_RED, 4,
     [(SB, 13, "TALBREK"), (SB, 12, "ENTRY"), (SB, 11, "14 MAY 2025"),
      (SB, 10, "NORTH PIER")]),
    ("circ", 915, 744, STAMP_RED, -4,
     [(SB, 13, "TALBREK"), (SB, 12, "EXIT"), (SB, 11, "28 MAY 2025"),
      (SB, 10, "NORTH PIER")]),
]
for kind, cx, cy, col, ang, lines in stamps:
    if kind == "rect":
        stamp_rect(cx, cy, lines, col, ang)
    else:
        stamp_circle(cx, cy, lines, col, ang)

# bottom note
note = ("This passport remains the property of the Republic of Tefraya. "
        "If found, please return it to any Tefrayan consulate or harbour office.")
for i, ln in enumerate(wrap_text("serif", 13, note, 450)):
    draw_text(RX, 906 + i * 17, "serif", 13, ln, GREY)
draw_text(RX + 380, 952, "sans", 10, DOC_NO, GREY)
draw_text_c(765, 968, "sans", 12, "3", GREY)

# ---------------------------------------------------------------- PNG encode
def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def write_png(path):
    raw = bytearray()
    prev = bytearray(W * 3)
    for y in range(H):
        row = canvas[y * W * 3:(y + 1) * W * 3]
        filt = bytearray(W * 3)
        for i in range(W * 3):
            a = row[i - 3] if i >= 3 else 0
            b = prev[i]
            c = prev[i - 3] if i >= 3 else 0
            filt[i] = (row[i] - _paeth(a, b, c)) & 0xFF
        raw.append(4)
        raw.extend(filt)
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    n = write_png(out)
    print("wrote %s %d bytes %dx%d" % (out, n, W, H))
    print("MRZ1 %s" % MRZ1)
    print("MRZ2 %s" % MRZ2)


if __name__ == "__main__":
    main()
