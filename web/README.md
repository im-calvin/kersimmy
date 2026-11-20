# Original reader with a browser library

From the project root:

```sh
python3 tools/serve.py
```

Open http://127.0.0.1:8000/. Python parses manuscripts and renders the same
original reader found in `tools/build_draft.py` and `tools/build_sync.py`.
SQLite saves your work and makes it available to other browsers using this server.

## Add a book

1. Click Add manuscript and choose `.txt` or `.docx`.
2. Enter its title. Leave encoding and paragraph layout on automatic initially.
3. Click Preview manuscript and inspect its chapters and paragraphs.
4. Add to library, then open the book.

Default headings include 第1章, 第一回, and Chapter 1. Use One chapter for an
unnumbered manuscript, or Custom heading pattern for a Python regular expression
with chapter number in capture group 1 and optional title in group 2. Python
parsing runs in a separate process with a 15-second timeout.

The original parser ignores text before the first chapter heading; move a preface
under a numbered heading if it should appear. With volume detection enabled, this
also applies to text between a volume heading and its first chapter. Duplicate
chapter numbers within the same volume are rejected. Word imports use XML
namespace-aware Python paragraph extraction with inserted
revisions retained and deleted text excluded. PDF and binary `.doc` need conversion.

## Volumes

New uploads detect headings such as `第一卷 晨光` and `Volume 1: Dawn`. Choose
No volume headings to keep those lines in the chapter text. Chapters may restart
numbering in different volumes; the reader displays their original numbers while
keeping their drafts distinct. Navigation groups chapters under their volume names.

For an existing book, click Organize volumes on its library card. Select chapters,
enter a volume name and apply, then Save organization. Applying an empty name clears
the assignment. Existing chapter keys, drafts, comments, formatting, timing and
review text remain intact. The save checks the book revision, so concurrent edits
require reopening the organizer before retrying.

JSON backups and Word exports retain volume structure. Plain text backups continue
to use unique, book-wide `Chapter N` headings for reliable text import. When pasting
review English with restarted chapter numbers, include the matching volume headings
before each set of chapters; reopening the review editor emits this structure.

## Draft and review

The drafting interface is the original reader: source on the left, English on the
right, paragraph synchronization, contextual term search, statistics, repeated
words, and configurable words per page. Use I or Cmd/Ctrl+I for italics. Select a
translation passage and choose the Add comment speech bubble beside the selection.
Click marked text to read or edit its note. If an edit detaches a comment,
select its replacement passage and use the reattach button below the English
pane. View contains the comment highlight color and Word comment author settings.
Word exports a DOCX with italic
runs and native Word comments. The find panel offers Source/Translation and
Future chapters/Whole book. Whole book shows earlier and current passages too;
Show more exposes results beyond the first 40. Search is literal and case-sensitive;
counts refer to matching paragraphs. Smart quotes remain disabled in hosted
pages, and the SOURCE/YOUR TRANSLATION labels are absent.

Stats includes Choose GIF and Remove GIF. The image is stored with the book and
included in JSON exports. Choose an animated GIF up to 5 MB.

Review opens the original `build_sync.py` interface. Paste English or use current
drafts; review text remains separate. Chapter, proportional, and disabled scroll
synchronization are the original implementations.

Click outside statistics/search/review overlays to dismiss them. Escape and the
original close buttons also work. The library/import form uses native dialogs.

## Saving, sync, migration

Wait for Synced to server before closing. Pending changes retain a local recovery
copy and retry after connection interruptions. Clean pages refresh when another
device saves; conflicting edits stop with a recovery message rather than silently
replacing drafts. Download recovery backup preserves source, drafts, review text,
settings, and GIF in the compatible JSON format.

Existing SQLite data and web-library JSON backups remain supported. Book links
from the old web reader redirect to the original generated reader. Import browser
library copies an older IndexedDB library at the same browser origin/profile;
for another address, export JSON there and use Restore backup here. Browser
copies are retained. Repeating migration creates new independent copies.

The library Back up library and book Backup buttons export full JSON. The
original editor's backup button exports English text; full project backup exports
its original full-project format. Import drafts accepts Chapter N text backups.
Use Download recovery backup for the complete server record.

## Original file-based reader

The prebuilt file reader is archived. To use it again, restore its files to
their original paths and open `draft.html` in Chrome.
Its localStorage and existing drafts are unchanged. To move local drafts and
settings to the hosted library, use full project backup there, then Restore backup
in the library. The file-based reader's generator workflow remains available. Optional volume
parsing uses `volume_heading_regex` in an alternate config;
`tools/chapter_structure.py` defines the built-in heading expression. If enabling
restarted numbering for an existing file project, first keep a full project backup,
use a new storage prefix/output and explicitly migrate work: newly parsed chapter
keys may differ. Existing root configuration keeps volume parsing off.

## Development

- `web/library.js`, `index.html`, `style.css`: book setup/library UI.
- `web/db.js`: small API client; `local-db.js` remains only for old-browser migration
  and compatible backup validation, not the active reader's storage.
- `web/reader-storage.js`: adapter that maps the original reader's storage fields
  to SQLite, with pending recovery and synchronization. Editing and statistics
  algorithms remain in the Python templates.
- `tools/reader_server.py`: API, original-parser upload preview, and generated pages.
- `tools/reader_store.py`: SQLite transactions and scheduled snapshots.
- `tools/build_web.py`: packages library/static adapter assets in `dist/`.

Restart the Python process after template/server edits and rebuild static assets
with `python3 tools/build_web.py` after library/adapter changes. Docker rebuilds
both. This library needs its Python service; standalone static hosting is no
longer the active architecture.

See [DEPLOYMENT.md](../DEPLOYMENT.md) for Docker, Portainer, backups and restoration.
Run storage tests with:

```sh
python3 -m unittest discover -s tests -p server_test.py
```

For end-to-end checks, start a separate server with disposable data:

```sh
python3 tools/reader_server.py --port 8002 --data /tmp/reader-test-data
```

In another terminal, with Python Playwright and Chrome installed:

```sh
python3 tests/original_reader_test.py --base-url http://127.0.0.1:8002
```

Use a temporary Python environment if Playwright is not installed. This suite
imports test books on the specified server; always use a disposable database.
It runs browsers with isolated profiles and leaves your normal Chrome storage alone.
