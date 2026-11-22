"""Build the profile page: the hero poster, one cover per project and README.md.

Everything on the page comes from `_src/projects.json`. To add, remove or reorder a
project, edit that file and run from the repo root:

    python -I _src/build.py            # hero + covers + README
    python -I _src/build.py --readme   # README only (no downloads)

Needs Pillow, fontTools and brotli. Fonts are downloaded into
`_src/cache/` (ignored by git) from Google Fonts.

The look: black posters where every picture is a halftone of small glowing glyphs.
- Each tool has an object, a photograph on black in `_src/art/<repo>.webp`.
- A picture is shrunk until one pixel is one grid cell. Cells are sorted by brightness
  into four layers, each shown through a mask tiled with its own glyph: a dot, a small
  plus, a plus, and a plus whose arms reach its neighbours. The brightest cells sparkle.
- The hero is a display that shows the objects in turn; a cover shows its own.
- A README cannot run scripts or CSS, but an SVG shown through <img> plays its own
  CSS animations. Every file is self-contained: fonts and pixels are inlined.
"""
import base64
import io
import json
import math
import pathlib
import random
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "_src"
CACHE = SRC / "cache"
OUT = ROOT / "assets"
DATA = json.loads((SRC / "projects.json").read_text(encoding="utf-8"))
OWNER = DATA["owner"]
PROJECTS = DATA["projects"]

FONT_URLS = {
    "Inter.ttf": "ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
    "InstrumentSerif-Italic.ttf": "ofl/instrumentserif/InstrumentSerif-Italic.ttf",
}

BG = "#0B0B0B"       # the poster
INK = "#F5F3EE"
MUTED = "#9C9A94"
FAINT = "#6A6863"
LINE = "#FFFFFF1F"

W = 1200
HERO_H = 866
COVER_H = 420
SLOT = 4.2           # seconds each object stays on the hero's display
LOOP_START = 0.5     # seconds before the first object appears
SERIF_SCALE = 1.16   # the italic serif is set larger so it matches the sans in height

FAMILIES = {
    "sans": "'AF Display','Inter','Helvetica Neue',Helvetica,Arial,system-ui,sans-serif",
    "text": "'AF Text','Inter','Helvetica Neue',Helvetica,Arial,system-ui,sans-serif",
    "serif": "'AF Serif','Instrument Serif',Georgia,'Times New Roman',serif",
}
FONTS = {  # role -> (file, variable axes or None, CSS weight)
    "sans": ("Inter.ttf", {"opsz": 32, "wght": 500}, 500),
    "text": ("Inter.ttf", {"opsz": 16, "wght": 450}, 450),
    "serif": ("InstrumentSerif-Italic.ttf", None, 400),
}


# ---------------------------------------------------------------- downloads

def fetch(url: str, dest: pathlib.Path) -> pathlib.Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "profile-build"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
    return dest


# -------------------------------------------------------------------- fonts

_FONT_BYTES: dict = {}
_METRICS: dict = {}


def font_bytes(role: str) -> bytes:
    """The font file for a role, pinned to one weight and optical size."""
    if role not in _FONT_BYTES:
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
        name, axes, _ = FONTS[role]
        path = fetch("https://raw.githubusercontent.com/google/fonts/main/" + FONT_URLS[name],
                     CACHE / "fonts" / name)
        font = TTFont(path)
        if axes:
            font = instancer.instantiateVariableFont(font, axes)
        buf = io.BytesIO()
        font.save(buf)
        _FONT_BYTES[role] = buf.getvalue()
    return _FONT_BYTES[role]


def font_faces(used: dict) -> str:
    """@font-face rules holding only the glyphs each role needs. `used`: role -> text."""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    css = []
    for role, text in used.items():
        if not text:
            continue
        font = TTFont(io.BytesIO(font_bytes(role)))
        opts = subset.Options()
        opts.layout_features = ["kern", "liga", "calt", "ccmp", "locl", "mark", "mkmk"]
        opts.name_IDs = [1, 2]
        opts.notdef_outline = True
        opts.desubroutinize = True
        sub = subset.Subsetter(opts)
        sub.populate(text=text + " ")
        sub.subset(font)
        font.flavor = "woff2"
        buf = io.BytesIO()
        font.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        family = FAMILIES[role].split(",")[0]
        css.append(f"@font-face{{font-family:{family};font-weight:{FONTS[role][2]};"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css)


