# Translation reader codebase guide

## Purpose and scope

This folder is a Chinese-to-English manuscript translation workspace. TTEOTM is
its configured book; the tools also support importing other manuscripts. It has
two entry points: a file-based reader with browser-local drafts, and a Python
service with a book library and shared SQLite storage. These have separate data
stores; moving work between them requires an explicit backup/import.

These instructions apply throughout this folder. Work in root `tools/` and
`web/` unless the task specifically targets a reusable template copy. Preserve
manuscripts, configuration, saved translations, and backups. Do not regenerate
root output merely to inspect the project.

## Product direction

See [ROADMAP.md](ROADMAP.md) for the high-level goal, completed product baseline,
remaining work, and shared-glossary stretch goal. Use the local editor as the
reference for hosted behavior. The draft walkthrough appears on the first visit
and can be reopened under **View → Walkthrough**. Theme follows the system by
default, with Light and Dark overrides. Dark mode uses beige reading text.

The hosted glossary is browser-local per book. Underlined Chinese terms show
their English translation and usage note on hover or keyboard focus. Google
Sheets integration and public glossary sharing remain deferred.

## Architecture

Python is the source of truth for manuscript parsing and reader behavior.
The original generators render the local reader and the hosted reader. A small
Python HTTP service adds a library/import form, SQLite persistence, sync, and
scheduled backups. There is no duplicate JavaScript reader or browser parser.
Runtime dependencies are Python's standard library and a modern browser.
Browser editing behavior is JavaScript embedded in the Python templates; the
Python service renders it rather than executing editor behavior on the server.
There is no Node/npm build step or frontend framework.

Hosted data flow:

1. `tools/serve.py` copies `web/` assets into `dist/` and starts the HTTP server.
2. The library sends uploads to `/api/preview`; a subprocess runs the shared
   parser with a 15-second timeout. Preview does not persist a book.
3. `/api/import` validates and atomically saves book/state records in SQLite.
4. `/books/<id>/draft` renders the editor. `/books/<id>/review` remains available
   for existing bookmarks. The draft toolbar omits Review. `generated_page`
   installs hosted hooks and the storage adapter.
5. `web/reader-storage.js` loads state before starting the template's script,
   maps its storage keys to state, and sends revision-checked saves to the API.

The file reader instead loads generated HTML and `corpus.js` directly, using
actual browser localStorage. `dist/` alone is not a standalone hosted app.

## Main files

- `tools/tlconfig.py`: configuration, encoding detection, TXT/DOCX extraction,
  heading recognition, chapter numbers, and paragraphs. `parse_source` is shared
  by the CLI and the server's upload preview. Text before the first chapter is
  omitted; DOCX uses namespace-aware XML extraction and explicit Word paragraphs.
  Optional volume detection is configured by `volume_heading_regex`; upload preview
  enables the built-in pattern by default, while the root config keeps it off. Binary DOC/PDF are unsupported.
- `tools/chapter_structure.py`: shared volume-heading expression and escaped grouped
  chapter options. `chapter.volume` and optional displayed `chapter.number` are
  additive metadata; numeric `chapter.no` remains the unique persistence key.
- `tools/build_draft.py`: original draft HTML/CSS/JavaScript, walkthrough,
  paragraph sync, search, statistics, repeated words, timing, and text/project export.
  `render_page(cfg, chapters, illustration)` is used by the CLI and server.
- `tools/draft_editor.py`: minimal native editable surface and italic range rendering,
  embedded by the draft generator. Plain draft strings and UTF-16 selection offsets
  remain the interface used by alignment, comments and exports; formatting uses
  the additive `draft:italics` key. Preserve native undo by avoiding DOM replacement
  during typing; rebuild markup only when loading a chapter.
- `tools/draft_comments.py`: inline passage comments, detachment and reattachment,
  and offline DOCX export with native Word comments, authors, and italics. Comment
  markers are drawn outside the editable DOM to preserve native editing and undo.
  Clicking a marked passage opens its notes. The recovery dialog is for detached
  notes. Preserve `draft:comments` and legacy replies in saves, recovery, and exports.
