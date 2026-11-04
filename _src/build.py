"""Build the profile hero and project cards (light + dark) as PNGs.

python -I _src/build.py   (from the profile repo root; needs Playwright + network for Google Fonts)
"""
import html
import pathlib

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
STUDIO = ROOT.parent
SHOTS = ROOT / "_src" / "shots"
OUT = ROOT / "assets"

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700'
         '&family=JetBrains+Mono:wght@400;500&display=block" rel="stylesheet">')

THEMES = {
    "light": dict(page="#ffffff", paper="#F5F4F0", ink="#141414", muted="#6E6C67",
                  faint="#A3A09A", line="rgba(20,20,20,.09)", card="#FAFAF8",
                  tile="#FFFFFF", shadow="0 1px 2px rgba(0,0,0,.06)"),
    "dark": dict(page="#0d1117", paper="#121418", ink="#F2F1EE", muted="#9A988F",
                 faint="#6B6962", line="rgba(255,255,255,.09)", card="#141920",
                 tile="#1B2028", shadow="0 1px 2px rgba(0,0,0,.4)"),
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

# name, repo, icon, tag, one-liner, shot (per theme or shared), object-position
PROJECTS = [
    ("Tempro", "tempro", "tempro", "Windows",
     "Automatic time tracking that works out what you actually did.",
     {"light": "tempro-light", "dark": "tempro-dark"}, "0% 30%"),
    ("Claude Profile Switcher", "claude-switcher", "switcher", "Windows",
     "Several Claude Desktop accounts on one PC, all signed in at once.",
     "switcher", "50% 50%"),
    ("orvey", "orvey-plugin", "orvey", "MCP plugin",
     "Images and concepts right in Claude, ChatGPT, Claude Code and Codex.",
     {"light": "orvey-light", "dark": "orvey-dark"}, "50% 50%"),
    ("Fount", "font-grabber", "fount", "Web · Extension · CLI",
     "Find the fonts behind any website and save them as clean TTF/OTF.",
     {"light": "fount-light", "dark": "fount-dark"}, "0% 50%"),
    ("earn›line", "earnline", "earnline", "iPhone",
     "A calm income ledger for independent work.",
     {"light": "earnline-light", "dark": "earnline-dark"}, "fit"),
    ("Cutoff", "Cutoff", "cutoff", "iPhone",
     "A calm trainer for tournament preflop decisions. Study only.",
     "cutoff", "50% 50%"),
    ("Pinterest Plus Plus", "pinterest-plus-plus", "pinterest", "Chrome",
     "Copy and download pins in full quality, and resize the grid.",
     "pinterest", "fit"),
    ("Blackboard Text", "blackboard", "blackboard", "Web · PWA",
     "A quiet, local-first place to write and sketch.",
     "blackboard", "fit"),
]


def uri(rel: str) -> str:
    return (STUDIO / rel).resolve().as_uri()


def base_css(t: dict) -> str:
    return f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:transparent}}
body{{font-family:'Inter Tight',system-ui,sans-serif;color:{t['ink']};
  -webkit-font-smoothing:antialiased;font-feature-settings:'ss01','cv11'}}
.mono{{font-family:'JetBrains Mono',ui-monospace,monospace}}
"""


def hero_html(theme: str) -> str:
    t = THEMES[theme]
    tiles = "".join(
        f'<div class="app"><div class="ic {"pad" if k in ("fount",) else ""} {"board" if k == "blackboard" else ""}">'
        f'<img src="{uri(ICONS[k])}"></div></div>'
        for k in ("tempro", "switcher", "orvey", "fount",
                  "earnline", "cutoff", "pinterest", "blackboard"))
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>
{base_css(t)}
#c{{width:1200px;height:410px;border-radius:28px;background:{t['paper']};
  border:1px solid {t['line']};position:relative;overflow:hidden;
  display:grid;grid-template-columns:1fr 392px;padding:52px 64px 48px}}
.left{{display:flex;flex-direction:column}}
.eyebrow{{font-size:13px;letter-spacing:.14em;color:{t['muted']};text-transform:uppercase;
  display:flex;align-items:center;gap:12px}}
.eyebrow i{{display:block;width:22px;height:22px;border-left:2px solid {t['ink']};
  border-bottom:2px solid {t['ink']};transform:translateY(-2px)}}
h1{{font-size:50px;line-height:1.06;letter-spacing:-.035em;font-weight:600;margin-top:36px;
  white-space:nowrap}}
h1 span{{color:{t['faint']}}}
.sub{{font-size:19px;line-height:1.5;color:{t['muted']};margin-top:22px;max-width:560px;
  letter-spacing:-.005em}}
.foot{{margin-top:auto;font-size:13px;color:{t['muted']};display:flex;gap:28px;
  letter-spacing:.02em}}
.foot b{{color:{t['ink']};font-weight:500}}
.grid{{display:grid;grid-template-columns:repeat(4,80px);grid-auto-rows:80px;gap:24px;
  align-content:center;justify-content:end}}
.ic{{width:80px;height:80px;border-radius:19px;overflow:hidden;background:{t['tile']};
  box-shadow:{t['shadow']},0 0 0 1px {t['line']}}}
.ic img{{width:100%;height:100%;object-fit:cover;display:block}}
.ic.pad{{padding:17px;background:#FAFAF8}}
.ic.board{{background:#0B0B0D}}
.ic.pad img{{object-fit:contain}}
</style></head><body><div id="c">
<div class="left">
  <div class="eyebrow mono"><i></i>Angleford · designer who codes</div>
  <h1>I make calm, local-first tools<br><span>for the things that annoy me.</span></h1>
  <p class="sub">Windows apps, iPhone apps, browser extensions and plugins. Designed and built end to end, by one person.</p>
  <div class="foot mono"><span><b>angleford.co</b></span><span>t.me/<b>where_00</b></span></div>
</div>
<div class="grid">{tiles}</div>
</div></body></html>"""


