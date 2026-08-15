#!/usr/bin/env python3
"""Scaffold a new AI Support Agent knowledge-base project.

Copies the `template/` tree to a destination directory and replaces the
`{{PLACEHOLDER}}` tokens with the values you provide, producing a ready-to-use
OpenCode knowledge-base project (AGENTS.md, support/maintainer agents, tools,
and an example doc).

Usage
-----
    python init_project.py --dest ../my-new-kb \\
        --project-name "My Project" --org "My Org" \\
        --doc-lang es --source-domain docs.myorg.com [--run-index]

You can also pass a JSON config file (see scaffold.config.example.json):

    python init_project.py --dest ../my-new-kb --config my.json

CLI flags override values from --config. After generation, remember to restart
OpenCode so it loads the new agent definitions.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "template"

# placeholder token -> (CLI dest / config key, human description, default)
FIELDS = {
    "PROJECT_NAME": ("project_name", "Human-readable project name", None),
    "ORG": ("org", "Organization name", None),
    "DOC_LANG": ("doc_lang", "Documentation language code (e.g. ca, es, en)", "en"),
    "SOURCE_DOMAIN": ("source_domain", "Primary source host of the docs", ""),
    "EXAMPLE_DOC": ("example_doc", "Example doc path used in citations", "docs/EXAMPLE.md"),
    "BOILERPLATE_SUFFIX": (
        "boilerplate_suffix",
        "Title suffix stripped from H1s/filenames (may be empty)",
        "",
    ),
    "DATE_LABEL": (
        "date_label",
        "Inline 'last updated' label used to parse dates",
        "Last updated",
    ),
}

# File extensions whose content gets placeholder substitution.
TEXT_SUFFIXES = {".md", ".py", ".json", ".yaml", ".yml", ".txt", ".gitignore"}


def load_values(args) -> dict[str, str]:
    cfg = {}
    if args.config:
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))

    values: dict[str, str] = {}
    missing = []
    for token, (key, desc, default) in FIELDS.items():
        cli_val = getattr(args, key, None)
        val = cli_val if cli_val is not None else cfg.get(key, default)
        if val is None:
            missing.append(f"  --{key.replace('_', '-')}  ({desc})")
        else:
            values[token] = str(val)
    if missing:
        sys.stderr.write("Missing required values:\n" + "\n".join(missing) + "\n")
        raise SystemExit(2)
    return values


def substitute(text: str, values: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        token = m.group(1)
        return values.get(token, m.group(0))

    return re.sub(r"\{\{([A-Z_]+)\}\}", repl, text)


def copy_and_fill(dest: Path, values: dict[str, str]) -> int:
    files = 0
    for src in sorted(TEMPLATE_DIR.rglob("*")):
        rel = src.relative_to(TEMPLATE_DIR)
        target = dest / rel
        if src.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() in TEXT_SUFFIXES or src.name == ".gitignore":
            content = src.read_text(encoding="utf-8")
            target.write_text(substitute(content, values), encoding="utf-8")
        else:
            shutil.copy2(src, target)
        files += 1
    return files


def check_no_placeholders(dest: Path) -> list[str]:
    leftovers = []
    for p in dest.rglob("*"):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
            if re.search(r"\{\{[A-Z_]+\}\}", p.read_text(encoding="utf-8")):
                leftovers.append(p.relative_to(dest).as_posix())
    return leftovers


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new AI Support Agent KB project.")
    ap.add_argument("--dest", required=True, help="Destination directory (must not already exist or be empty).")
    ap.add_argument("--config", help="Optional JSON config file with the field values.")
    for token, (key, desc, default) in FIELDS.items():
        ap.add_argument(f"--{key.replace('_', '-')}", dest=key, help=desc)
    ap.add_argument("--run-index", action="store_true", help="Run build_index.py in the destination after generating.")
    ap.add_argument("--force", action="store_true", help="Allow writing into a non-empty destination.")
    args = ap.parse_args(argv)

    dest = Path(args.dest).resolve()
    if dest.exists() and any(dest.iterdir()) and not args.force:
        sys.stderr.write(f"Destination is not empty: {dest}\nUse --force to write anyway.\n")
        return 2

    values = load_values(args)
    dest.mkdir(parents=True, exist_ok=True)

    files = copy_and_fill(dest, values)
    print(f"Generated {files} files in {dest}")

    leftovers = check_no_placeholders(dest)
    if leftovers:
        sys.stderr.write("WARNING: unresolved placeholders remain in:\n")
        for f in leftovers:
            sys.stderr.write(f"  - {f}\n")

    if args.run_index:
        script = dest / "tools" / "build_index.py"
        print("Running build_index.py ...")
        subprocess.run([sys.executable, str(script), "--root", str(dest)], check=False)

    print("\nDone. Next steps:")
    print(f"  1. cd {dest}")
    print("  2. Add your documents under docs/ and run the tools (see README.md).")
    print("  3. Restart OpenCode so it loads the new agent definitions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
