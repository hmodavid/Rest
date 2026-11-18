"""Artes do usuario: arquivos .txt (ASCII estatico/animado) e .py (plugins) na pasta 'arts'."""
from __future__ import annotations
import importlib.util
import os
import re
import shutil

from .arts import ARTS, BUILTIN, Art, make_text_art, parse_text_art

USER: dict[str, str] = {}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,23}$")

TEMPLATE_TXT = "\n".join([
    "      .-\"\"\"\"-.",
    "    .'  .--.  '.",
    "   /   (    )   \\",
    "  |  .-'----'-.  |",
    "   \\  '-....-'  /",
    "    '.        .'",
    "      '-....-'",
    "",
])

TEMPLATE_PY = '''"""Descanso de tela personalizado: {name}

Salve o arquivo e ele aparece ao vivo no Rest (recarrega sozinho).
compute() devolve, para cada celula (w*h, linha por linha):
  brilho  0..1  -> escolhe o caractere da rampa de texto
  fase    0..1  -> escolhe a cor no gradiente do tema (a cascata anda sozinha)
  glifos  lista de caracteres, ou None para usar a rampa
"""
from math import atan2, hypot, sin

from rest.arts import Art


class {cls}(Art):
    name = "{name}"
    desc = "Meu descanso de tela"
    defaults = dict(speed=1.0, arms=4)            # aparecem em 'params' e podem ser mudados com 'set'
    ranges = dict(speed=(0.1, 5.0), arms=(1, 12))

    def compute(self, w, h, t, p):
        br = [0.0] * (w * h)
        ph = [0.0] * (w * h)
        for j in range(h):
            y = (j + 0.5 - h / 2) / (h / 2)
            for i in range(w):
                x = (i + 0.5 - w / 2) * 0.5 / (h / 2)      # 0.5 = proporcao da celula do terminal
                r = hypot(x, y)
                v = 0.5 + 0.5 * sin(p["arms"] * atan2(y, x) + 6 * r - t * p["speed"] * 2)
                k = j * w + i
                br[k] = v * max(0.0, 1.0 - r * 0.6)
                ph[k] = r * 0.5 + v * 0.2
        return br, ph, None
'''


def clean_name(s: str) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "-", os.path.splitext(os.path.basename(s))[0].lower()).strip("-_")
    return s[:24]


def signature(cfg):
    d = cfg.arts_dir
    if not os.path.isdir(d):
        return ()
    out = []
    for f in sorted(os.listdir(d)):
        if f.lower().endswith((".txt", ".py")):
            try:
                out.append((f, os.stat(os.path.join(d, f)).st_mtime))
            except OSError:
                pass
    return tuple(out)


def load_user_arts(cfg) -> list[str]:
    """(Re)carrega a pasta de artes. Devolve avisos (erros por arquivo)."""
    for n in list(USER):
        ARTS.pop(n, None)
    USER.clear()
    warns = []
    d = cfg.arts_dir
    if not os.path.isdir(d):
        return warns
    for f in sorted(os.listdir(d)):
        path = os.path.join(d, f)
        low = f.lower()
        try:
            if low.endswith(".txt"):
                name = clean_name(f)
                if not NAME_RE.match(name) or name in BUILTIN:
                    warns.append(f"{f}: nome invalido/reservado")
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    ARTS[name] = make_text_art(name, parse_text_art(fh.read()))
                USER[name] = path
            elif low.endswith(".py"):
                spec = importlib.util.spec_from_file_location("rest_user_" + clean_name(f).replace("-", "_"), path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                found = [c for c in vars(mod).values()
                         if isinstance(c, type) and issubclass(c, Art) and c is not Art and c.__module__ == mod.__name__]
                if not found:
                    warns.append(f"{f}: nenhuma classe que herde de Art")
                for c in found:
                    if not NAME_RE.match(str(c.name)) or c.name in BUILTIN:
                        warns.append(f"{f}: nome '{c.name}' invalido/reservado")
                        continue
                    c.user = True
                    ARTS[c.name] = c
                    USER[c.name] = path
        except Exception as ex:
            warns.append(f"{f}: {type(ex).__name__}: {ex}")
    return warns


def create_template(cfg, name: str, kind: str = "txt") -> str:
    name = clean_name(name)
    if not NAME_RE.match(name) or name in BUILTIN:
        raise ValueError("nome invalido/reservado (use letras minusculas, numeros, - e _)")
    os.makedirs(cfg.arts_dir, exist_ok=True)
    path = os.path.join(cfg.arts_dir, name + (".py" if kind == "py" else ".txt"))
    if os.path.exists(path):
        raise ValueError(f"'{name}' ja existe: {path}")
    cls = "".join(p.capitalize() for p in re.split(r"[-_]", name)) or "Minha"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE_PY.format(name=name, cls=cls) if kind == "py" else TEMPLATE_TXT)
    return path


def import_file(cfg, src: str, name: str | None = None) -> tuple[str, str]:
    src = os.path.expanduser(src.strip().strip('"'))
    if not os.path.isfile(src):
        raise ValueError(f"arquivo nao encontrado: {src}")
    name = clean_name(name or src)
    if not NAME_RE.match(name) or name in BUILTIN:
        raise ValueError("nome invalido/reservado; informe outro: import <arquivo> <nome>")
    ext = ".py" if src.lower().endswith(".py") else ".txt"
    os.makedirs(cfg.arts_dir, exist_ok=True)
    dest = os.path.join(cfg.arts_dir, name + ext)
    shutil.copyfile(src, dest)
    return name, dest


def remove_art(cfg, name: str) -> str:
    path = USER.get(name)
    if not path:
        raise ValueError(f"'{name}' nao e uma arte sua (as nativas nao podem ser removidas)")
    os.remove(path)
    return path
