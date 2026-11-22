"""Preview README.md the way GitHub shows it, without pushing.

    python -I _src/preview.py          # writes .readme-preview/preview-{light,dark}.html
    python -I _src/preview.py --shots  # also screenshots them (needs Playwright)

The HTML comes from GitHub's own Markdown API (through `gh`), wrapped in GitHub's
stylesheet, so <details>, <picture>, <sup> and spacing match the real page. The two
files open from disk by double click.
"""
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / ".readme-preview"
CACHE = ROOT / "_src" / "cache" / "preview"
PAGE = {"light": ("#ffffff", "#d1d9e0", "#59636e"), "dark": ("#0d1117", "#3d444d", "#9198a1")}


def css(theme: str) -> str:
    f = CACHE / f"gh-{theme}.css"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.8.1/github-markdown-{theme}.min.css"
        f.write_bytes(urllib.request.urlopen(url, timeout=60).read())
    return f.read_text(encoding="utf-8")


def render() -> str:
    out = subprocess.run(
        ["gh", "api", "markdown", "-f", "mode=gfm", "-F", f"text=@{ROOT / 'README.md'}"],
        capture_output=True, check=True)
    return out.stdout.decode("utf-8")


def page(body: str, theme: str) -> str:
    bg, border, muted = PAGE[theme]
    # <picture> follows the system theme; pin it to the theme of this file instead.
    if theme == "dark":
        body = body.replace('media="(prefers-color-scheme: dark)"', 'media="all"')
    else:
        body = re.sub(r'<source media="\(prefers-color-scheme: dark\)"[^>]*>', "", body)
    body = body.replace('src="assets/', 'src="../assets/').replace('srcset="assets/', 'srcset="../assets/')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Profile preview ({theme})</title>
<style>{css(theme)}
html,body{{margin:0;background:{bg}}}
.wrap{{max-width:896px;margin:24px auto;padding:0 16px;box-sizing:border-box}}
.box{{border:1px solid {border};border-radius:6px;padding:24px}}
.file{{font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;color:{muted};margin:0 0 16px}}
@media (max-width:600px){{.wrap{{margin:12px auto}}.box{{padding:16px}}}}
</style></head><body><div class="wrap"><div class="box">
<p class="file">Piwqust / README.md</p>
<article class="markdown-body">{body}</article>
</div></div></body></html>"""


def shots() -> None:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        for theme in PAGE:
            url = (OUT / f"preview-{theme}.html").as_uri()
            for name, width, scale in (("desktop", 1012, 2), ("mobile", 390, 3)):
                ctx = b.new_context(viewport={"width": width, "height": 900},
                                    device_scale_factor=scale, color_scheme=theme)
                pg = ctx.new_page()
                pg.goto(url)
                pg.wait_for_timeout(3600)   # the intro has played, the first caption is up
                pg.screenshot(path=str(OUT / f"{theme}-{name}.png"), full_page=True)
                if name == "desktop":
                    for i in (0, 3, 7):
                        pg.locator("details").nth(i).evaluate("d => d.open = true")
                    pg.wait_for_timeout(1500)
                    pg.screenshot(path=str(OUT / f"{theme}-{name}-open.png"), full_page=True)
                ctx.close()
        b.close()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    body = render()
    for theme in PAGE:
        (OUT / f"preview-{theme}.html").write_text(page(body, theme), encoding="utf-8", newline="\n")
    print("wrote", OUT / "preview-light.html", "and preview-dark.html")
    if "--shots" in sys.argv:
        shots()
        print("screenshots in", OUT)


if __name__ == "__main__":
    main()
