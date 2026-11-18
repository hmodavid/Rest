"""Interpretador do terminal '>_' (comandos para mudar tudo ao vivo)."""
from __future__ import annotations
import os
import shlex

from . import system, userarts
from .arts import ARTS
from .charsets import PRESETS, resolve
from .colors import parse_color, ui_color_indices
from .export import render_png

HELP = {
    "art": ("art <nome>", "troca a arte: " + " ".join(ARTS)),
    "arts": ("arts", "lista as artes (nativas e suas) e mostra a pasta 'arts'"),
    "new": ("new <nome> [txt|py]", "cria um descanso novo (txt = arte ASCII, py = codigo) e abre no editor"),
    "import": ("import <arquivo> [nome]", "importa .txt (ASCII/animacao) ou .py (plugin); aceita arrastar o arquivo"),
    "rm": ("rm <nome>", "remove uma arte sua"),
    "colors": ("colors <c1> <c2> ...", "cores do tema (hex/nome, peso opcional: #ff8c1a:5)"),
    "color": ("colors add <c> | rm <n> | set <n> <c>", "edita a lista de cores"),
    "bg": ("bg <cor>", "cor de fundo"),
    "chars": ("chars <preset|texto>", "tipo do texto: " + " ".join(PRESETS) + " ou seus caracteres"),
    "speed": ("speed <0.1-5>", "velocidade da animacao"),
    "fps": ("fps <5-60>", "quadros por segundo"),
    "cascade": ("cascade <0-2>", "velocidade da cascata de cores"),
    "aspect": ("aspect <0.3-1>", "proporcao largura/altura da celula do terminal"),
    "set": ("set <param> <valor>", "parametro da arte atual (veja 'params')"),
    "params": ("params", "lista os parametros da arte atual"),
    "theme": ("theme <nome> | list | save <nome> | del <nome>", "temas prontos e seus"),
    "save": ("save", "salva as preferencias (tambem e automatico)"),
    "reload": ("reload", "recarrega o arquivo de config"),
    "reset": ("reset", "volta ao padrao"),
    "config": ("config", "mostra o caminho do arquivo"),
    "edit": ("edit [arte]", "abre o config (ou o arquivo da sua arte) no editor"),
    "saver": ("saver", "tela cheia (qualquer tecla sai)"),
    "wallpaper": ("wallpaper export [arq.png] | set | lock", "gera PNG do quadro atual / aplica como wallpaper / lockscreen"),
    "clock": ("clock on|off", "relogio grande no canto do protetor de tela"),
    "playlist": ("playlist <a> <b> ... | all | clear", "o protetor alterna entre essas artes"),
    "cycle": ("cycle <segundos>", "tempo de cada arte da playlist (5-3600)"),
    "doctor": ("doctor", "diagnostico: tamanho, cores 24 bits, tela cheia, pastas"),
    "scr": ("scr install [min] | uninstall", "protetor de tela (Windows, experimental)"),
    "pause": ("pause", "pausa/retoma"),
    "clear": ("clear", "limpa a saida"),
    "exit": ("exit", "sai do Rest"),
}


class Result:
    def __init__(self, lines=None, action=None):
        self.lines = lines or []
        self.action = action


def _unq(s):
    return s[1:-1] if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'" else s


