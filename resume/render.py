#!/usr/bin/env python3
"""
render.py — Dynamic Resume Renderer
Usage:
  python render.py                    # render base resume to PDF
  python render.py --job <slug>       # render with per-job override to PDF
  python render.py --job <slug> --out custom-name.pdf
  python render.py --preview          # open in browser (no PDF, instant visual)
  python render.py --job <slug> --preview
"""

import argparse
import copy
import os
import sys
import webbrowser
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader


BASE_DIR = Path(__file__).parent
BASE_YAML = BASE_DIR / "resume-base.yaml"
OVERRIDES_DIR = BASE_DIR / "overrides"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATE_FILE = "template.html"


def load_yaml(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on any key present."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def render_html(data: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(BASE_DIR)))
    template = env.get_template(TEMPLATE_FILE)
    return template.render(**data)


def export_pdf(html: str, output_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="Letter",
            margin={"top": "0.5in", "bottom": "0.5in", "left": "0.6in", "right": "0.6in"},
            print_background=True,
        )
        browser.close()


def preview_in_browser(html: str, slug: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    preview_path = OUTPUT_DIR / f"resume-{slug}-preview.html"
    preview_path.write_text(html, encoding="utf-8")
    webbrowser.open(preview_path.as_uri())
    print(f"✓ Preview opened in browser ({preview_path.name})")


def main():
    parser = argparse.ArgumentParser(description="Render resume to PDF or browser preview.")
    parser.add_argument("--job", metavar="SLUG", help="Job slug for per-job override file")
    parser.add_argument("--out", metavar="FILENAME", help="Output PDF filename (optional)")
    parser.add_argument("--preview", action="store_true", help="Open in browser instead of exporting PDF")
    args = parser.parse_args()

    # Load base
    if not BASE_YAML.exists():
        print(f"Error: {BASE_YAML} not found.", file=sys.stderr)
        sys.exit(1)
    data = load_yaml(BASE_YAML)

    # Apply override if --job given
    if args.job:
        override_path = OVERRIDES_DIR / f"resume-{args.job}.yaml"
        if not override_path.exists():
            print(f"Error: override file not found: {override_path}", file=sys.stderr)
            sys.exit(1)
        override = load_yaml(override_path)
        data = deep_merge(data, override)
        slug = args.job
    else:
        slug = "base"

    # Render HTML
    html = render_html(data)

    # Preview or export
    if args.preview:
        preview_in_browser(html, slug)
    else:
        OUTPUT_DIR.mkdir(exist_ok=True)
        filename = args.out or f"resume-{slug}.pdf"
        output_path = OUTPUT_DIR / filename
        export_pdf(html, output_path)
        print(f"✓ Exported {output_path}")


if __name__ == "__main__":
    main()
