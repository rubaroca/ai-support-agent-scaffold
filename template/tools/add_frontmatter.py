#!/usr/bin/env python3
"""Normalize the {{PROJECT_NAME}} knowledge-base Markdown docs.

For every `*.md` under the repository root this tool:

1. Strips a configurable boilerplate title suffix (see BOILERPLATE) from the
   first H1 heading.
2. Removes an immediately-duplicated H1 (a conversion artifact).
3. Derives metadata and prepends a YAML frontmatter block:
     title, category, source_domain, last_updated, tags, summary, language
4. Renames the file to drop the same boilerplate suffix from its filename.

It is idempotent: docs that already start with a `---` frontmatter block are
skipped (unless --force). Renaming only happens when --rename is passed.

Configure the project-specific constants near the top of this file
(BOILERPLATE, PREFERRED_HOSTS, DATE_RE, TAG_KEYWORDS, FOLDER_TAGS) and the
`language` value written into the frontmatter (DOC_LANG).

Usage
-----
    python tools/add_frontmatter.py --root . --rename        # apply
    python tools/add_frontmatter.py --root . --dry-run       # preview

Metadata notes
--------------
* ``source_domain`` records the primary documentation host referenced in the
  doc (e.g. ``{{SOURCE_DOMAIN}}``). A full ``source_url`` is intentionally NOT
  fabricated when the canonical page URL is not recoverable.
* ``last_updated`` is parsed from the inline "last updated" line (see DATE_RE)
  and converted from DD-MM-YYYY to ISO YYYY-MM-DD when possible.
* ``summary`` is the first substantive paragraph, trimmed; ``tags`` are derived
  from the folder path and title keywords. Both are heuristic and meant to be
  reviewed.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

# Boilerplate suffix stripped from H1 headings and filenames (project-specific).
# Set to the common title suffix your source pages carry, or leave empty to
# disable stripping. Example: ". My Org. Documentation Portal".
BOILERPLATE = "{{BOILERPLATE_SUFFIX}}"

# Primary documentation hosts, in priority order, used to pick source_domain.
# Add the hosts your documentation is captured from, most preferred first.
PREFERRED_HOSTS = (
    "{{SOURCE_DOMAIN}}",
)

# Inline "last updated" line pattern. Adjust the label to your source language
# (e.g. "Last updated", "Data d'actualitzacio", "Fecha de actualizacion").
# Captures a DD-MM-YYYY date on the same or next line.
DATE_RE = re.compile(r"{{DATE_LABEL}}[^\n]*\n?[^\d]*(\d{2})-(\d{2})-(\d{4})")
URL_RE = re.compile(r"https?://[^\s)\]]+")
H1_RE = re.compile(r"^# (.+?)\s*$", re.MULTILINE)

# Simple, conservative tag keywords -> tag mapping (matched against the title,
# case-insensitive). Extend with keywords relevant to your knowledge base.
TAG_KEYWORDS = {
    # "terraform": "terraform",
    # "kubernetes": "kubernetes",
}

# Folder name -> base category tag. Extend with your top-level folders.
FOLDER_TAGS = {
    # "Support": "support",
    # "Operations": "operations",
}


def yaml_escape(value: str) -> str:
    """Quote a scalar for YAML, escaping embedded double quotes."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def clean_title(raw: str) -> str:
    title = raw.strip()
    if title.endswith(BOILERPLATE):
        title = title[: -len(BOILERPLATE)].strip()
    return title


def category_of(path: Path, root: Path) -> str:
    rel = path.relative_to(root).parts
    return "/".join(rel[:-1]) if len(rel) > 1 else rel[0]


def pick_source_domain(text: str) -> str | None:
    hosts = Counter()
    for url in URL_RE.findall(text):
        host = urlparse(url).netloc
        if host:
            hosts[host] += 1
    if not hosts:
        return None
    for preferred in PREFERRED_HOSTS:
        if preferred in hosts:
            return preferred
    return hosts.most_common(1)[0][0]


def parse_last_updated(text: str) -> str | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    dd, mm, yyyy = m.groups()
    return f"{yyyy}-{mm}-{dd}"


def derive_tags(title: str, category: str) -> list[str]:
    tags: list[str] = []
    folder = category.split("/")[-1]
    base = FOLDER_TAGS.get(folder)
    if base:
        tags.append(base)
    low = title.lower()
    for kw, tag in TAG_KEYWORDS.items():
        if kw in low and tag not in tags:
            tags.append(tag)
    return tags[:6]


def first_paragraph(body: str) -> str:
    """First substantive paragraph after the H1, collapsed to one line."""
    lines = body.splitlines()
    # skip past the first H1
    idx = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            idx = i + 1
            break
    buf: list[str] = []
    for ln in lines[idx:]:
        s = ln.strip()
        if not s:
            if buf:
                break
            continue
        # Skip structural / non-prose lines (headings, tables, code fences,
        # images, list items, blockquotes, horizontal rules, numbered lists,
        # and the inline "last updated" metadata line).
        if (
            s.startswith(("#", "|", "```", "![", "- ", "* ", ">"))
            or re.match(r"^\d+\.", s)
            or re.fullmatch(r"[-=_*]{3,}", s)
            or re.match(r"(?i){{DATE_LABEL}}", s)
            or re.fullmatch(r"[\u00a0\s]*\d{2}-\d{2}-\d{4}[\u00a0\s]*", s)
        ):
            if buf:
                break
            continue
        buf.append(s)
    text = " ".join(buf)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # unwrap links
    text = re.sub(r"[*_`]", "", text)  # drop inline emphasis marks
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 240:
        text = text[:237].rsplit(" ", 1)[0] + "..."
    return text


