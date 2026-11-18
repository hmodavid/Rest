"""Artes ASCII. Cada arte devolve (brilho[], fase[], glifos|None) por celula.

brilho 0..1 escolhe o caractere da rampa; fase 0..1 escolhe a cor no gradiente
(o motor soma o deslocamento temporal -> efeito cascata)."""
from __future__ import annotations
import math
import random
import re
from collections import OrderedDict
from math import atan2, cos, exp, hypot, log, sin


def smooth(e0, e1, x):
    t = (x - e0) / (e1 - e0)
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


class Art:
    name = "art"
    desc = ""
    user = False
    defaults: dict = {}
    ranges: dict = {}
    choices: dict = {}

    def __init__(self):
        self._key = None
        self.pool = ["#"]

    def prepare(self, w, h, p, aspect):
        key = (w, h, aspect, tuple(sorted(p.items())))
        if key != self._key:
            self.setup(w, h, p, aspect)
            self._key = key

    def setup(self, w, h, p, aspect):
        pass

    def compute(self, w, h, t, p):
        raise NotImplementedError


# ------------------------------------------------------- fundo (estrelas + nebulosa)
class Backdrop:
    """Estrelas e nebulosa que cobrem a tela inteira (sem laterais vazias)."""

    def setup(self, w, h, aspect, density, nebula, mask=None, seed=2024):
        hh = h / 2.0
        rnd = random.Random(seed)
        self.stars, self.neb, self.nebula = [], [], nebula
        for _ in range(int(w * h * density)):
            k = rnd.randrange(w * h)
            if mask is None or not mask[k]:
                self.stars.append((k, 0.25 + 0.5 * rnd.random(), rnd.random() * 6.28, 0.6 + rnd.random() * 2))
        if nebula > 0:
            for j in range(h):
                y = (j + 0.5 - hh) / hh * 1.6
                for i in range(w):
                    k = j * w + i
                    if mask is None or not mask[k]:
                        self.neb.append((k, (i + 0.5 - w / 2.0) * aspect / hh * 1.6, y))

    def apply(self, br, ph, t):
        for k, b, tw, sd in self.stars:
            v = b * (0.55 + 0.45 * sin(t * sd + tw))
            if v > br[k]:
                br[k], ph[k] = v, 0.3
        if self.neb:
            amp = self.nebula * 0.5
            t1, t2, t3 = t * 0.07, t * 0.05, t * 0.04
            for k, x, y in self.neb:
                v = (sin(x * 1.1 + t1) + sin(y * 1.9 - t2 + 1.3) + sin((x + y) * 0.7 + t3) + 3) / 6
                v = (v - 0.6) * 2.5
                if v > 0:
                    b = v * amp
                    if b > br[k]:
                        br[k], ph[k] = b, 0.55 + v * 0.3


