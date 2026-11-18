"""Terminal cru multiplataforma (stdlib): VT, teclado, tela alternativa."""
from __future__ import annotations
import os
import shutil
import sys
import time

IS_WIN = os.name == "nt"
if IS_WIN:
    import msvcrt
else:
    import select
    import termios
    import tty

_WIN_KEYS = {"H": "up", "P": "down", "K": "left", "M": "right", "G": "home", "O": "end",
             "S": "delete", "I": "pgup", "Q": "pgdn"}
_NIX_KEYS = {"A": "up", "B": "down", "C": "right", "D": "left", "H": "home", "F": "end"}
_NIX_TILDE = {"3": "delete", "5": "pgup", "6": "pgdn", "1": "home", "4": "end", "7": "home", "8": "end"}


def enable_vt() -> None:
    if not IS_WIN:
        return
    import ctypes
    k = ctypes.windll.kernel32
    h = k.GetStdHandle(-11)
    mode = ctypes.c_ulong()
    if k.GetConsoleMode(h, ctypes.byref(mode)):
        k.SetConsoleMode(h, mode.value | 0x0004)


def mouse_pos():
    if not IS_WIN:
        return None
    import ctypes
    from ctypes import wintypes
    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


class Terminal:
    def __enter__(self):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        enable_vt()
        if not IS_WIN:
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        self.write("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J")
        return self

    def __exit__(self, *a):
        self.write("\x1b[0m\x1b]111\x07\x1b[?7h\x1b[?25h\x1b[?1049l")
        if not IS_WIN:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

    def set_bg(self, rgb):
        """Pinta o fundo padrao do terminal (OSC 11): elimina faixas pretas nas bordas."""
        self.write("\x1b]11;#%02x%02x%02x\x07" % tuple(rgb))

    @staticmethod
    def size():
        """Tamanho real da janela (ignora COLUMNS/LINES, que ficam velhos apos a tela cheia)."""
        for f in (sys.__stdout__, sys.__stderr__, sys.__stdin__):
            try:
                sz = os.get_terminal_size(f.fileno())
                if sz.columns > 0 and sz.lines > 0:
                    return sz.columns, sz.lines
            except Exception:
                continue
        sz = shutil.get_terminal_size((100, 30))
        return sz.columns, sz.lines

    @staticmethod
    def write(s: str):
        sys.stdout.write(s)
        sys.stdout.flush()

    def read_keys(self, timeout: float = 0.0) -> list[str]:
        return self._win(timeout) if IS_WIN else self._nix(timeout)

    # -- Windows
    def _win(self, timeout):
        end = time.perf_counter() + timeout
        while True:
            keys = []
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\x00", "\xe0"):
                    keys.append(_WIN_KEYS.get(msvcrt.getwch(), "?"))
                elif ch == "\r":
                    keys.append("enter")
                elif ch == "\x08":
                    keys.append("backspace")
                elif ch == "\x1b":
                    keys.append("esc")
                elif ch == "\t":
                    keys.append("tab")
                elif ch == "\x03":
                    keys.append("ctrl-c")
                elif ch >= " ":
                    keys.append(ch)
            if keys or time.perf_counter() >= end:
                return keys
            time.sleep(0.004)

    # -- POSIX
    def _nix(self, timeout):
        r, _, _ = select.select([sys.stdin], [], [], max(0.0, timeout))
        if not r:
            return []
        data = os.read(self.fd, 256).decode("utf-8", "ignore")
        keys, i, n = [], 0, len(data)
        while i < n:
            ch = data[i]
            if ch == "\x1b":
                if i + 1 < n and data[i + 1] in "[O":
                    j = i + 2
                    while j < n and not (data[j].isalpha() or data[j] == "~"):
                        j += 1
                    seq = data[i + 2:j + 1]
                    if seq.endswith("~"):
                        keys.append(_NIX_TILDE.get(seq[:-1].split(";")[0], "?"))
                    elif seq:
                        keys.append(_NIX_KEYS.get(seq[-1], "?"))
                    i = j + 1
                    continue
                keys.append("esc")
            elif ch in "\r\n":
                keys.append("enter")
            elif ch in "\x7f\x08":
                keys.append("backspace")
            elif ch == "\t":
                keys.append("tab")
            elif ch == "\x03":
                keys.append("ctrl-c")
            elif ch >= " ":
                keys.append(ch)
            i += 1
        return keys


# ---------------------------------------------------------------- tela cheia
def _win_is_fullscreen() -> bool:
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    r = wintypes.RECT()
    u.GetWindowRect(u.GetForegroundWindow(), ctypes.byref(r))
    return r.left <= 0 and r.top <= 0 and r.right >= u.GetSystemMetrics(0) and r.bottom >= u.GetSystemMetrics(1)


def _nix_active_window():
    import subprocess
    try:
        o = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"], capture_output=True, text=True, timeout=2).stdout
        return o.split()[-1]
    except Exception:
        return None


def _nix_is_fullscreen(wid) -> bool:
    import subprocess
    try:
        o = subprocess.run(["xprop", "-id", wid, "_NET_WM_STATE"], capture_output=True, text=True, timeout=2).stdout
        return "_NET_WM_STATE_FULLSCREEN" in o
    except Exception:
        return False


def _wait_resize(before, timeout=1.5):
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        if Terminal.size() != before:
            time.sleep(0.15)
            return
        time.sleep(0.05)


def enter_fullscreen():
    """Coloca a janela do terminal em tela cheia (se ainda nao estiver).
    Devolve um token para leave_fullscreen(); None se nada foi alterado."""
    try:
        if IS_WIN:
            if _win_is_fullscreen():
                return None
            import ctypes
            before = Terminal.size()
            k = ctypes.windll.user32.keybd_event
            k(0x12, 0, 0, 0); k(0x0D, 0, 0, 0); k(0x0D, 0, 2, 0); k(0x12, 0, 2, 0)  # Alt+Enter
            _wait_resize(before)
            return ("win",)
        import shutil
        import subprocess
        if shutil.which("wmctrl") and shutil.which("xprop"):
            wid = _nix_active_window()
            if wid and not _nix_is_fullscreen(wid):
                before = Terminal.size()
                subprocess.run(["wmctrl", "-i", "-r", wid, "-b", "add,fullscreen"], timeout=2)
                _wait_resize(before)
                return ("nix", wid)
    except Exception:
        pass
    return None


def leave_fullscreen(token):
    if not token:
        return
    try:
        before = Terminal.size()
        if token[0] == "win":
            import ctypes
            k = ctypes.windll.user32.keybd_event
            k(0x12, 0, 0, 0); k(0x0D, 0, 0, 0); k(0x0D, 0, 2, 0); k(0x12, 0, 2, 0)
        else:
            import subprocess
            subprocess.run(["wmctrl", "-i", "-r", token[1], "-b", "remove,fullscreen"], timeout=2)
        _wait_resize(before)
    except Exception:
        pass
