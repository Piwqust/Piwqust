"""Build the profile hero and project cards (light + dark).

Run from the profile repo root, with the project clones next to it
(../tempro, ../earnline, ...):

    python -I _src/shoot.py   # raster copies, used only to sample background colours
    python -I _src/build.py

Needs Playwright and network access for Google Fonts. Project heroes are
embedded as their original SVGs, so they stay sharp at the 3x render scale.
"""
import html
import pathlib
import re

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
STUDIO = ROOT.parent
SHOTS = ROOT / "_src" / "shots"
OUT = ROOT / "assets"
SCALE = 3  # GitHub shows a card ~520 CSS px wide; 3x stays crisp on 200% displays

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700'
         '&family=JetBrains+Mono:wght@400;500&display=block" rel="stylesheet">')

THEMES = {
    "light": dict(paper="#F5F4F0", ink="#141414", muted="#62605B", faint="#A3A09A",
                  line="rgba(20,20,20,.10)", card="#FAFAF8", tile="#FFFFFF",
                  shadow="0 1px 2px rgba(0,0,0,.06)"),
    "dark": dict(paper="#121418", ink="#F2F1EE", muted="#A3A198", faint="#6B6962",
                 line="rgba(255,255,255,.10)", card="#141920", tile="#1B2028",
                 shadow="0 1px 2px rgba(0,0,0,.4)"),
}

ICONS = {
    "tempro": "tempro/app/src-tauri/icons/icon.png",
    "switcher": "claude-switcher/docs/images/logo.png",
    "orvey": "orvey-plugin/plugins/orvey/assets/logo.png",
    "fount": "font-grabber/core/src/web/assets/fount-mark.svg",
    "earnline": "earnline/ios-app/earnline/Assets.xcassets/AppIcon.appiconset/AppIcon.png",
    "cutoff": "Cutoff/Cutoff/Assets.xcassets/AppIcon.appiconset/AppIcon.png",
    "pinterest": "pinterest-plus-plus/public/icon/128.png",
    "blackboard": "blackboard/icons/icon-512.png",
}


def themed(light: str, dark: str) -> dict:
    return {"light": light, "dark": dark}


# name, repo, icon, tag, one-liner, visual source(s), crop
# crop: ("cover", zoom, focus_x, focus_y) or ("fit", shot-name-for-bg-sampling)
PROJECTS = [
    ("Tempro", "tempro", "tempro", "Windows",
     "Automatic time tracking that works out what you actually did.",
     themed("tempro/docs/assets/readme-hero-light.svg", "tempro/docs/assets/readme-hero-dark.svg"),
     ("cover", 1.04, 0.0, 0.25)),
    ("Claude Profile Switcher", "claude-switcher", "switcher", "Windows",
     "Several Claude Desktop accounts on one PC, all signed in at once.",
     themed("claude-switcher/docs/images/picker-light.png", "claude-switcher/docs/images/picker-dark.png"),
     ("cover", 1.0, 0.5, 0.42)),
    ("orvey", "orvey-plugin", "orvey", "MCP plugin",
     "Images and concepts in Claude, ChatGPT, Claude Code, Codex.",
     themed("orvey-plugin/docs/readme/hero-light.svg", "orvey-plugin/docs/readme/hero-dark.svg"),
     ("cover", 1.04, 0.25, 0.5)),
    ("Fount", "font-grabber", "fount", "Web · Extension · CLI",
     "Find the fonts behind any website and save them as clean TTF/OTF.",
     themed("font-grabber/docs/readme/hero-light.svg", "font-grabber/docs/readme/hero-dark.svg"),
     ("cover", 1.04, 0.3, 0.5)),
    ("earn›line", "earnline", "earnline", "iPhone",
     "A calm income ledger for independent work.",
     themed("earnline/docs/readme/hero-light.svg", "earnline/docs/readme/hero-dark.svg"),
     ("fit", themed("earnline-light", "earnline-dark"))),
    ("Cutoff", "Cutoff", "cutoff", "iPhone",
     "A calm trainer for tournament preflop decisions. Study only.",
     "Cutoff/docs/readme/hero.svg",
     ("cover", 1.04, 0.5, 0.5)),
    ("Pinterest Plus Plus", "pinterest-plus-plus", "pinterest", "Chrome",
     "Copy and download pins in full quality, and resize the grid.",
     "pinterest-plus-plus/docs/readme/hero.svg",
     ("fit", "pinterest")),
    ("Blackboard Text", "blackboard", "blackboard", "Web · PWA",
     "A quiet, local-first place to write and sketch.",
     "blackboard/docs/readme/hero.svg",
     ("cover", 1.04, 0.2, 0.5)),
]