# ---------------------------------------------------------------- buraco negro
class BlackHole(Art):
    name = "blackhole"
    desc = "Buraco negro com disco de acrecao, lente gravitacional, anel de foton e efeito Doppler."
    defaults = dict(tilt=0.24, spin=1.0, zoom=1.0, doppler=0.7, ring=1.0, glow=1.0,
                    inner=1.5, outer=3.8, fill=True, stars=True, density=0.05, nebula=0.5)
    ranges = dict(tilt=(0.05, 0.7), spin=(-4, 4), zoom=(0.4, 2.5), doppler=(0, 1), ring=(0, 2.5),
                  glow=(0, 3), inner=(1.2, 3.0), outer=(2.0, 6.0), density=(0, 0.2), nebula=(0, 1))

    def setup(self, w, h, p, aspect):
        hh = h / 2.0
        rs = 0.34 * p["zoom"]          # raio da sombra em unidades de meia-altura
        tilt, r_in = p["tilt"], p["inner"]
        r_out = max(p["outer"], r_in + 0.4)
        if p["fill"]:                  # o disco se estende ate as bordas da tela
            r_out = max(r_out, 0.98 * ((w / 2.0) * aspect / hh) / rs)
        self.spin, self.doppler = p["spin"], p["doppler"]
        glow = p["glow"]
        mask = bytearray(w * h)
        act = []
        for j in range(h):
            Y = ((j + 0.5 - hh) / hh) / rs
            for i in range(w):
                X = ((i + 0.5 - w / 2.0) * aspect / hh) / rs
                r = hypot(X, Y)
                th = atan2(Y, X)
                if r < 1.1:
                    mask[j * w + i] = 1
                fl = None
                Yd = Y / tilt
                R = hypot(X, Yd)
                if r_in * 0.9 <= R <= r_out * 1.05:
                    front = Y >= 0
                    if front or r >= 1.0:
                        wgt = 1.0 if front else smooth(1.8, 3.0, r)
                        edge = smooth(r_in * 0.9, r_in + 0.25, R) * (1 - smooth(r_out - 0.9, r_out * 1.05, R))
                        em = edge * (r_in / R) ** 1.0 * 1.7 * wgt
                        if em > 0.02:
                            fl = (em, atan2(Yd, X), 1.6 / R ** 1.5, log(R), R * 0.22)
                ar = None
                if 1.0 <= r <= 2.9:
                    Re = r_in + (r - 1.0) * (min(r_out, 5.0) - r_in) / 1.9
                    aw = (1.0 if Y < 0 else 0.55) * exp(-(r - 1.0) / (0.5 * glow + 0.05))
                    em = (r_in / Re) ** 0.8 * 1.5 * aw
                    if em > 0.02:
                        ar = (em, th, 1.6 / Re ** 1.5, log(Re), Re * 0.22)
                pr = exp(-((r - 1.035) / 0.04) ** 2) * p["ring"] if r > 0.9 else 0.0
                haze = exp(-(r - 1.0) / 0.9) * 0.07 * glow if r >= 1.0 else 0.0
                if fl or ar or pr > 0.02 or haze > 0.02:
                    act.append((j * w + i, fl, ar, pr, haze))
        self.active = act
        self.back = Backdrop()
        self.back.setup(w, h, aspect, p["density"] if p["stars"] else 0.0, p["nebula"], mask)

    def compute(self, w, h, t, p):
        br = [0.0] * (w * h)
        ph = [0.0] * (w * h)
        self.back.apply(br, ph, t)
        spin, dop = self.spin, self.doppler
        for idx, fl, ar, pr, haze in self.active:
            b = haze
            f = 0.6
            if fl:
                em, phi, om, lg, fph = fl
                tex = 0.72 + 0.28 * sin(4.0 * (phi - om * spin * t) + 6.5 * lg)
                d = 1.0 - dop * 0.85 * cos(phi)
                v = em * tex * (d if d > 0.15 else 0.15)
                if v > b:
                    b, f = v, fph + 0.12 * tex
            if ar:
                em, phi, om, lg, aph = ar
                tex = 0.72 + 0.28 * sin(4.0 * (phi - om * spin * t) + 6.5 * lg)
                d = 1.0 - dop * 0.85 * cos(phi)
                v = em * tex * (d if d > 0.15 else 0.15)
                if v > b:
                    b, f = v, aph + 0.12 * tex
            if pr * 1.1 > b:
                b, f = pr * 1.1, 0.02
            if b > br[idx]:
                br[idx], ph[idx] = b, f
        return br, ph, None


# ---------------------------------------------------------------------- galaxia
class Galaxy(Art):
    name = "galaxy"
    desc = "Galaxia espiral girando com nucleo brilhante."
    defaults = dict(arms=3, twist=3.2, spin=1.0, zoom=1.0, stars=True, density=0.04, nebula=0.4)
    ranges = dict(arms=(1, 8), twist=(0.5, 8), spin=(-4, 4), zoom=(0.4, 3), density=(0, 0.2), nebula=(0, 1))

    def setup(self, w, h, p, aspect):
        hh = h / 2.0
        self.cells = []
        for j in range(h):
            y = (j + 0.5 - hh) / hh
            for i in range(w):
                x = (i + 0.5 - w / 2.0) * aspect / hh
                R = hypot(x, y) / (0.9 * p["zoom"])
                self.cells.append((atan2(y, x), log(R + 0.04), R))
        self.back = Backdrop()
        self.back.setup(w, h, aspect, p["density"] if p["stars"] else 0.0, p["nebula"])

    def compute(self, w, h, t, p):
        arms, tw, sp = p["arms"], p["twist"], p["spin"] * 0.8
        br, ph = [], []
        for th, lr, R in self.cells:
            v = 0.5 + 0.5 * cos(arms * (th - tw * lr) - t * sp)
            b = (v ** 2.5 * 0.9 + exp(-R * R * 14)) * exp(-R * 0.7)
            br.append(b)
            ph.append(R * 0.5 + v * 0.15)
        self.back.apply(br, ph, t)
        return br, ph, None


