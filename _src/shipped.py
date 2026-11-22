"""Keep the "Recently shipped" line in README.md current.

    python -I _src/shipped.py

Reads the latest release of every project in `_src/projects.json` and rewrites the
text between the `shipped:start` and `shipped:end` comments. Standard library only,
so the daily workflow (.github/workflows/shipped.yml) needs no setup. Dates are
absolute: if the workflow ever stops, the line stays true.
"""
import datetime
import json
import os
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "_src" / "projects.json").read_text(encoding="utf-8"))
START, END = "<!-- shipped:start -->", "<!-- shipped:end -->"
SHOW = 4


def latest(repo: str):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{DATA['owner']}/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-shipped"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:  # no releases yet
            return None
        raise


def main() -> None:
    items = [(p["name"], p["repo"]) for p in DATA["projects"]]
    items += [(a["name"], a["releases"]) for a in DATA.get("also", []) if a.get("releases")]
    found = []
    for name, repo in items:
        rel = latest(repo)
        if rel:
            when = datetime.datetime.fromisoformat(rel["published_at"].replace("Z", "+00:00"))
            found.append((when, name, rel["tag_name"].lstrip("v"), rel["html_url"]))
    found.sort(reverse=True)
    this_year = datetime.datetime.now(datetime.timezone.utc).year
    parts = []
    for when, name, version, url in found[:SHOW]:
        date = f"{when:%b} {when.day}" + ("" if when.year == this_year else f", {when.year}")
        parts.append(f'<a href="{url}">{name} {version}</a>, {date}')
    line = "<sub>Recently shipped: " + " &nbsp;·&nbsp; ".join(parts) + "</sub>" if parts else ""

    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    a, b = text.index(START) + len(START), text.index(END)
    new = text[:a] + "\n" + line + "\n" + text[b:]
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
        print("updated:", line)
    else:
        print("no change")


if __name__ == "__main__":
    main()