- `tools/build_sync.py`: original review renderer with separately stored pasted
  English and chapter/proportional/off sync. Keep saved review data compatible.
- `tools/reader_theme.py` and `web/theme.js`: shared theme preference logic, reader
  controls and palette. The generators embed the theme script for file output;
  the library loads it as a static asset and sets its palette in `web/style.css`.
- `tools/generate.py`: original contents and per-chapter reading pages/manifest.
- `tools/build_corpus.py`: complete source in `window.CORPUS` for the file reader.
- `tools/regenerate.sh`: original local reader generation.
- `tools/reader_server.py`: library API, upload preview through the original
  parser in a subprocess with a timeout, generated `/books/<id>/draft` and
  `/books/<id>/review` pages, same-origin write checks, and clean shutdown.
- `tools/reader_store.py`: SQLite transactions, validation, integrity-checked
  online backups and retention. Revision conflict checks live in the API handler.
- `tools/restore_reader.py`: offline database restore; snapshot existing DB first.
- `tools/illustration.py`: embeds a configured GIF for full-project migration.
- `tools/build_web.py`: copies library/adapter assets to generated `dist/`;
  optionally bundles the current source and original file reader as `legacy/`.
- `tools/serve.py`: build library assets, then launch the Python reader service.
- `web/index.html`, `library.js`, `style.css`: simple library/import form.
- `web/db.js`: server API and migration client. `web/local-db.js` remains for
  earlier IndexedDB library migration/backup validation only.
- `web/reader-storage.js`: maps original reader storage fields to SQLite,
  pending local recovery, retry, clean-page sync, GIF controls and text import.
  Do not implement editor/search/statistics algorithms here; change templates.
- `web/dialogs.js`: native library-dialog backdrop dismissal.
- `web/glossary-poc.js` and `web/glossary-poc.css`: hosted glossary editor, source
  marking, and definition tooltip. Glossary data uses browser storage.
- `web/illustration.js`: local GIF reading and validation (5 MB/16 MP limits).
- `tests/server_test.py`: persistence, atomic import, scheduled backups/retention.
- `tests/original_reader_test.py`: generated reader/import/review, alignment,
  exports, GIF, search, click-outside, sync, recovery, Word/custom headings.
- `Dockerfile`, `compose.yaml`, `compose.arcane.yaml`: container packaging,
  local Docker Compose, and the Arcane production project.
- `.github/workflows/reader.yml`: tests, Docker smoke check, GHCR image publishing,
  and optional Arcane redeploy webhook.
- `README.md`, `DEPLOYMENT.md`, `web/README.md`: operating instructions.

## Where to make changes

| Task | Primary files | Follow-up |
| --- | --- | --- |
| Encoding, DOCX extraction, chapter/paragraph parsing | `tools/tlconfig.py` | Check CLI diagnostics and hosted import preview |
| Editor, search, statistics, exports, alignment | `tools/build_draft.py` | Check file output and hosted draft page |
| Inline comments and Word export | `tools/draft_comments.py` | Check rendered markers, passage anchors, and DOCX output |
| Theme | `tools/reader_theme.py`, `web/theme.js`, `web/style.css` | Check file and hosted readers, library, and dark-mode annotations |
| Hosted glossary | `web/glossary-poc.js`, `web/glossary-poc.css` | Check hover and keyboard focus on marked Chinese terms |
| Review text and scroll synchronization | `tools/build_sync.py` | Check file output and hosted review page |
| Hosted template injection or navigation | `tools/reader_server.py` (`generated_page`) | Restart service; check injected controls/hooks |
| Recovery, save/retry, remote refresh | `web/reader-storage.js` | Rebuild static assets; check persistence and conflicts |
| Library/import UI and migration | `web/library.js`, `web/db.js`, other `web/` assets | Rebuild static assets; check import/restore |
| Database validation, transactions, snapshots | `tools/reader_store.py`, API handler | Run storage tests and relevant API/UI checks |

