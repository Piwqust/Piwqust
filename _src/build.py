"""Build the profile page: animated hero (light + dark), project covers and README.md.

Everything on the page comes from `_src/projects.json`. To add, remove or reorder a
project, edit that file and run from the repo root:

    python -I _src/build.py            # hero + covers + README
    python -I _src/build.py --readme   # README only (no downloads)

Needs Pillow, fontTools and brotli. Fonts and project images are downloaded into
`_src/cache/` (ignored by git) from Google Fonts and the project repositories.

How the page works on GitHub:
- A README cannot run scripts or CSS, but an SVG shown through <img> plays its own
  CSS animations. The hero is one self-contained SVG: fonts and icons are inlined.
- Light and dark versions are separate files, picked by <picture>.
- Each project is a native <details> block, so a click opens its cover and links.
"""
import base64
import io
import json
import pathlib
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
    "InterTight.ttf": "ofl/intertight/InterTight%5Bwght%5D.ttf",
    "InstrumentSerif-Italic.ttf": "ofl/instrumentserif/InstrumentSerif-Italic.ttf",
    "JetBrainsMono.ttf": "ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}

THEMES = {
    "light": dict(ink="#16161A", muted="#6B6A66", faint="#A09E98", rule="#16161A1F",
                  ring="#16161A1A", tile="#FFFFFF", tile_dark="#1B2028"),
    "dark": dict(ink="#F2F1EE", muted="#A3A198", faint="#77756E", rule="#FFFFFF24",
                 ring="#FFFFFF1F", tile="#1B2028", tile_dark="#1B2028"),
}

# Hero geometry, in SVG units (the image is 1200 units wide).
W, H = 1200, 432
ICON = 68
SHELF_Y = 268
RULE_Y = 364
CAP_Y = 408
SLOT = 3.4          # seconds each project stays in the caption
LOOP_START = 2.1    # seconds before the caption loop begins


# ---------------------------------------------------------------- downloads

def fetch(url: str, dest: pathlib.Path) -> pathlib.Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "profile-build"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
    return dest


def repo_file(p: dict, path: str) -> pathlib.Path:
    url = (f"https://raw.githubusercontent.com/{OWNER}/{p['repo']}/{p['branch']}/"
           + urllib.parse.quote(path))
    return fetch(url, CACHE / p["repo"] / path.replace("/", "__"))


def font_file(name: str) -> pathlib.Path:
    return fetch("https://raw.githubusercontent.com/google/fonts/main/" + FONT_URLS[name],
                 CACHE / "fonts" / name)


# -------------------------------------------------------------------- fonts

def subset_font(name: str, text: str, wght: int | None = None) -> str:
    """Return a base64 WOFF2 holding only the glyphs `text` needs."""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = TTFont(font_file(name))
    if wght is not None:
        font = instancer.instantiateVariableFont(font, {"wght": wght})
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
    return base64.b64encode(buf.getvalue()).decode()


# -------------------------------------------------------------------- icons

def open_image(path: pathlib.Path):
    from PIL import Image
    im = Image.open(path)
    if path.suffix == ".ico":
        im.size = max(im.info.get("sizes", [im.size]))
        im.load()
    return im.convert("RGBA")


def data_uri(im, quality: int = 92) -> str:
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


