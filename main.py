#!/usr/bin/env python3
"""Republic of Tefraya passport spread — make.fun program/v1 entry.
Pure Python 3 stdlib at runtime. Text is blitted from a real bitmap-font
atlas (atlas.bin/atlas.json, rendered at build time from Liberation/DejaVu
TTFs); the portrait ships as raw RGB (portrait.bin). Deterministic output:
1024x1024 PNG to /output/entry.png (or argv[1]).

Document: open passport of Mara Ilse Velkora, registered Ashfall Observer
(ST-2), Republic of Tefraya (fictional volcanic island republic), issued
Port Caldera 14 FEB 2023, expiry 13 FEB 2033. MRZ check digits are computed
in code with the ICAO 9303 algorithm (weights 7-3-1) and asserted.
"""
import json
import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1024, 1024

# ---------------------------------------------------------------- atlas
with open(os.path.join(HERE, "atlas.json")) as f:
    _ATLAS = json.load(f)
with open(os.path.join(HERE, "atlas.bin"), "rb") as f:
    _ATLAS_PIX = f.read()
_ATLAS_W = _ATLAS["w"]
_FONTS = _ATLAS["fonts"]


def glyph(font, ch):
    return _FONTS[font]["glyphs"].get(ch)


def text_w(s, font, track=0):
    w = 0
    for ch in s:
        g = glyph(font, ch)
        w += (g[4] if g else 0) + track
    return w - track if s else 0


# ---------------------------------------------------------------- canvas
class Canvas:
    """RGB canvas (ch=3) or RGBA canvas (ch=4, alpha in 4th byte)."""

    def __init__(self, w, h, ch=3, fill=(244, 238, 222)):
        self.w, self.h, self.ch = w, h, ch
        self.buf = bytearray(w * h * ch)
        for i in range(0, len(self.buf), ch):
            self.buf[i:i + ch] = bytes(fill[:ch])

    def _idx(self, x, y):
        return (y * self.w + x) * self.ch

    def px(self, x, y, color, alpha=255):
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = self._idx(x, y)
        if self.ch == 4:
            self.buf[i] = color[0]
            self.buf[i + 1] = color[1]
            self.buf[i + 2] = color[2]
            self.buf[i + 3] = max(self.buf[i + 3], alpha)
            return
        a = alpha / 255.0
        if a >= 1.0:
            self.buf[i] = color[0]
            self.buf[i + 1] = color[1]
            self.buf[i + 2] = color[2]
        elif a > 0:
            self.buf[i] = int(self.buf[i] + (color[0] - self.buf[i]) * a)
            self.buf[i + 1] = int(self.buf[i + 1] + (color[1] - self.buf[i + 1]) * a)
            self.buf[i + 2] = int(self.buf[i + 2] + (color[2] - self.buf[i + 2]) * a)

    def fill_rect(self, x0, y0, x1, y1, color, alpha=255):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.px(x, y, color, alpha)

    def rect(self, x0, y0, x1, y1, color, lw=1):
        for t in range(lw):
            for x in range(x0 + t, x1 - t):
                self.px(x, y0 + t, color)
                self.px(x, y1 - 1 - t, color)
            for y in range(y0 + t, y1 - t):
                self.px(x0 + t, y, color)
                self.px(x1 - 1 - t, y, color)

    def hline(self, x0, x1, y, color, lw=1):
        for t in range(lw):
            self.fill_rect(x0, y + t, x1, y + t + 1, color)

    def vline(self, x, y0, y1, color, lw=1):
        for t in range(lw):
            self.fill_rect(x + t, y0, x + t + 1, y1, color)

    def line(self, x0, y0, x1, y1, color):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            self.px(x, y, color)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, color, lw=1):
        # outline, midpoint algorithm, lw concentric rings
        for rr in range(r - lw + 1, r + 1):
            x, y, d = 0, rr, 1 - rr
            while x <= y:
                for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                               (x, -y), (y, -x), (-x, -y), (-y, -x)):
                    self.px(cx + sx, cy + sy, color)
                if d < 0:
                    d += 2 * x + 3
                else:
                    d += 2 * (x - y) + 5
                    y -= 1
                x += 1

    def disc(self, cx, cy, r, color):
        for y in range(cy - r, cy + r + 1):
            half = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            self.fill_rect(cx - half, y, cx + half + 1, y + 1, color)

    def text(self, s, font, x, y_baseline, color, align="l", track=0):
        """Draw text; y is the baseline. Returns width drawn."""
        w = text_w(s, font, track)
        if align == "c":
            x -= w // 2
        elif align == "r":
            x -= w
        pen = x
        for ch in s:
            g = glyph(font, ch)
            if g is None:
                continue
            ax, ay, gw, gh, adv, oy, bx = g
            if gw and gh:
                for r in range(gh):
                    src = (ay + r) * _ATLAS_W + ax
                    dy = y_baseline + oy + r
                    if dy < 0 or dy >= self.h:
                        continue
                    for c in range(gw):
                        a = _ATLAS_PIX[src + c]
                        if a:
                            self.px(pen + bx + c, dy, color, a)
            pen += adv + track
        return w


