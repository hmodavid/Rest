"""Motor: transforma (brilho, fase) em celulas coloridas (ANSI ou PNG)."""
from __future__ import annotations
import time
from .arts import ARTS
from .charsets import resolve
from .colors import bgc, fg, gradient, mix, parse_color

CLOCK_FONT = {
    "0": ("###", "# #", "# #", "# #", "###"), "1": (" # ", "## ", " # ", " # ", "###"),
    "2": ("###", "  #", "###", "#  ", "###"), "3": ("###", "  #", "###", "  #", "###"),
    "4": ("# #", "# #", "###", "  #", "  #"), "5": ("###", "#  ", "###", "  #", "###"),
    "6": ("###", "#  ", "###", "# #", "###"), "7": ("###", "  #", "  #", "  #", "  #"),
    "8": ("###", "# #", "###", "# #", "###"), "9": ("###", "# #", "###", "  #", "###"),
    ":": (" ", "#", " ", "#", " "), " ": (" ", " ", " ", " ", " "),
}


def stamp_clock(br, ph, ch, w, h, glyph):
    """Desenha HH:MM em letras grandes no canto inferior direito (os dois pontos piscam)."""
    if w < 40 or h < 12:
        return ch
    s = time.strftime("%H:%M")
    if int(time.time()) % 2:
        s = s.replace(":", " ")
    parts = [CLOCK_FONT[c] for c in s]
    total = sum(len(p[0]) for p in parts) + (len(parts) - 1)
    x0, y0 = w - total * 2 - 4, h - 7
    if ch is None:
        ch = [None] * (w * h)
    px = 0
    for part in parts:
        for r in range(5):
            for c, on in enumerate(part[r]):
                if on == "#":
                    for dx in (0, 1):
                        x = x0 + (px + c) * 2 + dx
                        k = (y0 + r) * w + x
                        br[k], ch[k], ph[k] = 1.0, glyph, 0.2 + x / w * 0.4
        px += len(part[0]) + 1
    return ch


P_STEPS = 64
B_STEPS = 20


class Engine:
    def __init__(self, cfg):
        self.inst = {}
        self.last_error = self.new_error = None
        self.apply(cfg)

    def apply(self, cfg):
        self.cfg = cfg
        d = cfg.data
        self.stops = [parse_color(c)[0] for c in d["colors"]]
        self.bg = parse_color(d["background"])[0]
        self.bg_esc = bgc(self.bg)
        self.ramp = resolve(d["charset"])
        self.cascade = float(d["cascade"])
        self.aspect = float(d["aspect"])
        self.rgb, self.esc = [], []
        for pi in range(P_STEPS):
            c = gradient(self.stops, pi / (P_STEPS - 1))
            for bi in range(B_STEPS):
                m = 0.10 + 0.90 * (bi / (B_STEPS - 1)) ** 0.85
                col = mix(self.bg, c, m)
                self.rgb.append(col)
                self.esc.append(fg(col))

    def art(self, name=None):
        name = name or self.cfg.data["art"]
        if name not in self.inst:
            self.inst[name] = ARTS[name]()
        return self.inst[name]

    def compute(self, w, h, t, name=None):
        try:
            a = self.art(name)
            a.pool = [c for c in self.ramp if c != " "] or ["#"]
            p = self.cfg.art_params(type(a))
            a.prepare(w, h, p, self.aspect)
            return a.compute(w, h, t, p)
        except Exception as ex:  # uma arte quebrada nunca derruba o app
            msg = f"{name or self.cfg.data['art']}: {type(ex).__name__}: {ex}"
            if msg != self.last_error:
                self.last_error = self.new_error = msg
            n = w * h
            return [0.0] * n, [0.0] * n, None

    def cells(self, w, h, t, name=None, clock=False):
        """-> (chars, ci): ci=-1 para celula vazia, senao indice na LUT de cor."""
        br, ph, ch = self.compute(w, h, t, name)
        if clock:
            glyph = self.ramp[-1] if self.ramp[-1] != " " else "#"
            ch = stamp_clock(br, ph, ch, w, h, glyph)
        ramp, top = self.ramp, len(self.ramp) - 1
        tc = t * self.cascade
        chars, cis = [" "] * (w * h), [-1] * (w * h)
        for k in range(w * h):
            b = br[k]
            if b < 0.035:
                continue
            if b > 1.0:
                b = 1.0
            c = ch[k] if ch is not None else None
            if c is None:
                c = ramp[int(b * top + 0.5)]
            if c == " ":
                continue
            p = (ph[k] - tc) % 1.0
            tri = 1.0 - abs(2.0 * p - 1.0)
            chars[k] = c
            cis[k] = int(tri * (P_STEPS - 1) + 0.5) * B_STEPS + int(b * (B_STEPS - 1) + 0.5)
        return chars, cis

    def ansi_rows(self, w, h, t, name=None, clock=False):
        chars, cis = self.cells(w, h, t, name, clock)
        esc = self.esc
        rows = []
        for j in range(h):
            out, last = [], -2
            for k in range(j * w, j * w + w):
                ci = cis[k]
                if ci < 0:
                    out.append(" ")
                    continue
                if ci != last:
                    out.append(esc[ci])
                    last = ci
                out.append(chars[k])
            rows.append("".join(out))
        return rows
