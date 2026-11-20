# Translation workspace goal

Build a maximally simple Chinese-to-English translation workspace that keeps the
writer focused on the manuscript: source and English side by side, reliable saving,
precise alignment, and useful tools without clutter. Use the local reader's editing
experience as the reference when developing the website.

## Core editing experience

The product baseline is a minimal text editor with smart quotes, automatic
hyphen-to-dash conversion, and italics, plus line-by-line Chinese/English sync,
statistics, and autosaving. Visible italics is now implemented with a minimal native editable surface and
Cmd/Ctrl+I. Drafts remain plain strings with separate formatting ranges, retained
in autosave, recovery, project backups, rich copy for Docs and Word export.
Smart quotes and hyphen conversion remain available locally; hosted smart
punctuation is currently disabled.

Use line-offset counts to align English with Chinese, including manual offset
adjustments when paragraphs are merged or split. Avoid proportional scaling for
drafting sync. The current drafting template already uses paragraph-index sync
with offsets; preserve that behavior and clarify whether finer line alignment is
needed. Scroll sync identifies the visible text position, so a long wrapped English
paragraph does not consume multiple source-paragraph indexes. Review currently
offers a separate proportional mode.

## Remaining work

| Area | Desired outcome | Current position |
| --- | --- | --- |
| Comments | Add comments attached to manuscript/translation passages. | Translation-passage comments implemented in shared draft templates, including edit/delete, stable offsets, reattachment after passage edits, autosave, recovery and backups. Source-side comments remain a possible extension. |
| Word export | Export translated work to a Word document, carrying comments into the document. | Portable DOCX export implemented for local and hosted drafts, with native Word comments. Package contents and ranges are tested; opening in Microsoft Word still needs manual verification. Italic runs are included. |
| Website | Bring the preferred local editing experience to a website. | Python service and hosted readers exist; preserve and extend local behavior parity. |
| DOCX upload | Upload Word manuscripts and parse them into the library. | Already supported; retain and test. |
| Multiple manuscripts | Work across multiple manuscripts, keeping each book's work separate. | Hosted library already supports multiple books; refine the workflow as needed. |
| Manuscript hierarchy | Organize content as book → volume → chapter. | Optional volume heading detection, grouped draft/review navigation and a revision-checked library organizer are implemented. Restarted chapter numbering remains distinct. JSON and Word exports retain structure. |
| Vocabulary lookup | Search/grep vocabulary across an entire book with context. | Source/translation search offers future chapters or the whole book, including earlier/current passages and expandable results. |

## Deferred stretch goal: shared glossary

The hosted draft reader has a glossary prototype with user-created terms and
browser-local storage per book. Google Sheets integration and public sharing
remain deferred.

Future idea: provide a glossary table that other people can access publicly. Explore two-way
Google Sheets synchronization so entries can be read and updated from both the
workspace and the sheet. Public readability does not by itself imply public write
access; editing permissions and conflict handling need a design before implementation.

## Delivery principles

- Keep the editing interface maximally simple as features are added.
- Preserve manuscripts, drafts, comments, preferences, and backups across changes.
- Use local and hosted Playwright checks to protect the editing experience.
- Track existing support separately from desired behavior; this roadmap is not a
  claim that every feature is complete or that the website is publicly deployed.
