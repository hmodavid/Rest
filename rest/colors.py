"""Utilitarios de cor: parse, mistura, gradiente e regra de cores da UI."""
from __future__ import annotations
import re

NAMED = {
    "orange": "#ff8c1a", "laranja": "#ff8c1a",
    "yellow": "#ffd54a", "amarelo": "#ffd54a",
    "gold": "#ffc233", "dourado": "#ffc233",
    "pink": "#ff4d6d", "rosa": "#ff4d6d", "rose": "#ff4d6d",
    "red": "#e63946", "vermelho": "#e63946",
    "white": "#f2efe9", "branco": "#f2efe9",
    "gray": "#9aa0a6", "cinza": "#9aa0a6",
    "cyan": "#4dd0e1", "ciano": "#4dd0e1",
    "blue": "#4d8bff", "azul": "#4d8bff",
    "green": "#5bd67a", "verde": "#5bd67a",
    "purple": "#a06bff", "roxo": "#a06bff",
    "magenta": "#ff4de1",
}
_HEX = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
RGB = tuple


def parse_color(spec) -> tuple[RGB, float]:
    """'#ff8c1a', 'laranja' ou '#ff8c1a:5' -> ((r,g,b), peso)."""
    s = str(spec).strip().lower()
    weight = 1.0
    if ":" in s:
        s, w = s.rsplit(":", 1)
        weight = float(w)
    s = NAMED.get(s, s)
    m = _HEX.match(s)
    if not m:
        raise ValueError(f"cor invalida: {spec!r}")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)), max(0.0, weight)


def to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def mix(a, b, t: float):
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def gradient(stops, t: float):
    n = len(stops)
    if n == 1:
        return stops[0]
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    pos = t * (n - 1)
    i = int(pos)
    if i >= n - 1:
        return stops[-1]
    return mix(stops[i], stops[i + 1], pos - i)


def fg(rgb) -> str:
    return "\x1b[38;2;%d;%d;%dm" % (rgb[0], rgb[1], rgb[2])


def bgc(rgb) -> str:
    return "\x1b[48;2;%d;%d;%dm" % (rgb[0], rgb[1], rgb[2])


def ui_color_indices(specs) -> list[int]:
    """Regra da UI: 1->1, 2->2, 3->2, 4+->3 (maximo 3).
    Escolhe as mais predominantes (maior peso; empate = ordem da lista)."""
    items = [parse_color(s) for s in specs]
    n = len(items)
    if n == 0:
        return []
    k = n if n <= 2 else (2 if n == 3 else 3)
    idx = sorted(range(n), key=lambda i: (-items[i][1], i))[:k]
    return sorted(idx)


def ui_stops(specs) -> list[RGB]:
    items = [parse_color(s)[0] for s in specs]
    idx = ui_color_indices(specs)
    return [items[i] for i in idx] or [(255, 140, 26)]
