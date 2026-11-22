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
3. Click **Preview manuscript**. The chapter list shows the detected labels and
   the selected chapter’s opening paragraphs. Use **Chapter title** to add or
   correct its title before importing.
4. Add to library, then open the book.

Open **Settings → Set book icon** on a library card to choose its icon. The icon is stored
with the book and included in JSON backups.

Use **Settings → Remove book → Delete book** to remove a book and its
saved drafts and comments. Use **Settings → Back up book** first if you want to
keep a restorable copy.

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
keeping their drafts distinct. The preview and reader group chapters under
their volume names. Automatic import also groups numbered `番外` stories under
a `番外篇` heading.

For an existing book, click **Settings** on its library card. Edit titles
directly or select chapters and assign a volume. Applying an empty volume name
clears the assignment. **Save chapters** keeps chapter keys and draft state
intact. The save checks the book revision, so concurrent edits require reopening
the organizer before retrying.

Use **Settings → Recheck import** to upload the original file again and
try different parsing settings. You can apply the new titles and volume metadata
if the chapter IDs, order, and source paragraphs still match. If the source or
chapter boundaries change, use **Add manuscript** to import a separate copy.

JSON backups and Word exports retain volume structure. Plain text backups continue
to use unique, book-wide `Chapter N` headings for reliable text import. When pasting
review English with restarted chapter numbers, include the matching volume headings
before each set of chapters; reopening the review editor emits this structure.

## Draft and review

The drafting interface is the original reader: source on the left, English on the
right, paragraph synchronization, contextual term search, statistics,
and configurable words per page. The walkthrough opens when you open the
first draft you added through **Add manuscript** in that browser. Replay it from
**View → Walkthrough**. Use I or Cmd/Ctrl+I
for italics. Select a translation passage and choose the Add comment speech bubble
beside the selection.

**Stats** displays the total time recorded while editing drafts and comments.
Full project and library JSON backups store chapter times in `state.times`,
keyed by chapter ID in milliseconds. Update that field in a backup to correct
recorded times before restoring a copy of the book.
Use the sun or moon icon under **View** in the draft, or in the library or review
toolbar, to switch themes. The reader follows your system theme until you choose
a theme, then remembers it in your browser.
Click blue-highlighted text to read or edit its note. If an edit detaches a comment,
select its replacement passage and use the reattach button below the English
pane. Set the Word comment author under **View**. Use **Exports** to download a
DOCX with italics and native Word comments or copy the current chapter for Google Docs.
Find searches the whole book. Queries containing
Chinese characters look in the source first, and other queries start in the
translation. Find tries the other side if there are no matches. Show more
exposes results beyond the first 40. Search is literal and case-sensitive,
and Find shows both the number of matches and the number of matching paragraphs. Smart quotes remain disabled in hosted
pages, and the SOURCE/YOUR TRANSLATION labels are absent.

Stats includes Choose GIF and Remove GIF. The image is stored with the book and
included in JSON exports. Choose an animated GIF up to 5 MB.

Previously saved review text remains in project backups. The original
`/books/<id>/review` address is available for existing bookmarks.

Click outside statistics/search/review overlays to dismiss them. Escape and the
original close buttons also work. The library/import form uses native dialogs.

## Saving, sync, migration

The toolbar shows a filled circle when synced and an empty circle otherwise. Click it for details and
**Retry save** when a save can be retried. The first time you open a draft
online, check for **Available offline** there. You can then refresh and edit
that draft without a connection using the same browser and address. The library
and imports require a connection. Draft changes stay on the device until the
status reads **Synced to server**.

Clean pages refresh when another device saves. If there are pending edits, the
server compares the book revision and rejects an older write. Your local draft
stays open across refreshes. **Download recovery backup** preserves the local
copy as JSON. **Use server version** discards the pending edits after you confirm
and reloads the latest saved draft.

Existing SQLite data and web-library JSON backups remain supported. Book links
from the old web reader redirect to the original generated reader. Import browser
library copies an older IndexedDB library at the same browser origin/profile;
for another address, export JSON there and use Restore backup here. Browser
copies are retained. Repeating migration creates new independent copies.

The library Back up library and **Settings → Back up book** export full JSON. In the
draft's **Exports** menu, **Draft text backup** exports English text and
**Full project backup** exports a project JSON. **Import drafts** accepts
Chapter N text backups.

## Original file-based reader

The prebuilt file reader is archived. To use it again, restore its files to
their original paths and open `draft.html` in Chrome.
Its localStorage and existing drafts are unchanged. To move local drafts and
settings to the hosted library, use **Exports → Full project backup**, then Restore backup
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

See [DEPLOYMENT.md](../DEPLOYMENT.md) for Docker, Arcane, backups and restoration.
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
