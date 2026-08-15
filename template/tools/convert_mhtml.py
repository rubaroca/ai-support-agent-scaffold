#!/usr/bin/env python3
"""Convert MHTML web archives (*.mhtml) into Markdown (*.md).

This tool parses `.mhtml` files (MIME HTML archives, e.g. saved from Chromium
"Save as > Webpage, Single File"), extracts only the main article body, and
converts it to Markdown. Remote image references are kept as-is (as remote
URLs). By default each source `.mhtml` is deleted after a successful
conversion; use --keep-source to preserve them.

Usage
-----
    # Convert every .mhtml under the current directory (recursive):
    python convert_mhtml.py

    # Convert specific files and/or folders:
    python convert_mhtml.py "Soporte" "Cloud/Containers/foo.mhtml"

    # Preview without writing or deleting anything:
    python convert_mhtml.py --dry-run

    # Convert but keep the source .mhtml files:
    python convert_mhtml.py --keep-source

    # Re-convert files even if a .md already exists:
    python convert_mhtml.py --overwrite

Requirements
------------
    pip install markdownify beautifulsoup4 lxml

The `.md` file is written next to its source `.mhtml` with the same base name.
Content container is selected via the fallback chain:
    <main> -> <article> -> element with role="main" -> <body>
"""

from __future__ import annotations

import argparse
import email
import re
import sys
from email import policy
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    from markdownify import markdownify as html_to_md
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(
        "Missing dependency: %s\n"
        "Install with: pip install markdownify beautifulsoup4 lxml\n" % exc
    )
    raise SystemExit(1)


# Tags removed from the extracted content before Markdown conversion.
_STRIP_TAGS = ("script", "style", "nav", "header", "footer", "noscript", "form")

# Excess blank lines collapsed to at most one empty line.
_MULTI_BLANK = re.compile(r"\n{3,}")


def extract_html(mhtml_path: Path) -> str | None:
    """Return the decoded text/html part of an MHTML archive, or None.

    The transfer encoding (e.g. quoted-printable) is decoded to bytes, then
    decoded to text using the part's declared charset. Many MHTML archives omit
    the charset from the MIME part header (declaring it only in an HTML <meta>
    tag), so we fall back to UTF-8, then latin-1 as a last resort.
    """
    with mhtml_path.open("rb") as fh:
        msg = email.message_from_binary_file(fh, policy=policy.default)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            raw = part.get_payload(decode=True)  # bytes, transfer-decoded
            charset = part.get_content_charset()
            for enc in (charset, "utf-8", "latin-1"):
                if not enc:
                    continue
                try:
                    return raw.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode("utf-8", errors="replace")
    return None


def get_title(mhtml_path: Path, soup: BeautifulSoup) -> str | None:
    """Best-effort page title from <title>, else the MIME Subject header."""
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    with mhtml_path.open("rb") as fh:
        msg = email.message_from_binary_file(fh, policy=policy.default)
    subj = msg.get("Subject")
    return subj.strip() if subj else None


def select_content(soup: BeautifulSoup):
    """Pick the main content container via the fallback chain."""
    node = soup.find("main")
    if node is None:
        node = soup.find("article")
    if node is None:
        node = soup.find(attrs={"role": "main"})
    if node is None:
        node = soup.body
    return node or soup


def convert_html(html: str, title: str | None) -> str:
    """Extract the main body and convert it to Markdown text."""
    soup = BeautifulSoup(html, "lxml")
    content = select_content(soup)

    for tag in content.find_all(_STRIP_TAGS):
        tag.decompose()

    markdown = html_to_md(str(content), heading_style="ATX", bullets="-")
    markdown = _MULTI_BLANK.sub("\n\n", markdown).strip()

    # Ensure a top-level H1 exists.
    if title and not re.match(r"^#\s", markdown):
        markdown = f"# {title}\n\n{markdown}"

    return markdown + "\n"


def convert_file(
    mhtml_path: Path,
    *,
    overwrite: bool,
    keep_source: bool,
    dry_run: bool,
) -> str:
    """Convert one file. Returns a status string: converted|skipped|failed."""
    md_path = mhtml_path.with_suffix(".md")

    if md_path.exists() and not overwrite:
        print(f"  SKIP   {mhtml_path.name} (.md already exists)")
        return "skipped"

    html = extract_html(mhtml_path)
    if not html:
        print(f"  FAIL   {mhtml_path.name} (no text/html part found)")
        return "failed"

    soup = BeautifulSoup(html, "lxml")
    title = get_title(mhtml_path, soup)
    markdown = convert_html(html, title)

    if not markdown.strip():
        print(f"  FAIL   {mhtml_path.name} (empty content after conversion)")
        return "failed"

    if dry_run:
        print(f"  DRY    {mhtml_path.name} -> {md_path.name} ({len(markdown)} chars)")
        return "converted"

    md_path.write_text(markdown, encoding="utf-8")

    # Delete source only after a confirmed, non-empty .md file.
    if not keep_source:
        if md_path.exists() and md_path.stat().st_size > 0:
            mhtml_path.unlink()
            print(f"  OK     {mhtml_path.name} -> {md_path.name} (source deleted)")
        else:  # pragma: no cover - defensive
            print(f"  WARN   {mhtml_path.name} -> {md_path.name} (source kept: verify failed)")
    else:
        print(f"  OK     {mhtml_path.name} -> {md_path.name}")

    return "converted"


def gather_targets(paths: list[str]) -> list[Path]:
    """Expand CLI paths into a sorted list of .mhtml files."""
    targets: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            targets.update(p.rglob("*.mhtml"))
        elif p.is_file() and p.suffix.lower() == ".mhtml":
            targets.add(p)
        elif not p.exists():
            sys.stderr.write(f"warning: path not found: {raw}\n")
    return sorted(targets)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert *.mhtml web archives into *.md Markdown files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or folders to convert (default: current directory, recursive).",
    )
    parser.add_argument(
        "--keep-source",
        action="store_true",
        help="Do not delete the .mhtml source after conversion.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-convert even if the target .md already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen without writing or deleting files.",
    )
    args = parser.parse_args(argv)

    targets = gather_targets(args.paths or ["."])
    if not targets:
        print("No .mhtml files found.")
        return 0

    print(f"Found {len(targets)} .mhtml file(s).")
    counts = {"converted": 0, "skipped": 0, "failed": 0}
    for path in targets:
        try:
            status = convert_file(
                path,
                overwrite=args.overwrite,
                keep_source=args.keep_source,
                dry_run=args.dry_run,
            )
        except Exception as exc:  # noqa: BLE001 - keep going, report at end
            print(f"  FAIL   {path.name} ({exc})")
            status = "failed"
        counts[status] += 1

    print(
        "\nSummary: "
        f"{counts['converted']} converted, "
        f"{counts['skipped']} skipped, "
        f"{counts['failed']} failed."
    )
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
