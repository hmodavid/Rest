"""Tipos de texto ASCII (rampas do mais apagado ao mais denso)."""
PRESETS = {
    "classic": " .:-=+*#%@",
    "dense": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "blocks": " \u2591\u2592\u2593\u2588",
    "dots": " \u00b7\u2219\u2022\u25cf",
    "binary": " 01",
    "braille": " \u2801\u2803\u2807\u2847\u2867\u28b7\u28ff",
    "stars": " .,'+*x",
    "hex": " .:0123456789ABCDEF",
}


def resolve(name_or_text: str) -> str:
    s = str(name_or_text)
    if s in PRESETS:
        return PRESETS[s]
    if len(s.strip()) < 1:
        return PRESETS["classic"]
    if not s.startswith(" "):
        s = " " + s
    return s