# ------------------------------------------------------------------------ rosca
class Donut(Art):
    name = "donut"
    desc = "Toro girando em 3D (classico donut.c) com z-buffer."
    defaults = dict(r1=1.0, r2=2.0, k2=5.0, spin=1.0, zoom=1.0, stars=True, density=0.04, nebula=0.5)
    ranges = dict(r1=(0.5, 1.5), r2=(1.0, 3.0), k2=(3, 10), spin=(-4, 4), zoom=(0.4, 2),
                  density=(0, 0.2), nebula=(0, 1))

    def setup(self, w, h, p, aspect):
        self.th = [(cos(a), sin(a), a / 6.2832) for a in (i * 0.09 for i in range(70))]
        self.pp = [(cos(a), sin(a)) for a in (i * 0.045 for i in range(140))]
        self.back = Backdrop()
        self.back.setup(w, h, aspect, p["density"] if p["stars"] else 0.0, p["nebula"])

    def compute(self, w, h, t, p):
        r1, r2, k2 = p["r1"], p["r2"], p["k2"]
        A, B = t * 0.9 * p["spin"], t * 0.5 * p["spin"]
        cA, sA, cB, sB = cos(A), sin(A), cos(B), sin(B)
        k1y = 0.42 * h * k2 / (r1 + r2) * p["zoom"]
        k1x = k1y / 0.5
        n = w * h
        zb, br, ph = [0.0] * n, [0.0] * n, [0.0] * n
        self.back.apply(br, ph, t)
        for ct, st, tf in self.th:
            cx, cy = r2 + r1 * ct, r1 * st
            for cp, sp in self.pp:
                x = cx * (cB * cp + sA * sB * sp) - cy * cA * sB
                y = cx * (sB * cp - sA * cB * sp) + cy * cA * cB
                z = k2 + cA * cx * sp + cy * sA
                ooz = 1.0 / z
                xp = int(w / 2 + k1x * ooz * x)
                yp = int(h / 2 - k1y * ooz * y)
                if 0 <= xp < w and 0 <= yp < h:
                    L = cp * ct * sB - cA * ct * sp - sA * st + cB * (cA * st - ct * sA * sp)
                    if L > 0:
                        k = yp * w + xp
                        if ooz > zb[k]:
                            zb[k] = ooz
                            br[k] = L * 0.72 + 0.1
                            ph[k] = tf
        return br, ph, None


# ----------------------------------------------------------------------- matrix
class Matrix(Art):
    name = "matrix"
    desc = "Chuva de glifos (usa o tipo de texto escolhido como alfabeto)."
    defaults = dict(density=0.9, length=14, speed=1.0)
    ranges = dict(density=(0.1, 1), length=(4, 40), speed=(0.2, 4))

    def setup(self, w, h, p, aspect):
        rnd = random.Random(7)
        self.cols = [(rnd.uniform(0.5, 1.6), rnd.uniform(0, 200), rnd.uniform(0.6, 1.3), rnd.random() < p["density"])
                     for _ in range(w)]

    def compute(self, w, h, t, p):
        n = w * h
        br, ph, ch = [0.0] * n, [0.0] * n, [None] * n
        L = int(p["length"])
        pool = self.pool or ["#"]
        pl = len(pool)
        tick = int(t * 6)
        for i, (sp, off, lm, on) in enumerate(self.cols):
            if not on:
                continue
            ln = max(3, int(L * lm))
            head = (t * sp * p["speed"] * 8 + off) % (h + ln)
            for j in range(h):
                d = head - j
                if 0 <= d < ln:
                    k = j * w + i
                    br[k] = 1.0 if d < 1 else (1 - d / ln) ** 1.5
                    ph[k] = i / w * 0.5 + d / ln * 0.4
                    ch[k] = pool[(i * 7919 + j * 104729 + tick * 13) % pl]
        return br, ph, ch


# ----------------------------------------------------------------------- plasma
class Plasma(Art):
    name = "plasma"
    desc = "Plasma classico de senoides sobrepostas."
    defaults = dict(scale=1.0, speed=1.0)
    ranges = dict(scale=(0.3, 3), speed=(0.2, 4))

    def setup(self, w, h, p, aspect):
        hh = h / 2.0
        s = p["scale"]
        self.cells = []
        for j in range(h):
            y = (j + 0.5 - hh) / hh * s
            for i in range(w):
                x = (i + 0.5 - w / 2.0) * aspect / hh * s
                self.cells.append((x, y, hypot(x, y)))

    def compute(self, w, h, t, p):
        t *= p["speed"]
        br, ph = [], []
        for x, y, d in self.cells:
            v = sin(x * 3 + t) + sin(y * 4 - t * 1.3) + sin((x + y) * 2.5 + t * 0.7) + sin(d * 4 - t * 1.1)
            v = (v + 4) / 8
            br.append(0.15 + 0.85 * v)
            ph.append(v)
        return br, ph, None