Hosted integration uses literal replacements and script hooks in generated HTML.
When changing template markup or initialization, inspect `generated_page` too:
a template edit can otherwise silently remove a hosted control or adapter hook.
The adapter wraps the main plain `<script>` block. The early theme script uses
`<script data-reader-theme>` and reads actual browser storage. Keep explicit
`window.localStorage` access for browser-only preferences when adding hosted hooks.

Draft alignment counts paragraphs, skipping blank lines and the leading chapter
heading. Option/Alt-click sets alignment and Shift-click extends the current
Chinese range in either direction. Holding Option/Alt with Shift also extends it.
Reject overlaps silently. Ordinary source clicks show the corresponding English
without changing the saved alignment.

## Existing local project

Root `tools/config.json` resolves `../source/TTEOTM-zh.txt` to the root
`source/` folder and uses GB18030, line paragraphs,
290 words/page, the `tl` storage prefix, and `bear.gif`. Source currently parses
131 chapters, 18,380 paragraphs, and 514,918 characters with no numbering gaps.
Docker is the active output. The old file-reader pages, corpus, manifest, and
launcher are archived outside the workspace. The file-reader generators remain
available for alternate output directories. Restore archived files to their
original paths if you need to access browser drafts associated with those paths.

The old reusable reader templates and archives have been moved outside the
workspace. The active implementation is in root `tools/` and `web/`.

## Commands

```sh
python3 tools/serve.py                       # library + original reader + SQLite
docker compose up -d --build --wait           # local Docker app on port 8000
python3 tools/reader_server.py --data ./data # same server, assets already built
python3 tools/build_web.py                   # rebuild library/static adapter
python3 tools/tlconfig.py                    # original parser diagnostics
bash tools/regenerate.sh 1-10                # original file reader, selected range
bash tools/regenerate.sh all                 # all chapters
open -a "Google Chrome" draft.html           # original file reader
```

Run commands from the root. Python server/template edits need a process restart;
static asset edits need `build_web.py`. Docker rebuilds both. Original generator
module docstrings may contain outdated positional arguments; use `--help`.
Configuration source paths are relative to the config, not the shell directory.
The regeneration script changes into `tools/`, so relative `CONFIG` and `OUTDIR`
values are resolved there. Prefer absolute paths for alternate output/config.
It defaults to chapters 1–10; `corpus.js` always contains the complete source.
`build_web.py` includes the configured manuscript and existing root reader output
by default; use `--without-current` to omit both when packaging a generic library.
Docker uses that option. Do not publish manuscript bundles unintentionally.

## Data compatibility

The server preserves the existing `reader.sqlite3` schema (`books` with JSON book,
JSON state, revision) and version-1 JSON backups. Every book imported through
JSON restore or migration gets an independent UUID; offline SQLite snapshot
restore preserves the stored IDs. Do not discard existing SQLite or browser
data during edits.
Volume assignments on existing books use `/api/books/<id>/volumes` with an
expected revision; they must never renumber chapters or replace translation state.
New imports with numbering restarted across volumes get distinct numeric keys and
preserve their original displayed numbers. Version-1 backups retain both fields.
The fourth corpus row item optionally holds this metadata; keep the first three
items compatible with old generated readers.

Server book records include complete source and optional GIF data URLs. State
holds drafts, italic ranges, passage comments, positions, offsets, alignment
groups, times, font size, page size, review text/settings, and legacy storage
values. Image updates are separate from frequent state writes. Theme, comment
highlight color, walkthrough dismissal, and the hosted glossary stay in browser
storage. The Word comment author is saved with the book.

Generated hosted pages use an in-memory `readerStorage` adapter with the original
key conventions. The file reader continues to use its actual localStorage keys.
Never silently rename/clear the root file reader's keys. Full project backup from
the original page includes source, drafts, timings, preferences and review data;
JSON restore and browser-library migration remain available in the library.

Revision-checked SQLite writes reject conflicting edits. Pending work gets local
recovery before a server write; preserve this recovery if saving fails. Clean
pages poll and refresh on remote changes; unsaved/review-editor content blocks
refresh. No offline app shell is provided. Hosted smart punctuation is disabled;
SOURCE and YOUR TRANSLATION labels remain absent. Preserve requested backdrop
closing and per-book GIF customization when updating generated page integration.