FRONTMATTER_RE = re.compile(r"^\ufeff?---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def has_frontmatter(text: str) -> bool:
    return text.lstrip().startswith("---")


def strip_frontmatter(text: str) -> str:
    """Remove a leading YAML frontmatter block, if present."""
    return FRONTMATTER_RE.sub("", text, count=1).lstrip("\n")


def process(path: Path, root: Path, *, force: bool) -> tuple[str, str] | None:
    """Return (new_title, rename_target_name) or None if skipped."""
    text = path.read_text(encoding="utf-8")
    if has_frontmatter(text):
        if not force:
            return None
        text = strip_frontmatter(text)

    m = H1_RE.search(text)
    raw_title = m.group(1) if m else path.stem
    title = clean_title(raw_title)

    # Rewrite the first H1 to the clean title, guaranteeing a blank line after.
    if m:
        start, end = m.span()
        after = text[end:]
        after = "\n" + after.lstrip("\n")  # normalize spacing below H1
        text = text[:start] + f"# {title}" + after

    # Collapse a duplicated H1 (same title), even if breadcrumb lines sit
    # between the two occurrences (a conversion artifact). Keep the first H1
    # and drop everything up to and including the second identical H1.
    esc = re.escape(title)
    dup_between = re.compile(
        r"(# " + esc + r"\n)(.*?\n)?# " + esc + r"(?:" + re.escape(BOILERPLATE) + r")?\s*\n",
        re.DOTALL,
    )

    def _dedup(mm: re.Match) -> str:
        middle = mm.group(2) or ""
        # Only strip the middle if it is short breadcrumb/nav noise.
        if middle.count("\n") <= 6:
            return mm.group(1)
        return mm.group(0)

    text = dup_between.sub(_dedup, text, count=1)

    category = category_of(path, root)
    source_domain = pick_source_domain(text)
    last_updated = parse_last_updated(text)
    tags = derive_tags(title, category)
    summary = first_paragraph(text)

    fm_lines = ["---", f"title: {yaml_escape(title)}", f"category: {yaml_escape(category)}"]
    if source_domain:
        fm_lines.append(f"source_domain: {yaml_escape(source_domain)}")
    if last_updated:
        fm_lines.append(f"last_updated: {yaml_escape(last_updated)}")
    if tags:
        fm_lines.append("tags: [" + ", ".join(yaml_escape(t) for t in tags) + "]")
    if summary:
        fm_lines.append(f"summary: {yaml_escape(summary)}")
    fm_lines.append('language: "{{DOC_LANG}}"')
    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines) + "\n\n"

    new_text = frontmatter + text.lstrip("\n")

    # Determine rename target (strip boilerplate from the filename).
    stem = path.stem
    if stem.endswith(BOILERPLATE):
        stem = stem[: -len(BOILERPLATE)].strip()
    new_name = stem + path.suffix

    return (new_text, new_name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Normalize KB docs: clean H1, add frontmatter, rename.")
    ap.add_argument("--root", default=".", help="Repository root to scan.")
    ap.add_argument("--rename", action="store_true", help="Rename files to strip boilerplate suffix.")
    ap.add_argument("--force", action="store_true", help="Reprocess docs that already have frontmatter.")
    ap.add_argument("--dry-run", action="store_true", help="Report only; do not write or rename.")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    md_files = [
        p for p in root.rglob("*.md")
        if ".opencode" not in p.parts and "tools" not in p.parts
        and p.name not in ("README.md", "AGENTS.md")
    ]
    md_files.sort()

    processed = skipped = renamed = 0
    collisions: list[str] = []

    for path in md_files:
        result = process(path, root, force=args.force)
        if result is None:
            skipped += 1
            print(f"  SKIP  {path.relative_to(root)} (already has frontmatter)")
            continue

        new_text, new_name = result
        target = path.with_name(new_name)

        if args.dry_run:
            action = "rename->" + new_name if args.rename and target != path else "in-place"
            print(f"  DRY   {path.relative_to(root)}  [{action}]")
            processed += 1
            continue

        path.write_text(new_text, encoding="utf-8")
        processed += 1

        if args.rename and target != path:
            if target.exists():
                collisions.append(str(target.relative_to(root)))
                print(f"  WARN  collision, not renaming: {target.relative_to(root)}")
            else:
                path.rename(target)
                renamed += 1
                print(f"  OK    {path.name}  ->  {new_name}")
        else:
            print(f"  OK    {path.relative_to(root)}")

    print(
        f"\nSummary: {processed} processed, {skipped} skipped, "
        f"{renamed} renamed, {len(collisions)} collisions."
    )
    if collisions:
        print("Collisions:")
        for c in collisions:
            print("  -", c)
    return 1 if collisions else 0


if __name__ == "__main__":
    raise SystemExit(main())