# ------------------------------------------------------------------------- warp
class Warp(Art):
    name = "warp"
    desc = "Viagem em dobra: estrelas com rastro vindo do centro."
    defaults = dict(count=180, speed=1.0, trail=0.05)
    ranges = dict(count=(20, 600), speed=(0.1, 4), trail=(0.01, 0.15))

    def setup(self, w, h, p, aspect):
        rnd = random.Random(99)
        n = int(p["count"] * w * h / 2000) + 10
        self.stars = []
        for _ in range(n):
            a = rnd.random() * 6.2832
            self.stars.append((cos(a), sin(a), rnd.random(), rnd.uniform(0.6, 1.4), a / 6.2832))
        self.rmax = hypot(w * aspect / 2, h / 2) * 1.05
        self.aspect = aspect

    def compute(self, w, h, t, p):
        n = w * h
        br, ph = [0.0] * n, [0.0] * n
        tr, asp, rmax = p["trail"], self.aspect, self.rmax
        for ca, sa, off, sp, af in self.stars:
            z = (off + t * 0.12 * sp * p["speed"]) % 1.0
            for k in range(3):
                zz = z - k * tr
                if zz < 0:
                    continue
                r = zz ** 2.2 * rmax
                xi = int(w / 2 + ca * r / asp)
                yi = int(h / 2 + sa * r)
                if 0 <= xi < w and 0 <= yi < h:
                    q = yi * w + xi
                    b = zz ** 1.2 * (1 - k * 0.35)
                    if b > br[q]:
                        br[q] = b
                        ph[q] = af + zz * 0.3
        return br, ph, None


# ------------------------------------------------------------------------ ondas
class Waves(Art):
    name = "waves"
    desc = "Camadas de ondas em movimento."
    defaults = dict(layers=5, amp=0.12, freq=1.0)
    ranges = dict(layers=(2, 9), amp=(0.02, 0.4), freq=(0.3, 4))

    def compute(self, w, h, t, p):
        n = w * h
        br, ph = [0.0] * n, [0.0] * n
        L = int(p["layers"])
        for i in range(w):
            x = i * 0.5 / max(1, h / 2)
            for l in range(L):
                base = h * (0.30 + 0.60 * l / max(1, L - 1))
                y0 = int(base + p["amp"] * h * sin(p["freq"] * x * 2.2 + t * (0.5 + 0.2 * l) + l * 1.7))
                for d in range(4):
                    j = y0 + d
                    if 0 <= j < h:
                        k = j * w + i
                        br[k] = 0.3 + 0.7 * (l + 1) / L * (1 - d / 4)
                        ph[k] = l / L + j / h * 0.3
        return br, ph, None


# ------------------------------------------------------------------------ fogo
class Fire(Art):
    name = "fire"
    desc = "Chamas subindo, com o gradiente do tema do chao ate a ponta."
    defaults = dict(speed=1.0, height=1.0, wind=0.4)
    ranges = dict(speed=(0.1, 4), height=(0.3, 2), wind=(0, 2))

    def compute(self, w, h, t, p):
        s = t * p["speed"]
        reach = 0.35 + 0.4 * p["height"]
        wind = p["wind"]
        br, ph = [], []
        for j in range(h):
            yn = (h - 1 - j) / max(1, h - 1)
            heat = max(0.0, 1.0 - yn / reach)
            wob = sin(yn * 6 - s * 2.2) * 1.5 + yn * wind * 4
            for i in range(w):
                x = i * 0.12
                n = 0.5 + 0.25 * sin(x * 2.3 + s * 3.1 + wob) + 0.25 * sin(x * 5.1 - s * 4.3 + yn * 9)
                br.append(heat * (0.35 + 0.9 * n))
                ph.append((1.0 - heat) * 0.6)
        return br, ph, None


