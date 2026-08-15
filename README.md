# AI Support Agent — Knowledge-Base Scaffold

A reusable scaffold for building **OpenCode AI Support Agent** knowledge-base
projects: a documentation-only repository that OpenCode uses as its **primary
source of truth** to answer questions, troubleshoot incidents, and explain
procedures — with two agents (`support` = read-only, `maintainer` = write-enabled).

## What it generates

```
<your-project>/
├── AGENTS.md              # global operating rules for every agent
├── opencode.json          # default_agent: support; loads AGENTS.md
├── README.md              # generated index of all docs (via build_index.py)
├── .opencode/
│   └── agent/
│       ├── support.md     # read-only Q&A agent (edit/bash denied)
│       └── maintainer.md   # write-enabled "document the solution" agent
├── tools/
│   ├── convert_mhtml.py   # convert *.mhtml web archives to *.md
│   ├── add_frontmatter.py # normalize headings/filenames + add YAML frontmatter
│   └── build_index.py     # regenerate README.md index from frontmatter
└── docs/
    └── EXAMPLE.md         # sample doc (replace or delete)
```

## Requirements

- Python 3.9+
- For the tools: `pip install pyyaml markdownify beautifulsoup4 lxml`
  (`markdownify`/`beautifulsoup4`/`lxml` are only needed for `convert_mhtml.py`).

## Usage

Generate a new project (CLI flags):

```bash
python init_project.py --dest ../my-new-kb \
    --project-name "My Project" \
    --org "My Organization" \
    --doc-lang es \
    --source-domain docs.myorg.example \
    --run-index
```

Or via a JSON config (copy `scaffold.config.example.json`):

```bash
python init_project.py --dest ../my-new-kb --config my.json --run-index
```

### Configurable values (placeholders)

| Placeholder            | Flag / config key      | Meaning                                             |
| ---------------------- | ---------------------- | --------------------------------------------------- |
| `{{PROJECT_NAME}}`     | `--project-name`       | Human-readable project name                          |
| `{{ORG}}`              | `--org`                | Organization name                                    |
| `{{DOC_LANG}}`         | `--doc-lang`           | Documentation language code (`ca`, `es`, `en`, ...)  |
| `{{SOURCE_DOMAIN}}`    | `--source-domain`      | Primary source host of the docs                      |
| `{{EXAMPLE_DOC}}`      | `--example-doc`        | Example doc path used in citations                   |
| `{{BOILERPLATE_SUFFIX}}` | `--boilerplate-suffix` | Title suffix stripped from H1s/filenames (optional)  |
| `{{DATE_LABEL}}`       | `--date-label`         | Inline "last updated" label used to parse dates      |

The agent prompts and `AGENTS.md` are written in **English**; `DOC_LANG` sets the
language of the **documentation content** and the agents always answer in the
user's language.

## Loading your own documents

After generating the project (`cd` into it):

1. **From web archives (`.mhtml`)** — put them under `docs/` and convert:
   ```bash
   python tools/convert_mhtml.py docs
   ```
2. **From existing Markdown** — drop `.md` files under `docs/<category>/`.
3. **Normalize + add frontmatter** (preview first):
   ```bash
   python tools/add_frontmatter.py --root . --dry-run
   python tools/add_frontmatter.py --root . --rename
   ```
   Adjust the project-specific constants at the top of `tools/add_frontmatter.py`
   (`BOILERPLATE`, `PREFERRED_HOSTS`, `DATE_RE`, `TAG_KEYWORDS`, `FOLDER_TAGS`).
4. **Regenerate the index**:
   ```bash
   python tools/build_index.py --root .
   ```
5. **Restart OpenCode** so it loads the `support` and `maintainer` agents. Use
   `support` for questions (read-only) and switch to `maintainer` to create or
   fix documentation.

## Initial prompt (paste into OpenCode, `maintainer` agent)

Once you have added raw documents and restarted OpenCode, select the
**`maintainer`** agent and paste this prompt to bootstrap the knowledge base:

```text
You are the knowledge-base maintainer for this repository. Follow AGENTS.md.

I have added raw documentation under docs/. Please:

1. Review the repository structure and list what is under docs/.
2. For every *.md under docs/ that lacks YAML frontmatter, add it following the
   template in AGENTS.md §7: title, category (its folder path), source_domain
   (only if a source host is clearly present — never invent URLs), last_updated
   (only if a date is present in the doc), tags (from folder + title keywords),
   a factual one-line summary, and language.
   Use the tool when helpful:
     python tools/add_frontmatter.py --root . --dry-run
     python tools/add_frontmatter.py --root . --rename
3. Regenerate the index:
     python tools/build_index.py --root .
4. Report: documentation gaps (topics not covered), stale docs (old
   last_updated), and likely duplicates (overlapping docs) — as a maintenance
   backlog. Do NOT invent project-specific facts; if something is unverified,
   say so.

Work in <DOC_LANG> for the documentation content. Cite files by path.
```

Replace `<DOC_LANG>` with your documentation language.

## Notes

- Agent definitions (`.opencode/agent/*.md`) are loaded **at OpenCode startup**;
  restart after generating or editing them.
- The repository is **documentation-only**: never commit application/infra source
  code, secrets, credentials, tokens, private keys, or sensitive config.
- `build_index.py` writes `README.md` at the project root and indexes everything
  under the tree except `.opencode/` and `tools/`.