def card_html(theme: str, p) -> str:
    t = THEMES[theme]
    name, _repo, icon, tag, line, shot, pos = p
    shot = shot[theme] if isinstance(shot, dict) else shot
    pad = "pad" if icon == "fount" else ("board" if icon == "blackboard" else "")
    shot_png = SHOTS / (shot + ".png")
    if pos == "fit":
        # Wide (3:1) heroes lose words under object-fit:cover; show them whole on
        # their own background colour instead (sampled inside the left edge).
        from PIL import Image
        im = Image.open(shot_png).convert("RGB")
        r, g, b = im.getpixel((24, im.height // 2))
        fit_css = (f"object-fit:contain;object-position:50% 50%;"
                   f"background:rgb({r},{g},{b})")
    else:
        fit_css = f"object-fit:cover;object-position:{pos}"
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>
{base_css(t)}
#c{{width:600px;height:352px;border-radius:22px;background:{t['card']};overflow:hidden;
  border:1px solid {t['line']};display:flex;flex-direction:column}}
.shot{{height:240px;border-bottom:1px solid {t['line']};overflow:hidden}}
.shot img{{width:100%;height:100%;{fit_css};display:block}}
.meta{{padding:20px 24px 0;display:flex;align-items:center;gap:12px}}
.ic{{width:34px;height:34px;border-radius:9px;overflow:hidden;flex:none;
  box-shadow:0 0 0 1px {t['line']};background:{t['tile']}}}
.ic img{{width:100%;height:100%;object-fit:cover;display:block}}
.ic.pad{{padding:6px;background:#FAFAF8}} .ic.pad img{{object-fit:contain}}
.ic.board{{background:#0B0B0D}}
.name{{font-size:21px;font-weight:600;letter-spacing:-.02em}}
.tag{{margin-left:auto;font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;
  color:{t['muted']};border:1px solid {t['line']};border-radius:999px;padding:5px 10px}}
.line{{padding:11px 24px 0 70px;font-size:15.5px;line-height:1.45;color:{t['muted']};
  letter-spacing:-.003em}}
</style></head><body><div id="c">
<div class="shot"><img src="{shot_png.as_uri()}"></div>
<div class="meta"><div class="ic {pad}"><img src="{uri(ICONS[icon])}"></div>
<div class="name">{html.escape(name)}</div><div class="tag mono">{html.escape(tag)}</div></div>
<div class="line">{html.escape(line)}</div>
</div></body></html>"""


def shoot(pg, markup: str, out: pathlib.Path) -> None:
    tmp = ROOT / "_src" / "_page.html"
    tmp.write_text(markup, encoding="utf-8")
    pg.goto(tmp.as_uri(), wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    pg.locator("#c").screenshot(path=str(out), omit_background=True)
    tmp.unlink()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1300, "height": 900}, device_scale_factor=2)
        for theme in THEMES:
            shoot(pg, hero_html(theme), OUT / f"hero-{theme}.png")
            for proj in PROJECTS:
                shoot(pg, card_html(theme, proj), OUT / f"card-{proj[1].lower()}-{theme}.png")
        b.close()
    print("built", len(list(OUT.glob("*.png"))), "images")


if __name__ == "__main__":
    main()
