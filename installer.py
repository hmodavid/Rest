#!/usr/bin/env python3
"""Instalador do Rest: gera o executavel com banner REST e barra de progresso em gradiente.

Uso:  python installer.py [--skip-tests] [--strict-tests] [--dry-run] [--no-color]
(build_exe.bat e build_exe.sh chamam este arquivo.)
"""
from __future__ import annotations

import argparse
import importlib.util
import math
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from rest import __version__  # noqa: E402
from rest.colors import fg, gradient  # noqa: E402

ORANGE, PINK, PURPLE = (255, 140, 26), (255, 77, 141), (160, 107, 255)
STOPS = [ORANGE, PINK, PURPLE]            # laranja -> rosa -> roxo
TEXT, MUTED, ERR = (226, 222, 214), (110, 110, 122), (255, 96, 96)
RESET, BOLD = "\x1b[0m", "\x1b[1m"

BANNER = [
    r" ____  _____ ____ _____",
    r"|  _ \| ____/ ___|_   _|",
    r"| |_) |  _| \___ \ | |",
    r"|  _ <| |___ ___) || |",
    r"|_| \_\_____|____/ |_|",
]
TAGLINE = [
    "descanso de tela ASCII para o terminal",
    f"instalador  v{__version__}",
    "Windows e Linux",
    "",
    "",
]
HIDDEN_IMPORTS = ["colorsys", "itertools", "functools", "string", "statistics", "datetime", "json"]
IS_WIN = os.name == "nt"


def fmt_time(s: float) -> str:
    m, s = divmod(int(s), 60)
    return f"{m:02d}:{s:02d}"


class UI:
    """Desenha banner, barra de progresso em gradiente e linhas de status."""

    def __init__(self, color: bool, cols: int):
        self.color, self.cols = color, cols
        self.live = False                      # ha uma linha de barra "viva" na tela
        compact = cols < 62
        self.lw = 22 if compact else 26
        self.show_time = not compact
        used = 4 + 5 + 1 + self.lw + 1 + 1 + 4 + (7 if self.show_time else 0) + 2
        self.bw = max(8, min(44, cols - used))

    # -- cores ---------------------------------------------------------
    def c(self, rgb, text, bold=False):
        return (BOLD if bold else "") + fg(rgb) + text + RESET if self.color else text

    # -- banner --------------------------------------------------------
    def banner(self):
        if self.cols < 26:
            return
        width = max(len(x) for x in BANNER)
        print()
        for r, line in enumerate(BANNER):
            art = ""
            for i, ch in enumerate(line.ljust(width)):
                if ch == " " or not self.color:
                    art += ch
                else:
                    art += fg(gradient(STOPS, min(1.0, (i + r * 2) / (width + 8)))) + BOLD + ch + RESET
            tag = TAGLINE[r] if self.cols >= width + 36 else ""
            print("  " + art + "     " + (self.c(MUTED, tag) if tag else ""))
        print()

    # -- barra ---------------------------------------------------------
    def bar(self, p: float) -> str:
        n = self.bw
        filled = int(round(max(0.0, min(1.0, p)) * n))
        if not self.color:
            return "[" + "#" * filled + "-" * (n - filled) + "]"
        out = []
        for i in range(n):
            if i < filled:
                out.append(fg(gradient(STOPS, i / max(1, n - 1))) + "\u2588")
            else:
                out.append(fg((58, 58, 68)) + "\u2591")
        return "".join(out) + RESET

    def progress(self, p, label, idx, total, elapsed):
        spin = "|/-\\"[int(time.perf_counter() * 10) % 4]
        line = (f"  {self.c(PINK, spin, True)} {self.c(TEXT, f'[{idx}/{total}]')} {label.ljust(self.lw)[:self.lw]} "
                f"{self.bar(p)} {int(p * 100 + 0.5):3d}%" + (f"  {fmt_time(elapsed)}" if self.show_time else ""))
        if self.color:
            sys.stdout.write("\r\x1b[2K" + line)
            sys.stdout.flush()
            self.live = True

    def clear_live(self):
        if self.live:
            sys.stdout.write("\r\x1b[2K")
            self.live = False

    def done(self, label, idx, total, secs):
        self.clear_live()
        mark = self.c(PINK, "\u2713" if self.color else "ok", True)
        print(f"  {mark} {self.c(TEXT, f'[{idx}/{total}]')} {label.ljust(self.lw)[:self.lw]} {self.c(MUTED, f'{secs:.0f}s')}")
        if not self.color:
            print("      " + self.bar(idx / total))

    def warn(self, label, idx, total, lines):
        self.clear_live()
        mark = self.c(ORANGE, "!", True)
        print(f"  {mark} {self.c(TEXT, f'[{idx}/{total}]')} {self.c(ORANGE, label + ' - avisos (continuando)')}")
        for ln in lines[-6:]:
            print("      " + self.c(MUTED, ln.rstrip()[: max(10, self.cols - 8)]))

    def fail(self, label, idx, total, lines):
        self.clear_live()
        print(f"  {self.c(ERR, 'x' if not self.color else '\u2717', True)} {self.c(TEXT, f'[{idx}/{total}]')} {self.c(ERR, label + ' - falhou')}")
        for ln in lines:
            print("      " + self.c(MUTED, ln.rstrip()[: max(10, self.cols - 8)]))


