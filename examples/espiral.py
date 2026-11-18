"""Exemplo de plugin: tunel em espiral. Importe com:  import examples/espiral.py"""
from math import atan2, hypot, log, sin

from rest.arts import Art


class Espiral(Art):
    name = "espiral"
    desc = "Tunel em espiral hipnotico (exemplo de plugin)."
    defaults = dict(speed=1.0, arms=5, twist=2.0)
    ranges = dict(speed=(0.1, 5.0), arms=(1, 12), twist=(0.2, 6.0))

    def compute(self, w, h, t, p):
        br = [0.0] * (w * h)
        ph = [0.0] * (w * h)
        for j in range(h):
            y = (j + 0.5 - h / 2) / (h / 2)
            for i in range(w):
                x = (i + 0.5 - w / 2) * 0.5 / (h / 2)
                r = hypot(x, y) + 0.02
                v = 0.5 + 0.5 * sin(p["arms"] * atan2(y, x) + p["twist"] * log(r) * 3 - t * p["speed"] * 2.5)
                k = j * w + i
                br[k] = v ** 1.5 * min(1.0, r * 2.0)
                ph[k] = log(r) * 0.15 + v * 0.2
        return br, ph, None