# ----------------------------------------------------------------------- tunel
class Tunnel(Art):
    name = "tunnel"
    desc = "Tunel infinito de aneis e raios em perspectiva."
    defaults = dict(speed=1.0, arms=6, depth=3.0)
    ranges = dict(speed=(0.1, 4), arms=(1, 16), depth=(0.5, 8))

    def setup(self, w, h, p, aspect):
        hh = h / 2.0
        self.cells = []
        for j in range(h):
            y = (j + 0.5 - hh) / hh
            for i in range(w):
                x = (i + 0.5 - w / 2.0) * aspect / hh
                r = hypot(x, y) + 0.03
                self.cells.append((atan2(y, x), 1.0 / r, min(1.0, r * 2.2)))

    def compute(self, w, h, t, p):
        arms, d, s = p["arms"], p["depth"], t * p["speed"] * 2.0
        br, ph = [], []
        for a, inv, fade in self.cells:
            u = inv * d - s
            v = 0.5 + 0.5 * sin(u * 3.0) * cos(a * arms + u * 0.5)
            br.append(v * fade)
            ph.append(u * 0.08)
        return br, ph, None


# ------------------------------------------------------ arte de texto (importada)
FRAME_SEP = re.compile(r"^\s*---\s*frame\s*---\s*$", re.I)


def parse_text_art(text: str):
    """Texto -> lista de quadros (cada quadro = lista de linhas). Separador: ---frame---"""
    frames, cur = [], []
    for line in text.replace("\r", "").expandtabs(4).split("\n"):
        if FRAME_SEP.match(line):
            frames.append(cur)
            cur = []
        else:
            cur.append(line.rstrip())
    frames.append(cur)
    out = []
    for f in frames:
        while f and not f[-1].strip():
            f.pop()
        while f and not f[0].strip():
            f.pop(0)
        if f:
            out.append(f)
    return out or [["(arte vazia)"]]


class TextArt(Art):
    name = "text"
    desc = "Arte ASCII importada."
    defaults = dict(mode="center", speed=1.0, fps=4.0, gap=2)
    ranges = dict(speed=(0.1, 5), fps=(0.5, 30), gap=(0, 20))
    choices = dict(mode=("center", "bounce", "scroll", "wave", "tile"))
    frames = [["(vazio)"]]

    @staticmethod
    def _blit(lines, ox, oy, w, h, br, ph, ch, t, wave=0.0):
        for j, line in enumerate(lines):
            y = oy + j
            if not 0 <= y < h:
                continue
            dx = int(round(sin(t * 2 + j * 0.45) * wave)) if wave else 0
            row = y * w
            for i, c in enumerate(line):
                if c != " ":
                    x = ox + i + dx
                    if 0 <= x < w:
                        k = row + x
                        br[k], ch[k], ph[k] = 1.0, c, x / w * 0.6 + y / h * 0.4

    def compute(self, w, h, t, p):
        n = w * h
        br, ph, ch = [0.0] * n, [0.0] * n, [None] * n
        fr = self.frames[int(t * p["fps"]) % len(self.frames)] if len(self.frames) > 1 else self.frames[0]
        ah, aw = len(fr), max(len(l) for l in fr)
        sp, mode = p["speed"], p["mode"]
        cx, cy = (w - aw) // 2, (h - ah) // 2
        if mode == "bounce":
            rx, ry = max(1, w - aw), max(1, h - ah)
            cx = int(rx * abs((t * sp * 10 / rx) % 2 - 1))
            cy = int(ry * abs((t * sp * 5 / ry) % 2 - 1))
            self._blit(fr, cx, cy, w, h, br, ph, ch, t)
        elif mode == "scroll":
            self._blit(fr, w - int(t * sp * 10) % (w + aw), cy, w, h, br, ph, ch, t)
        elif mode == "wave":
            self._blit(fr, cx, cy, w, h, br, ph, ch, t, wave=3.0)
        elif mode == "tile":
            px, py = aw + p["gap"] * 2, ah + p["gap"]
            sx, sy = int(t * sp * 3) % px, int(t * sp * 1.5) % py
            for oy in range(-py + sy, h, py):
                for ox in range(-px + sx, w, px):
                    self._blit(fr, ox, oy, w, h, br, ph, ch, t)
        else:
            self._blit(fr, cx, cy, w, h, br, ph, ch, t)
        return br, ph, ch


def make_text_art(name: str, frames, desc: str = ""):
    return type("Text_" + name.replace("-", "_"), (TextArt,), dict(
        name=name, user=True, frames=frames,
        desc=desc or f"Arte importada ({len(frames)} quadro{'s' if len(frames) > 1 else ''})."))


ARTS: "OrderedDict[str, type]" = OrderedDict(
    (c.name, c) for c in (BlackHole, Galaxy, Donut, Matrix, Plasma, Warp, Waves, Fire, Tunnel)
)
BUILTIN = frozenset(ARTS)
