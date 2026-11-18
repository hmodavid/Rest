import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["REST_NO_EDITOR"] = "1"   # os testes nunca abrem editores

from rest.arts import ARTS
from rest.colors import ui_color_indices, ui_stops, parse_color
from rest.commands import Shell
from rest.config import Config
from rest.engine import Engine
from rest.export import render_png

ANSI = re.compile(r"\x1b\[[0-9;]*m")


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = Config(os.path.join(self.d, "c.json"))
        self.eng = Engine(self.cfg)

    def test_ui_color_rule(self):
        mk = lambda n: [f"#{i:02x}0000" for i in range(1, n + 1)]
        self.assertEqual([len(ui_stops(mk(n))) for n in (1, 2, 3, 4, 5, 8)], [1, 2, 2, 3, 3, 3])

    def test_ui_picks_most_predominant(self):
        self.assertEqual(ui_color_indices(["#111111:1", "#222222:9", "#333333:5"]), [1, 2])
        self.assertEqual(ui_color_indices(["#111111", "#222222", "#333333"]), [0, 1])

    def test_default_theme_is_warm(self):
        r, g, b = parse_color(self.cfg.data["colors"][0])[0]
        self.assertTrue(r > 200 and b < 80)

    def test_all_arts_render_exact_width(self):
        for name in ARTS:
            rows = self.eng.ansi_rows(90, 28, 2.5, name)
            self.assertEqual(len(rows), 28)
            for r in rows:
                self.assertEqual(len(ANSI.sub("", r)), 90, name)

    def test_shell_and_persistence(self):
        sh = Shell(self.cfg, self.eng)
        sh.run("colors #ff0000 #00ff00 #0000ff #ffffff")
        sh.run("art galaxy")
        sh.run("set arms 5")
        sh.run("chars blocks")
        c2 = Config(self.cfg.path)
        self.assertEqual(len(c2.data["colors"]), 4)
        self.assertEqual(c2.data["art"], "galaxy")
        self.assertEqual(c2.art_params(ARTS["galaxy"])["arms"], 5)

    def test_bad_config_does_not_crash(self):
        with open(self.cfg.path, "w") as f:
            f.write("{ not json")
        c = Config(self.cfg.path)
        self.assertTrue(c.warnings)
        self.assertEqual(c.data["art"], "blackhole")

    def test_png(self):
        p = os.path.join(self.d, "w.png")
        render_png(self.eng, p, 640, 360, 1, 3.0)
        with open(p, "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")