VECTOR_ICONS = {
    # The V2pn glyph from its favicon, white on the brand red.
    "v2pn": lambda t: (
        f'<rect width="{ICON}" height="{ICON}" fill="#FF3D1F"/>'
        '<path transform="translate(19 17.5) scale(.29)" fill="#fff" d="M0,0 L32,0 L32,40 L72,0 '
        'L104,0 L104,32 L85.255,32 L64,53.255 L64,112 L32,112 L32,72 L0,40 Z"/>'),
    # The Fount mark on its own paper tile.
    "fount": lambda t: (
        f'<rect width="{ICON}" height="{ICON}" fill="#FAFAF8"/>'
        '<g transform="translate(14.5 13.5) scale(.085)">'
        '<path fill="#202020" d="M48 32H268C285.673112 32 300 46.326888 300 64V70C288 64 277 62 260 '
        '62H252C216 62 196 84 196 120V192C196 228 216 248 252 248H300V284H252C216 284 196 306 196 '
        '342V376C196 420 218 440 262 446V452H48V446C88 442 104 420 104 376V112C104 68 88 44 48 38Z"/>'
        '<path fill="#548fe7" d="M268 32C285.673112 32 300 46.326888 300 64V118C300 140.091390 '
        '317.908610 158 340 158H404C402 144 394 134 384 124L302 42C293 35 281 32 268 32Z"/>'
        '<path fill="#202020" d="M338 180C338 176 342 174 345 177L430 240C434 243 433 248 428 '
        '249L398 256L418 295C420 299 418 303 414 305L402 311C398 313 394 311 392 307L374 270L348 '
        '292C344 295 340 293 340 288Z"/></g>'),
}