CARD_W, SHOT_H = 600, 250


def uri(rel: str) -> str:
    return (STUDIO / rel).resolve().as_uri()


def natural_size(path: pathlib.Path) -> tuple[float, float]:
    if path.suffix == ".svg":
        head = path.read_text(encoding="utf-8")[:2000]
        vb = re.search(r'viewBox="([\d.\s-]+)"', head)
        _, _, w, h = (float(v) for v in vb.group(1).split())
        return w, h
    return Image.open(path).size


def base_css(t: dict) -> str:
    return f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:transparent}}
body{{font-family:'Inter Tight',system-ui,sans-serif;color:{t['ink']};
  -webkit-font-smoothing:antialiased;text-rendering:geometricPrecision}}
.mono{{font-family:'JetBrains Mono',ui-monospace,monospace}}
"""


def hero_html(theme: str) -> str:
    t = THEMES[theme]
    tiles = "".join(
        f'<div class="ic {"pad" if k == "fount" else ""} {"board" if k == "blackboard" else ""}">'
        f'<img src="{uri(ICONS[k])}"></div>'
        for k in ("tempro", "switcher", "orvey", "fount",
                  "earnline", "cutoff", "pinterest", "blackboard"))
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>
{base_css(t)}
#c{{width:1200px;height:420px;border-radius:28px;background:{t['paper']};
  border:1px solid {t['line']};overflow:hidden;
  display:grid;grid-template-columns:1fr 392px;padding:52px 64px 50px}}
.left{{display:flex;flex-direction:column}}
.eyebrow{{font-size:15px;letter-spacing:.12em;color:{t['muted']};text-transform:uppercase;
  display:flex;align-items:center;gap:14px}}
.eyebrow i{{display:block;width:22px;height:22px;border-left:2px solid {t['ink']};
  border-bottom:2px solid {t['ink']};transform:translateY(-3px)}}
h1{{font-size:54px;line-height:1.05;letter-spacing:-.035em;font-weight:600;margin-top:36px;
  white-space:nowrap}}
h1 span{{color:{t['faint']}}}
.sub{{font-size:21px;line-height:1.5;color:{t['muted']};margin-top:22px;letter-spacing:-.008em}}
.foot{{margin-top:auto;font-size:15px;color:{t['muted']};display:flex;gap:32px}}
.foot b{{color:{t['ink']};font-weight:500}}
.grid{{display:grid;grid-template-columns:repeat(4,80px);grid-auto-rows:80px;gap:24px;
  align-content:center;justify-content:end}}
.ic{{width:80px;height:80px;border-radius:19px;overflow:hidden;background:{t['tile']};
  box-shadow:{t['shadow']},0 0 0 1px {t['line']}}}
.ic img{{width:100%;height:100%;object-fit:cover;display:block}}
.ic.pad{{padding:17px;background:#FAFAF8}} .ic.pad img{{object-fit:contain}}
.ic.board{{background:#0B0B0D}}
</style></head><body><div id="c">
<div class="left">
  <div class="eyebrow mono"><i></i>Angleford · designer who codes</div>
  <h1>I make calm, local-first tools<br><span>for the things that annoy me.</span></h1>
  <p class="sub">Windows apps, iPhone apps, browser extensions and plugins.<br>Designed and built end to end, by one person.</p>
  <div class="foot mono"><span><b>angleford.co</b></span><span>t.me/<b>where_00</b></span></div>
</div>
<div class="grid">{tiles}</div>
</div></body></html>"""


