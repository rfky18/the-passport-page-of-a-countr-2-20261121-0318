#!/usr/bin/env python3
"""Republic of Tefraya passport spread — v2.
Pure stdlib. Reads atlas.bin/atlas.json + portrait.bin next to this file,
renders a 1024x1024 open-passport spread to /output/entry.png (or argv[1]).
Text is blitted from a real bitmap-font atlas rendered at build time.
MRZ check digits are computed in code with the ICAO 9303 algorithm.
"""
import json, math, os, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
W = H = 1024

# ---------------------------------------------------------------- data
with open(os.path.join(HERE, "atlas.json")) as fh:
    ATLAS = json.load(fh)
with open(os.path.join(HERE, "atlas.bin"), "rb") as fh:
    ABIN = fh.read()
AW = ATLAS["w"]
with open(os.path.join(HERE, "portrait.bin"), "rb") as fh:
    PORTRAIT = fh.read()
PW, PH = 186, 236

# ---------------------------------------------------------------- canvas
class Img:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.p = bytearray(bg) * (w * h)

    def px(self, x, y, r, g, b, a=255):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            if a >= 255:
                self.p[i], self.p[i + 1], self.p[i + 2] = r, g, b
            else:
                self.p[i] = (r * a + self.p[i] * (255 - a)) // 255
                self.p[i + 1] = (g * a + self.p[i + 1] * (255 - a)) // 255
                self.p[i + 2] = (b * a + self.p[i + 2] * (255 - a)) // 255

    def fill(self, x0, y0, x1, y1, col, a=255):
        r, g, b = col
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.px(x, y, r, g, b, a)

    def rect(self, x0, y0, x1, y1, col, t=1):
        for k in range(t):
            self.hline(x0, y0 + k, x1, col)
            self.hline(x0, y1 - k, x1, col)
            self.vline(x0 + k, y0, y1, col)
            self.vline(x1 - k, y0, y1, col)

    def hline(self, x0, y, x1, col, a=255):
        r, g, b = col
        for x in range(min(x0, x1), max(x0, x1) + 1):
            self.px(x, y, r, g, b, a)

    def vline(self, x, y0, y1, col, a=255):
        r, g, b = col
        for y in range(min(y0, y1), max(y0, y1) + 1):
            self.px(x, y, r, g, b, a)

    def line(self, x0, y0, x1, y1, col, a=255):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err, x, y = dx - dy, x0, y0
        while True:
            self.px(x, y, *col, a)
            if x == x1 and y == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def circle(self, cx, cy, r, col, a=255):
        x, y, d = 0, r, 3 - 2 * r
        while x <= y:
            for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                           (x, -y), (y, -x), (-x, -y), (-y, -x)):
                self.px(cx + sx, cy + sy, *col, a)
            if d < 0:
                d += 4 * x + 6
            else:
                d += 4 * (x - y) + 10
                y -= 1
            x += 1

    def disc(self, cx, cy, r, col, a=255):
        for y in range(cy - r, cy + r + 1):
            dx = int(math.sqrt(max(0, r * r - (y - cy) ** 2)))
            self.hline(cx - dx, y, cx + dx, col, a)

    def polyfill(self, pts, col, a=255):
        for y in range(min(p[1] for p in pts), max(p[1] for p in pts) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.hline(int(xs[k]), y, int(xs[k + 1]), col, a)

    def blit_rgb(self, data, sw, sh, dx, dy, alpha=255):
        for y in range(sh):
            for x in range(sw):
                i = (y * sw + x) * 3
                self.px(dx + x, dy + y, data[i], data[i + 1], data[i + 2], alpha)

# ---------------------------------------------------------------- text
def tw(font, s, track=0):
    f = ATLAS["fonts"][font]
    w = 0
    for ch in s:
        g = f["chars"].get(ch) or f["chars"]["?"]
        w += g["adv"] + track
    return int(w - track) if s else 0

def text(img, x, y, font, s, col, align="l", track=0, alpha=255):
    """y = top of the em box. align l/c/r around x."""
    f = ATLAS["fonts"][font]
    w = tw(font, s, track)
    if align == "c":
        x -= w // 2
    elif align == "r":
        x -= w
    r, g, b = col
    cx = int(x)
    for ch in s:
        gl = f["chars"].get(ch) or f["chars"]["?"]
        cell = gl["cell"]
        cw, chh = cell[2], cell[3]
        for gy in range(chh):
            ay = y + gy
            if ay < 0 or ay >= img.h:
                continue
            row = (cell[1] + gy) * AW + cell[0]
            for gx in range(cw):
                v = ABIN[row + gx]
                if v:
                    img.px(cx + gx, ay, r, g, b, (v * alpha) // 255)
        cx += int(gl["adv"] + track)

# ---------------------------------------------------------------- MRZ (ICAO 9303)
def mrz_cd(s):
    wts = (7, 3, 1)
    tot = 0
    for i, ch in enumerate(s):
        if "0" <= ch <= "9":
            v = ord(ch) - 48
        elif "A" <= ch <= "Z":
            v = ord(ch) - 55
        else:
            v = 0
        tot += v * wts[i % 3]
    return str(tot % 10)

def build_mrz():
    line1 = "P<TEFVELKORA<<MARA<ILSE"
    line1 += "<" * (44 - len(line1))
    doc = "TF284917<"
    dob, exp = "900312", "330213"
    pers = "9003124471<<<<"
    l2 = (doc + mrz_cd(doc) + "TEF" + dob + mrz_cd(dob) + "F" +
          exp + mrz_cd(exp) + pers + mrz_cd(pers))
    comp = mrz_cd(doc + mrz_cd(doc) + dob + mrz_cd(dob) +
                  exp + mrz_cd(exp) + pers + mrz_cd(pers))
    l2 += comp
    assert len(line1) == 44 and len(l2) == 44, (len(line1), len(l2))
    return line1, l2

# ---------------------------------------------------------------- PNG
def save_png(img, path):
    raw = bytearray()
    for y in range(img.h):
        raw.append(0)
        raw += img.p[y * img.w * 3:(y + 1) * img.w * 3]
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", struct.pack(">IIBBBBB", img.w, img.h, 8, 2, 0, 0, 0)) +
           chunk(b"IDAT", zlib.compress(bytes(raw), 6)) +
           chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)

# ---------------------------------------------------------------- colours
PAPER = (247, 242, 228)
PAPER2 = (250, 246, 236)
NAVY = (28, 42, 84)
INK = (32, 32, 36)
RED = (142, 34, 34)
GREEN = (28, 108, 68)
PURPLE = (108, 58, 138)
BLUE = (28, 68, 158)
GOLD = (148, 108, 28)
GREY = (104, 97, 78)
LGREY = (206, 198, 176)
GUI = (222, 214, 188)

# ---------------------------------------------------------------- stamps
class Stamp:
    """Small RGBA canvas, drawn then rotated onto the page."""
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.p = bytearray(w * h * 4)

    def px(self, x, y, col, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 4
            self.p[i], self.p[i + 1], self.p[i + 2], self.p[i + 3] = (
                col[0], col[1], col[2], a)

    def rect(self, x0, y0, x1, y1, col, t=1, a=215):
        for k in range(t):
            for x in range(x0, x1 + 1):
                self.px(x, y0 + k, col, a)
                self.px(x, y1 - k, col, a)
            for y in range(y0, y1 + 1):
                self.px(x0 + k, y, col, a)
                self.px(x1 - k, y, col, a)

    def circle(self, cx, cy, r, col, a=215):
        x, y, d = 0, r, 3 - 2 * r
        while x <= y:
            for sx, sy in ((x, y), (y, x), (-x, y), (-y, x),
                           (x, -y), (y, -x), (-x, -y), (-y, -x)):
                self.px(cx + sx, cy + sy, col, a)
            if d < 0:
                d += 4 * x + 6
            else:
                d += 4 * (x - y) + 10
                y -= 1
            x += 1

    def text(self, x, y, font, s, col, align="l", track=0, alpha=215):
        f = ATLAS["fonts"][font]
        w = tw(font, s, track)
        if align == "c":
            x -= w // 2
        elif align == "r":
            x -= w
        cx = int(x)
        for ch in s:
            gl = f["chars"].get(ch) or f["chars"]["?"]
            cell = gl["cell"]
            for gy in range(cell[3]):
                row = (cell[1] + gy) * AW + cell[0]
                for gx in range(cell[2]):
                    v = ABIN[row + gx]
                    if v:
                        self.px(cx + gx, y + gy, col, (v * alpha) // 255)
            cx += int(gl["adv"] + track)

    def paste_rotated(self, img, cx, cy, deg):
        th = math.radians(deg)
        cs, sn = math.cos(th), math.sin(th)
        hw, hh = self.w / 2, self.h / 2
        rad = int(math.hypot(hw, hh)) + 2
        for oy in range(-rad, rad + 1):
            for ox in range(-rad, rad + 1):
                sx = ox * cs + oy * sn + hw
                sy = -ox * sn + oy * cs + hh
                ix, iy = int(sx), int(sy)
                if 0 <= ix < self.w and 0 <= iy < self.h:
                    i = (iy * self.w + ix) * 4
                    a = self.p[i + 3]
                    if a:
                        img.px(cx + ox, cy + oy, self.p[i], self.p[i + 1],
                               self.p[i + 2], int(a * 0.88))

def rect_stamp(place, action, date, loc, col, rot):
    s = Stamp(158, 88)
    s.rect(2, 2, 155, 85, col, 2)
    s.rect(7, 7, 150, 80, col, 1)
    s.text(79, 12, "sans_b12", place, col, "c")
    s.text(79, 29, "sans_b12", action, col, "c")
    s.text(79, 46, "sans_b11", date, col, "c")
    s.text(79, 63, "sans_b9", loc, col, "c")
    return s, rot

def circ_stamp(place, action, date, loc, col, rot):
    s = Stamp(112, 112)
    s.circle(56, 56, 53, col)
    s.circle(56, 56, 46, col)
    s.text(56, 22, "sans_b11", place, col, "c")
    s.text(56, 38, "sans_b11", action, col, "c")
    s.text(56, 54, "sans_b10", date, col, "c")
    s.text(56, 70, "sans_b9", loc, col, "c")
    return s, rot

def fee_stamp():
    s = Stamp(158, 88)
    s.rect(2, 2, 155, 85, GOLD, 2)
    s.rect(7, 7, 150, 80, GOLD, 1)
    s.text(79, 11, "sans_b11", "TEFRAYA", GOLD, "c")
    s.text(79, 27, "sans_b11", "ASHFALL LEVY", GOLD, "c")
    s.text(79, 43, "sans_b13", "PAID", GOLD, "c")
    s.text(79, 61, "sans_b11", "12 TEF", GOLD, "c")
    return s, -12

# ---------------------------------------------------------------- helpers
def field(img, x, y, label, value, vfont="sans_b15"):
    text(img, x, y, "sans_r9", label, GREY)
    text(img, x, y + 12, vfont, value, INK)

def guilloche(img, cx, cy, rmax):
    r = 46
    while r <= rmax:
        img.circle(cx, cy, r, GUI, 110)
        r += 22

def barcode(img, x, y, digits, h=34):
    bx = x
    for d in digits:
        w = 2 + (int(d) % 3)
        img.fill(bx, y, bx + w, y + h, INK)
        bx += w + 2
    return bx - x

# ---------------------------------------------------------------- build
def build():
    img = Img(W, H, (12, 12, 14))
    img.fill(12, 12, 508, 1012, PAPER)
    img.fill(516, 12, 1012, 1012, PAPER)
    img.fill(508, 12, 516, 1012, (196, 188, 168))
    img.fill(12, 12, 1012, 1012, PAPER2, 0)  # no-op keeps paper flat
    guilloche(img, 260, 700, 300)
    guilloche(img, 764, 560, 280)

    # ---- left page: emblem + titles
    img.circle(260, 58, 33, NAVY)
    img.circle(260, 58, 28, NAVY)
    img.polyfill([(242, 78), (260, 38), (278, 78)], NAVY)
    img.polyfill([(256, 38), (264, 38), (260, 48)], RED)
    for k, yy in enumerate((84, 89)):
        for x in range(232, 289):
            img.px(x, yy + int(2 * math.sin((x - 232) / 9.0)), *NAVY)
    text(img, 260, 102, "serif_b34", "REPUBLIC OF TEFRAYA", NAVY, "c")
    text(img, 260, 138, "sans_b11", "TEFRAYA REPUBLIKA", RED, "c", track=3)
    text(img, 260, 156, "sans_b13", "PASSPORT", NAVY, "c", track=6)
    img.hline(30, 176, 490, NAVY)
    img.hline(30, 179, 490, NAVY)

    # ---- photo + signature
    img.blit_rgb(PORTRAIT, PW, PH, 30, 190)
    img.rect(30, 190, 30 + PW - 1, 190 + PH - 1, NAVY, 2)
    text(img, 30, 438, "serif_i26", "Mara Ilse Velkora", NAVY)
    img.hline(30, 470, 212, NAVY)
    text(img, 30, 476, "sans_r9", "HOLDER'S SIGNATURE", GREY)

    # ---- fields (English labels only — v1 bilingual labels mis-rendered)
    fx = 232
    field(img, fx, 190, "Type", "P", "sans_b16")
    field(img, 300, 190, "Code", "TEF", "sans_b16")
    field(img, 372, 190, "Passport No.", "TF284917", "sans_b16")
    field(img, fx, 238, "Surname", "VELKORA")
    field(img, fx, 284, "Given names", "MARA ILSE")
    field(img, fx, 330, "Nationality", "TEFRAYAN")
    field(img, fx, 376, "Date of birth", "12 MAR 1990")
    field(img, 430, 376, "Sex", "F")
    field(img, fx, 422, "Place of birth", "PORT CALDERA")
    field(img, fx, 468, "Personal No.", "900312-4471")
    field(img, fx, 514, "Date of issue", "14 FEB 2023")
    field(img, 384, 514, "Date of expiry", "13 FEB 2033")
    text(img, fx, 560, "sans_r9", "Authority", GREY)
    text(img, fx, 572, "sans_b15", "PASSPORT OFFICE,", INK)
    text(img, fx, 590, "sans_b15", "PORT CALDERA", INK)

    # ---- observations + ghost image
    img.rect(30, 640, 490, 748, NAVY, 1)
    text(img, 44, 652, "sans_b11", "OBSERVATIONS", NAVY)
    text(img, 44, 672, "sans_r11",
         "Registered Ashfall Observer (ST-2).", INK)
    text(img, 44, 690, "sans_r11",
         "Crater road closed during eruption alerts;", INK)
    text(img, 44, 708, "sans_r11", "see endorsement on page 3.", INK)
    # ghost portrait: downscaled, faded toward paper
    gw, gh = 52, 66
    for y in range(gh):
        for x in range(gw):
            si = (int(y * PH / gh) * PW + int(x * PW / gw)) * 3
            pr, pg, pb = PORTRAIT[si], PORTRAIT[si + 1], PORTRAIT[si + 2]
            img.px(424 + x, 664 + y,
                   (pr * 3 + PAPER[0] * 7) // 10,
                   (pg * 3 + PAPER[1] * 7) // 10,
                   (pb * 3 + PAPER[2] * 7) // 10)
    img.rect(424, 664, 424 + gw - 1, 664 + gh - 1, GREY, 1)

    # ---- watermark + MRZ
    text(img, 260, 772, "serif_b34", "TF284917", LGREY, "c")
    text(img, 260, 812, "sans_b9", "ASHFALL OBSERVER - ST-2 - PORT CALDERA",
         LGREY, "c", track=1)
    m1, m2 = build_mrz()
    img.hline(30, 852, 490, NAVY)
    text(img, 30, 864, "mono_b17", m1, INK)
    text(img, 30, 888, "mono_b17", m2, INK)
    img.hline(30, 914, 490, NAVY)
    text(img, 260, 980, "sans_r10", "2", GREY, "c")

    # ---- right page: visas
    text(img, 532, 30, "serif_b26", "VISAS", RED)
    text(img, 648, 40, "sans_b11", "/ VIZE", GREY)
    text(img, 1000, 36, "sans_r10", "3", GREY, "r")
    img.hline(532, 64, 996, RED)
    img.hline(532, 67, 996, RED)

    # endorsement
    img.rect(532, 78, 996, 186, NAVY, 1)
    text(img, 546, 90, "sans_b11", "ENDORSEMENT 1 / 2023 - ASHFALL ADVISORY",
         NAVY)
    text(img, 982, 92, "sans_r9", "Port Caldera, 14 FEB 2023", GREY, "r")
    text(img, 546, 112, "sans_r11",
         "The holder is a registered Ashfall Observer (ST-2).", INK)
    text(img, 546, 130, "sans_r11",
         "Landing permitted only while the ash advisory is GREEN;", INK)
    text(img, 546, 148, "sans_r11",
         "crater road closed during eruption alerts.", INK)
    text(img, 546, 166, "sans_r11",
         "The ashfall levy must be paid before departure.", INK)
    st, rot = fee_stamp()
    st.paste_rotated(img, 930, 152, rot)

    # Selmara visa sticker — valid 01-31 MAR 2023, used by the Mar 2023 trip
    img.rect(532, 198, 996, 356, GREEN, 2)
    img.rect(538, 204, 990, 350, GREEN, 1)
    text(img, 548, 212, "serif_b20", "REPUBLIC OF SELMARA", GREEN)
    text(img, 548, 240, "sans_r10", "SHORT-STAY VISA", GREY)
    text(img, 980, 212, "sans_b13", "VISA C", INK, "r")
    text(img, 980, 232, "sans_b11", "No. SEL 552 091", RED, "r")
    field(img, 548, 262, "VALID FROM / DU", "01 MAR 2023", "sans_b11")
    field(img, 700, 262, "UNTIL / AU", "31 MAR 2023", "sans_b11")
    field(img, 866, 262, "STAY / SEJOUR", "15 DAYS", "sans_b11")
    field(img, 548, 296, "ENTRIES", "1 - SINGLE", "sans_b11")
    field(img, 700, 296, "ISSUED AT / DELIVRE A", "CONSULATE, PORT CALDERA",
         "sans_b11")
    field(img, 548, 330, "PASSPORT", "TF284917", "sans_b11")
    text(img, 700, 330, "sans_r9", "REMARKS", GREY)
    text(img, 700, 342, "sans_b10",
         "ENTRY BY FERRY ONLY - FEE 35 SEL PAID", INK)
    barcode(img, 906, 296, "552091")
    text(img, 936, 334, "sans_r9", "552 091", INK, "c")

    # ---- travel history: 3 trips, every trip fully paired
    # DEP home -> ENTRY abroad -> EXIT abroad -> ARR home, chronological.
    text(img, 532, 370, "sans_b11", "ENTRY AND EXIT - TRAVEL HISTORY", NAVY)
    trips = [
        ("TEFRAYA", "DEPARTURE", "02 MAR 2023", "PORT CALDERA", "rect", RED, -4),
        ("SELMARA", "ENTRY", "03 MAR 2023", "FERRY TERMINAL", "circ", PURPLE, 3),
        ("SELMARA", "EXIT", "17 MAR 2023", "FERRY TERMINAL", "rect", PURPLE, -3),
        ("TEFRAYA", "ARRIVAL", "18 MAR 2023", "PORT CALDERA", "rect", BLUE, 4),
        ("TEFRAYA", "DEPARTURE", "01 AUG 2024", "PORT CALDERA", "rect", RED, 3),
        ("ORVIND", "ENTRY", "02 AUG 2024", "HARBOUR GATE 3", "circ", GREEN, -4),
        ("ORVIND", "EXIT", "16 AUG 2024", "HARBOUR GATE 3", "rect", GREEN, 3),
        ("TEFRAYA", "ARRIVAL", "17 AUG 2024", "PORT CALDERA", "circ", BLUE, -3),
        ("TEFRAYA", "DEPARTURE", "13 MAY 2025", "PORT CALDERA", "rect", RED, -3),
        ("TALBREK", "ENTRY", "14 MAY 2025", "NORTH PIER", "circ", RED, 4),
        ("TALBREK", "EXIT", "28 MAY 2025", "NORTH PIER", "rect", PURPLE, -4),
        ("TEFRAYA", "ARRIVAL", "29 MAY 2025", "PORT CALDERA", "rect", BLUE, 3),
    ]
    for i, (pl, ac, dt, loc, shape, col, rot) in enumerate(trips):
        colx = 532 + (i % 3) * 158
        rowy = 384 + (i // 3) * 90
        if shape == "rect":
            s, r = rect_stamp(pl, ac, dt, loc, col, rot)
            s.paste_rotated(img, colx + 75, rowy + 41, r)
        else:
            s, r = circ_stamp(pl, ac, dt, loc, col, rot)
            s.paste_rotated(img, colx + 75, rowy + 41, r)

    # ---- ash advisory strip fills the lower-right page
    img.rect(532, 752, 996, 796, GREEN, 2)
    text(img, 548, 762, "sans_b12", "ASH ADVISORY - GREEN  |  CRATER ROAD OPEN",
         GREEN)
    text(img, 548, 780, "sans_r10",
         "NEXT REVIEW 30 JUN 2025 - PORT CALDERA ASH DESK", GREY)
    ash = Stamp(76, 76)
    ash.circle(38, 38, 36, GREEN)
    ash.circle(38, 38, 30, GREEN)
    ash.text(38, 14, "sans_b9", "ASH", GREEN, "c")
    ash.text(38, 26, "sans_b9", "DESK", GREEN, "c")
    ash.text(38, 40, "sans_b9", "29 MAY", GREEN, "c")
    ash.text(38, 51, "sans_b9", "2025", GREEN, "c")
    ash.paste_rotated(img, 956, 774, 8)

    text(img, 532, 850, "sans_r10",
         "This passport remains the property of the Republic of Tefraya.", GREY)
    text(img, 532, 868, "sans_r10",
         "If found, please return it to any Tefrayan consulate or harbour office.",
         GREY)
    text(img, 764, 980, "sans_r10", "3", GREY, "c")
    text(img, 1000, 980, "sans_b10", "TF284917", INK, "r")
    return img

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    img = build()
    n = save_png(img, out)
    print("wrote", out, n, "bytes")
    m1, m2 = build_mrz()
    print(m1)
    print(m2)

if __name__ == "__main__":
    main()
