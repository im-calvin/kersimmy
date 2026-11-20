TTEOTM reader
=============

Bookmark ../index.html (contents) and ../draft.html (drafting surface).
corpus.js must stay beside draft.html or whole-manuscript term lookup goes dead.

Files
  ../index.html      contents, all 131 chapters, resume link
  ../draft.html      drafting: Chinese left, editor right, find, rate tracker
  ../sync.html       review: two panes, paste English, chapter scroll sync
  ../ch0NN.html      single-chapter reading pages
  ../corpus.js       all 131 chapters' text, for term lookup
  ../bear.gif        dashboard illustration (must stay beside draft.html)
  ../manifest.json   chapter numbers, titles, paragraph and character counts
  source/            the Chinese source (GB18030)

Regenerate
  ./regenerate.sh            chapters 1-10
  ./regenerate.sh 11-40      a range
  ./regenerate.sh all        all 131

Notes
  Chrome needs Zhongwen set to "Allow access to file URLs" (chrome://extensions
  -> Zhongwen -> Details) or the dictionary will not pop on these pages.
  Drafts, preferences, chapter times and alignment offsets live in browser
  localStorage under the shared file:// origin, so they survive moving this
  folder. They do NOT survive clearing browsing data: copy each chapter into
  Google Docs as you finish it.
