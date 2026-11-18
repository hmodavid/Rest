"""Linha de comando: rest | rest saver | rest wallpaper ... | rest scr ..."""
from __future__ import annotations
import argparse
import os
import sys

from . import __version__, system
from .app import App, run_saver
from .arts import ARTS
from .config import Config
from .engine import Engine
from .export import render_png
from .term import Terminal


def _is_scr() -> bool:
    return os.path.basename(sys.argv[0]).lower().endswith(".scr")


def _maximize_console():
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
    except Exception:
        pass


def saver(cfg, art=None):
    if art:
        cfg.data["art"] = art
        cfg.data["saver"]["playlist"] = []   # --art manda; nao grava
    eng = Engine(cfg)
    with Terminal() as term:
        run_saver(term, cfg, eng)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cfg = Config()
    # convencao de protetores de tela do Windows: /s /c /p
    if argv and argv[0].lower().lstrip("/-")[:1] in ("s", "c", "p") and argv[0].startswith("/"):
        flag = argv[0].lower()[1:2]
        if flag == "p":
            return 0
        if flag == "s":
            _maximize_console()
            return saver(cfg)
        argv = []
    elif _is_scr() and not argv:
        _maximize_console()
        return saver(cfg)

    ap = argparse.ArgumentParser(prog="rest", description="Rest - descanso de tela ASCII (buraco negro e mais)")
    ap.add_argument("--version", action="version", version="Rest " + __version__)
    ap.add_argument("--config", help="caminho de outro config.json")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("saver", help="tela cheia")
    s.add_argument("--art", choices=list(ARTS))
    w = sub.add_parser("wallpaper", help="gera/aplica PNG do quadro atual")
    w.add_argument("action", choices=["export", "set", "lock"], nargs="?", default="export")
    w.add_argument("-o", "--out")
    w.add_argument("--size", help="LxA, ex: 2560x1440")
    w.add_argument("--scale", type=int)
    w.add_argument("--time", type=float)
    w.add_argument("--art", choices=list(ARTS))
    sc = sub.add_parser("scr", help="protetor de tela (Windows)")
    sc.add_argument("action", choices=["install", "uninstall"])
    sc.add_argument("--minutes", type=int)
    d = sub.add_parser("do", help="executa um comando do terminal >_ (ex: rest do import arte.txt)")
    d.add_argument("words", nargs=argparse.REMAINDER)
    sub.add_parser("doctor", help="diagnostico do terminal e do ambiente")
    c = sub.add_parser("config", help="caminho / editar / resetar")
    c.add_argument("action", choices=["path", "edit", "reset"], nargs="?", default="path")
    a = ap.parse_args(argv)
    if a.config:
        cfg = Config(a.config)

    if a.cmd == "saver":
        return saver(cfg, a.art)
    if a.cmd == "wallpaper":
        eng = Engine(cfg)
        wp = cfg.data["wallpaper"]
        W, H = (int(x) for x in a.size.lower().split("x")) if a.size else (int(wp["width"]), int(wp["height"]))
        out = os.path.abspath(a.out or os.path.join(system.data_dir(), "rest-wallpaper.png"))
        render_png(eng, out, W, H, a.scale or int(wp["scale"]), a.time if a.time is not None else float(wp["time"]), a.art)
        print("PNG:", out)
        if a.action == "set":
            print(system.set_wallpaper(out))
        elif a.action == "lock":
            print(system.set_lockscreen(out))
        return 0
    if a.cmd == "doctor":
        for kind, text in system.doctor(cfg):
            print(("! " if kind == "err" else "") + text)
        return 0
    if a.cmd == "do":
        from .commands import Shell
        line = " ".join(f'"{x}"' if " " in x else x for x in a.words)
        res = Shell(cfg, Engine(cfg)).run(line)
        for kind, text in res.lines:
            print(("! " if kind == "err" else "") + text)
        return 1 if any(k == "err" for k, _ in res.lines) else 0
    if a.cmd == "scr":
        print(system.scr_install(a.minutes or int(cfg.data["saver"]["timeout_minutes"])) if a.action == "install" else system.scr_uninstall())
        return 0
    if a.cmd == "config":
        if a.action == "reset":
            cfg.reset()
        cfg.save()
        if a.action == "edit":
            print(system.open_in_editor(cfg.path))
        print(cfg.path)
        return 0
    if not sys.stdout.isatty():
        print("Rest precisa de um terminal interativo.", file=sys.stderr)
        return 1
    App(cfg, Engine(cfg)).run()
    return 0
