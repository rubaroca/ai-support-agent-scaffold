---
title: "Example document"
category: "Support"
source_domain: "{{SOURCE_DOMAIN}}"
last_updated: "2026-01-01"
tags: ["example", "getting-started"]
summary: "Example knowledge-base document showing the expected frontmatter and section structure. Replace it with real content or delete it once you add your own docs."
language: "{{DOC_LANG}}"
---

# Example document

## Context / Problem

This is a placeholder document included by the scaffold so the index generator
has something to list. It demonstrates the frontmatter and the recommended
section structure defined in `AGENTS.md` §7.

## Procedure / Solution

1. Add your real documents under `docs/` (in one or more category folders).
2. Run `python tools/add_frontmatter.py --root . --dry-run` to preview
   normalization, then without `--dry-run` to apply.
3. Run `python tools/build_index.py --root .` to regenerate `README.md`.
4. Delete this example once you have real content.

## Validation

- `README.md` lists your documents grouped by `category`.
- Every doc under `docs/` starts with a valid YAML frontmatter block.

## Assumptions and limitations

- This document contains no project-specific facts; it is illustrative only.

## Related documents

- See [`README.md`](../README.md) for the full index.