def text_width(role: str, text: str, size: float, tracking: float = 0.0) -> float:
    """Width of `text` in SVG units (kerning ignored, which is close enough to fit a line)."""
    if role not in _METRICS:
        from fontTools.ttLib import TTFont
        font = TTFont(io.BytesIO(font_bytes(role)))
        _METRICS[role] = (font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm)
    cmap, hmtx, upm = _METRICS[role]
    units = sum(hmtx[cmap.get(ord(ch), ".notdef")][0] for ch in text)
    return units / upm * size + tracking * size * len(text)


def rich_lines(text: str, size: float, width: float) -> list:
    """Wrap a sentence where *stars* mark the words set in italic serif.

    Returns lines; a line is a list of (role, text) runs.
    """
    words = []   # (role, word, glued to the word before it)
    for i, part in enumerate(text.split("*")):
        role = "serif" if i % 2 else "sans"
        for j, w in enumerate(part.split()):
            words.append((role, w, bool(words) and j == 0 and not part[:1].isspace() and i % 2 == 0))
    space = text_width("sans", " ", size, -0.04)
    lines, cur, used = [], [], 0.0
    for role, word, glued in words:
        w = (text_width("serif", word, size * SERIF_SCALE, -0.01) if role == "serif"
             else text_width("sans", word, size, -0.04))
        if cur and not glued and used + space + w > width:
            lines.append(cur)
            cur, used = [], 0.0
        used += (space if cur and not glued else 0) + w
        cur.append((role, word, glued))
    lines.append(cur)
    out = []
    for line in lines:  # join neighbouring words of one role into a run
        runs = []
        for k, (role, word, glued) in enumerate(line):
            lead = "" if (k == 0 or glued) else " "
            if runs and runs[-1][0] == role:
                runs[-1] = (role, runs[-1][1] + lead + word)
            else:
                runs.append((role, lead + word))
        out.append(runs)
    return out


def rich_text(lines: list, x: float, y: float, leading: float, cls: str, delay: float) -> str:
    out = []
    for i, runs in enumerate(lines):
        spans = []
        for role, text in runs:
            if role == "serif":
                # the space before an italic word is set in the sans, so it keeps its width
                lead = " " if text.startswith(" ") else ""
                spans.append((f"<tspan>{lead}</tspan>" if lead else "")
                             + f'<tspan class="serif acc">{esc(text.strip())}</tspan>')
            else:
                spans.append(f'<tspan>{esc(text)}</tspan>')
        out.append(f'<text class="sans {cls} rise" style="animation-delay:{delay + i * .09:.2f}s" '
                   f'x="{x}" y="{y + i * leading:.1f}" xml:space="preserve">{"".join(spans)}</text>')
    return "".join(out)


# ----------------------------------------------------------------- halftone

def plus(cx: float, cy: float, arm: float, thick: float) -> str:
    """A plus sign with round ends, as one path."""
    r = thick / 2
    return (f"M{cx - arm:.2f} {cy - r:.2f}h{2 * arm:.2f}a{r:.2f} {r:.2f} 0 0 1 0 {thick:.2f}"
            f"h{-2 * arm:.2f}a{r:.2f} {r:.2f} 0 0 1 0 {-thick:.2f}z"
            f"M{cx - r:.2f} {cy - arm:.2f}a{r:.2f} {r:.2f} 0 0 1 {thick:.2f} 0v{2 * arm:.2f}"
            f"a{r:.2f} {r:.2f} 0 0 1 {-thick:.2f} 0z")


def png_uri(im) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# The grade every object shares: cool in the shadows, sand in the middle, cream in the light.
GRADE = [(30, 104, 146), (208, 162, 138), (255, 243, 224)]
KEEP = 0.56   # how much of the photograph's own colour survives the grade


def graded(r: float, g: float, b: float) -> tuple:
    l = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    lo, hi, t = (GRADE[0], GRADE[1], l / 0.5) if l < 0.5 else (GRADE[1], GRADE[2], (l - 0.5) / 0.5)
    tone = [a + (z - a) * t for a, z in zip(lo, hi)]
    k = l * 255 / max(1.0, 0.2126 * tone[0] + 0.7152 * tone[1] + 0.0722 * tone[2])
    return tuple(min(255, round(c * KEEP + tc * k * (1 - KEEP))) for c, tc in zip((r, g, b), tone))