def icon_markup(p: dict, theme: str) -> str:
    """One 68-unit tile: the app icon clipped to a rounded square with a hairline ring."""
    t = THEMES[theme]
    spec = p["icon"]
    if "vector" in spec:
        inner = VECTOR_ICONS[spec["vector"]](t)
    else:
        im = open_image(repo_file(p, spec["path"]))
        px = ICON * 3
        if spec.get("fit") == "contain":
            tile = spec.get("tile", "theme")
            bg = t["tile"] if tile == "theme" else tile
            pad = spec.get("pad", 0.0)
            size = round(ICON * (1 - 2 * pad), 2)
            off = round(ICON * pad, 2)
            im.thumbnail((px, px))
            inner = (f'<rect width="{ICON}" height="{ICON}" fill="{bg}"/>'
                     f'<image x="{off}" y="{off}" width="{size}" height="{size}" '
                     f'href="{data_uri(im)}"/>')
        else:
            # Full-bleed icon. Fill the tile with the icon's own edge colour first, so its
            # rounded corners never show the page through.
            r, g, b, _ = im.getpixel((im.width // 2, max(2, im.height // 40)))
            im = im.resize((px, px))
            inner = (f'<rect width="{ICON}" height="{ICON}" fill="rgb({r},{g},{b})"/>'
                     f'<image width="{ICON}" height="{ICON}" href="{data_uri(im)}"/>')
    return (f'<g clip-path="url(#tile)">{inner}</g>'
            f'<rect x=".5" y=".5" width="{ICON - 1}" height="{ICON - 1}" rx="15.5" fill="none" '
            f'stroke="{t["ring"]}"/>')


# --------------------------------------------------------------------- hero

def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def hero_svg(theme: str) -> str:
    t = THEMES[theme]
    n = len(PROJECTS)
    total = n * SLOT
    gap = (W - n * ICON) / (n - 1)
    xs = [round(i * (ICON + gap), 2) for i in range(n)]

    eyebrow = "ANGLEFORD · DESIGNER WHO CODES"
    line1 = "I make calm, local-first tools"
    line2 = "for the things that annoy me."
    tags = [f'{p["tag"].upper()}   {i + 1:02d} / {n:02d}' for i, p in enumerate(PROJECTS)]

    fonts = {
        "AF Sans": (subset_font("InterTight.ttf", line1 + "".join(p["name"] for p in PROJECTS), 500), 500),
        "AF Text": (subset_font("InterTight.ttf", "".join(p["caption"] for p in PROJECTS), 400), 400),
        "AF Serif": (subset_font("InstrumentSerif-Italic.ttf", line2), 400),
        "AF Mono": (subset_font("JetBrainsMono.ttf", eyebrow + "".join(tags), 400), 400),
    }
    faces = "".join(
        f"@font-face{{font-family:'{fam}';font-weight:{w};"
        f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
        for fam, (b64, w) in fonts.items())

    pct = lambda sec: f"{sec / total * 100:.3f}%"

    # The marker under the shelf: rest under one icon, then glide to the next.
    stops = []
    for i, x in enumerate(xs):
        stops.append(f"{pct(i * SLOT)},{pct((i + 1) * SLOT - 0.65)}{{transform:translateX({x}px)}}")
    stops.append(f"100%{{transform:translateX({xs[0]}px)}}")
    marker_kf = "".join(stops)

    css = f"""
{faces}
text{{font-kerning:normal}}
.sans{{font-family:'AF Sans','Inter Tight','Inter',system-ui,-apple-system,'Segoe UI',sans-serif;font-weight:500}}
.text{{font-family:'AF Text','Inter Tight','Inter',system-ui,-apple-system,'Segoe UI',sans-serif;font-weight:400}}
.serif{{font-family:'AF Serif','Instrument Serif',Georgia,'Times New Roman',serif;font-style:italic}}
.mono{{font-family:'AF Mono','JetBrains Mono',ui-monospace,SFMono-Regular,Consolas,monospace}}
.eyebrow{{font-size:15px;letter-spacing:.14em;fill:{t['muted']}}}
.h1{{font-size:70px;letter-spacing:-.036em;fill:{t['ink']}}}
.h2{{font-size:80px;letter-spacing:-.012em;fill:{t['muted']}}}
.name{{font-size:24px;letter-spacing:-.015em;fill:{t['ink']}}}
.line{{font-size:24px;letter-spacing:-.008em;fill:{t['muted']}}}
.tag{{font-size:14px;letter-spacing:.12em;fill:{t['faint']}}}

.draw{{stroke-dasharray:1;animation:draw .7s cubic-bezier(.6,0,.2,1) .1s backwards}}
.rise{{animation:rise .9s cubic-bezier(.2,.8,.2,1) backwards}}
.pop{{transform-box:fill-box;transform-origin:50% 100%;animation:pop .7s cubic-bezier(.3,1.5,.5,1) backwards}}
.rule{{transform-box:fill-box;transform-origin:0 50%;animation:grow 1.1s cubic-bezier(.6,0,.2,1) 1.1s backwards}}
.lift{{transform-box:fill-box;transform-origin:50% 100%;animation:lift {total}s cubic-bezier(.3,.9,.3,1) infinite}}
.marker{{transform:translateX(0px);animation:fade .5s ease {LOOP_START - .4}s backwards,
  glide {total}s cubic-bezier(.7,0,.2,1) {LOOP_START}s infinite}}
.cap{{opacity:0;animation:cap {total}s cubic-bezier(.2,.8,.2,1) infinite}}

@keyframes draw{{from{{stroke-dashoffset:1}}to{{stroke-dashoffset:0}}}}
@keyframes rise{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{from{{opacity:0;transform:translateY(10px) scale(.72)}}to{{opacity:1;transform:none}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:none}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes lift{{0%,{pct(SLOT)},100%{{transform:none}}
  {pct(.5)},{pct(SLOT - .65)}{{transform:translateY(-9px) scale(1.07)}}}}
@keyframes glide{{{marker_kf}}}
@keyframes cap{{0%{{opacity:0;transform:translateY(9px)}}
  {pct(.5)},{pct(SLOT - .65)}{{opacity:1;transform:none}}
  {pct(SLOT - .25)},100%{{opacity:0;transform:translateY(-7px)}}}}

/* Narrow screens: the image is scaled down as a whole, so the small text grows
   and the long caption gives way to the project's name. */
@media (max-width:560px){{
  .eyebrow{{font-size:29px;letter-spacing:.1em}}
  .name{{font-size:44px}}
  .line,.tag{{display:none}}
}}
/* No motion: show the finished frame with the first project in the caption. */
@media (prefers-reduced-motion:reduce){{
  *{{animation:none!important}}
  .cap0{{opacity:1}}
}}
"""

    icons = []
    captions = []
    for i, p in enumerate(PROJECTS):
        start = LOOP_START + i * SLOT
        icons.append(
            f'<g transform="translate({xs[i]} {SHELF_Y})">'
            f'<g class="pop" style="animation-delay:{0.75 + i * 0.055:.3f}s">'
            f'<g class="lift" style="animation-delay:{start:.2f}s">{icon_markup(p, theme)}</g></g></g>')
        captions.append(
            f'<g class="cap cap{i}" style="animation-delay:{start:.2f}s">'
            f'<text y="{CAP_Y}"><tspan class="sans name">{esc(p["name"])}</tspan>'
            f'<tspan class="text line" dx="14">{esc(p["caption"])}</tspan></text>'
            f'<text class="mono tag" x="{W}" y="{CAP_Y - 2}" text-anchor="end" '
            f'xml:space="preserve">{esc(tags[i])}</text></g>')

    names = ", ".join(p["name"] for p in PROJECTS)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Angleford, designer who codes</title>
<desc id="d">{esc(line1)} {esc(line2)} A shelf of app icons: {esc(names)}.</desc>
<style>{css}</style>
<defs><clipPath id="tile"><rect width="{ICON}" height="{ICON}" rx="16"/></clipPath></defs>

<path class="draw" d="M1.25 6V26.75H23" pathLength="1" fill="none" stroke="{t['ink']}" stroke-width="2.5"/>
<text class="mono eyebrow rise" style="animation-delay:.3s" x="38" y="24.5">{esc(eyebrow)}</text>

<text class="sans h1 rise" style="animation-delay:.4s" x="-3" y="132">{esc(line1)}</text>
<text class="serif h2 rise" style="animation-delay:.55s" x="-2" y="212">{esc(line2)}</text>

{''.join(icons)}

<rect class="rule" y="{RULE_Y}" width="{W}" height="1" fill="{t['rule']}"/>
<rect class="marker" y="{RULE_Y - 1}" width="{ICON}" height="2.5" rx="1.25" fill="{t['ink']}"/>

{''.join(captions)}
</svg>
"""


# ------------------------------------------------------------------- covers

def rounded(im, radius: int):
    from PIL import Image, ImageChops, ImageDraw
    scale = 4
    mask = Image.new("L", (im.width * scale, im.height * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, mask.width - 1, mask.height - 1), radius * scale, fill=255)
    mask = mask.resize(im.size, Image.LANCZOS)
    im = im.convert("RGBA")
    im.putalpha(ImageChops.multiply(im.getchannel("A"), mask))
    return im


def save_cover(im, name: str) -> None:
    box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:  # drop the empty margin a window screenshot carries around its shadow
        im = im.crop(box)
    if im.width > 1700:
        im = im.resize((1700, round(im.height * 1700 / im.width)))
    im.save(OUT / name, "WEBP", quality=90, method=6)


def cover_files(p: dict) -> dict:
    """Write the project's cover(s) into assets/ and return {theme: file name}."""
    from PIL import Image
    c = p["cover"]
    slug = p["repo"].lower()
    if "phones" in c:
        shots = [open_image(repo_file(p, s)) for s in c["phones"]]
        w, gap = 500, 44
        shots = [s.resize((w, round(s.height * w / s.width))) for s in shots]
        sheet = Image.new("RGBA", (len(shots) * w + (len(shots) - 1) * gap, shots[0].height))
        for i, s in enumerate(shots):
            s = rounded(s, 58)
            sheet.paste(s, (i * (w + gap), 0), s)
        save_cover(sheet, f"cover-{slug}.webp")
        return {"dark": f"cover-{slug}.webp"}
    files = {}
    for theme in ("dark", "light"):
        if theme not in c:
            continue
        src = repo_file(p, c[theme])
        suffix = f"-{theme}" if "light" in c else ""
        if c.get("copy"):
            name = f"cover-{slug}{suffix}{src.suffix}"
            (OUT / name).write_bytes(src.read_bytes())
        else:
            im = open_image(src)
            opaque = im.getchannel("A").getextrema()[0] == 255
            if opaque:  # a plain rectangle: give it the same soft corners as the rest
                if im.width > 1700:
                    im = im.resize((1700, round(im.height * 1700 / im.width)))
                im = rounded(im, 26)
            name = f"cover-{slug}{suffix}.webp"
            save_cover(im, name)
        files[theme] = name
    return files


# ------------------------------------------------------------------- readme

NUMBER = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
          "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen"]


def cover_names(p: dict) -> dict:
    c = p["cover"]
    slug = p["repo"].lower()
    if "phones" in c:
        return {"dark": f"cover-{slug}.webp"}
    ext = pathlib.PurePosixPath(c["dark"]).suffix if c.get("copy") else ".webp"
    if "light" in c:
        return {"dark": f"cover-{slug}-dark{ext}", "light": f"cover-{slug}-light{ext}"}
    return {"dark": f"cover-{slug}{ext}"}


def project_block(p: dict) -> str:
    repo = f"https://github.com/{OWNER}/{p['repo']}"
    files = cover_names(p)
    alt = f"{p['name']}: {p['caption']}"
    width = p["cover"]["width"]
    if "light" in files:
        img = (f'<picture><source media="(prefers-color-scheme: dark)" srcset="assets/{files["dark"]}">'
               f'<img src="assets/{files["light"]}" width="{width}" alt="{alt}"></picture>')
    else:
        img = f'<img src="assets/{files["dark"]}" width="{width}" alt="{alt}">'
    links = []
    if p.get("download"):
        links.append(f'<a href="{p["download"]}"><b>Download</b></a>')
    if p.get("site"):
        host = urllib.parse.urlparse(p["site"]).netloc
        path = urllib.parse.urlparse(p["site"]).path.strip("/")
        label = host + ("/" + path if path else "")
        links.append(f'<a href="{p["site"]}">{"<b>" if not links else ""}{label}{"</b>" if not links else ""}</a>')
    links.append(f'<a href="{repo}">{"<b>Source</b>" if not links else "Source"}</a>')
    return f"""<details>
<summary>“{p['problem']}” &nbsp;→&nbsp; <b>{p['name']}</b> <sup>{p['tag']}</sup></summary>
<br>
<a href="{repo}">{img}</a>
<p>{p['blurb']}<br>
{' &nbsp;·&nbsp; '.join(links)}</p>
</details>
"""


def readme() -> str:
    n = len(PROJECTS)
    names = ", ".join(p["name"] for p in PROJECTS)
    alt = ("Angleford, designer who codes. I make calm, local-first tools for the things that "
           f"annoy me. A shelf of app icons: {names}.")
    blocks = "\n".join(project_block(p) for p in PROJECTS)
    also = ", and ".join(f'[**{a["name"]}**]({a["url"]}), {a["line"]}' for a in DATA["also"])
    count = NUMBER[n] if n < len(NUMBER) else str(n)
    # Keep this on one line: split over several, GitHub's Markdown parser empties the <picture>.
    hero = (f'<a href="{DATA["site"]}"><picture>'
            '<source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">'
            f'<img src="assets/hero-light.svg" width="100%" alt="{alt}"></picture></a>')
    return f"""{hero}

Windows apps, iPhone apps, browser extensions and plugins. Designed and built end to end, by one person.

**[angleford.co]({DATA['site']})** &nbsp;·&nbsp; [Telegram]({DATA['telegram']})

<br>

**{count.capitalize()} things that annoyed me, and what I built about each.** Open any line.

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
        for theme in THEMES:
            svg = hero_svg(theme)
            (OUT / f"hero-{theme}.svg").write_text(svg, encoding="utf-8", newline="\n")
            print(f"hero-{theme}.svg  {len(svg) / 1024:.0f} KB")
        for p in PROJECTS:
            print(p["name"], cover_files(p))
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