## Backups and deployment

SQLite uses WAL/FULL commits on local disk. Automatic snapshots use SQLite's
online backup API, integrity checks, temporary files/atomic rename, and bounded
retention (15 minutes / newest 96 by default). Never copy a live WAL database
as a plain file. Restore requires the app stopped. Snapshots in the same Docker
volume do not protect against host/disk loss; external replication is separate.
Data lives at `/data` in containers, root `data/` locally; do not delete these.

The service has no application login and binds to loopback by default. The
production deployment uses an Arcane Docker Compose project. GitHub Actions
tests pushes to `main` and publishes passing builds to
`ghcr.io/im-calvin/translate` for AMD64 and ARM64. Use Ubuntu 24.04 for the test
job to match the pinned Playwright release. Optional automatic redeploy requires
repository variable `ARCANE_DEPLOY_ENABLED=true` and the `ARCANE_WEBHOOK_URL`
secret in GitHub's `production` environment. Arcane records the deployment
result. Cloudflared routes
`translate.bxian03.com` to `http://translation-reader:8000` on the shared Docker
network. Protect public access with Cloudflare Access. Verify the remote
deployment on the Docker host before reporting it as live.

Arcane Compose mounts an external volume at `/data`. Create the default
`translation-reader_reader_data` volume once, or use `READER_DATA_VOLUME` to
reuse an existing volume. `CLOUDFLARED_NETWORK` names the connector's Docker
network. Arcane Git Pull sync uses `main` and `compose.arcane.yaml`. Confirm
that the Compose file and workflow are pushed before relying on remote deploys.

The workspace is a Git checkout tracking `main` on `im-calvin/translate`.
Check `git status` and the remote branch before reporting what has shipped.
The public repository and container builds exclude manuscripts, local config,
database files, backups, and credentials.

## Validation

Self-contained Playwright setup and local/hosted behavior checks are documented in
`tests/README.md`. Install `requirements-test.txt` and Chromium in `.venv`, then run
`.venv/bin/python -m pytest`. This generates synthetic file-reader output and starts
a disposable hosted server automatically; no real manuscript or database is used.
The shared reader tests cover walkthrough and theme settings. Alignment and
editing tests live in `tests/test_editor.py`. `tests/test_comments.py` checks
rendered highlight pixels and native DOCX comment ranges, formatting, and
authors. `tests/test_glossary_poc.py` checks glossary tooltips. Failure traces
and screenshots go to `test-results/`.

```sh
python3 -m unittest discover -s tests -p server_test.py
# Use a fresh directory for each run; stop this server when checks finish.
TEST_DATA="$(mktemp -d /tmp/reader-test-data.XXXXXX)"
python3 tools/build_web.py --without-current --output "$TEST_DATA/site"
python3 tools/reader_server.py --port 8002 --site "$TEST_DATA/site" --data "$TEST_DATA/data"
# In a second terminal, use the bundled Playwright Chromium:
READER_BROWSER_CHANNEL= .venv/bin/python tests/original_reader_test.py --base-url http://127.0.0.1:8002
```

For a generator smoke check without overwriting the current file reader:

```sh
READER_OUTPUT="$(mktemp -d /tmp/reader-output.XXXXXX)"
OUTDIR="$READER_OUTPUT" bash tools/regenerate.sh 1-2
# corpus.js is generated there too; copy bear.gif there if checking the GIF.
```

Storage tests use temporary databases and require no third-party dependencies.
Pytest uses bundled Chromium by default. Pass `--browser-channel chrome` to use
installed Chrome. The standalone integration script defaults to Chrome unless
`READER_BROWSER_CHANNEL` is set. For interactive browser work, follow the active
environment's browser tool instructions.

UI tests create books on the specified server: always use disposable data, not
the user's live database. Browser profiles are isolated. After generator changes,
smoke-test file output in a temporary directory and check generated hosted pages.