class Installer:
    def __init__(self, args, ui: UI):
        self.args, self.ui = args, ui
        self.log_path = os.path.join(ROOT, "build.log")
        self.name = "Rest" if IS_WIN else "rest"
        self.out_path = os.path.join(ROOT, "dist", self.name + (".exe" if IS_WIN else ""))
        self.steps = self._steps()

    # (rotulo, peso %, constante de tempo da animacao, tarefa)
    def _steps(self):
        py = sys.executable
        if self.args.dry_run:
            scale = float(os.environ.get("REST_DRY_SCALE", "1"))

            def nap(sec):
                return [py, "-c", f"import time; time.sleep({sec * scale})"]
            return [
                ("Verificando o Python", 1, 1, self.check_python, False),
                ("Instalando o PyInstaller", 20, 1.0, nap(1.0), False),
                ("Rodando os testes", 10, 1.0, nap(0.8), False),
                ("Compilando o executavel", 60, 1.0, nap(1.8), False),
                ("Finalizando", 9, 1, lambda: (True, ""), False),
            ]
        build = [py, "-m", "PyInstaller", "--onefile", "--console", "--clean", "--name", self.name]
        for h in HIDDEN_IMPORTS:
            build += ["--hidden-import", h]
        build.append("rest_entry.py")
        def have_pyinstaller():            # sem internet, mas ja instalado: segue em frente
            return importlib.util.find_spec("PyInstaller") is not None
        steps = [
            ("Verificando o Python", 1, 1, self.check_python, False),
            ("Instalando o PyInstaller", 20, 14, [py, "-m", "pip", "install", "--upgrade", "pyinstaller"], have_pyinstaller),
        ]
        if not self.args.skip_tests:       # falha nos testes vira aviso (a menos que --strict-tests)
            steps.append(("Rodando os testes", 10, 6, [py, "-m", "unittest", "discover", "-s", "tests"],
                          not getattr(self.args, "strict_tests", False)))
        steps += [("Compilando o executavel", 60, 40, build, False), ("Finalizando", 9, 1, self.finalize, False)]
        return steps

    # -- tarefas ---------------------------------------------------------
    def check_python(self):
        if sys.version_info < (3, 9):
            return False, f"Python 3.9+ necessario (encontrado {sys.version.split()[0]})"
        return True, ""

    def finalize(self):
        if not os.path.isfile(self.out_path):
            return False, f"nao encontrei {os.path.relpath(self.out_path, ROOT)}"
        try:                               # extras: nunca derrubam a instalacao
            if IS_WIN:
                shutil.copyfile(self.out_path, os.path.join(ROOT, "dist", "Rest.scr"))
            else:
                os.chmod(self.out_path, 0o755)
        except OSError:
            pass
        return True, ""

    # -- execucao ----------------------------------------------------------
    def run_cmd(self, cmd, label, idx, total, base, weight, tau):
        t0 = time.perf_counter()
        with open(self.log_path, "ab") as log:
            log.write(f"\n=== {label}: {' '.join(cmd)}\n".encode())
            log.flush()                                  # o filho escreve direto no arquivo: cabecalho vem antes
            start = os.fstat(log.fileno()).st_size
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            try:
                while proc.poll() is None:
                    el = time.perf_counter() - t0
                    self.ui.progress(base + weight * 0.94 * (1 - math.exp(-el / tau)), label, idx, total, el)
                    time.sleep(0.1)
            except KeyboardInterrupt:
                proc.terminate()
                raise
        ok = proc.returncode == 0
        tail = []
        if not ok:
            with open(self.log_path, "rb") as f:
                f.seek(start)
                tail = f.read().decode("utf-8", "replace").splitlines()[-14:]
        return ok, tail

    def run(self) -> int:
        ui, total = self.ui, len(self.steps)
        total_w = sum(s[1] for s in self.steps)
        open(self.log_path, "wb").close()
        base, t_all = 0.0, time.perf_counter()
        try:
            for idx, (label, weight, tau, job, soft) in enumerate(self.steps, 1):
                w = weight / total_w
                t0 = time.perf_counter()
                if callable(job):
                    ui.progress(base, label, idx, total, 0.0)
                    ok, msg = job()
                    tail = [msg] if msg else []
                    time.sleep(0.15 if not self.args.dry_run else 0.05)
                else:
                    ok, tail = self.run_cmd(job, label, idx, total, base, w, tau)
                if not ok:
                    if soft() if callable(soft) else soft:
                        ui.warn(label, idx, total, tail + [f"(log completo: {os.path.relpath(self.log_path)})"])
                        base += w
                        ui.progress(base, label, idx, total, time.perf_counter() - t0)
                        continue
                    ui.fail(label, idx, total, tail + [f"(log completo: {os.path.relpath(self.log_path)})"])
                    return 1
                base += w
                ui.progress(base, label, idx, total, time.perf_counter() - t0)
                ui.done(label, idx, total, time.perf_counter() - t0)
        except KeyboardInterrupt:
            ui.clear_live()
            print("\n  Cancelado.")
            return 130
        ui.progress(1.0, "Concluido", total, total, time.perf_counter() - t_all)
        ui.clear_live()
        print(f"\n  {ui.bar(1.0)} 100%  {ui.c(MUTED, fmt_time(time.perf_counter() - t_all))}")
        self.summary()
        return 0

    def summary(self):
        ui = self.ui
        rel = os.path.relpath(self.out_path, ROOT)
        if self.args.dry_run:
            print(f"\n  {ui.c(PINK, 'Simulacao concluida.', True)} Nada foi instalado nem compilado.\n")
            return
        try:
            size = f"({os.path.getsize(self.out_path) / 1048576:.1f} MB)"
        except OSError:
            size = ""
        print(f"\n  {ui.c(PINK, 'Pronto!', True)} {ui.c(TEXT, rel)} {ui.c(MUTED, size)}")
        if IS_WIN:
            print(f"  {ui.c(MUTED, 'Abrir:')} {rel}      {ui.c(MUTED, 'Protetor de tela:')} Rest.exe scr install 5")
        else:
            print(f"  {ui.c(MUTED, 'Abrir:')} ./{rel}")
        print()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Instalador do Rest (gera o executavel)")
    ap.add_argument("--skip-tests", action="store_true", help="nao roda os testes antes de compilar")
    ap.add_argument("--strict-tests", action="store_true", help="falha nos testes interrompe (padrao: so avisa)")
    ap.add_argument("--dry-run", action="store_true", help="simula as etapas (so para ver a interface)")
    ap.add_argument("--no-color", action="store_true", help="sem cores/animacao")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    color = sys.stdout.isatty() and not args.no_color and not os.environ.get("NO_COLOR")
    if color:
        try:
            from rest.term import enable_vt
            enable_vt()
        except Exception:
            pass
    cols = shutil.get_terminal_size((80, 24)).columns
    ui = UI(color, cols)
    ui.banner()
    if color:
        sys.stdout.write("\x1b[?25l")
    try:
        return Installer(args, ui).run()
    finally:
        if color:
            sys.stdout.write("\x1b[?25h" + RESET)
            sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
