#!/usr/bin/env python3
"""
Builds the artwork for profile/README.md.

GitHub strips CSS from READMEs, so every designed section is an SVG with
light and dark variants. Text is set in Inter / Inter Display, subset and
embedded per file, so it renders the same everywhere.

    pip install fonttools brotli
    python design/build.py <path-to-inter-ttf-folder>

The font folder is `extras/ttf` from https://github.com/rsms/inter/releases.
Output goes to profile/media/.
"""

import base64
import io
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset as ftsubset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "profile" / "media"
FONT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "fonts"

W = 1200

# ── Type ─────────────────────────────────────────────────────────────────────

FACES = {
    "display": ("InterDisplay-Bold.ttf", "AxDisplay", 700),
    "display-semi": ("InterDisplay-SemiBold.ttf", "AxDisplaySemi", 600),
    "text": ("Inter-Regular.ttf", "AxText", 400),
    "text-semi": ("Inter-SemiBold.ttf", "AxTextSemi", 600),
}
FALLBACK = "-apple-system,BlinkMacSystemFont,'SF Pro Display','Helvetica Neue',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,'SF Mono',SFMono-Regular,'Cascadia Code',Menlo,Consolas,monospace"


class Face:
    def __init__(self, file):
        self.path = FONT_DIR / file
        font = TTFont(self.path)
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"]
        self.upm = font["head"].unitsPerEm

    def width(self, s, size):
        adv = sum(self.hmtx[self.cmap.get(ord(c), ".notdef")][0] for c in s)
        return adv * size / self.upm + tracking(size) * size * len(s)


def tracking(size):
    """Inter's dynamic metrics: tighter as type gets larger (em)."""
    return -0.0223 + 0.185 * math.exp(-0.1745 * size)


FONTS = {k: Face(v[0]) for k, v in FACES.items()}


def wrap(s, face, size, max_w):
    lines, line = [], ""
    for word in s.split():
        trial = f"{line} {word}".strip()
        if line and FONTS[face].width(trial, size) > max_w:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


# ── Themes ───────────────────────────────────────────────────────────────────

THEMES = {
    "light": dict(
        text="#1d1d1f", text2="#6e6e73", text3="#86868b", accent="#0071e3",
        canvas="#fbfbfd", tile="#f5f5f7", hair="#d2d2d7", line="#c7c7cc",
        node="#ffffff", node_stroke="#e8e8ed", hub="#1d1d1f", hub_fg="#ffffff",
        term="#1d1d1f", term_stroke="none", green="#28cd41", aura=0.28,
        shadow=True,
    ),
    "dark": dict(
        text="#f5f5f7", text2="#a1a1a6", text3="#6e6e73", accent="#2997ff",
        canvas="#000000", tile="#141416", hair="#2c2c2e", line="#48484a",
        node="#1c1c1e", node_stroke="#2c2c2e", hub="#f5f5f7", hub_fg="#000000",
        term="#0a0a0a", term_stroke="#2c2c2e", green="#30d158", aura=0.55,
        shadow=False,
    ),
}

SPECTRUM = ["#0090f7", "#ba62fc", "#f2416b", "#f55600"]
GLOW = ["#2997ff", "#bf5af2", "#ff375f", "#ff9f0a", "#64d2ff"]


# ── SVG document ─────────────────────────────────────────────────────────────

