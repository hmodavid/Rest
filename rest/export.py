"""Exporta um quadro como PNG (wallpaper / lockscreen) usando so a stdlib."""
from __future__ import annotations
import struct
import zlib

GLYPHS = {
    ".": ["     ", "     ", "     ", "     ", "     ", "  #  ", "  #  "],
    ":": ["     ", "     ", "  #  ", "     ", "     ", "  #  ", "     "],
    "-": ["     ", "     ", "     ", " ### ", "     ", "     ", "     "],
    "=": ["     ", "     ", " ### ", "     ", " ### ", "     ", "     "],
    "+": ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    "*": ["     ", "# # #", " ### ", "#####", " ### ", "# # #", "     "],
    "#": [" # # ", " # # ", "#####", " # # ", "#####", " # # ", " # # "],
    "%": ["##  #", "## # ", "   # ", "  #  ", " #   ", " # ##", "#  ##"],
    "@": [" ### ", "#   #", "# ###", "# # #", "# ###", "#    ", " ### "],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "o": ["     ", "     ", " ### ", "#   #", "#   #", "#   #", " ### "],
    "(": ["  #  ", " #   ", "#    ", "#    ", "#    ", " #   ", "  #  "],
    ")": ["  #  ", "   # ", "    #", "    #", "    #", "   # ", "  #  "],
    "/": ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    "\\": ["#    ", "#    ", " #   ", "  #  ", "   # ", "    #", "    #"],
    "|": ["  #  "] * 7,
    "^": ["  #  ", " # # ", "#   #", "     ", "     ", "     ", "     "],
    "v": ["     ", "     ", "#   #", "#   #", " # # ", " # # ", "  #  "],
    "&": [" ##  ", "#  # ", "#  # ", " ##  ", "# # #", "#  # ", " ## #"],
    ",": ["     ", "     ", "     ", "     ", "  #  ", "  #  ", " #   "],
    "'": ["  #  ", "  #  ", " #   ", "     ", "     ", "     ", "     "],
    "`": [" #   ", "  #  ", "     ", "     ", "     ", "     ", "     "],
    '"': [" # # ", " # # ", "     ", "     ", "     ", "     ", "     "],
    "_": ["     "] * 6 + ["#####"],
    "~": ["     ", "     ", " ## #", "# ## ", "     ", "     ", "     "],
    "<": ["   # ", "  #  ", " #   ", "#    ", " #   ", "  #  ", "   # "],
    ">": [" #   ", "  #  ", "   # ", "    #", "   # ", "  #  ", " #   "],
    "!": ["  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  ", "  #  "],
    ";": ["     ", "  #  ", "     ", "     ", "  #  ", "  #  ", " #   "],
    "[": [" ### ", " #   ", " #   ", " #   ", " #   ", " #   ", " ### "],
    "]": [" ### ", "   # ", "   # ", "   # ", "   # ", "   # ", " ### "],
    "c": ["     ", "     ", " ### ", "#    ", "#    ", "#   #", " ### "],
    "x": ["     ", "     ", "#   #", " # # ", "  #  ", " # # ", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
}
_DENS = {"\u2591": 0.25, "\u2592": 0.5, "\u2593": 0.75, "\u2588": 1.0}
# ordem pseudo-aleatoria fixa das 35 celulas de um glifo (para tons de cinza por pontilhado)
_ORDER = sorted(range(35), key=lambda i: (i * 2654435761) % 4294967296)


def _bitmap(ch, ramp):
    if ch in GLYPHS:
        return [[c == "#" for c in row] for row in GLYPHS[ch]]
    if ch in _DENS:
        d = _DENS[ch]
    else:
        d = ramp.index(ch) / max(1, len(ramp) - 1) if ch in ramp else 0.5
    n = int(round(d * 35))
    on = set(_ORDER[:n])
    return [[(r * 5 + c) in on for c in range(5)] for r in range(7)]


def _png(path, w, h, rows):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw, 6)))
        f.write(chunk(b"IEND", b""))


def render_png(engine, path, width=1920, height=1080, scale=2, t=8.0, art=None):
    """Celula = (6*scale) x (12*scale) px, mesma proporcao 1:2 de um terminal."""
    cw, ch_ = 6 * scale, 12 * scale
    cols, rows = max(1, width // cw), max(1, height // ch_)
    ox, oy = (width - cols * cw) // 2, (height - rows * ch_) // 2
    chars, cis = engine.cells(cols, rows, t, art)
    bg = bytes(engine.bg)
    img = [bytearray(bg * width) for _ in range(height)]
    cache = {}
    s = scale
    for k in range(cols * rows):
        ci = cis[k]
        if ci < 0:
            continue
        c = chars[k]
        key = (c, ci)
        sprite = cache.get(key)
        if sprite is None:
            bm = _bitmap(c, engine.ramp)
            fgb, sprite = bytes(engine.rgb[ci]), []
            blank = bg * cw
            for _ in range(2 * s):
                sprite.append(blank)
            for r in range(7):
                line = b"".join((fgb if on else bg) * s for on in bm[r]) + bg * s
                sprite.extend([line] * s)
            for _ in range(3 * s):
                sprite.append(blank)
            cache[key] = sprite
        x0 = (ox + (k % cols) * cw) * 3
        y0 = oy + (k // cols) * ch_
        for r in range(ch_):
            img[y0 + r][x0:x0 + cw * 3] = sprite[r]
    _png(path, width, height, img)
    return path