# The four glyphs of the halftone, darkest to brightest: (plus arm, plus thickness) in cells.
TIERS = [(0.11, 0.22), (0.25, 0.17), (0.38, 0.19), (0.5, 0.21)]
EDGES = (0.16, 0.36, 0.6)


def art(p: dict):
    """The project's object: a photograph on black in `_src/art/<repo>.webp`."""
    from PIL import Image
    return Image.open(SRC / "art" / f"{p['repo'].lower()}.webp").convert("RGB")


def glyph_defs(uid: str, cols: int, rows: int, pitch: float) -> str:
    """One tiled mask per glyph. Every picture of the same size shares them."""
    wpx, hpx, c = cols * pitch, rows * pitch, pitch / 2
    out = []
    for i, (arm, thick) in enumerate(TIERS):
        shape = (f'<circle cx="{c}" cy="{c}" r="{pitch * arm:.2f}"/>' if i == 0
                 else f'<path d="{plus(c, c, pitch * arm, pitch * thick)}"/>')
        out.append(
            f'<pattern id="{uid}p{i}" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse">'
            f'<g fill="#fff">{shape}</g></pattern>'
            f'<mask id="{uid}m{i}" maskUnits="userSpaceOnUse" x="0" y="0" width="{wpx}" height="{hpx}">'
            f'<rect width="{wpx}" height="{hpx}" fill="url(#{uid}p{i})"/></mask>')
    # the bloom, the resting grid of the display, and the falloff both of them share
    out.append(
        f'<filter id="{uid}bloom" x="-10%" y="-10%" width="120%" height="120%">'
        f'<feGaussianBlur stdDeviation="{pitch * 1.0:.1f}"/></filter>'
        f'<pattern id="{uid}grid" width="{pitch}" height="{pitch}" patternUnits="userSpaceOnUse">'
        f'<circle cx="{c}" cy="{c}" r="{pitch * .085:.2f}" fill="#fff"/></pattern>'
        f'<radialGradient id="{uid}fall"><stop offset="0" stop-color="#fff"/>'
        f'<stop offset=".55" stop-color="#fff" stop-opacity=".5"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>')
    out.append(
        f'<mask id="{uid}rest" maskUnits="userSpaceOnUse" x="0" y="0" width="{wpx}" height="{hpx}">'
        f'<ellipse cx="{wpx / 2}" cy="{hpx / 2}" rx="{wpx / 2}" ry="{hpx / 2}" fill="url(#{uid}fall)"/>'
        f'</mask>')
    return "".join(out)


def resting_grid(uid: str, cols: int, rows: int, pitch: float) -> str:
    """The display with nothing on it: a faint field of dots that fades towards its edge."""
    wpx, hpx = cols * pitch, rows * pitch
    return (f'<g mask="url(#{uid}rest)"><rect width="{wpx}" height="{hpx}" fill="url(#{uid}grid)" '
            f'opacity=".2"/></g>')


