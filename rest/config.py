"""Preferencias persistentes (JSON editavel a mao, recarregado ao vivo)."""
from __future__ import annotations
import copy
import json
import os
import sys

from .colors import parse_color

DEFAULTS = {
    "art": "blackhole",
    "colors": ["#ff8c1a:5", "#ffd54a:3", "#ff4d6d:1"],
    "background": "#1f2124",
    "charset": "classic",
    "speed": 1.0,
    "fps": 24,
    "cascade": 0.35,
    "aspect": 0.5,
    "params": {},
    "themes": {},
    "saver": {"exit_on_mouse": False, "timeout_minutes": 5, "clock": False, "playlist": [], "cycle_seconds": 60},
    "wallpaper": {"width": 1920, "height": 1080, "scale": 2, "time": 8.0},
}

PRESET_THEMES = {
    "gargantua": {"colors": ["#ff8c1a:5", "#ffd54a:3", "#ff4d6d:1"], "background": "#1f2124"},
    "sunset": {"colors": ["#ff5e62:4", "#ff9966:3", "#ffd194:1"], "background": "#1d1b22"},
    "ice": {"colors": ["#4dd0e1:4", "#4d8bff:3", "#e8f7ff:1"], "background": "#14181f"},
    "matrix": {"colors": ["#00ff5f:4", "#00b341:3", "#c8ffd9:1"], "background": "#0b0f0c"},
    "vapor": {"colors": ["#ff4de1:4", "#a06bff:3", "#4dd0e1:3", "#ffd54a:1"], "background": "#17141f"},
    "mono": {"colors": ["#e8e6e1"], "background": "#1a1a1a"},
    "ember": {"colors": ["#ff4500:5", "#ff8c00:3", "#ffd700:2", "#ffe9a8:1"], "background": "#1b1512"},
    "aurora": {"colors": ["#39ffb0:4", "#4d8bff:3", "#a06bff:2"], "background": "#10151c"},
    "synthwave": {"colors": ["#ff2e97:4", "#7b2ff7:3", "#00e5ff:2"], "background": "#160f26"},
    "sakura": {"colors": ["#ff9ebb:4", "#ffd1dc:3", "#c779d0:1"], "background": "#1d1820"},
    # vermelho / rosa com branco sobre grafite escuro
    "crimson": {"colors": ["#e10a2d:5", "#ffffff:3"], "background": "#1c1c1f"},
    "blush": {"colors": ["#ff5c9a:5", "#ffffff:3"], "background": "#1e1d20"},
    "rosewhip": {"colors": ["#c8102e:5", "#ff4d8d:3", "#ffffff:2"], "background": "#1b1a1d"},
    "ruby": {"colors": ["#9b111e:5", "#e0115f:3", "#ffb3c6:2", "#ffffff:1"], "background": "#1a181b"},
    # outros pares com branco / paletas extras
    "midnight": {"colors": ["#4d8bff:5", "#ffffff:3"], "background": "#14171c"},
    "gold": {"colors": ["#ffc233:5", "#ffffff:2"], "background": "#1a1a1a"},
    "lavender": {"colors": ["#a06bff:5", "#ffffff:3"], "background": "#1a1822"},
    "tangerine": {"colors": ["#ff7a00:5", "#ffffff:3"], "background": "#1d1a18"},
    "forest": {"colors": ["#5bd67a:5", "#e8ffe8:2", "#2e8b57:1"], "background": "#121714"},
    "ocean": {"colors": ["#00b4d8:4", "#90e0ef:3", "#ffffff:2"], "background": "#10161b"},
    "cyberpunk": {"colors": ["#00e5ff:4", "#ff2e97:4", "#ffe600:2"], "background": "#14111d"},
}

NUM_RANGES = {"speed": (0.1, 5.0), "fps": (5, 60), "cascade": (0.0, 2.0), "aspect": (0.3, 1.0)}


def default_path() -> str:
    env = os.environ.get("REST_CONFIG")
    if env:
        return env
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Rest", "config.json")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "rest", "config.json")


