# Browser regression tests

The file reader is the reference for editor behavior. The shared tests run against
both freshly generated `file://` pages and the hosted reader. Hosted persistence,
import, recovery and migration checks also run through the existing integration
script. Runtime code still needs only Python's standard library; these dependencies
are for development.

From the project root (Python 3.10+):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest
```

No server setup is necessary. Tests use synthetic Chinese text, temporary generated
files, a fresh SQLite database, an automatically assigned loopback port, and isolated
browser contexts. The fixture shuts down its server after the run. Root reader output,
real manuscripts, browser profiles and `data/` are untouched.

Useful commands:

```sh
# Focus on the local reader
.venv/bin/python -m pytest tests/test_reader_behavior.py -k local
# Compare shared local/hosted behavior in a visible browser
.venv/bin/python -m pytest tests/test_reader_behavior.py --headed
# Use installed Google Chrome instead of bundled Chromium
.venv/bin/python -m pytest --browser-channel chrome
# Step through an individual shared behavior test
PWDEBUG=1 .venv/bin/python -m pytest tests/test_reader_behavior.py -k chapter -x
# Storage/API unit tests remain separate
python3 -m unittest discover -s tests -p server_test.py
```

Shared tests cover chapter-specific autosave/reload, paragraph alignment, full-corpus
search, statistics, panel dismissal, text/project exports, separate review text,
and review sync preferences. Local panels use their close buttons; hosted panels
also support outside-click dismissal. The local-only punctuation test protects curly quotes
and em dashes; hosted punctuation is deliberately disabled in the current product.
Add shared expectations to `test_reader_behavior.py` when restoring more local behavior
on the hosted page. These are behavioral checks, not a claim of complete UI parity.

## Product acceptance criteria

| Goal | Playwright checks |
| --- | --- |
| Keep commenting simple and the surrounding English visible | `test_comments.py` checks that the icon and popover appear beside the selected English passage, and clicking the underlined text reopens the saved note directly. |
| Make saved comments visibly distinct from spellcheck and reading sync | `test_comments.py` screenshots the English passage after reloading and selecting its Chinese source. It checks that the browser actually painted the purple marker. |
| Keep comments usable in Word | `test_comments.py` checks that italic formatting and a multiline Unicode comment with a custom author transfer together in a native DOCX. Tests inspect the package relationship, exact passage, text, and formatting, and cover reattachment and export of previously saved replies. |
| Keep drafts and comments safe while moving between manuscripts | `test_comments.py`, `test_reader_behavior.py`, and `test_volumes.py` check reload, offline recovery, JSON restore, and isolation between books and chapters. |
| Keep English and Chinese aligned while translating | `test_editor.py` checks wrapped lines, one English paragraph mapped to multiple Chinese paragraphs, rejection of overlapping assignments, and scroll handoff near both viewport edges. |
| Preserve the editing and manuscript workflow | `test_editor.py` and `test_reader_behavior.py` check italics, smart punctuation, statistics, autosave, and local snapshots. `test_volumes.py` and `test_vocabulary.py` check DOCX import, book/volume/chapter structure, and whole-book vocabulary search. |

### Quip inline comment specifications

- Select a word or phrase, then open its comment bubble beside the selection.
  The same composer opens with Cmd+Shift+M on Mac or Ctrl+Shift+M on Windows.
  Enter submits the note. [Quip inline comments](https://help.salesforce.com/s/articleView?id=000389933&language=en_US&type=1), [Quip keyboard shortcuts](https://help.salesforce.com/s/articleView?id=000389937&language=en_US&type=1)
- Open saved feedback in context and edit it inline. Two phrases in the same
  paragraph retain separate notes and anchors after an edit. [Quip inline comments](https://help.salesforce.com/s/articleView?id=000389933&language=en_US&type=1), [Quip inline editing](https://help.salesforce.com/s/articleView?id=xcloud.quip_edit_a_comment.htm&language=en_US&type=5)
- TTEOTM opens a single note when you click the marked English text. The shared
  tests also check that the surrounding passage stays visible and that exported
  Word comments retain their exact text ranges and edits.

Run these Quip-based cases in both readers with
`.venv/bin/python -m pytest tests/test_comments.py -k quip_style`.

For a Playwright MCP smoke test, open a disposable hosted manuscript with draft
text. Select a word, open the comment control beside it, and save a note. Wait
for the server status to show it has synced. Reload and click the underlined word
to reopen the note, then use Word to download the document. Check the download
for the original passage and note. The automated suite checks the DOCX package
structure. Opening the file in Microsoft Word is a separate check.

Editor tests cover visible italics, keyboard toggling, native undo/redo, line and
paragraph breaks, literal-text paste, emoji selection offsets, chapter/reload
persistence, JSON restore, rich copy for Docs, formatted Word output, hosted offline
recovery, and plain-text import replacement. Wrapped English paragraphs must retain
paragraph-based scroll sync. Draft text remains plain; italic ranges are an additive
state field. The draft's `#ta` is now a native editable element exposing the original
text/selection interface, so tests assert its `value` JS property rather than a
textarea-only form value. The review paste editor remains a textarea.

Volume tests cover DOCX import (including arbitrary XML namespace prefixes),
restarted numbering, independent drafts, grouped local/hosted navigation, review
round trips, structured JSON and Word exports, revision conflicts, atomic validation
and clean-page refresh. Vocabulary tests cover source and translation across the
whole book, earlier/current context and expansion beyond 40 results.

Pytest retains screenshots and Playwright traces for failed shared tests in
`test-results/`. Open a trace with:

```sh
.venv/bin/python -m playwright show-trace test-results/<test-folder>/trace.zip
```

The hosted integration script reports its separate screenshot artifact directory
in failure output. It covers upload preview, DOCX/custom headings, GIF settings,
backup/restore, cross-browser sync, offline retry and stale-revision rejection.
Its subprocess has a 180-second timeout. `--headed` and pytest tracing apply to the
shared tests; the existing integration script runs headless. You can still run it
manually against a **disposable** server with installed Chrome:

```sh
.venv/bin/python tests/original_reader_test.py --base-url http://127.0.0.1:8002
```
