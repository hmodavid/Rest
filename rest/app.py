"""Interface TUI do Rest: paineis de bordas arredondadas em gradiente do tema, com layout responsivo."""
from __future__ import annotations
import os
import textwrap
import time

from . import __version__
from .arts import ARTS
from .colors import bgc, fg, gradient, mix, parse_color, ui_color_indices, ui_stops
from . import userarts
from .commands import Shell
from .term import Terminal, enter_fullscreen, leave_fullscreen, mouse_pos

RESET = "\x1b[0m"
BOLD, NOBOLD = "\x1b[1m", "\x1b[22m"
TEXT, MUTED_MIX = (222, 218, 208), 0.45


def fit(parts, width):
    out, used = [], 0
    for part in parts:
        text, col = part[0], part[1]
        bold = len(part) > 2 and part[2]
        if used >= width:
            break
        text = text[: width - used]
        out.append((BOLD if bold else "") + (fg(col) if col else "") + text + (NOBOLD if bold else ""))
        used += len(text)
    out.append(" " * (width - used))
    return "".join(out)


class App:
    def __init__(self, cfg, engine):
        self.cfg, self.engine = cfg, engine
        self.shell = Shell(cfg, engine)
        self.focus = "nav"
        self.buf, self.cur = "", 0
        self.hist, self.hpos = [], 0
        self.out = [("info", "Rest " + __version__ + " - digite 'help' ou pressione > para o terminal")]
        for w in cfg.warnings:
            self.out.append(("err", w))
        self.scroll = 0
        self.out_ver = 0
        self._wrap_key, self._wrap_lines = None, []
        self._term_avail = 4
        self.paused = False
        self.sim_t = 0.0
        self.frame_ms = 0.0
        self.W = self.H = 0
        self.prev = []
        self._theme_sig = None
        self._arts_sig = userarts.signature(cfg)
        self.refresh_theme()

    # ------------------------------------------------------------- tema
    def refresh_theme(self):
        d = self.cfg.data
        self.bg = parse_color(d["background"])[0]
        self.bg_esc = bgc(self.bg)
        self.stops = ui_stops(d["colors"])
        self.ui_idx = ui_color_indices(d["colors"])
        self.accent = self.stops[0]
        self.muted = mix(TEXT, self.bg, MUTED_MIX)
        self.ok = self.stops[-1]
        self.lut = {}
        for foc, f in ((True, 1.0), (False, 0.5)):
            self.lut[foc] = [fg(mix(self.bg, gradient(self.stops, i / 255), f)) for i in range(256)]

    def gcol(self, x, y, foc):
        t = 0.85 * x / max(1, self.W - 1) + 0.15 * y / max(1, self.H - 1)
        return self.lut[foc][int(min(1.0, max(0.0, t)) * 255)]

    # ------------------------------------------------------------- boxes
    def box(self, x0, y0, w, h, title, lines, foc, footer=""):
        inner = w - 2
        g = lambda x, y: self.gcol(x, y, foc)
        top = [g(x0, y0) + "\u256d"]
        label = " " + title + " "
        seg = "\u2500" + label
        for i in range(w - 2):
            c = seg[i] if i < len(seg) else "\u2500"
            top.append(g(x0 + 1 + i, y0) + (BOLD if i >= 1 and i < len(seg) else "") + c + NOBOLD)
        top.append(g(x0 + w - 1, y0) + "\u256e")
        rows = ["".join(top)]
        for j in range(h - 2):
            body = lines[j] if j < len(lines) else " " * inner
            rows.append(g(x0, y0 + 1 + j) + "\u2502" + body + g(x0 + w - 1, y0 + 1 + j) + "\u2502")
        bot = ["\u2570"]
        fs = ("\u2524 " + footer + " \u251c") if footer else ""
        fs = fs[: w - 4]
        for i in range(w - 2):
            k = i - (w - 3 - len(fs))
            c = fs[k] if 0 <= k < len(fs) else "\u2500"
            bot.append(g(x0 + 1 + i, y0 + h - 1) + c)
        bot.append(g(x0 + w - 1, y0 + h - 1) + "\u256f")
        rows.append("".join(bot))
        return rows

    # ----------------------------------------------------------- conteudos
    def pane_arts(self, w, h):
        names = list(ARTS)
        cur = self.cfg.data["art"]
        i = names.index(cur) if cur in names else 0
        vis = max(3, h - 4) if h > 9 else h
        start = min(max(0, i - vis // 2), max(0, len(names) - vis))
        lines = []
        for n in names[start:start + vis]:
            sel = n == cur
            tag = " *" if ARTS[n].user else ""
            lines.append(fit([("\u25b8 " if sel else "  ", self.accent, True), (n + tag, TEXT if sel else self.muted, sel)], w))
        if h > 9:
            lines.append(" " * w)
            for l in textwrap.wrap(ARTS[cur].desc, w - 1):
                lines.append(fit([(l, self.muted)], w))
        return lines, f"{i + 1}/{len(names)}"

    def pane_theme(self, w, h):
        specs = self.cfg.data["colors"]
        stops = [parse_color(c)[0] for c in specs]
        lines = ["".join(fg(gradient(stops, i / max(1, w - 1))) + "\u2588" for i in range(w))]
        for i, c in enumerate(specs):
            rgb, wt = parse_color(c)
            mark = ("\u25c6 ", self.accent) if i in self.ui_idx else ("  ", self.muted)
            lines.append(fit([mark, ("\u2588\u2588 ", rgb), (c.split(":")[0], TEXT), (f"  x{wt:g}", self.muted)], w))
        lines.append(fit([(f"UI usa {len(self.ui_idx)} de {len(specs)} cores", self.muted)], w))
        return lines, "theme"

    def pane_params(self, w, h):
        d = self.cfg.data
        rows = [("speed", f"{d['speed']:g}"), ("fps", str(d["fps"])), ("cascade", f"{d['cascade']:g}"),
                ("aspect", f"{d['aspect']:g}"), ("chars", d["charset"][:14].replace(" ", "\u00b7")), ("bg", d["background"]),
                ("clock", "on" if d["saver"]["clock"] else "off"),
                ("playlist", str(len(d["saver"]["playlist"])) if d["saver"]["playlist"] else "-")]
        cls = ARTS[d["art"]]
        rows.append(("", ""))
        rows += [(k, f"{v:g}" if isinstance(v, float) else str(v)) for k, v in self.cfg.art_params(cls).items()]
        lines = []
        for k, v in rows:
            lines.append(fit([(k.ljust(9), self.muted), (v, TEXT)], w) if k else fit([("\u2500 " + cls.name, self.accent, True)], w))
        return lines, "set"

    def pane_meta(self, w, h):
        d = self.cfg.data
        lines = [
            fit([("estado   ", self.muted), ("pausado" if self.paused else "rodando", TEXT)], w),
            fit([("quadro   ", self.muted), (f"{self.frame_ms:.1f} ms", TEXT)], w),
            fit([("versao   ", self.muted), (__version__, TEXT)], w),
            fit([("config   ", self.muted), (os.path.basename(os.path.dirname(self.cfg.path)) + "/" + os.path.basename(self.cfg.path), TEXT)], w),
        ]
        return lines, ""

    def term_lines(self, w):
        """Saida do terminal quebrada na largura do painel (cache por versao/largura)."""
        key = (self.out_ver, w)
        if self._wrap_key != key:
            lines = []
            for k, t in self.out:
                for part in textwrap.wrap(t, max(4, w), subsequent_indent="  ", replace_whitespace=False) or [""]:
                    lines.append((k, part))
            self._wrap_key, self._wrap_lines = key, lines
        return self._wrap_lines

    def prompt_line(self, w):
        pre = ">_ "
        if self.focus == "term":
            b, cur = self.buf, self.cur
            room = max(1, w - len(pre) - 1)
            off = max(0, cur - room + 1)
            vis, c = b[off:off + room], cur - off
            return fit([(pre, self.accent, True), (vis[:c], TEXT), ("\u2588", self.accent), (vis[c + 1:], TEXT)], w)
        return fit([(pre, self.muted, True), ("pressione > para digitar comandos", self.muted)], w)

    def _kcol(self):
        return {"ok": self.ok, "err": (255, 110, 110), "info": self.accent, "out": TEXT}

    def pane_term(self, w, h):
        avail = max(1, h - 1)
        self._term_avail = avail
        lines = self.term_lines(w)
        maxs = max(0, len(lines) - avail)
        self.scroll = max(0, min(self.scroll, maxs))
        end = len(lines) - self.scroll
        shown = lines[max(0, end - avail):end]
        cm = self._kcol()
        rows = [fit([(t, cm.get(k, TEXT))], w) for k, t in shown]
        rows = [" " * w] * (avail - len(rows)) + rows
        rows.append(self.prompt_line(w))
        if self.scroll:
            foot = f"\u2191 {self.scroll}/{maxs} \u00b7 PgDn"
        else:
            foot = "Enter executa \u00b7 Esc sai \u00b7 PgUp rola" if self.focus == "term" else ""
        return rows, foot

    def footer_bar(self, w):
        items = {">": ("> ", "terminal"), "j/k": ("j/k ", "arte"), "c": ("c ", "tema"), "s": ("s ", "saver"),
                 "sp": ("espaco ", "pausa"), "+/-": ("+/- ", "velocidade"), "q": ("q ", "sair")}
        order = [">", "j/k", "c", "s", "sp", "+/-", "q"]
        prio = [">", "q", "s", "j/k", "c", "sp", "+/-"]

        def width(sel):
            return sum(len(items[k][0]) + len(items[k][1]) for k in sel) + 3 * (len(sel) - 1)

        chosen = []
        for k in prio:
            if width([x for x in order if x in chosen + [k]]) <= w:
                chosen.append(k)
        parts = []
        for i, k in enumerate(x for x in order if x in chosen):
            if i:
                parts.append((" | ", self.muted))
            parts += [(items[k][0], self.accent, True), (items[k][1], self.muted)]
        return fit(parts or [("> ", self.accent, True), ("terminal", self.muted)], w)

    def header_bar(self, w):
        title = "\u25c6 REST"
        art, folder = self.cfg.data["art"], os.path.dirname(self.cfg.path)
        tail = ""
        for cand in ("  ascii screensaver \u00b7 " + art + " \u00b7 " + folder, "  " + art + " \u00b7 " + os.path.basename(folder), "  " + art):
            if len(title) + len(cand) <= w:
                tail = cand
                break
        parts = [(ch, gradient(self.stops, i / max(1, len(title) - 1)), True) for i, ch in enumerate(title)]
        parts.append((tail, self.muted))
        return fit(parts, w)

    # ------------------------------------------------------------ desenho
    MIN_W, MIN_H = 44, 12

    def layout(self):
        """Faixas de largura/altura. Devolve (L, R, hb): colunas laterais e altura da linha de baixo."""
        W, H = self.W, self.H
        if W >= 112:
            L, R = max(22, min(30, W // 5)), max(28, min(38, W // 4))   # completo: 3 colunas
        elif W >= 84:
            L, R = max(20, min(26, W // 4)), 0                          # medio: artes + preview
        else:
            L = R = 0                                                   # estreito: so preview + terminal
        hb = 10 if H >= 32 else 9 if H >= 28 else 7 if H >= 22 else 6 if H >= 16 else 5
        return L, R, hb

    def compose_compact(self):
        """Janela muito pequena: a arte ocupa tudo; uma ou duas linhas embaixo para comandos."""
        W, H = self.W, self.H
        if W < 1 or H < 1:
            return [""] * max(H, 0)
        foot = 2 if (self.focus == "term" and H >= 5) else 1
        rows = [self.bg_esc + r + RESET for r in self.engine.ansi_rows(W, H - foot, self.sim_t)] if H - foot > 0 else []
        if foot == 2:
            lines = self.term_lines(W)
            k, t = lines[-1] if lines else ("out", "")
            rows.append(self.bg_esc + fit([(t, self._kcol().get(k, TEXT))], W) + RESET)
        if self.focus == "term":
            rows.append(self.bg_esc + self.prompt_line(W) + RESET)
        else:
            hint = "s saver | > comandos | q sair" if W >= 28 else "s > q"
            rows.append(self.bg_esc + fit([(hint, self.muted)], W) + RESET)
        return rows[-H:] if len(rows) > H else rows

    def compose(self):
        W, H = self.W, self.H
        if W < self.MIN_W or H < self.MIN_H:
            return self.compose_compact()
        L, R, hb = self.layout()
        ht = H - 2 - hb
        C = W - L - R
        rows = [self.header_bar(W)]
        t = self.sim_t
        foc_nav = self.focus == "nav"
        cols_top, cols_bot = [], []
        if L:
            ln, ft = self.pane_arts(L - 2, ht - 2)
            cols_top.append(self.box(0, 1, L, ht, "\u25c6 Artes", ln, foc_nav, ft))
            ln, ft = self.pane_theme(L - 2, hb - 2)
            cols_bot.append(self.box(0, 1 + ht, L, hb, "\u25c8 Tema", ln, False, ft))
        pr = self.engine.ansi_rows(C - 2, ht - 2, t)
        info = f"{C - 2}x{ht - 2}" + (f" \u00b7 {self.cfg.data['fps']}fps" if C >= 36 else "")
        cols_top.append(self.box(L, 1, C, ht, "\u2261 Preview \u00b7 " + self.cfg.data["art"], pr, True, info))
        ln, ft = self.pane_term(C - 2, hb - 2)
        cols_bot.append(self.box(L, 1 + ht, C, hb, ">_ Terminal", ln, not foc_nav, ft))
        if R:
            ln, ft = self.pane_params(R - 2, ht - 2)
            cols_top.append(self.box(L + C, 1, R, ht, "\u25c7 Parametros", ln, False, ft))
            ln, ft = self.pane_meta(R - 2, hb - 2)
            cols_bot.append(self.box(L + C, 1 + ht, R, hb, "\u25a4 Metadata", ln, False, ft))
        for j in range(ht):
            rows.append("".join(c[j] for c in cols_top))
        for j in range(hb):
            rows.append("".join(c[j] for c in cols_bot))
        rows.append(self.footer_bar(W))
        return [self.bg_esc + r + RESET for r in rows]

    def draw(self, term):
        rows = self.compose()
        buf = []
        for i, r in enumerate(rows):
            if i >= len(self.prev) or self.prev[i] != r:
                buf.append(f"\x1b[{i + 1};1H{self.bg_esc}\x1b[K{r}")
        self.prev = rows
        if buf:
            term.write("".join(buf))

    # ------------------------------------------------------------- entrada
    def say(self, kind, text):
        self.out.append((kind, text))
        self.out = self.out[-300:]
        self.out_ver += 1
        self.scroll = 0

    def run_line(self, line):
        self.say("out", ">_ " + line)
        res = self.shell.run(line)
        for k, t in res.lines:
            self.say(k, t)
        self.refresh_theme()
        return res.action

    def handle_term_key(self, k):
        b, c = self.buf, self.cur
        if k == "enter":
            line = b.strip()
            self.buf, self.cur, self.hpos = "", 0, 0
            if line:
                self.hist.append(line)
                self.hpos = len(self.hist)
                return self.run_line(line)
        elif k == "esc":
            self.focus = "nav"
        elif k == "backspace":
            if c:
                self.buf, self.cur = b[:c - 1] + b[c:], c - 1
        elif k == "delete":
            self.buf = b[:c] + b[c + 1:]
        elif k == "left":
            self.cur = max(0, c - 1)
        elif k == "right":
            self.cur = min(len(b), c + 1)
        elif k == "home":
            self.cur = 0
        elif k == "end":
            self.cur = len(b)
        elif k in ("up", "down"):
            if self.hist:
                self.hpos = max(0, min(len(self.hist), self.hpos + (-1 if k == "up" else 1)))
                self.buf = self.hist[self.hpos] if self.hpos < len(self.hist) else ""
                self.cur = len(self.buf)
        elif k == "pgup":
            self.scroll += max(2, self._term_avail - 1)     # limitado ao renderizar
        elif k == "pgdn":
            self.scroll = max(0, self.scroll - max(2, self._term_avail - 1))
        elif k == "ctrl-c":
            self.buf, self.cur = "", 0
        elif len(k) == 1:
            self.buf, self.cur = b[:c] + k + b[c:], c + 1
        return None

    def handle_nav_key(self, k):
        d = self.cfg.data
        names = list(ARTS)
        i = names.index(d["art"])
        if k in ("q", "ctrl-c"):
            return "quit"
        if k in ("j", "down", "tab"):
            d["art"] = names[(i + 1) % len(names)]
        elif k in ("k", "up"):
            d["art"] = names[(i - 1) % len(names)]
        elif k in (">", ":", "/", "enter"):
            self.focus = "term"
        elif k == "?":
            self.focus = "term"
            return self.run_line("help")
        elif k == "s":
            return "saver"
        elif k == " ":
            self.paused = not self.paused
        elif k in ("+", "="):
            d["speed"] = min(5.0, round(d["speed"] + 0.25, 2))
        elif k in ("-", "_"):
            d["speed"] = max(0.1, round(d["speed"] - 0.25, 2))
        elif k == "c":
            ths = list(self.cfg.themes())
            cur = next((n for n, t in self.cfg.themes().items() if t["colors"] == d["colors"]), None)
            self.cfg.apply_theme(ths[(ths.index(cur) + 1) % len(ths)] if cur in ths else ths[0])
        elif k == "r":
            self.cfg.load()
        else:
            return None
        self.cfg.save()
        self.engine.apply(self.cfg)
        self.refresh_theme()
        return None

    # --------------------------------------------------------------- loop
    def dispatch(self, term, k):
        act = self.handle_term_key(k) if self.focus == "term" else self.handle_nav_key(k)
        if act == "quit":
            return True
        if act == "pause":
            self.paused = not self.paused
        elif act == "clear":
            self.out, self.scroll = [], 0
            self.out_ver += 1
        elif act == "saver":
            run_saver(term, self.cfg, self.engine, self.sim_t)
            self.prev = []
            term.write(self.bg_esc + "\x1b[2J")
        return False

    def run(self):
        with Terminal() as term:
            last = time.perf_counter()
            last_chk = 0.0
            pending = []
            cur_bg = None
            while True:
                t0 = time.perf_counter()
                if cur_bg != self.bg:
                    cur_bg = self.bg
                    term.set_bg(cur_bg)
                size = term.size()
                if size != (self.W, self.H):
                    self.W, self.H = size
                    self.prev = []
                    term.write(self.bg_esc + "\x1b[2J")
                for k in pending:
                    if self.dispatch(term, k):
                        return
                pending = []
                if t0 - last_chk > 0.5:
                    last_chk = t0
                    sig = userarts.signature(self.cfg)
                    if sig != self._arts_sig:
                        self._arts_sig = sig
                        for wmsg in userarts.load_user_arts(self.cfg):
                            self.say("err", wmsg)
                        self.engine.inst.clear()
                        if self.cfg.data["art"] not in ARTS:
                            self.cfg.data["art"] = "blackhole"
                        self.prev = []
                        self.say("info", "artes recarregadas")
                    if self.cfg.changed_on_disk():
                        self.cfg.load()
                        self.engine.apply(self.cfg)
                        self.refresh_theme()
                        self.prev = []
                        self.say("info", "config recarregada do arquivo")
                now = time.perf_counter()
                if not self.paused:
                    self.sim_t += (now - last) * self.cfg.data["speed"]
                last = now
                if self.engine.new_error:
                    self.say("err", self.engine.new_error)
                    self.engine.new_error = None
                self.draw(term)
                self.frame_ms = (time.perf_counter() - t0) * 1000
                rest = 1.0 / self.cfg.data["fps"] - (time.perf_counter() - t0)
                pending = term.read_keys(max(0.0, rest))


def run_saver(term, cfg, engine, t=0.0, grace=0.6, fullscreen=True):
    """Tela cheia de verdade. Sai com Esc, ou com qualquer outra tecla apertada 2 vezes."""
    bg = bgc(engine.bg)
    sv = cfg.data["saver"]
    pl = [n for n in sv.get("playlist", []) if n in ARTS]
    cycle = float(sv.get("cycle_seconds", 60))
    pi, art_t0, current = 0, time.perf_counter(), (pl[0] if pl else None)
    clock = bool(sv.get("clock"))
    token = enter_fullscreen() if fullscreen else None
    term.set_bg(engine.bg)
    term.write(bg + "\x1b[2J")
    term.read_keys(0)  # descarta teclas que sobraram (inclui o proprio 's' e o Alt+Enter)
    start = time.perf_counter()
    last = start
    m0 = mouse_pos()
    wiggle = cfg.data["saver"].get("exit_on_mouse", False)
    size = term.size()
    presses = 0

    def wants_exit(keys):
        """Esc sai na hora; qualquer outra tecla precisa ser apertada 2 vezes."""
        nonlocal presses
        for k in keys:
            if k == "esc":
                return True
            presses += 1
            if presses >= 2:
                return True
        return False

    try:
        while True:
            t0 = time.perf_counter()
            if term.size() != size:
                size = term.size()
                term.write(bg + "\x1b[2J")
            w, h = size
            if t0 - start > 0.3 and wants_exit(term.read_keys(0)):
                return
            if wiggle and m0 and t0 - start > grace:
                m = mouse_pos()
                if m and (abs(m[0] - m0[0]) + abs(m[1] - m0[1]) > 8):
                    return
            t += (t0 - last) * cfg.data["speed"]
            last = t0
            if pl and t0 - art_t0 > cycle:
                pi, art_t0 = pi + 1, t0
                current = pl[pi % len(pl)]
                term.write(bg + "\x1b[2J")
            rows = engine.ansi_rows(w, h, t, current, clock)
            term.write("".join(f"\x1b[{i + 1};1H{bg}\x1b[K{r}\x1b[0m" for i, r in enumerate(rows)))
            rest = 1.0 / cfg.data["fps"] - (time.perf_counter() - t0)
            if rest > 0 and time.perf_counter() - start > 0.3 and wants_exit(term.read_keys(rest)):
                return
            elif rest > 0 and time.perf_counter() - start <= 0.3:
                time.sleep(rest)
    finally:
        leave_fullscreen(token)
        term.read_keys(0)
