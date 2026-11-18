"""Integracao com o SO: wallpaper, lockscreen, screensaver (Windows e Linux)."""
from __future__ import annotations
import os
import shutil
import subprocess
import sys

IS_WIN = os.name == "nt"


def data_dir() -> str:
    if IS_WIN:
        d = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Rest")
    else:
        d = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "rest")
    os.makedirs(d, exist_ok=True)
    return d


def _run(cmd) -> bool:
    try:
        return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15).returncode == 0
    except Exception:
        return False


def set_wallpaper(path: str) -> str:
    path = os.path.abspath(path)
    if IS_WIN:
        import ctypes
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, "10")  # preencher
            winreg.SetValueEx(k, "TileWallpaper", 0, winreg.REG_SZ, "0")
        ok = ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        return "wallpaper aplicado" if ok else "falhou ao aplicar wallpaper"
    uri = "file://" + path
    if shutil.which("gsettings"):
        a = _run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri])
        _run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri])
        _run(["gsettings", "set", "org.gnome.desktop.background", "picture-options", "zoom"])
        if a:
            return "wallpaper aplicado (GNOME)"
    if shutil.which("plasma-apply-wallpaperimage") and _run(["plasma-apply-wallpaperimage", path]):
        return "wallpaper aplicado (KDE)"
    if shutil.which("feh") and _run(["feh", "--bg-fill", path]):
        return "wallpaper aplicado (feh)"
    if shutil.which("nitrogen") and _run(["nitrogen", "--set-zoom-fill", "--save", path]):
        return "wallpaper aplicado (nitrogen)"
    return f"nao achei como aplicar automaticamente; defina manualmente: {path}"


def set_lockscreen(path: str) -> str:
    path = os.path.abspath(path)
    if IS_WIN:
        import winreg
        msg = []
        try:  # exige administrador; funciona no Windows Home/Pro via PersonalizationCSP
            key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\PersonalizationCSP"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, "LockScreenImagePath", 0, winreg.REG_SZ, path)
                winreg.SetValueEx(k, "LockScreenImageUrl", 0, winreg.REG_SZ, path)
                winreg.SetValueEx(k, "LockScreenImageStatus", 0, winreg.REG_DWORD, 1)
            return "lockscreen definido (bloqueie com Win+L para ver)"
        except PermissionError:
            msg.append("sem permissao de administrador")
        except OSError as e:
            msg.append(str(e))
        try:
            os.startfile("ms-settings:lockscreen")
        except Exception:
            pass
        return (f"{'; '.join(msg)}. Abri Configuracoes > Tela de bloqueio: escolha 'Imagem' > Procurar e "
                f"selecione {path} (ou rode o Rest como administrador)")
    done = []
    if shutil.which("gsettings") and _run(["gsettings", "set", "org.gnome.desktop.screensaver", "picture-uri", "file://" + path]):
        done.append("GNOME")
    kw = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if kw and _run([kw, "--file", "kscreenlockerrc", "--group", "Greeter", "--group", "Wallpaper",
                    "--group", "org.kde.image", "--group", "General", "--key", "Image", "file://" + path]):
        done.append("KDE")
    if done:
        return "lockscreen definido (" + ", ".join(done) + ")"
    return f"defina a imagem da tela de bloqueio manualmente: {path} (i3lock -i, swaylock -i, etc.)"


def scr_install(minutes: int = 5, secure: bool = False) -> str:
    if IS_WIN:
        if not getattr(sys, "frozen", False):
            return "use o Rest.exe (versao compilada) para instalar como protetor de tela"
        import ctypes
        import winreg
        dest = os.path.join(data_dir(), "Rest.scr")
        shutil.copyfile(sys.executable, dest)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, "SCRNSAVE.EXE", 0, winreg.REG_SZ, dest)
            winreg.SetValueEx(k, "ScreenSaveActive", 0, winreg.REG_SZ, "1")
            winreg.SetValueEx(k, "ScreenSaveTimeOut", 0, winreg.REG_SZ, str(minutes * 60))
            winreg.SetValueEx(k, "ScreenSaverIsSecure", 0, winreg.REG_SZ, "1" if secure else "0")
        ctypes.windll.user32.SystemParametersInfoW(17, 1, None, 3)
        ctypes.windll.user32.SystemParametersInfoW(15, minutes * 60, None, 3)
        _run(["rundll32.exe", "user32.dll,UpdatePerUserSystemParameters"])
        return f"protetor de tela instalado em {dest} ({minutes} min). Recurso experimental: abre em console."
    return ("Linux: instale xscreensaver/xss-lock e use o Rest em tela cheia, por exemplo:\n"
            "  xset s 300 && xss-lock -- xterm -fullscreen -e rest saver\n"
            "  (Wayland/sway: swayidle -w timeout 300 'foot -F rest saver')")


