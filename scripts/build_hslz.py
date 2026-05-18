#!/usr/bin/env python3
"""Build .hslz archives for the HSL2 and HSL3 deliverables.

An .hslz file is a renamed ZIP containing the .hsl plus optional help
files. Per the SDK doc (HSL/HSLZ/en/hslz_structure.html):

  <ID>_<Name>.hsl              the logic node
  <SPR>-log<ID>.html           language-prefixed help (SPR in DE|EN|FR|IT)
  log<ID>.html                 single help (uses Experte UI language)
  <ID>/hsupload/*.*            optional companion files uploaded to HS
  style.css                    optional shared stylesheet referenced by help

The source layout in this repo keeps help under help/{en,de}/log24815.html
which references ../style.css. This script flattens that into the
HSLZ-required EN-log24815.html / DE-log24815.html and rewrites the
stylesheet href from "../style.css" to "style.css".

Usage:
    python3 scripts/build_hslz.py
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent

LBS_ID = "24815"

HELP_SOURCES = [
    ("EN", ROOT / "help" / "en" / f"log{LBS_ID}.html"),
    ("DE", ROOT / "help" / "de" / f"log{LBS_ID}.html"),
]
STYLE_CSS = ROOT / "help" / "style.css"


def rewrite_stylesheet_href(html_text: str) -> str:
    """In source the help files reference ../style.css; in the HSLZ all
    files are siblings so the path is just style.css."""
    return html_text.replace('href="../style.css"', 'href="style.css"')


def build_hslz(out_path: Path, hsl_source: Path, hsl_name_in_archive: str,
               include_help: bool = True) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(hsl_source, arcname=hsl_name_in_archive)
        if include_help:
            for lang, src in HELP_SOURCES:
                if not src.exists():
                    continue
                text = src.read_text(encoding="utf-8")
                text = rewrite_stylesheet_href(text)
                z.writestr(f"{lang}-log{LBS_ID}.html", text)
            if STYLE_CSS.exists():
                z.write(STYLE_CSS, arcname="style.css")
    print(f"wrote {out_path.relative_to(ROOT)}  ({out_path.stat().st_size} bytes)")


def list_archive(path: Path) -> Iterable[str]:
    with zipfile.ZipFile(path) as z:
        return z.namelist()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-help", action="store_true",
                        help="Build .hslz without bundled help files.")
    args = parser.parse_args()

    targets = [
        (
            ROOT / "projects/airtame_emergency/release"
                 / f"{LBS_ID}_AirtameEmergencyAlert.hsl",
            ROOT / "projects/airtame_emergency/release"
                 / f"{LBS_ID}_AirtameEmergencyAlert.hslz",
            f"{LBS_ID}_AirtameEmergencyAlert.hsl",
        ),
        (
            ROOT / "projects/airtame_emergency_hsl3"
                 / f"{LBS_ID}_airtame_emergency.hsl",
            ROOT / "projects/airtame_emergency_hsl3"
                 / f"{LBS_ID}_airtame_emergency.hslz",
            f"{LBS_ID}_airtame_emergency.hsl",
        ),
    ]
    for hsl, hslz, arcname in targets:
        if not hsl.exists():
            print(f"SKIP {hslz.name}: source missing ({hsl})")
            continue
        build_hslz(hslz, hsl, arcname, include_help=not args.no_help)
        for entry in list_archive(hslz):
            print(f"  - {entry}")


if __name__ == "__main__":
    main()
