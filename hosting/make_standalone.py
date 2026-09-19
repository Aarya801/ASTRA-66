"""Wrap the generated page in a full HTML document for standalone hosting.

ASTRA-66_Engineering_Package.html is authored as *page content* (no <!doctype>, <html>,
<head> or <body> tags). This script adds a minimal document shell so the standalone page
renders in standards mode with a mobile viewport and zero body margin. The page file itself
is copied in unchanged.

Usage (from the project root):
    python hosting/make_standalone.py                 # -> dist/index.html
    python hosting/make_standalone.py --out public/index.html
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Document shell: charset + viewport meta and a small reset
# (light color-scheme, zero body margin, 14px system font on an off-white ground,
# img max-width, [hidden] rule). The page's own CSS overrides body font and background.
HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{color-scheme:light}
body{margin:0;font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:#f7f7f5}
img{max-width:100%}
[hidden]{display:none!important}
</style>
</head>
<body>
"""
TAIL = "\n</body>\n</html>\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(ROOT / "documentation" / "ASTRA-66_Engineering_Package.html"))
    ap.add_argument("--out", default=str(ROOT / "dist" / "index.html"))
    args = ap.parse_args()
    src, out = Path(args.src), Path(args.out)
    body = src.read_text(encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(HEAD + body + TAIL, encoding="utf-8", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