class UserArts(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = Config(os.path.join(self.d, "c.json"))
        self.eng = Engine(self.cfg)
        self.sh = Shell(self.cfg, self.eng)

    def _src(self, name, text):
        p = os.path.join(self.d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_import_text_all_modes(self):
        src = self._src("Minha Arte.txt", " /\\\n/__\\\n---frame---\n /\\\n/--\\\n")
        r = self.sh.run(f'import "{src}"')
        self.assertEqual(r.lines[0][0], "ok", r.lines)
        self.assertIn("minha-arte", ARTS)
        for mode in ("center", "bounce", "scroll", "wave", "tile"):
            self.sh.run(f"set mode {mode}")
            for t in (0.0, 1.7, 9.3):
                rows = self.eng.ansi_rows(60, 20, t)
                self.assertEqual([len(ANSI.sub("", x)) for x in rows], [60] * 20, mode)

    def test_new_template_txt_and_py(self):
        self.assertEqual(self.sh.run("new meu-logo").lines[0][0], "ok")
        self.assertEqual(self.sh.run("new minha-onda py").lines[0][0], "ok")
        self.assertIn("meu-logo", ARTS)
        self.assertIn("minha-onda", ARTS)
        self.sh.run("art minha-onda")
        rows = self.eng.ansi_rows(50, 15, 1.0)
        self.assertEqual(len(rows), 15)
        self.assertIsNone(self.eng.new_error)

    def test_builtin_names_are_protected(self):
        src = self._src("blackhole.txt", "x")
        self.assertEqual(self.sh.run(f'import "{src}"').lines[0][0], "err")
        self.assertEqual(self.sh.run("rm blackhole").lines[0][0], "err")

    def test_broken_plugin_does_not_crash(self):
        os.makedirs(self.cfg.arts_dir, exist_ok=True)
        with open(os.path.join(self.cfg.arts_dir, "ruim.py"), "w") as f:
            f.write("from rest.arts import Art\nclass R(Art):\n    name='ruim'\n    def compute(self,w,h,t,p): return 1/0\n")
        with open(os.path.join(self.cfg.arts_dir, "sintaxe.py"), "w") as f:
            f.write("def (:\n")
        self.sh.run("reload")
        self.sh.run("art ruim")
        rows = self.eng.ansi_rows(30, 8, 1.0)
        self.assertEqual(len(rows), 8)
        self.assertIn("ZeroDivisionError", self.eng.new_error)

    def test_art_fills_wide_screens(self):
        w, h = 200, 40
        for name in ("blackhole", "galaxy", "donut"):
            rows = self.eng.ansi_rows(w, h, 3.0, name)
            right = sum(1 for r in rows for ch in ANSI.sub("", r)[int(w * 0.85):] if ch != " ")
            left = sum(1 for r in rows for ch in ANSI.sub("", r)[:int(w * 0.15)] if ch != " ")
            self.assertGreater(right, 40, name)
            self.assertGreater(left, 40, name)


class V03(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = Config(os.path.join(self.d, "c.json"))
        self.eng = Engine(self.cfg)
        self.sh = Shell(self.cfg, self.eng)

    def test_all_themes_valid_and_ui_rule(self):
        from rest.config import PRESET_THEMES
        for name, th in PRESET_THEMES.items():
            n = len(th["colors"])
            self.assertEqual(len(ui_stops(th["colors"])), n if n <= 2 else (2 if n == 3 else 3), name)
            parse_color(th["background"])

    def test_clock_overlay(self):
        a = self.eng.ansi_rows(100, 26, 2.0, "plasma")
        b = self.eng.ansi_rows(100, 26, 2.0, "plasma", clock=True)
        self.assertNotEqual(a[-4:], b[-4:])
        self.assertEqual(a[:10], b[:10])
        for r in b:
            self.assertEqual(len(ANSI.sub("", r)), 100)
        small = self.eng.ansi_rows(30, 8, 2.0, "plasma", clock=True)  # tela pequena: sem relogio, sem erro
        self.assertEqual(len(small), 8)

    def test_playlist_clock_cycle_commands(self):
        self.assertEqual(self.sh.run("playlist fire tunnel").lines[0][0], "ok")
        self.assertEqual(self.sh.run("playlist nada").lines[0][0], "err")
        self.sh.run("clock on")
        self.sh.run("cycle 30")
        c2 = Config(self.cfg.path)
        self.assertEqual(c2.data["saver"]["playlist"], ["fire", "tunnel"])
        self.assertTrue(c2.data["saver"]["clock"])
        self.assertEqual(c2.data["saver"]["cycle_seconds"], 30.0)
        self.sh.run("playlist all")
        self.assertEqual(len(self.cfg.data["saver"]["playlist"]), len(ARTS))
        self.sh.run("playlist clear")
        self.assertEqual(self.cfg.data["saver"]["playlist"], [])

    def test_doctor_and_new_arts(self):
        lines = self.sh.run("doctor").lines
        self.assertTrue(any("janela do terminal" in t for _, t in lines))
        self.assertIn("fire", ARTS)
        self.assertIn("tunnel", ARTS)

    def test_saver_app_rows_use_playlist_art(self):
        self.sh.run("playlist fire")
        rows = self.eng.ansi_rows(80, 24, 1.0, "fire")
        self.assertEqual(len(rows), 24)


class V04(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.cfg = Config(os.path.join(self.d, "c.json"))
        self.eng = Engine(self.cfg)
        self.sh = Shell(self.cfg, self.eng)

    def test_new_themes_present(self):
        th = self.cfg.themes()
        for n in ("crimson", "blush", "rosewhip", "ruby", "midnight", "gold", "lavender", "tangerine", "forest", "ocean", "cyberpunk"):
            self.assertIn(n, th)
        r, g, b = parse_color(th["crimson"]["colors"][0])[0]
        self.assertTrue(r > 200 and g < 40)
        self.assertEqual(parse_color(th["crimson"]["colors"][1])[0], (255, 255, 255))
        self.assertEqual(parse_color(th["blush"]["colors"][1])[0], (255, 255, 255))
        for n in ("crimson", "blush", "rosewhip"):  # fundo grafite escuro
            bg = parse_color(th[n]["background"])[0]
            self.assertTrue(max(bg) < 50)
        self.assertTrue(self.sh.run("theme rosewhip").lines[0][0] == "ok")

    def test_removed_art_in_old_config_falls_back(self):
        self.cfg.data["art"] = "romantic"
        self.cfg.data["saver"]["playlist"] = ["romantic", "fire"]
        self.cfg.save()
        c2 = Config(self.cfg.path)
        self.assertEqual(c2.data["art"], "blackhole")
        self.assertNotIn("romantic", ARTS)
        Engine(c2).ansi_rows(40, 12, 1.0)  # nao quebra

    def test_exporter_has_symbol_glyphs(self):
        from rest.export import GLYPHS
        for ch in "()/\\|^v&":
            self.assertIn(ch, GLYPHS)


class V05(unittest.TestCase):
    ANSI_ALL = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

    def _app(self, W, H, focus="nav"):
        from rest.app import App
        cfg = Config(os.path.join(tempfile.mkdtemp(), "c.json"))
        eng = Engine(cfg)
        app = App(cfg, eng)
        app.W, app.H, app.focus = W, H, focus
        return app, eng

    def test_layout_exact_size_everywhere(self):
        sizes = [(w, h) for w in (1, 10, 30, 43, 44, 60, 83, 84, 111, 112, 200, 320)
                 for h in (1, 3, 5, 11, 12, 16, 22, 28, 32, 60)]
        for focus in ("nav", "term"):
            for W, H in sizes:
                app, eng = self._app(W, H, focus)
                app.run_line("help")
                app.buf, app.cur, app.scroll = "x" * 300, 300, 99
                rows = app.compose()
                self.assertEqual(len(rows), H, (W, H, focus))
                self.assertEqual({len(self.ANSI_ALL.sub("", r)) for r in rows}, {W}, (W, H, focus))
                self.assertIsNone(eng.new_error, (W, H))

    def test_breakpoints(self):
        for W, expect in ((120, 3), (90, 2), (60, 1)):
            app, _ = self._app(W, 30)
            L, R, hb = app.layout()
            self.assertEqual(1 + (L > 0) + (R > 0), expect, W)
        app, _ = self._app(40, 10)
        txt = "\n".join(self.ANSI_ALL.sub("", r) for r in app.compose())
        self.assertNotIn("Preview", txt)  # modo compacto: sem paineis

    def test_terminal_output_wraps_to_pane(self):
        app, _ = self._app(60, 20)
        app.say("out", "palavra " * 40)
        lines = app.term_lines(30)
        self.assertGreater(len(lines), 5)
        self.assertTrue(all(len(t) <= 30 for _, t in lines))

    def test_footer_adapts_to_width(self):
        app, _ = self._app(100, 30)
        for w in (12, 25, 40, 80, 120):
            plain = self.ANSI_ALL.sub("", app.footer_bar(w))
            self.assertEqual(len(plain), w)
        self.assertIn("sair", self.ANSI_ALL.sub("", app.footer_bar(30)))
        self.assertIn("velocidade", self.ANSI_ALL.sub("", app.footer_bar(120)))

    def test_all_arts_tiny_sizes(self):
        cfg = Config(os.path.join(tempfile.mkdtemp(), "c.json"))
        for name in ARTS:
            for w, h in ((1, 1), (2, 1), (1, 3), (5, 2), (10, 3), (44, 10)):
                eng = Engine(cfg)
                rows = eng.ansi_rows(w, h, 2.0, name, clock=True)
                self.assertEqual(len(rows), h)
                self.assertIsNone(eng.new_error, (name, w, h))


class V06(unittest.TestCase):
    ROOT = os.path.join(os.path.dirname(__file__), "..")

    def _inst(self):
        sys.path.insert(0, self.ROOT)
        import installer
        return installer

    def test_dry_run_prints_banner_and_reaches_100(self):
        import subprocess
        env = dict(os.environ, REST_DRY_SCALE="0.05")
        p = subprocess.run([sys.executable, os.path.join(self.ROOT, "installer.py"), "--dry-run", "--no-color"],
                           capture_output=True, text=True, env=env, cwd=self.ROOT, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(r"|_| \_\_____|____/ |_|", p.stdout)
        self.assertIn("100%", p.stdout)
        self.assertIn("[5/5]", p.stdout)

    def test_bar_gradient_orange_pink_purple(self):
        inst = self._inst()
        from rest.colors import fg
        ui = inst.UI(True, 100)
        full = ui.bar(1.0)
        self.assertIn(fg(inst.ORANGE) + "\u2588", full)       # comeca laranja
        self.assertIn(fg(inst.PURPLE) + "\u2588", full)       # termina roxo
        mid = ANSI.sub("", "")  # (so para manter o import usado)
        cols = [tuple(int(x) for x in m.groups()) for m in re.finditer(r"38;2;(\d+);(\d+);(\d+)m\u2588", full)]
        r, g, b = cols[len(cols) // 2]
        self.assertTrue(r > 230 and b > 100 and g < 100, cols[len(cols) // 2])   # meio rosa
        self.assertNotIn("\u2588", ui.bar(0.0))
        self.assertEqual(ui.bar(0.5).count("\u2588"), round(ui.bw * 0.5))

    def test_failure_is_reported_and_stops(self):
        import io
        import contextlib
        inst = self._inst()
        ui = inst.UI(False, 100)
        args = type("A", (), dict(dry_run=False, skip_tests=True))()
        ins = inst.Installer(args, ui)
        ins.log_path = os.path.join(tempfile.mkdtemp(), "build.log")
        ins.steps = [("Etapa boa", 1, 1, lambda: (True, ""), False),
                     ("Etapa ruim", 1, 1, [sys.executable, "-c", "print('boom'); import sys; sys.exit(3)"], False),
                     ("Nunca roda", 1, 1, lambda: (True, ""), False)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ins.run()
        out = buf.getvalue()
        self.assertEqual(rc, 1)
        self.assertIn("falhou", out)
        self.assertIn("boom", out)
        self.assertNotIn("Nunca roda", out)


class V061(unittest.TestCase):
    ROOT = os.path.join(os.path.dirname(__file__), "..")

    def _run(self, soft):
        import contextlib
        import io
        sys.path.insert(0, self.ROOT)
        import installer
        ins = installer.Installer(type("A", (), dict(dry_run=False, skip_tests=True))(), installer.UI(False, 100))
        ins.log_path = os.path.join(tempfile.mkdtemp(), "build.log")
        ins.steps = [("Rodando os testes", 1, 1, [sys.executable, "-c", "import sys; print('falhou'); sys.exit(1)"], soft),
                     ("Compilando", 1, 1, lambda: (True, ""), False)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ins.run()
        return rc, buf.getvalue()

    def test_soft_failure_is_a_warning_and_build_continues(self):
        rc, out = self._run(True)
        self.assertEqual(rc, 0)
        self.assertIn("avisos", out)
        self.assertIn("[2/2]", out)

    def test_strict_failure_still_stops(self):
        rc, out = self._run(False)
        self.assertEqual(rc, 1)
        self.assertNotIn("[2/2]", out)

    def test_no_editor_env_is_respected(self):
        from rest import system
        self.assertIn("manualmente", system.open_in_editor(os.path.join(tempfile.mkdtemp(), "x.txt")))


if __name__ == "__main__":
    unittest.main()
