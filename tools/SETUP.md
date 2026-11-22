# Kersimmy setup for a new manuscript

A side-by-side Chinese→English drafting tool. Static HTML, no server, no
install, no internet. Works on any Chinese source text file.

## What you need

- macOS or Linux with Python 3 (already on macOS)
- Google Chrome
- A popup dictionary extension if you want one — Zhongwen, Zhongzhong, or
  similar. **Chrome must be told to allow it on local files:** go to
  `chrome://extensions`, find the extension, click Details, and switch on
  *Allow access to file URLs*. Without this the dictionary silently does
  nothing on these pages.
- Your source manuscript as a single `.txt` file

## Setup

1. **Drop your source in.** Put the text file in `source/`. Any encoding is
   fine — GB18030, UTF-8, Big5 — it is detected automatically.

Brew
3. **Check it parsed correctly** before generating anything:

   ```
   cd tools
   python3 tlconfig.py
   ```

   This prints the encoding it chose, how many chapters it found, any gaps or
   duplicates in the numbering, the paragraph mode, and the first few chapter
   titles. If the chapter count looks wrong, fix `heading_regex`. If the
   paragraph count looks wildly too high, set `paragraph_mode` to `"blank"`.

4. **Generate.**

   ```
   ./regenerate.sh 1-10     # first ten chapters
   ./regenerate.sh all      # everything
   ```

5. **Open `draft.html`** in Chrome and bookmark it, along with `index.html`.

## The one warning that matters

Chrome treats every local file as the same origin, so **two projects sharing a
`storage_prefix` will overwrite each other's drafts.** If you run more than one
book, give each a different prefix. Changing a prefix later makes existing
drafts invisible (not deleted, but the page stops looking where they are), so
pick it once at the start.

Drafts, preferences, chapter timings and alignment offsets all live in browser
storage. That survives regenerating the HTML and moving the folder. It does
**not** survive clearing browsing data, a different Chrome profile, or
Incognito. Use **Exports → Copy for Google Docs** as you finish each chapter.
It also downloads a timestamped `.txt` backup.

## `paragraph_mode`, briefly

- `line` — one paragraph per line, as in most web-novel `.txt` files, often
  indented with a full-width space
- `blank` — paragraphs separated by blank lines, possibly wrapped across
  several lines
- `auto` — picks `blank` if blank lines make up 15% or more of the file

Getting this wrong is obvious: `line` on a wrapped file produces hundreds of
one-line fragments; `blank` on a line-per-paragraph file produces one giant
paragraph per chapter.

## Files

```
index.html     contents, every chapter, resume link
draft.html     drafting: source left, editor right, term lookup, statistics
sync.html      review: two panes, paste your English, chapter scroll sync
ch0NN.html     single-chapter reading pages
corpus.js      the whole source as data, for term lookup
manifest.json  chapter numbers, titles, counts
source/        your manuscript
tools/         generators, config.json, regenerate.sh
```

`corpus.js` and your illustration must stay beside `draft.html`.

## Known cosmetic limitation

Chapter labels in the interface are written as 第N章 regardless of what your
source uses, so a manuscript numbered 第N回 will still display 章. The parsing
and alignment are unaffected.