class Shell:
    def __init__(self, cfg, engine):
        self.cfg, self.engine = cfg, engine

    def _commit(self):
        self.cfg.save()
        self.engine.apply(self.cfg)

    def run(self, line: str) -> Result:
        try:
            toks = [_unq(t) for t in shlex.split(line, posix=(os.name != "nt"))]
        except ValueError:
            toks = line.split()
        if not toks:
            return Result()
        cmd, args = toks[0].lower().lstrip(">"), toks[1:]
        fn = getattr(self, "c_" + cmd, None)
        if fn is None:
            return Result([("err", f"comando desconhecido: {cmd} (digite help)")])
        try:
            return fn(args) or Result()
        except (ValueError, IndexError) as e:
            return Result([("err", str(e) or "argumentos invalidos"), ("info", "uso: " + HELP.get(cmd, ("?",))[0])])

    # ------------------------------------------------------------ comandos
    def c_help(self, a):
        if a and a[0] in HELP:
            u, d = HELP[a[0]]
            return Result([("info", u), ("out", d)])
        return Result([("info", f"{u}  -  {d}") for u, d in HELP.values()])

    def c_arts(self, a):
        lines = [("out", ("> " if n == self.cfg.data["art"] else "  ") + n + (" [seu]" if c.user else "") + " - " + c.desc)
                 for n, c in ARTS.items()]
        lines.append(("info", "pasta: " + self.cfg.arts_dir))
        return Result(lines)

    def _reload_arts(self, select=None):
        warns = userarts.load_user_arts(self.cfg)
        self.engine.inst.clear()
        if select and select in ARTS:
            self.cfg.data["art"] = select
        if self.cfg.data["art"] not in ARTS:
            self.cfg.data["art"] = "blackhole"
        self._commit()
        return [("err", w) for w in warns]

    def c_new(self, a):
        kind = (a[1] if len(a) > 1 else "txt").lower()
        if kind not in ("txt", "py"):
            raise ValueError("tipo: txt ou py")
        path = userarts.create_template(self.cfg, a[0], kind)
        name = userarts.clean_name(a[0])
        out = [("ok", "criado: " + path)] + self._reload_arts(name)
        out.append(("info", system.open_in_editor(path)))
        out.append(("out", "salve o arquivo: a arte atualiza ao vivo"))
        return Result(out)

    def c_import(self, a):
        name, dest = userarts.import_file(self.cfg, a[0], a[1] if len(a) > 1 else None)
        out = self._reload_arts(name)
        ok = name in ARTS
        return Result([("ok" if ok else "err", f"importado: {name} -> {dest}")] + out)

    def c_rm(self, a):
        path = userarts.remove_art(self.cfg, a[0])
        return Result([("ok", "removido: " + path)] + self._reload_arts())

    def c_art(self, a):
        if not a:
            return self.c_arts(a)
        if a[0] not in ARTS:
            raise ValueError("arte desconhecida; opcoes: " + " ".join(ARTS))
        self.cfg.data["art"] = a[0]
        self._commit()
        return Result([("ok", "arte: " + a[0])])

    def _set_colors(self, specs):
        for s in specs:
            parse_color(s)
        if not specs:
            raise ValueError("informe ao menos uma cor")
        self.cfg.data["colors"] = list(specs)
        self._commit()
        n, ui = len(specs), ui_color_indices(specs)
        return Result([("ok", f"{n} cor(es); UI usa {len(ui)}: " + ", ".join(specs[i] for i in ui))])

    def c_colors(self, a):
        cur = list(self.cfg.data["colors"])
        if not a:
            return Result([("out", " ".join(cur))])
        sub = a[0].lower()
        if sub == "add":
            return self._set_colors(cur + a[1:])
        if sub in ("rm", "del"):
            i = int(a[1]) - 1
            if not 0 <= i < len(cur):
                raise ValueError("indice fora da lista")
            del cur[i]
            return self._set_colors(cur)
        if sub == "set":
            i = int(a[1]) - 1
            if not 0 <= i < len(cur):
                raise ValueError("indice fora da lista")
            cur[i] = a[2]
            return self._set_colors(cur)
        return self._set_colors(a)

    c_color = c_colors

    def c_bg(self, a):
        parse_color(a[0])
        self.cfg.data["background"] = a[0]
        self._commit()
        return Result([("ok", "fundo: " + a[0])])

    def c_chars(self, a):
        if not a:
            return Result([("out", "atual: " + repr(self.cfg.data["charset"]) + "  presets: " + " ".join(PRESETS))])
        txt = " ".join(a) if a[0] not in PRESETS else a[0]
        self.cfg.data["charset"] = txt
        self._commit()
        return Result([("ok", "texto: " + repr(resolve(txt)[:24]))])

    def _num(self, key, a):
        if not a:
            return Result([("out", f"{key} = {self.cfg.data[key]}")])
        self.cfg.data[key] = float(a[0])
        self._commit()
        return Result([("ok", f"{key} = {self.cfg.data[key]}")])

    def c_speed(self, a): return self._num("speed", a)
    def c_fps(self, a): return self._num("fps", a)
    def c_cascade(self, a): return self._num("cascade", a)
    def c_aspect(self, a): return self._num("aspect", a)

    def c_params(self, a):
        cls = ARTS[self.cfg.data["art"]]
        p = self.cfg.art_params(cls)
        def hint(k):
            if k in cls.ranges:
                return f"   [{cls.ranges[k][0]}..{cls.ranges[k][1]}]"
            if k in cls.choices:
                return "   [" + "|".join(cls.choices[k]) + "]"
            return ""
        return Result([("out", f"{k} = {v}" + hint(k)) for k, v in p.items()])

    def c_set(self, a):
        key, val = a[0], a[1]
        cls = ARTS[self.cfg.data["art"]]
        if key not in cls.defaults:
            raise ValueError(f"'{key}' nao existe em {cls.name}: " + " ".join(cls.defaults))
        if key in cls.choices and val not in cls.choices[key]:
            raise ValueError(f"{key}: use " + "|".join(cls.choices[key]))
        self.cfg.data["params"].setdefault(cls.name, {})[key] = val
        self._commit()
        return Result([("ok", f"{cls.name}.{key} = {self.cfg.art_params(cls)[key]}")])

    def c_theme(self, a):
        th = self.cfg.themes()
        if not a or a[0] == "list":
            return Result([("out", " ".join(th))])
        if a[0] == "save":
            self.cfg.data["themes"][a[1]] = {"colors": list(self.cfg.data["colors"]), "background": self.cfg.data["background"]}
            self._commit()
            return Result([("ok", "tema salvo: " + a[1])])
        if a[0] == "del":
            self.cfg.data["themes"].pop(a[1], None)
            self._commit()
            return Result([("ok", "tema removido")])
        if not self.cfg.apply_theme(a[0]):
            raise ValueError("tema desconhecido: " + " ".join(th))
        self._commit()
        return Result([("ok", "tema: " + a[0])])

    def c_save(self, a):
        self._commit()
        return Result([("ok", "salvo em " + self.cfg.path)])

    def c_reload(self, a):
        self.cfg.load()
        self.engine.apply(self.cfg)
        return Result([("ok", "config recarregada")] + [("err", w) for w in self.cfg.warnings])

    def c_reset(self, a):
        self.cfg.reset()
        self._commit()
        return Result([("ok", "preferencias restauradas")])

    def c_config(self, a):
        return Result([("out", self.cfg.path)])

    def c_edit(self, a):
        if a:
            path = userarts.USER.get(a[0])
            if not path:
                raise ValueError(f"'{a[0]}' nao e uma arte sua (veja: arts)")
            return Result([("info", system.open_in_editor(path))])
        self.cfg.save()
        return Result([("info", system.open_in_editor(self.cfg.path))])

    def c_saver(self, a):
        return Result(action="saver")

    def c_pause(self, a):
        return Result(action="pause")

    def c_clear(self, a):
        return Result(action="clear")

    def c_exit(self, a):
        return Result(action="quit")

    c_quit = c_exit

    def c_wallpaper(self, a):
        sub = a[0] if a else "export"
        wp = self.cfg.data["wallpaper"]
        path = os.path.join(system.data_dir(), "rest-wallpaper.png")
        if sub == "export" and len(a) > 1:
            path = os.path.abspath(a[1])
        render_png(self.engine, path, int(wp["width"]), int(wp["height"]), int(wp["scale"]), float(wp["time"]))
        out = [("ok", "PNG gerado: " + path)]
        if sub == "set":
            out.append(("info", system.set_wallpaper(path)))
        elif sub == "lock":
            out.append(("info", system.set_lockscreen(path)))
        elif sub != "export":
            raise ValueError("use export | set | lock")
        return Result(out)

    def c_clock(self, a):
        sv = self.cfg.data["saver"]
        if a:
            sv["clock"] = a[0].lower() in ("on", "1", "true", "sim", "yes")
            self._commit()
        return Result([("ok", "relogio: " + ("ligado" if sv["clock"] else "desligado"))])

    def c_playlist(self, a):
        sv = self.cfg.data["saver"]
        if a:
            if a[0] == "clear":
                sv["playlist"] = []
            elif a[0] == "all":
                sv["playlist"] = list(ARTS)
            else:
                bad = [n for n in a if n not in ARTS]
                if bad:
                    raise ValueError("arte desconhecida: " + ", ".join(bad))
                sv["playlist"] = list(a)
            self._commit()
        pl = sv["playlist"]
        return Result([("ok", ("playlist: " + " ".join(pl) + f" (a cada {sv['cycle_seconds']:g}s)") if pl else "playlist vazia (o protetor usa so a arte atual)")])

    def c_cycle(self, a):
        sv = self.cfg.data["saver"]
        sv["cycle_seconds"] = float(a[0])
        self._commit()
        return Result([("ok", f"troca a cada {sv['cycle_seconds']:g}s")])

    def c_doctor(self, a):
        return Result(system.doctor(self.cfg))

    def c_scr(self, a):
        sub = a[0] if a else ""
        if sub == "install":
            m = int(a[1]) if len(a) > 1 else int(self.cfg.data["saver"]["timeout_minutes"])
            return Result([("info", l) for l in system.scr_install(m).split("\n")])
        if sub == "uninstall":
            return Result([("info", system.scr_uninstall())])
        raise ValueError("use install | uninstall")
