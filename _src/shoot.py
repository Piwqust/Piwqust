"""Rasterize each project's README hero so the profile cards can reuse it."""
import pathlib, sys
from playwright.sync_api import sync_playwright
S = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).parent / "shots"
SRC = {
  "tempro-light": "tempro/docs/assets/readme-hero-light.svg",
  "tempro-dark": "tempro/docs/assets/readme-hero-dark.svg",
  "switcher": "claude-switcher/docs/images/hero.png",
  "orvey-light": "orvey-plugin/docs/readme/hero-light.svg",
  "orvey-dark": "orvey-plugin/docs/readme/hero-dark.svg",
  "fount-light": "font-grabber/docs/readme/hero-light.svg",
  "fount-dark": "font-grabber/docs/readme/hero-dark.svg",
  "earnline-light": "earnline/docs/readme/hero-light.svg",
  "earnline-dark": "earnline/docs/readme/hero-dark.svg",
  "cutoff": "Cutoff/docs/readme/hero.svg",
  "pinterest": "pinterest-plus-plus/docs/readme/hero.svg",
  "blackboard": "blackboard/docs/readme/hero.svg",
  "lintsense-dark": "lintsense/docs/readme/hero-dark.svg",
}
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=2)
    for name, rel in SRC.items():
        f = S / rel
        if not f.exists():
            print("missing", rel); continue
        tmp = OUT / "_page.html"
        tmp.write_text(f'<html><body style="margin:0;background:transparent"><img id=i src="{f.as_uri()}" style="width:1200px;display:block"></body></html>')
        pg.goto(tmp.as_uri(), wait_until="networkidle")
        pg.locator("#i").screenshot(path=str(OUT / f"{name}.png"), omit_background=True)
        print(name, pg.evaluate("[document.getElementById('i').naturalWidth, document.getElementById('i').naturalHeight]"))
    b.close()