def halftone(im, cols: int, pitch: float, uid: str, *, sparkles: int, seed: int,
             sat: float = 0.95) -> tuple:
    """Turn a photograph on black into a halftone of glyphs.

    The picture is shrunk until one pixel is one cell. Darkness thins out into scattered
    dots instead of fading; the rest is sorted by brightness into four layers, one per
    glyph. Returns (layers, sparks): four SVG fragments, darkest first, and the sparkles.
    """
    from PIL import Image
    rnd = random.Random(seed)
    rows = round(cols * im.height / im.width)
    small = im.resize((cols, rows), Image.LANCZOS)
    lit = sorted(v / 255 for v in small.convert("L").getdata() if v > 12)
    gain = min(3.2, 0.93 / lit[int(len(lit) * 0.97)])
    mid = min(0.9, max(0.05, lit[len(lit) // 2] * gain))
    gamma = min(1.05, max(0.55, math.log(0.4) / math.log(mid)))   # aim the middle grey at 0.4
    src = small.load()
    tiers = [Image.new("RGBA", (cols, rows), (0, 0, 0, 0)) for _ in TIERS]
    lum = {}
    for y in range(rows):
        for x in range(cols):
            r, g, b = (min(255.0, c * gain) for c in src[x, y])
            l = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
            t = min(1.0, max(0.0, (l - 0.035 * gain) / 0.2))
            if rnd.random() > (t * t * (3 - 2 * t)) ** 0.7:
                continue
            grey = 0.2126 * r + 0.7152 * g + 0.0722 * b      # mute the colour, keep the light
            r, g, b = (grey + (c - grey) * sat for c in (r, g, b))
            r, g, b = graded(*(min(255.0, 255 * (max(c, 0) / 255) ** gamma * 1.1)
                               for c in (r, g, b)))
            l = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
            tiers[sum(l > e for e in EDGES)].putpixel((x, y), (r, g, b, 255))
            lum[x, y] = (l, (r, g, b))

    wpx, hpx, c = cols * pitch, rows * pitch, pitch / 2
    layers = []
    for i in range(len(TIERS)):
        href = png_uri(tiers[i])
        layer = (f'<g mask="url(#{uid}m{i})"><image width="{wpx}" height="{hpx}" '
                 f'preserveAspectRatio="none" style="image-rendering:pixelated" href="{href}"/></g>')
        if i == len(TIERS) - 1:   # the light spills a little around the brightest cells
            layer = (f'<image width="{wpx}" height="{hpx}" preserveAspectRatio="none" opacity=".3" '
                     f'filter="url(#{uid}bloom)" href="{href}"/>' + layer)
        layers.append(layer)
    cells = list(lum.items())
    mean = [sum(v[1][1][k] * v[1][0] for v in cells) / max(1e-6, sum(v[1][0] for v in cells))
            for k in range(3)]
    cx = sum(x * v[0] for (x, _), v in cells) / max(1e-6, sum(v[0] for _, v in cells))
    cy = sum(y * v[0] for (_, y), v in cells) / max(1e-6, sum(v[0] for _, v in cells))
    tone = f"rgb({mean[0]:.0f},{mean[1]:.0f},{mean[2]:.0f})"
    back = (f'<radialGradient id="{uid}g{seed}"><stop offset="0" stop-color="{tone}" stop-opacity=".3"/>'
            f'<stop offset=".5" stop-color="{tone}" stop-opacity=".1"/>'
            f'<stop offset="1" stop-color="{tone}" stop-opacity="0"/></radialGradient>'
            f'<circle cx="{(cx + .5) * pitch:.0f}" cy="{(cy + .5) * pitch:.0f}" r="{wpx * .62:.0f}" '
            f'fill="url(#{uid}g{seed})"/>')
    layers[0] = back + layers[0]
    picked, sparks = [], []
    for (x, y), (l, _) in sorted(lum.items(), key=lambda kv: -kv[1][0] - rnd.random() * 0.2):
        if len(picked) >= sparkles or l < 0.42:
            break
        if all(abs(x - qx) + abs(y - qy) > 5 for qx, qy in picked):
            picked.append((x, y))
    for x, y in picked:
        tint = "#%02X%02X%02X" % tuple(round(v + (255 - v) * 0.8) for v in lum[x, y][1])
        size = pitch * rnd.choice((0.8, 1.0, 1.25))
        sparks.append(
            f'<path class="tw" style="animation-duration:{rnd.uniform(2.6, 5.2):.2f}s;'
            f'animation-delay:-{rnd.uniform(0, 5):.2f}s" fill="{tint}" '
            f'd="{plus(x * pitch + c, y * pitch + c, size, pitch * .3)}"/>')
    return layers, "".join(sparks)


# ------------------------------------------------------------------ posters

def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


BASE_CSS = f"""
text{{font-kerning:normal}}
.sans{{font-family:{FAMILIES['sans']};font-weight:500}}
.text{{font-family:{FAMILIES['text']};font-weight:450}}
.serif{{font-family:{FAMILIES['serif']};font-style:italic;font-weight:400}}
.acc{{font-size:{SERIF_SCALE}em;letter-spacing:-.01em}}
.label{{font-size:12.5px;letter-spacing:.16em;fill:{MUTED}}}
.rise{{animation:rise 1.1s cubic-bezier(.2,.8,.2,1) backwards}}
.show{{animation:show 1.4s cubic-bezier(.3,.7,.2,1) backwards}}
.tw{{transform-box:fill-box;transform-origin:center;animation:tw 4s ease-in-out infinite}}
@keyframes rise{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}
@keyframes show{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes tw{{0%,100%{{opacity:.12;transform:scale(.5)}}50%{{opacity:1;transform:none}}}}
"""


def frame(width: int, height: int, title: str, desc: str, css: str, defs: str, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="t d">
<title id="t">{esc(title)}</title>
<desc id="d">{esc(desc)}</desc>
<style>{css}</style>
<defs><clipPath id="card"><rect width="{width}" height="{height}" rx="18"/></clipPath>{defs}</defs>
<g clip-path="url(#card)">
<rect width="{width}" height="{height}" fill="{BG}"/>
{body}
</g>
</svg>
"""


HERO_LINES = ["I make calm, local-first tools", "for the things that *annoy* me."]


def hero_svg() -> str:
    """The poster: a display of glyphs that shows each tool's object in turn."""
    n = len(PROJECTS)
    total = n * SLOT
    left_label, right_label = "ANGLEFORD", "DESIGNER WHO CODES"
    tags = [f'NO. {i + 1:02d} / {n:02d}  —  {p["tag"].upper()}' for i, p in enumerate(PROJECTS)]
    lines = [rich_lines(l, 88, 9999)[0] for l in HERO_LINES]

    cols, pitch = 84, 6.4
    size = cols * pitch
    defs = glyph_defs("h", cols, cols, pitch)
    objects, captions, index = [], [], []
    for i, p in enumerate(PROJECTS):
        start = LOOP_START + i * SLOT
        layers, sparks = halftone(art(p), cols, pitch, "h", sparkles=26, seed=i + 3)
        parts = [f'<g class="tier" style="animation-delay:{start + k * .16:.2f}s">{layer}</g>'
                 for k, layer in enumerate(layers)]
        parts.append(f'<g class="tier" style="animation-delay:{start + .7:.2f}s">{sparks}</g>')
        objects.append(f'<g class="obj{i}">{"".join(parts)}</g>')
        y = 186 + i * 33
        after = 48 + text_width("text", p["name"], 20, -0.02) + 14
        index.append(f'<text class="text idx" x="48" y="{y}">{esc(p["name"])}</text>')
        captions.append(
            f'<g class="cap cap{i}" style="animation-delay:{start + .25:.2f}s">'
            f'<text class="text label" x="48" y="132" xml:space="preserve">{esc(tags[i])}</text>'
            f'<text class="text name" x="48" y="{y}">{esc(p["name"])}</text>'
            f'<text class="text line" x="{after:.1f}" y="{y}">{esc(p["short"])}</text>'
            f'<text class="text big" x="48" y="186">{esc(p["name"])}</text></g>')

    faces = font_faces({
        "sans": "".join(t for l in lines for r, t in l if r == "sans"),
        "serif": "".join(t for l in lines for r, t in l if r == "serif"),
        "text": left_label + right_label + "".join(tags)
                + "".join(p["name"] + p["short"] for p in PROJECTS),
    })
    pct = lambda sec: f"{sec / total * 100:.3f}%"
    css = f"""{faces}{BASE_CSS}
.h1{{font-size:88px;letter-spacing:-.045em;fill:#fff}}
.idx,.name,.line{{font-size:20px;letter-spacing:-.02em}}
.idx{{fill:#4A4946}}
.name{{fill:#fff;stroke:{BG};stroke-width:5px;paint-order:stroke}}
.line{{fill:{MUTED}}}
.big{{display:none;font-size:40px;letter-spacing:-.02em;fill:#fff}}
.rule{{transform-box:fill-box;transform-origin:0 50%;animation:grow 1.2s cubic-bezier(.6,0,.2,1) .2s backwards}}
.tier{{opacity:0;visibility:hidden;animation:tier {total}s linear infinite}}
.cap{{opacity:0;animation:cap {total}s cubic-bezier(.2,.8,.2,1) infinite}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:none}}}}
/* One object's turn on the display: its layers arrive dim first, bright last. */
@keyframes tier{{0%{{opacity:0;visibility:visible}}{pct(.7)},{pct(SLOT - .75)}{{opacity:1;visibility:visible}}
  {pct(SLOT - .1)}{{opacity:0;visibility:visible}}{pct(SLOT)},100%{{opacity:0;visibility:hidden}}}}
@keyframes cap{{0%{{opacity:0}}{pct(.45)},{pct(SLOT - .7)}{{opacity:1}}{pct(SLOT - .3)},100%{{opacity:0}}}}
/* Narrow screens: the picture is scaled down as a whole, so the small text grows. */
@media (max-width:560px){{
  .label{{font-size:24px;letter-spacing:.08em}}
  .idx,.name,.line{{display:none}}
  .big{{display:inline}}
}}
/* No motion: the first object, still. */
@media (prefers-reduced-motion:reduce){{
  *{{animation:none!important}}
  .cap0,.obj0 .tier{{opacity:1;visibility:visible}}
}}
"""
    body = f"""
<text class="text label rise" style="animation-delay:.2s" x="48" y="52.5">{left_label}</text>
<text class="text label rise" style="animation-delay:.2s;text-anchor:end" x="1152" y="52.5">{right_label}</text>
<rect class="rule" x="48" y="82" width="1104" height="1" fill="{LINE}"/>

<g transform="translate({W - 48 - size:.1f} 104)"><g class="show" style="animation-delay:.2s">{resting_grid("h", cols, cols, pitch)}</g>{''.join(objects)}</g>
<g class="show" style="animation-delay:.6s">{''.join(index)}</g>
{''.join(captions)}

{rich_text(lines, 44, 722, 92, "h1", .35)}
"""
    names = ", ".join(p["name"] for p in PROJECTS)
    plain = " ".join(l.replace("*", "") for l in HERO_LINES)
    return frame(W, HERO_H, "Angleford, designer who codes",
                 f"{plain} A display of small glowing crosses shows one object for each tool "
                 f"in turn. Projects: {names}.", css, defs, body)


def cover_svg(p: dict, index: int) -> str:
    """One project's poster: its name and what it is on the left, its object on the right."""
    n = len(PROJECTS)
    cols, pitch = 54, 6.3
    size = cols * pitch
    defs = glyph_defs("c", cols, cols, pitch)
    layers, sparks = halftone(art(p), cols, pitch, "c", sparkles=14, seed=index + 3)
    left = 64
    room = W - 48 - size - left - 36
    name_size = 88.0
    while text_width("serif", p["name"], name_size, -0.015) > room and name_size > 56:
        name_size -= 2
    words, lines, cur = p["line"].split(), [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if cur and text_width("text", trial, 27, -0.02) > room:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    tag = f'NO. {index + 1:02d} / {n:02d}  —  {p["tag"].upper()}'
    u = urllib.parse.urlparse(p.get("site", ""))
    host = (u.netloc + u.path.rstrip("/") if p.get("site") else f"github.com/{OWNER}/{p['repo']}").upper()
    faces = font_faces({"serif": p["name"], "text": tag + host + p["line"]})
    css = f"""{faces}{BASE_CSS}
.h1{{font-size:{name_size:.0f}px;letter-spacing:-.015em;fill:#fff}}
.line{{font-size:27px;letter-spacing:-.02em;fill:{INK};fill-opacity:.82}}
.foot{{fill:{FAINT}}}
@media (max-width:560px){{.label{{font-size:24px;letter-spacing:.06em}}.foot{{display:none}}
  .line{{font-size:40px}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
    top = 196 - (len(lines) - 1) * 17
    text = "".join(
        f'<text class="text line rise" style="animation-delay:{.22 + i * .08:.2f}s" x="{left}" '
        f'y="{top + 58 + i * 37}">{esc(line)}</text>' for i, line in enumerate(lines))
    stack = "".join(f'<g class="show" style="animation-delay:{k * .16:.2f}s">{layer}</g>'
                    for k, layer in enumerate(layers))
    body = f"""
<g transform="translate({W - 48 - size:.1f} {(COVER_H - size) / 2:.1f})">{resting_grid("c", cols, cols, pitch)}{stack}<g class="show" style="animation-delay:.7s">{sparks}</g></g>
<text class="text label rise" x="{left}" y="80" xml:space="preserve">{esc(tag)}</text>
<text class="serif h1 rise" style="animation-delay:.1s" x="{left - 2}" y="{top}">{esc(p["name"])}</text>
{text}
<text class="text label foot" x="{left}" y="{COVER_H - 56}">{esc(host)}</text>
"""
    return frame(W, COVER_H, p["name"], f"{p['line']} Its object drawn as a halftone of small "
                 "glowing crosses.", css, defs, body)


# ------------------------------------------------------------------- readme

NUMBER = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
          "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen"]


def project_block(p: dict) -> str:
    repo = f"https://github.com/{OWNER}/{p['repo']}"
    img = f'<img src="assets/cover-{p["repo"].lower()}.svg" width="100%" alt="{p["name"]}. {p["line"]}">'
    links = []
    if p.get("download"):
        links.append(f'<a href="{p["download"]}"><b>Download</b></a>')
    if p.get("site"):
        u = urllib.parse.urlparse(p["site"])
        label = u.netloc + ("/" + u.path.strip("/") if u.path.strip("/") else "")
        links.append(f'<a href="{p["site"]}">{label}</a>' if links
                     else f'<a href="{p["site"]}"><b>{label}</b></a>')
    links.append(f'<a href="{repo}">{"Source" if links else "<b>Source</b>"}</a>')
    return f"""<details>
<summary><b>{p['name']}</b> &nbsp;—&nbsp; {p['short']} <sup>{p['tag']}</sup></summary>
<br>
<a href="{repo}">{img}</a>
<p>{' &nbsp;·&nbsp; '.join(links)}</p>
</details>
"""


def readme() -> str:
    n = len(PROJECTS)
    names = ", ".join(p["name"] for p in PROJECTS)
    alt = ("Angleford, designer who codes. I make calm, local-first tools for the things that "
           "annoy me. A display of small glowing crosses shows one object for each tool in "
           f"turn. Projects: {names}.")
    blocks = "\n".join(project_block(p) for p in PROJECTS)
    also = ", and ".join(f'[**{a["name"]}**]({a["url"]}), {a["line"]}' for a in DATA["also"])
    count = NUMBER[n] if n < len(NUMBER) else str(n)
    # Keep the hero on one line: split over several, GitHub's Markdown parser breaks the link.
    hero = (f'<a href="{DATA["site"]}"><img src="assets/hero.svg" width="100%" alt="{alt}"></a>')
    return f"""{hero}

Windows apps, iPhone apps, browser extensions and plugins. Designed and built end to end, by one person.

**[angleford.co]({DATA['site']})** &nbsp;·&nbsp; [Telegram]({DATA['telegram']})

<br>

**{count.capitalize()} tools.** Open any line.

{blocks}
Also: {also}.

<!-- shipped:start -->
<!-- shipped:end -->

<sub>{DATA['stack']}</sub>
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    if "--readme" not in sys.argv:
        for old in OUT.glob("*"):
            old.unlink()
        svg = hero_svg()
        (OUT / "hero.svg").write_text(svg, encoding="utf-8", newline="\n")
        print(f"hero.svg  {len(svg) / 1024:.0f} KB")
        for i, p in enumerate(PROJECTS):
            svg = cover_svg(p, i)
            name = f"cover-{p['repo'].lower()}.svg"
            (OUT / name).write_text(svg, encoding="utf-8", newline="\n")
            print(f"{name}  {len(svg) / 1024:.0f} KB")
        total = sum(f.stat().st_size for f in OUT.iterdir())
        print(f"assets: {len(list(OUT.iterdir()))} files, {total / 1e6:.2f} MB")

    path = ROOT / "README.md"
    new = readme()
    # Keep the "recently shipped" line that _src/shipped.py maintains.
    if path.exists():
        old = path.read_text(encoding="utf-8")
        a, b = "<!-- shipped:start -->", "<!-- shipped:end -->"
        if a in old and b in old:
            kept = old[old.index(a):old.index(b) + len(b)]
            new = new[:new.index(a)] + kept + new[new.index(b) + len(b):]
    path.write_text(new, encoding="utf-8", newline="\n")
    print("README.md written")


if __name__ == "__main__":
    main()