def visual_css(theme: str, src: pathlib.Path, crop) -> str:
    w, h = natural_size(src)
    if crop[0] == "fit":
        # Wide 3:1 heroes lose words under a cover crop; show them whole on
        # their own background colour (sampled inside the left edge).
        shot = crop[1][theme] if isinstance(crop[1], dict) else crop[1]
        im = Image.open(SHOTS / f"{shot}.png").convert("RGB")
        r, g, b = im.getpixel((24, im.height // 2))
        dw = CARD_W
        dh = h * dw / w
        return (f"background:rgb({r},{g},{b});",
                f"width:{dw}px;height:{dh}px;left:0;top:{(SHOT_H - dh) / 2}px")
    _, zoom, fx, fy = crop
    s = max(CARD_W / w, SHOT_H / h) * zoom
    dw, dh = w * s, h * s
    return ("", f"width:{dw}px;height:{dh}px;left:{-(dw - CARD_W) * fx}px;"
                f"top:{-(dh - SHOT_H) * fy}px")


def card_html(theme: str, p) -> str:
    t = THEMES[theme]
    name, _repo, icon, tag, line, visual, crop = p
    src = STUDIO / (visual[theme] if isinstance(visual, dict) else visual)
    shot_bg, img_css = visual_css(theme, src, crop)
    ic = "pad" if icon == "fount" else ("board" if icon == "blackboard" else "")
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>
{base_css(t)}
#c{{width:{CARD_W}px;height:368px;border-radius:22px;background:{t['card']};overflow:hidden;
  border:1px solid {t['line']};display:flex;flex-direction:column}}
.shot{{height:{SHOT_H}px;flex:none;position:relative;overflow:hidden;
  border-bottom:1px solid {t['line']};{shot_bg}}}
.shot img{{position:absolute;display:block;{img_css}}}
.meta{{padding:20px 24px 0;display:flex;align-items:center;gap:12px}}
.ic{{width:36px;height:36px;border-radius:9px;overflow:hidden;flex:none;
  box-shadow:0 0 0 1px {t['line']};background:{t['tile']}}}
.ic img{{width:100%;height:100%;object-fit:cover;display:block}}
.ic.pad{{padding:6px;background:#FAFAF8}} .ic.pad img{{object-fit:contain}}
.ic.board{{background:#0B0B0D}}
.name{{font-size:23px;font-weight:600;letter-spacing:-.02em}}
.tag{{margin-left:auto;font-size:12.5px;letter-spacing:.08em;text-transform:uppercase;
  color:{t['muted']};border:1px solid {t['line']};border-radius:999px;padding:5px 11px}}
.line{{padding:10px 24px 0 72px;font-size:17px;line-height:1.4;color:{t['muted']};
  letter-spacing:-.005em}}
</style></head><body><div id="c">
<div class="shot"><img src="{src.as_uri()}"></div>
<div class="meta"><div class="ic {ic}"><img src="{uri(ICONS[icon])}"></div>
<div class="name">{html.escape(name)}</div><div class="tag mono">{html.escape(tag)}</div></div>
<div class="line">{html.escape(line)}</div>
</div></body></html>"""


def shoot(pg, markup: str, out: pathlib.Path) -> None:
    tmp = ROOT / "_src" / "_page.html"
    tmp.write_text(markup, encoding="utf-8")
    pg.goto(tmp.as_uri(), wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    png = out.with_suffix(".png")
    pg.locator("#c").screenshot(path=str(png), omit_background=True)
    tmp.unlink()
    # Lossless WebP: same pixels as the PNG at roughly half the weight.
    Image.open(png).save(out, "WEBP", lossless=True, quality=100, method=6)
    png.unlink()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1300, "height": 900}, device_scale_factor=SCALE)
        for theme in THEMES:
            shoot(pg, hero_html(theme), OUT / f"hero-{theme}.webp")
            for proj in PROJECTS:
                shoot(pg, card_html(theme, proj), OUT / f"card-{proj[1].lower()}-{theme}.webp")
        b.close()
    total = sum(f.stat().st_size for f in OUT.glob("*.webp"))
    print(f"built {len(list(OUT.glob('*.webp')))} images, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