def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict) and k not in ("params", "themes"):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Config:
    def __init__(self, path: str | None = None):
        self.path = path or default_path()
        self.data = copy.deepcopy(DEFAULTS)
        self.warnings: list[str] = []
        self._mtime = 0.0
        self.load()

    # ---- disco -------------------------------------------------------
    def load(self) -> None:
        self.data = copy.deepcopy(DEFAULTS)
        self.warnings = []
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    _merge(self.data, json.load(f))
            except Exception as e:  # arquivo quebrado nao derruba o app
                self.warnings.append(f"config invalida ({e}); usando padrao")
                self.data = copy.deepcopy(DEFAULTS)
            self._mtime = self._stat()
        from .userarts import load_user_arts
        self.warnings += load_user_arts(self)
        self.validate()

    @property
    def arts_dir(self) -> str:
        return os.path.join(os.path.dirname(self.path) or ".", "arts")

    def save(self) -> None:
        self.validate()
        self.fill_art_defaults()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
        self._mtime = self._stat()

    def _stat(self) -> float:
        try:
            return os.stat(self.path).st_mtime
        except OSError:
            return 0.0

    def changed_on_disk(self) -> bool:
        m = self._stat()
        return m != 0.0 and m != self._mtime

    # ---- validacao -----------------------------------------------------
    def validate(self) -> None:
        d = self.data
        good = []
        for c in d.get("colors", []):
            try:
                parse_color(c)
                good.append(str(c))
            except Exception:
                self.warnings.append(f"cor ignorada: {c!r}")
        d["colors"] = good or list(DEFAULTS["colors"])
        try:
            parse_color(d["background"])
        except Exception:
            self.warnings.append("background invalido; usando padrao")
            d["background"] = DEFAULTS["background"]
        for k, (lo, hi) in NUM_RANGES.items():
            try:
                v = float(d[k])
            except Exception:
                v = DEFAULTS[k]
            v = clamp(v, lo, hi)
            d[k] = int(v) if k == "fps" else v
        from .arts import ARTS
        if d.get("art") not in ARTS:
            self.warnings.append(f"arte desconhecida {d.get('art')!r}")
            d["art"] = "blackhole"
        sv = d["saver"]
        sv["clock"] = bool(sv.get("clock", False))
        pl = sv.get("playlist", [])
        sv["playlist"] = [str(x) for x in pl] if isinstance(pl, list) else []
        try:
            sv["cycle_seconds"] = clamp(float(sv.get("cycle_seconds", 60)), 5.0, 3600.0)
        except Exception:
            sv["cycle_seconds"] = 60.0
        if not isinstance(d.get("params"), dict):
            d["params"] = {}
        if not isinstance(d.get("themes"), dict):
            d["themes"] = {}

    def fill_art_defaults(self) -> None:
        from .arts import ARTS
        for name, cls in ARTS.items():
            cur = self.data["params"].setdefault(name, {})
            for k, v in cls.defaults.items():
                cur.setdefault(k, v)

    # ---- helpers -------------------------------------------------------
    def art_params(self, cls) -> dict:
        """Parametros da arte: defaults + usuario, convertidos e limitados."""
        user = self.data["params"].get(cls.name, {})
        out = {}
        for k, dv in cls.defaults.items():
            v = user.get(k, dv)
            try:
                if isinstance(dv, str):
                    v = str(v)
                    if k in cls.choices and v not in cls.choices[k]:
                        v = dv
                elif isinstance(dv, bool):
                    v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "on", "sim", "yes")
                elif isinstance(dv, int):
                    v = int(round(float(v)))
                else:
                    v = float(v)
                if not isinstance(dv, (bool, str)) and k in cls.ranges:
                    lo, hi = cls.ranges[k]
                    v = clamp(v, lo, hi)
            except Exception:
                v = dv
            out[k] = v
        return out

    def themes(self) -> dict:
        t = dict(PRESET_THEMES)
        t.update({k: v for k, v in self.data.get("themes", {}).items() if isinstance(v, dict)})
        return t

    def apply_theme(self, name: str) -> bool:
        th = self.themes().get(name)
        if not th:
            return False
        self.data["colors"] = list(th.get("colors", self.data["colors"]))
        self.data["background"] = th.get("background", self.data["background"])
        self.validate()
        return True

    def reset(self) -> None:
        self.data = copy.deepcopy(DEFAULTS)
        self.validate()
