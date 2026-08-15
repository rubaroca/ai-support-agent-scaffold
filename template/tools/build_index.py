#!/usr/bin/env python3
"""Generate the root README.md index from doc frontmatter.

Scans every knowledge-base ``*.md`` under ``docs/`` (excluding README.md,
tools/, .opencode/), reads its YAML frontmatter, and writes a categorized index
with links and one-line summaries. Re-run whenever docs are added, renamed, or
removed.

Usage
-----
    python tools/build_index.py --root .
    python tools/build_index.py --root . --check   # exit 1 if README is stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

import yaml

EXCLUDE_PARTS = {".opencode", "tools"}

HEADER = """# {{PROJECT_NAME}} — Knowledge Base

This repository is a **documentation-only knowledge base** for supporting
{{PROJECT_NAME}} ({{ORG}}). It is designed to be used by **OpenCode as an AI
Support Agent**, which treats these documents as its primary source of truth
when answering questions, troubleshooting incidents, and explaining procedures.

- Documentation language: **{{DOC_LANG}}**.
- The agent must **search this knowledge base before answering** project-specific
  questions and must **cite the documents** it used.
- The agent must **never invent** project-specific facts (resource names, URLs,
  permissions, configuration values, procedures). If something is not documented,
  it says so explicitly.

See [`AGENTS.md`](AGENTS.md) for the full agent operating rules. Tooling lives in
[`tools/`](tools/).

> **Constraint:** This repository contains **documentation only** — no
> application/infrastructure source code, secrets, credentials, tokens, private
> keys, or real sensitive configuration values.

"""

TOOLS_SECTION = """
## Tools

Utility scripts in [`tools/`](tools/):

- `convert_mhtml.py` — convert `*.mhtml` web archives into `*.md`.
- `add_frontmatter.py` — normalize doc headings/filenames and add YAML frontmatter.
- `build_index.py` — regenerate this `README.md` index from doc frontmatter.

Run `build_index.py` after adding, renaming, or removing documents to keep this
index in sync.

## Knowledge-base maintenance backlog

Known gaps and follow-ups for the `maintainer` agent:

- _(none yet — add documentation gaps, stale docs, or duplicate candidates here)_
"""


def link(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return "/".join(quote(part) for part in rel.split("/"))


def load(root: Path):
    docs = []
    for p in sorted(root.rglob("*.md")):
        if set(p.parts) & EXCLUDE_PARTS or p.name == "README.md":
            continue
        text = p.read_text(encoding="utf-8")
        meta = {}
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                try:
                    meta = yaml.safe_load(text[3:end]) or {}
                except yaml.YAMLError:
                    meta = {}
        docs.append((p, meta))
    return docs


def build(root: Path) -> str:
    docs = load(root)
    by_cat: dict[str, list] = {}
    for p, meta in docs:
        cat = meta.get("category") or p.parent.relative_to(root).as_posix()
        by_cat.setdefault(cat, []).append((p, meta))

    out = [HEADER]
    out.append(f"## Documentation index ({len(docs)} documents)\n")

    for cat in sorted(by_cat):
        entries = sorted(by_cat[cat], key=lambda e: (e[1].get("title") or e[0].stem).lower())
        out.append(f"### {cat}\n")
        for p, meta in entries:
            title = meta.get("title") or p.stem
            summary = meta.get("summary") or ""
            updated = meta.get("last_updated")
            href = link(p, root)
            line = f"- [{title}]({href})"
            if summary:
                line += f" — {summary}"
            if updated:
                line += f" _(updated {updated})_"
            out.append(line)
        out.append("")

    out.append(TOOLS_SECTION)
    return "\n".join(out).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate root README.md index.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", action="store_true", help="Exit 1 if README is out of date.")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    content = build(root)
    readme = root / "README.md"

    if args.check:
        current = readme.read_text(encoding="utf-8") if readme.exists() else ""
        if current != content:
            print("README.md is out of date. Run: python tools/build_index.py")
            return 1
        print("README.md is up to date.")
        return 0

    readme.write_text(content, encoding="utf-8")
    print(f"Wrote {readme} ({len(content)} bytes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