class Svg:
    def __init__(self, h, title, t):
        self.h, self.title, self.t = h, title, t
        self.defs, self.body, self.css = [], [], []
        self.used = {k: set() for k in FACES}

    def add(self, *parts):
        self.body.extend(parts)

    def text(self, s, x, y, face="text", size=22, fill=None, anchor="start", attrs=""):
        self.used[face].update(s)
        fill = fill or self.t["text"]
        self.body.append(
            f'<text x="{x:.1f}" y="{y:.1f}" class="{face}" font-size="{size}" '
            f'letter-spacing="{tracking(size) * size:.2f}" fill="{fill}" '
            f'text-anchor="{anchor}"{attrs}>{escape(s)}</text>'
        )

    def gradient(self, gid, stops, x2=1, y2=0):
        s = "".join(f'<stop offset="{i / (len(stops) - 1):.3f}" stop-color="{c}"/>' for i, c in enumerate(stops))
        self.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">{s}</linearGradient>')

    def fonts_css(self):
        css = []
        for key, (file, family, weight) in FACES.items():
            if not self.used[key]:
                continue
            opts = ftsubset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["kern", "liga", "calt", "case"]
            opts.hinting = False
            opts.name_IDs = []
            font = ftsubset.load_font(str(FONTS[key].path), opts)
            sub = ftsubset.Subsetter(opts)
            sub.populate(text="".join(sorted(self.used[key])) + " ")
            sub.subset(font)
            buf = io.BytesIO()
            ftsubset.save_font(font, buf, opts)
            b64 = base64.b64encode(buf.getvalue()).decode()
            css.append(f"@font-face{{font-family:'{family}';font-weight:{weight};"
                       f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
            css.append(f".{key}{{font-family:'{family}',{FALLBACK};font-weight:{weight}}}")
        return "".join(css)

    def render(self):
        css = (self.fonts_css() + f".mono{{font-family:{MONO}}}" + "".join(self.css)
               + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" '
            f'viewBox="0 0 {W} {self.h}" role="img" aria-label="{escape(self.title)}" fill="none">'
            f"<title>{escape(self.title)}</title><style>{css}</style>"
            f'<defs>{"".join(self.defs)}</defs>{"".join(self.body)}</svg>'
        )


def logo(x, y, size, fill):
    """The Artex mark, redrawn as vectors from the 500×500 master (bbox 10,30 → 488,471)."""
    s = size / 478
    return (
        f'<g transform="translate({x - 10 * s:.2f} {y - 30 * s:.2f}) scale({s:.4f})" fill="{fill}">'
        '<circle cx="251" cy="127" r="97"/><circle cx="107" cy="358" r="97"/>'
        '<circle cx="392" cy="375" r="96"/>'
        '<path d="M154 127V175C154 215 78 249 38 289L107 358H204V310C204 270 280 236 320 196L251 127Z"/>'
        "</g>"
    )


# ── Sections ─────────────────────────────────────────────────────────────────

def hero(t):
    H = 570
    svg = Svg(H, "artex software. Precision, engineered. Systems and software, designed with intention and built to last.", t)
    cx, cy = W / 2, 330

    for i, c in enumerate(GLOW):
        svg.defs.append(f'<radialGradient id="g{i}"><stop offset="0" stop-color="{c}"/>'
                        f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
    # Frameless aura: an eased radial falloff, so the colour has no edges at all.
    fade = "".join(f'<stop offset="{o}" stop-color="#fff" stop-opacity="{a}"/>'
                   for o, a in [(0, 1), (.2, .84), (.4, .54), (.6, .25), (.8, .07), (.92, .015), (1, 0)])
    svg.defs.append(
        f'<radialGradient id="fade">{fade}</radialGradient>'
        f'<mask id="aura" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">'
        f'<ellipse cx="{cx}" cy="{cy}" rx="{W / 2}" ry="{H / 2}" fill="url(#fade)"/></mask>'
    )
    svg.gradient("spectrum", SPECTRUM)

    svg.css.append(f".spin{{transform-origin:{cx}px {cy}px;animation:spin 16s linear infinite}}"
                   "@keyframes spin{to{transform:rotate(360deg)}}")
    blobs = "".join(
        f'<circle cx="{cx + 300 * math.cos(2 * math.pi * i / len(GLOW)):.0f}" '
        f'cy="{cy + 170 * math.sin(2 * math.pi * i / len(GLOW)):.0f}" r="360" fill="url(#g{i})"/>'
        for i in range(len(GLOW))
    )

    svg.add(
        f'<g mask="url(#aura)" opacity="{t["aura"]}"><g class="spin">{blobs}</g></g>',
        logo(cx - 30, 64, 60, t["text"]),
    )
    svg.text("artex software", cx, 196, "text-semi", 28, t["text2"], "middle")
    svg.text("Precision,", cx, 316, "display", 120, t["text"], "middle")
    svg.text("engineered.", cx, 438, "display", 120, "url(#spectrum)", "middle")
    svg.text("Systems and software, designed with intention and built to last.", cx, 524, "text", 28, t["text2"], "middle")
    return svg


def statement(t):
    H = 330
    svg = Svg(H, "The best software disappears. It just works. Quietly, flawlessly, at scale. "
                 "We obsess over the details you’ll never notice, so everything you do notice simply feels right.", t)
    svg.text("The best software disappears.", W / 2, 80, "display", 64, t["text"], "middle")
    svg.text("It just works.", W / 2, 154, "display", 64, t["text3"], "middle")
    body = ("Quietly, flawlessly, at scale. We obsess over the details you’ll never "
            "notice, so everything you do notice simply feels right.")
    for i, line in enumerate(wrap(body, "text", 26, 760)):
        svg.text(line, W / 2, 236 + i * 38, "text", 26, t["text2"], "middle")
    return svg


def tile(svg, x, y, w, h):
    t = svg.t
    stroke = "" if t["shadow"] else f' stroke="{t["hair"]}" stroke-opacity=".6"'
    svg.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="30" fill="{t["tile"]}"{stroke}/>')


def bento(t):
    H = 1350
    svg = Svg(H, "What we build. Systems: servers that set themselves up. Libraries: PSR-3 and PSR-11, "
                 "lightweight standards-compliant PHP. Developer tools: made for the command line. "
                 "Products: designed, built and run under one roof.", t)
    svg.gradient("spectrum", SPECTRUM)
    svg.gradient("spectrumV", SPECTRUM, x2=1, y2=1)
    if t["shadow"]:
        svg.defs.append('<filter id="lift" x="-20%" y="-40%" width="140%" height="200%">'
                        '<feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000" flood-opacity=".07"/></filter>')
    svg.css.append(
        ".flow{stroke-dasharray:2 9;animation:flow 1.6s linear infinite}@keyframes flow{to{stroke-dashoffset:-22}}"
        ".ping{transform-box:fill-box;transform-origin:center;animation:ping 2.4s ease-out infinite}"
        "@keyframes ping{0%{transform:scale(1);opacity:.55}80%,100%{transform:scale(3.2);opacity:0}}"
        ".type{animation:type .5s ease-out both}@keyframes type{from{opacity:0;transform:translateY(6px)}}"
        ".caret{animation:caret 1.1s steps(1) infinite}@keyframes caret{50%{opacity:0}}"
        ".ring{animation:ring 1.8s cubic-bezier(.2,.8,.2,1) both}"
    )

    svg.text("What we build.", W / 2, 72, "display", 64, t["text"], "middle")

    # Systems ─ full width, network visual on the right
    y = 130
    tile(svg, 0, y, W, 380)
    svg.text("Systems", 56, y + 84, "text-semi", 22, t["accent"])
    svg.text("Servers that", 56, y + 148, "display", 50, t["text"])
    svg.text("set themselves up.", 56, y + 206, "display", 50, t["text"])
    for i, line in enumerate(wrap("Provisioning, hardening and environment setup, automated end to end — "
                                  "so every machine starts life production‑ready.", "text", 22, 470)):
        svg.text(line, 56, y + 262 + i * 32, "text", 22, t["text2"])

    hx, hy = 880, y + 190
    nodes = ["edge‑01", "api‑02", "auth‑01", "db‑primary", "cache‑01", "queue‑01"]
    pts = [(hx + 215 * math.cos(math.radians(a)), hy + 122 * math.sin(math.radians(a)))
           for a in (-150, -90, -30, 30, 90, 150)]
    for px, py in pts:
        svg.add(f'<line x1="{hx}" y1="{hy}" x2="{px:.1f}" y2="{py:.1f}" stroke="{t["line"]}" '
                f'stroke-width="2" stroke-linecap="round" class="flow"/>')
    lift = ' filter="url(#lift)"' if t["shadow"] else ""
    for i, ((px, py), name) in enumerate(zip(pts, nodes)):
        pw, ph = 156, 46
        x0, y0 = px - pw / 2, py - ph / 2
        svg.add(f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{pw}" height="{ph}" rx="23" fill="{t["node"]}" '
                f'stroke="{t["node_stroke"]}"{lift}/>',
                f'<circle cx="{x0 + 24:.1f}" cy="{py:.1f}" r="5" fill="{t["green"]}" class="ping" '
                f'style="animation-delay:{i * 0.4:.1f}s"/>',
                f'<circle cx="{x0 + 24:.1f}" cy="{py:.1f}" r="5" fill="{t["green"]}"/>')
        svg.text(name, x0 + 40, py + 6, "text-semi", 16, t["text"])
    svg.add(f'<rect x="{hx - 50}" y="{hy - 50}" width="100" height="100" rx="26" fill="{t["hub"]}"{lift}/>',
            logo(hx - 24, hy - 22, 48, t["hub_fg"]))

    # Libraries ─ pure type
    y = 530
    tile(svg, 0, y, 590, 420)
    svg.text("Libraries", 56, y + 84, "text-semi", 22, t["accent"])
    svg.text("PSR‑3.", 52, y + 196, "display", 104, "url(#spectrum)")
    svg.text("PSR‑11.", 52, y + 300, "display", 104, "url(#spectrum)")
    for i, line in enumerate(wrap("Lightweight, standards‑compliant PHP for logging, "
                                  "dependency injection and debugging.", "text", 22, 470)):
        svg.text(line, 56, y + 350 + i * 32, "text", 22, t["text2"])

    # Developer tools ─ terminal
    x = 610
    tile(svg, x, y, 590, 420)
    svg.text("Developer tools", x + 56, y + 84, "text-semi", 22, t["accent"])
    svg.text("Made for the", x + 56, y + 142, "display", 44, t["text"])
    svg.text("command line.", x + 56, y + 194, "display", 44, t["text"])
    tx, ty, tw, th = x + 56, y + 228, 478, 152
    stroke = f' stroke="{t["term_stroke"]}"' if t["term_stroke"] != "none" else ""
    svg.add(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="14" fill="{t["term"]}"{stroke}/>')
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        svg.add(f'<circle cx="{tx + 22 + i * 20}" cy="{ty + 20}" r="6" fill="{c}"/>')
    rows = [("$", "artex new aurora"), ("✓", "Project scaffolded"), ("✓", "Ready. Ship something great."), ("$", "")]
    for i, (glyph, cmd) in enumerate(rows):
        ly = ty + 64 + i * 26
        delay = f' style="animation-delay:{0.3 + i * 0.6:.1f}s"'
        g = [f'<g class="type"{delay}>']
        if glyph == "$":
            g.append(f'<text x="{tx + 22}" y="{ly}" class="mono" font-size="16" fill="#8e8e93">$</text>')
        else:
            g.append(f'<path d="M{tx + 22} {ly - 5}l4 4 8-9" stroke="#30d158" stroke-width="2.2" '
                     'stroke-linecap="round" stroke-linejoin="round"/>')
        if cmd:
            col = "#f5f5f7" if glyph == "$" else "#a1a1a6"
            g.append(f'<text x="{tx + 42}" y="{ly}" class="mono" font-size="16" fill="{col}">{escape(cmd)}</text>')
        else:
            g.append(f'<rect x="{tx + 42}" y="{ly - 14}" width="9" height="18" rx="1.5" fill="#f5f5f7" class="caret"/>')
        g.append("</g>")
        svg.add(*g)

    # Products ─ rings on the left, copy on the right
    y = 970
    tile(svg, 0, y, W, 380)
    rcx, rcy = 250, y + 190
    rings = [(132, "#f2416b", "Design"), (100, "#ba62fc", "Engineering"), (68, "#0090f7", "Operations")]
    for i, (r, c, _) in enumerate(rings):
        circ = 2 * math.pi * r
        svg.css.append(f".r{i}{{stroke-dasharray:{circ:.1f};animation-delay:{0.2 + i * 0.18:.2f}s}}")
        svg.add(f'<circle cx="{rcx}" cy="{rcy}" r="{r}" stroke="{c}" stroke-opacity=".18" stroke-width="26"/>',
                f'<circle cx="{rcx}" cy="{rcy}" r="{r}" stroke="{c}" stroke-width="26" stroke-linecap="round" '
                f'class="ring r{i}" transform="rotate(-90 {rcx} {rcy})"/>')
        svg.css.append(f"@keyframes ring{i}{{from{{stroke-dashoffset:{circ:.1f}}}}}.r{i}{{animation-name:ring{i}}}")

    x = 480
    svg.text("Products", x, y + 84, "text-semi", 22, t["accent"])
    svg.text("Designed, built and run.", x, y + 148, "display", 50, t["text"])
    svg.text("Under one roof.", x, y + 206, "display", 50, t["text3"])
    for i, line in enumerate(wrap("End‑to‑end products, from the first sketch to the final deploy — "
                                  "crafted by one team that sweats every detail.", "text", 22, 640)):
        svg.text(line, x, y + 262 + i * 32, "text", 22, t["text2"])
    lx = x
    for r, c, label in rings:
        svg.add(f'<circle cx="{lx + 6}" cy="{y + 334}" r="6" fill="{c}"/>')
        svg.text(label, lx + 20, y + 340, "text-semi", 17, t["text2"])
        lx += 20 + FONTS["text-semi"].width(label, 17) + 32
    return svg


ICONS = {
    # 56×56 glyphs drawn in the spirit of SF Symbols.
    "considered": '<circle cx="28" cy="28" r="20" stroke-width="3.5"/><circle cx="28" cy="28" r="6" stroke="none" fill="url(#ic{i})"/>'
                  '<path d="M28 2v10M28 44v10M2 28h10M44 28h10" stroke-width="3.5" stroke-linecap="round"/>',
    "fast": '<path d="M31 3 9 32h17l-3 21 24-31H29l2-19Z" stroke="none" fill="url(#ic{i})"/>',
    "lasting": '<path d="M28 4 8 11v15c0 13 8.5 22.5 20 26 11.5-3.5 20-13 20-26V11L28 4Z" stroke-width="3.5" stroke-linejoin="round"/>'
               '<path d="m19 28 6.5 6.5L38 22" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>',
}


def principles(t):
    H = 420
    items = [
        ("considered", "Considered.", "Every detail is deliberate. If it doesn’t earn its place, it doesn’t ship."),
        ("fast", "Fast by default.", "Performance isn’t a feature we add later. It’s the foundation we start from."),
        ("lasting", "Built to last.", "Clean interfaces, durable architecture and code that ages gracefully."),
    ]
    svg = Svg(H, "How we work. " + " ".join(f"{a} {b}" for _, a, b in items), t)
    svg.text("How we work.", W / 2, 72, "display", 64, t["text"], "middle")
    pairs = [("#0090f7", "#5ac8fa"), ("#ba62fc", "#f2416b"), ("#30d158", "#0090f7")]
    for i, ((icon, title, body), (c1, c2)) in enumerate(zip(items, pairs)):
        x = 48 + i * 392
        svg.gradient(f"ic{i}", [c1, c2], x2=1, y2=1)
        svg.add(f'<g transform="translate({x} 150)" stroke="url(#ic{i})" fill="none">{ICONS[icon].format(i=i)}</g>')
        svg.text(title, x, 262, "display", 32, t["text"])
        for j, line in enumerate(wrap(body, "text", 21, 320)):
            svg.text(line, x, 306 + j * 31, "text", 21, t["text2"])
    return svg


def stack(t):
    H = 170
    words = ["Rust", "PHP", "C", "TypeScript", "SQL", "Shell", "Linux"]
    svg = Svg(H, "Fluent in " + ", ".join(words) + ".", t)
    svg.text("Fluent in", W / 2, 34, "text-semi", 22, t["text2"], "middle")
    size, gap = 46, 54
    widths = [FONTS["display-semi"].width(w, size) for w in words]
    x = (W - sum(widths) - gap * (len(words) - 1)) / 2
    mask = []
    for word, w in zip(words, widths):
        mask.append(f'<text x="{x:.1f}" y="118" class="display-semi" font-size="{size}" '
                    f'letter-spacing="{tracking(size) * size:.2f}" fill="#fff">{word}</text>')
        svg.used["display-semi"].update(word)
        x += w + gap
    svg.defs.append(f'<mask id="words" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{H}">{"".join(mask)}</mask>')
    sheen = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in
                    [(0, "#0090f7", 0), (.3, "#0090f7", 1), (.5, "#ba62fc", 1), (.7, "#f2416b", 1), (1, "#f2416b", 0)])
    svg.defs.append(f'<linearGradient id="sheen">{sheen}</linearGradient>')
    svg.css.append(".sheen{animation:sheen 7s cubic-bezier(.45,0,.25,1) infinite}"
                   "@keyframes sheen{from{transform:translateX(-520px)}65%,to{transform:translateX(1720px)}}")
    svg.add('<g mask="url(#words)">',
            f'<rect width="{W}" height="{H}" fill="{t["text3"]}"/>',
            f'<rect width="520" height="{H}" fill="url(#sheen)" class="sheen" style="animation-delay:1s"/>',
            "</g>")
    return svg


def footer(t):
    H = 190
    svg = Svg(H, "Designed and engineered by Artex. © 2026 Artex Software. All rights reserved.", t)
    svg.add(f'<rect x="0" y="0" width="{W}" height="1" fill="{t["hair"]}"/>',
            logo(W / 2 - 18, 52, 36, t["text"]))
    svg.text("Designed and engineered by Artex.", W / 2, 140, "text-semi", 22, t["text2"], "middle")
    svg.text("© 2026 Artex Software. All rights reserved.", W / 2, 172, "text", 17, t["text3"], "middle")
    return svg


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in [("hero", hero), ("statement", statement), ("bento", bento),
                        ("principles", principles), ("stack", stack), ("footer", footer)]:
        for theme, t in THEMES.items():
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(build(t).render(), encoding="utf-8")
            print(f"{path.relative_to(HERE.parent)}  {path.stat().st_size / 1024:.1f} KB")
