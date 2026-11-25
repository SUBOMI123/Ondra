"""Inline Tabler icons, the logo and the call waveform into a prototype page.
Usage: python3 design/prototypes/build.py design/prototypes/system.src.html design/prototypes/system.html
Icons come from apps/site/node_modules/@tabler/icons (run npm install in apps/site first)."""
import re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
ICONS = ROOT / "apps/site/node_modules/@tabler/icons/icons"
src, out = sys.argv[1], sys.argv[2]
html = open(src).read()

def svg(name, cls, filled=False, style=""):
    p = ICONS / ("filled" if filled else "outline") / f"{name}.svg"
    s = p.read_text()
    s = re.sub(r'\s(width|height|class)="[^"]*"', "", s)
    s = s.replace("<svg", f'<svg class="{cls}" aria-hidden="true" focusable="false"' + (f' style="{style}"' if style else ""), 1)
    return re.sub(r"\s+", " ", s).replace("> <", "><").strip()

def rep(m):
    kind, name = m.group(1), m.group(2)
    if name == "crown-vip":
        return svg("crown", "i", filled=True, style="color:var(--vip)")
    return svg(name, {"i": "i", "i20": "i i20", "iBig": "big"}[kind])

html = re.sub(r"\{\{(i|i20|iBig):([a-z0-9-]+)\}\}", rep, html)
logo = (ROOT / "design/brand/ondra-logo-on-dark.svg").read_text().strip()
html = html.replace("{{logo}}", logo)
heights = [6, 12, 9, 16, 11, 7, 14, 18, 10, 6, 13, 8, 15, 9, 5]
html = html.replace("{{wave}}", "".join(f'<i style="height:{h}px"></i>' for h in heights))
left = re.findall(r"\{\{[^}]+\}\}", html)
assert not left, left
open(out, "w").write(html)
print("ok", len(html))