def wrap(s, font, maxw):
    words, lines, cur = s.split(" "), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_w(trial, font) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- PNG out
def write_png(c, path):
    raw = bytearray()
    for y in range(c.h):
        raw.append(0)  # filter None
        raw += c.buf[y * c.w * 3:(y + 1) * c.w * 3]
    raw_sub = bytearray()
    for y in range(c.h):
        raw_sub.append(1)  # filter Sub
        row = c.buf[y * c.w * 3:(y + 1) * c.w * 3]
        prev = bytearray(3)
        out = bytearray(len(row))
        for i in range(0, len(row), 3):
            for k in range(3):
                out[i + k] = (row[i + k] - prev[k]) & 0xFF
            prev = row[i:i + 3]
        raw_sub += out
    comp = min((zlib.compress(bytes(raw), 6), zlib.compress(bytes(raw_sub), 6)),
               key=len)
    ihdr = struct.pack(">IIBBBBB", c.w, c.h, 8, 2, 0, 0, 0)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- MRZ
def _mrz_val(ch):
    if ch == "<":
        return 0
    if ch.isdigit():
        return int(ch)
    return ord(ch) - 55  # A=10


def mrz_check(s):
    return sum(_mrz_val(ch) * w for ch, w in
               zip(s, [7, 3, 1] * ((len(s) + 2) // 3))) % 10


def build_mrz():
    line1 = "P<TEFVELKORA<<MARA<ILSE<<<<<<<<<<<<<<<<<<<<<"
    doc = "TF284917<"
    doc += str(mrz_check(doc))          # 5
    dob = "900312"
    dob += str(mrz_check(dob))          # 9
    exp = "330213"
    exp += str(mrz_check(exp))          # 0
    pers = "9003124471<<<<"
    pers += str(mrz_check(pers))        # 3
    body = doc + "TEF" + dob + "F" + exp + pers
    # Composite digit is 6 in the specified MRZ (kept verbatim per brief;
    # the four field check digits above are ICAO-verified in code).
    line2 = body + "6"
    assert len(line1) == 44 and len(line2) == 44, (len(line1), len(line2))
    assert line1 == "P<TEFVELKORA<<MARA<ILSE<<<<<<<<<<<<<<<<<<<<<"
    assert line2 == "TF284917<5TEF9003129F33021309003124471<<<<36", line2
    return line1, line2


# ---------------------------------------------------------------- stamps
def _aabb(cx, cy, w, h, angle_deg):
    """Axis-aligned bbox of a w x h rect centred at (cx, cy), rotated."""
    a = math.radians(abs(angle_deg))
    hw = (w * math.cos(a) + h * math.sin(a)) / 2.0
    hh = (w * math.sin(a) + h * math.cos(a)) / 2.0
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def _gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2])
    dy = max(b[1] - a[3], a[1] - b[3])
    return dx, dy


def _assert_gap(a, b, min_gap, what):
    dx, dy = _gap(a, b)
    assert dx >= min_gap or dy >= min_gap, (what, dx, dy)


def make_stamp(shape, lines, color, w=138, h=74):
    """lines: [(text, font), ...] centred. Returns RGBA Canvas."""
    if shape == "rect":
        buf = Canvas(w + 22, h + 22, ch=4, fill=(0, 0, 0, 0))
        ox, oy = 11, 11
        buf.rect(ox, oy, ox + w, oy + h, color, 2)
        buf.rect(ox + 4, oy + 4, ox + w - 4, oy + h - 4, color, 1)
        cy = oy + h // 2
        baselines = [cy - 20, cy - 6, cy + 7, cy + 20]
    else:  # circle, 88 mm diameter
        w = h = 88
        buf = Canvas(110, 110, ch=4, fill=(0, 0, 0, 0))
        ox = oy = 11
        cx, cy = ox + 44, oy + 44
        buf.circle(cx, cy, 44, color, 2)
        buf.circle(cx, cy, 39, color, 1)
        baselines = [cy - 24, cy - 8, cy + 8, cy + 22]
    for (txt, font), base in zip(lines, baselines):
        buf.text(txt, font, buf.w // 2, base, color, align="c")
    return buf


def paste_rotated(dst, buf, cx, cy, angle_deg):
    """Paste RGBA buffer centred at (cx, cy), rotated (bilinear)."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    hw, hh = buf.w / 2.0, buf.h / 2.0
    ext = int(max(abs(hw * ca) + abs(hh * sa),
                  abs(hw * sa) + abs(hh * ca))) + 2
    bcx, bcy = buf.w / 2.0, buf.h / 2.0
    for dy in range(-ext, ext + 1):
        for dx in range(-ext, ext + 1):
            # inverse rotation: source point for dest offset (dx, dy)
            sx = dx * ca + dy * sa + bcx
            sy = -dx * sa + dy * ca + bcy
            if sx < 0 or sy < 0 or sx > buf.w - 1 or sy > buf.h - 1:
                continue
            x0, y0 = int(sx), int(sy)
            fx, fy = sx - x0, sy - y0
            x1 = min(x0 + 1, buf.w - 1)
            y1 = min(y0 + 1, buf.h - 1)
            al = 0.0
            rgb = [0.0, 0.0, 0.0]
            for wy, yy in ((1 - fy, y0), (fy, y1)):
                for wx, xx in ((1 - fx, x0), (fx, x1)):
                    i = (yy * buf.w + xx) * 4
                    wgt = wx * wy
                    al += buf.buf[i + 3] * wgt
                    for k in range(3):
                        rgb[k] += buf.buf[i + k] * wgt
            if al > 4:
                dst.px(cx + dx, cy + dy,
                       (int(rgb[0]), int(rgb[1]), int(rgb[2])),
                       int(min(255, al)))


# ---------------------------------------------------------------- palette
PAPER = (244, 238, 222)
NAVY = (28, 42, 78)
DRED = (140, 32, 32)
GREEN = (30, 95, 60)
GREY = (112, 106, 92)
LGREY = (150, 142, 120)
GUI = (230, 224, 204)
RED = (165, 40, 40)
BLUE = (35, 70, 140)
PURP = (110, 60, 140)
GOLD = (150, 115, 30)


def guilloche(c, cx, cy, rmax, color):
    r = 26
    while r <= rmax:
        c.circle(cx, cy, r, color, 1)
        r += 16
    # faint horizontal wave lines
    for yy in range(40, 1000, 92):
        prev = None
        for x in range(20, 1004, 8):
            y = yy + int(3 * math.sin((x + yy) / 55.0))
            if prev is not None:
                c.line(prev[0], prev[1], x, y, color)
            prev = (x, y)


def draw_emblem(c, cx, cy):
    """Volcano + smoke + waves + stars inside a double circle."""
    c.circle(cx, cy, 37, NAVY, 2)
    c.circle(cx, cy, 31, NAVY, 1)
    # compass ticks on inner ring
    for k in range(8):
        a = math.radians(k * 45)
        x0 = cx + int(26 * math.cos(a))
        y0 = cy + int(26 * math.sin(a))
        x1 = cx + int(30 * math.cos(a))
        y1 = cy + int(30 * math.sin(a))
        c.line(x0, y0, x1, y1, NAVY)
    # volcano: apex (cx, cy-20), base (cx-22, cy+20)-(cx+22, cy+20)
    apex = (cx, cy - 20)
    c.line(cx - 22, cy + 20, apex[0], apex[1], NAVY)
    c.line(cx + 22, cy + 20, apex[0], apex[1], NAVY)
    c.line(cx - 22, cy + 20, cx + 22, cy + 20, NAVY)
    # crater notch + lava dot
    c.line(cx - 4, cy - 16, cx + 4, cy - 16, NAVY)
    c.disc(cx, cy - 15, 2, DRED)
    # smoke puffs above crater
    for sx, sy, sr in ((-7, -24, 3), (0, -27, 4), (7, -24, 3)):
        c.disc(cx + sx, cy + sy, sr, (120, 118, 110))
    # waves at the base
    for wy in (cy + 12, cy + 17):
        for x in range(cx - 20, cx + 20, 4):
            y = wy + int(2 * math.sin(x / 5.0))
            c.px(x, y, (40, 90, 140))
            c.px(x + 1, y, (40, 90, 140))


def paste_portrait(c, x, y, w, h, alpha=255):
    with open(os.path.join(HERE, "portrait.bin"), "rb") as f:
        raw = f.read()
    pw, ph = 200, 250
    for dy in range(h):
        sy = dy * ph // h
        for dx in range(w):
            sx = dx * pw // w
            i = (sy * pw + sx) * 3
            c.px(x + dx, y + dy,
                 (raw[i], raw[i + 1], raw[i + 2]), alpha)


# ---------------------------------------------------------------- layout
STAMPS = [
    # (place, kind, date, location, shape, color)
    ("TEFRAYA", "DEPARTURE", "02 MAR 2023", "PORT CALDERA", "rect", RED),
    ("SELMARA", "ENTRY", "03 MAR 2023", "FERRY TERMINAL", "circle", PURP),
    ("SELMARA", "EXIT", "17 MAR 2023", "FERRY TERMINAL", "rect", PURP),
    ("TEFRAYA", "ARRIVAL", "18 MAR 2023", "PORT CALDERA", "rect", BLUE),
    ("TEFRAYA", "DEPARTURE", "01 AUG 2024", "PORT CALDERA", "rect", RED),
    ("ORVIND", "ENTRY", "02 AUG 2024", "HARBOUR GATE 3", "circle", GREEN),
    ("ORVIND", "EXIT", "16 AUG 2024", "HARBOUR GATE 3", "rect", GREEN),
    ("TEFRAYA", "ARRIVAL", "17 AUG 2024", "PORT CALDERA", "circle", BLUE),
    ("TEFRAYA", "DEPARTURE", "13 MAY 2025", "PORT CALDERA", "rect", RED),
    ("TALBREK", "ENTRY", "14 MAY 2025", "NORTH PIER", "circle", RED),
    ("TALBREK", "EXIT", "28 MAY 2025", "NORTH PIER", "rect", PURP),
    ("TEFRAYA", "ARRIVAL", "29 MAY 2025", "PORT CALDERA", "rect", BLUE),
]
ANGLES = [-3, 2.5, -2, 3, -2.5, 2, -3, 2.5, -2, 3, -2.5, 2]


def field(c, x, y, label, value, vfont="s16", label_font="r9"):
    c.text(label, label_font, x, y + 9, GREY)
    c.text(value, vfont, x, y + 30, NAVY)


def build():
    c = Canvas(W, H, 3, fill=(18, 18, 18))
    # pages
    c.fill_rect(16, 16, 504, 1008, PAPER)
    c.fill_rect(520, 16, 1008, 1008, PAPER)
    c.vline(504, 16, 1008, (60, 55, 45), 2)
    c.vline(520, 16, 1008, (120, 112, 95), 2)
    guilloche(c, 260, 520, 470, GUI)
    guilloche(c, 764, 520, 470, GUI)

    # ============================ LEFT PAGE (p.2) =======================
    draw_emblem(c, 260, 66)
    c.text("REPUBLIC OF TEFRAYA", "s40", 260, 152, NAVY, align="c")
    c.text("TEFRAYA REPUBLIKA", "s13", 260, 176, DRED, align="c", track=4)
    c.text("P A S S P O R T", "s16", 260, 200, NAVY, align="c")
    c.hline(40, 480, 210, NAVY, 1)
    c.hline(40, 480, 213, NAVY, 1)

    # portrait
    c.rect(40, 222, 210, 434, NAVY, 2)
    paste_portrait(c, 42, 224, 166, 208)
    # signature under portrait
    c.text("Mara Ilse Velkora", "i24", 40, 468, NAVY)
    c.hline(40, 210, 474, NAVY, 1)
    c.text("HOLDER'S SIGNATURE", "r9", 40, 488, GREY)

    # data fields, right of portrait
    field(c, 226, 222, "Type", "P")
    field(c, 300, 222, "Code", "TEF")
    field(c, 372, 222, "Passport No.", "TF284917")
    field(c, 226, 262, "Surname", "VELKORA")
    field(c, 226, 302, "Given names", "MARA ILSE")
    field(c, 226, 342, "Nationality", "TEFRAYAN")
    field(c, 226, 382, "Date of birth", "12 MAR 1990")
    field(c, 400, 382, "Sex", "F")
    field(c, 226, 422, "Place of birth", "PORT CALDERA")
    field(c, 226, 462, "Personal No.", "900312-4471")
    field(c, 226, 502, "Date of issue", "14 FEB 2023")
    field(c, 366, 502, "Date of expiry", "13 FEB 2033")
    c.text("Authority", "r9", 226, 551, GREY)
    c.text("PASSPORT OFFICE,", "s16", 226, 572, NAVY)
    c.text("PORT CALDERA", "s16", 226, 592, NAVY)

    # observations box + ghost image
    c.rect(40, 612, 480, 700, NAVY, 1)
    c.text("OBSERVATIONS", "s12", 52, 634, NAVY)
    c.text("Registered Ashfall Observer (ST-2).", "r12", 52, 656, NAVY)
    c.text("Crater road closed during eruption alerts;", "r12", 52, 674, NAVY)
    c.text("see endorsement on page 3.", "r12", 52, 692, NAVY)
    paste_portrait(c, 424, 622, 44, 55, alpha=64)

    # watermark + MRZ
    c.text("TF284917", "s40", 260, 752, (222, 212, 186), align="c")
    c.text("ASHFALL OBSERVER - ST-2 - PORT CALDERA", "r10", 260, 776,
           LGREY, align="c", track=1)
    line1, line2 = build_mrz()
    c.hline(40, 480, 806, NAVY, 1)
    c.text(line1, "m16", 260, 834, NAVY, align="c")
    c.text(line2, "m16", 260, 862, NAVY, align="c")
    c.hline(40, 480, 874, NAVY, 1)
    c.text("2", "r11", 260, 992, GREY, align="c")

    # ============================ RIGHT PAGE (p.3) ======================
    c.text("VISAS", "s28", 544, 52, DRED)
    c.text("/ VIZE", "r13", 648, 52, GREY)
    c.text("3", "r11", 984, 52, GREY, align="r")
    c.hline(544, 984, 60, NAVY, 1)
    c.hline(544, 984, 63, NAVY, 1)

    # endorsement box (narrowed: levy stamp gets its own clear column)
    c.rect(544, 72, 856, 200, NAVY, 1)
    c.text("Port Caldera, 14 FEB 2023", "r10", 844, 90, GREY, align="r")
    c.text("ENDORSEMENT 1 / 2023 - ASHFALL ADVISORY", "s12", 556, 108, NAVY)
    body = ("The holder is a registered Ashfall Observer (ST-2). "
            "Landing permitted only while the ash advisory is GREEN; "
            "crater road closed during eruption alerts. "
            "The ashfall levy must be paid before departure.")
    for i, ln in enumerate(wrap(body, "r12", 288)):
        c.text(ln, "r12", 556, 128 + i * 16, NAVY)

    # ASHFALL LEVY fee stamp — own clear zone, top-right of visas page
    levy = make_stamp("rect", [("TEFRAYA", "s12"), ("ASHFALL LEVY", "b10"),
                               ("PAID", "s16"), ("12 TEF", "b10")], GOLD,
                      w=124, h=70)
    levy_cx, levy_cy = 930, 136
    paste_rotated(c, levy, levy_cx, levy_cy, -4)
    levy_box = _aabb(levy_cx, levy_cy, 124, 70, -4)
    _assert_gap(levy_box, (544, 72, 856, 200), 8, "levy vs endorsement")
    _assert_gap(levy_box, (544, 214, 984, 380), 8, "levy vs visa")

    # Selmara visa sticker
    c.rect(544, 214, 984, 380, GREEN, 2)
    c.rect(548, 218, 980, 376, GREEN, 1)
    c.text("REPUBLIC OF SELMARA", "s24", 560, 250, GREEN)
    c.text("VISA C", "s16", 968, 250, GREEN, align="r")
    c.text("SHORT-STAY VISA", "r10", 560, 268, GREEN)
    c.text("No. SEL 552 091", "s13", 968, 268, DRED, align="r")
    c.text("VALID FROM / DU", "r9", 560, 286, GREY)
    c.text("01 MAR 2023", "b11", 560, 304, NAVY)
    c.text("UNTIL / AU", "r9", 720, 286, GREY)
    c.text("31 MAR 2023", "b11", 720, 304, NAVY)
    c.text("STAY / SEJOUR", "r9", 880, 286, GREY)
    c.text("15 DAYS", "b11", 880, 304, NAVY)
    c.text("ENTRIES", "r9", 560, 322, GREY)
    c.text("1 - SINGLE", "b11", 560, 340, NAVY)
    c.text("ISSUED AT / DELIVRE A", "r9", 720, 322, GREY)
    c.text("CONSULATE, PORT CALDERA", "b11", 720, 340, NAVY)
    c.text("PASSPORT", "r9", 560, 358, GREY)
    c.text("TF284917", "b11", 560, 374, NAVY)
    c.text("REMARKS", "r9", 700, 358, GREY)
    c.text("ENTRY BY FERRY ONLY - FEE 35 SEL PAID", "b11", 700, 374, NAVY)
    # barcode, right edge, clear of the remarks line
    bars = [2, 1, 1, 1, 1, 2, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 2, 1]
    bx = 928
    for bw in bars:
        c.fill_rect(bx, 296, bx + bw, 326, NAVY)
        bx += bw + 1
    c.text("552 091", "m12", 968, 342, NAVY, align="r")

    # stamp grid heading
    c.text("ENTRY AND EXIT - TRAVEL HISTORY", "s12", 544, 398, NAVY)

    # 12 stamps, 3 cols x 4 rows, rotation <= 3 deg, verified gaps
    boxes = []
    for i, (place, kind, date, loc, shape, color) in enumerate(STAMPS):
        col, row = i % 3, i // 3
        cx = 544 + 69 + col * 151
        cy = 412 + 37 + row * 92
        if shape == "rect":
            lines = [(place, "s13"), (kind, "b11"), (date, "s12"), (loc, "r9")]
            buf = make_stamp("rect", lines, color)
            bw, bh = 138, 74
        else:
            lines = [(place, "b11"), (kind, "b10"), (date, "s12"), (loc, "r8")]
            buf = make_stamp("circle", lines, color)
            bw = bh = 88
        ang = ANGLES[i]
        paste_rotated(c, buf, cx, cy, ang)
        box = _aabb(cx, cy, bw, bh, ang)
        for j, prev in enumerate(boxes):
            _assert_gap(box, prev, 3, "stamp %d vs %d" % (i, j))
        boxes.append(box)

    # ash advisory strip
    c.fill_rect(544, 776, 984, 812, GREEN)
    c.text("ASH ADVISORY - GREEN  |  CRATER ROAD OPEN", "b11", 764, 792,
           (244, 238, 222), align="c")
    c.text("NEXT REVIEW 30 JUN 2025 - PORT CALDERA ASH DESK", "r10", 764,
           806, (244, 238, 222), align="c")

    # ASH DESK circular stamp — bottom-right, clear of strip and footer
    ash = make_stamp("circle", [("ASH", "b10"), ("DESK", "b10"),
                                ("29 MAY", "b10"), ("2025", "b10")], GREEN)
    ash_cx, ash_cy = 930, 872
    paste_rotated(c, ash, ash_cx, ash_cy, 3)
    ash_box = _aabb(ash_cx, ash_cy, 88, 88, 3)
    _assert_gap(ash_box, (544, 776, 984, 812), 10, "ash desk vs strip")
    _assert_gap(ash_box, (544, 828, 830, 876), 10, "ash desk vs footer")

    c.text("This passport remains the property of the", "r11", 544, 840, GREY)
    c.text("Republic of Tefraya. If found, please return it", "r11", 544, 856,
           GREY)
    c.text("to any Tefrayan consulate or harbour office.", "r11", 544, 872,
           GREY)
    c.text("3", "r11", 764, 992, GREY, align="c")
    c.text("TF284917", "r11", 984, 992, GREY, align="r")
    return c


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    c = build()
    n = write_png(c, out)
    print("wrote %s (%d bytes)" % (out, n))
    assert n <= 1048576, "entry.png over 1 MiB"
    return 0


if __name__ == "__main__":
    sys.exit(main())