def scr_uninstall() -> str:
    if not IS_WIN:
        return "nada a desinstalar no Linux"
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, "SCRNSAVE.EXE")
    except OSError:
        pass
    return "protetor de tela removido"


def open_in_editor(path: str) -> str:
    if os.environ.get("REST_NO_EDITOR"):
        return f"edite manualmente: {path}"
    try:
        if IS_WIN:
            subprocess.Popen(["notepad.exe", path])
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            return f"edite manualmente: {path}"
        return "aberto no editor (as mudancas recarregam sozinhas ao salvar)"
    except Exception as e:
        return f"nao consegui abrir ({e}); arquivo: {path}"


def doctor(cfg) -> list[tuple[str, str]]:
    """Diagnostico do ambiente (terminal, cores, tela cheia, pastas)."""
    import platform
    from . import __version__
    from .term import Terminal
    out = [("info", f"Rest {__version__} · Python {platform.python_version()} · {platform.system()} {platform.release()}"
                    + (" · exe compilado" if getattr(sys, "frozen", False) else ""))]
    cols, rows = Terminal.size()
    out.append(("out", f"janela do terminal: {cols}x{rows} colunas/linhas"))
    env_c, env_l = os.environ.get("COLUMNS"), os.environ.get("LINES")
    if env_c or env_l:
        stale = (env_c and env_c != str(cols)) or (env_l and env_l != str(rows))
        out.append(("err" if stale else "out",
                    f"COLUMNS/LINES = {env_c}/{env_l}" + (" (diferem da janela; o Rest ignora essas variaveis)" if stale else "")))
    term, ct = os.environ.get("TERM", "?"), os.environ.get("COLORTERM", "")
    truecolor = ct.lower() in ("truecolor", "24bit") or bool(os.environ.get("WT_SESSION")) or os.name == "nt"
    out.append(("out", f"TERM={term} COLORTERM={ct or '-'}" + (" · Windows Terminal" if os.environ.get("WT_SESSION") else "")))
    out.append(("ok" if truecolor else "err", "cores 24 bits: provavel" if truecolor else
                "cores 24 bits: nao detectado (use Windows Terminal/kitty/gnome-terminal; ou defina COLORTERM=truecolor)"))
    out.append(("out" if sys.stdout.isatty() else "err", "stdout e um terminal" if sys.stdout.isatty() else "stdout NAO e um terminal"))
    if IS_WIN:
        try:
            from .term import _win_is_fullscreen
            out.append(("out", "janela em tela cheia agora: " + ("sim" if _win_is_fullscreen() else "nao")))
        except Exception as e:
            out.append(("err", f"nao consegui checar tela cheia: {e}"))
    else:
        have = [x for x in ("wmctrl", "xprop") if shutil.which(x)]
        out.append(("ok" if len(have) == 2 else "info",
                    "tela cheia automatica (wmctrl+xprop): " + ("ok" if len(have) == 2 else "faltam " + ", ".join(sorted({"wmctrl", "xprop"} - set(have))) + " (use F11 antes)")))
    from .arts import ARTS
    out.append(("out", f"config: {cfg.path}" + ("" if os.path.exists(cfg.path) else " (ainda nao salvo)")))
    out.append(("out", f"artes: {len(ARTS)} ({sum(1 for c in ARTS.values() if c.user)} suas) · pasta {cfg.arts_dir}"))
    for w in cfg.warnings:
        out.append(("err", w))
    return out
