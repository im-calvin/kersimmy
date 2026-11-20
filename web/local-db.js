import {validateIllustration} from './illustration.js';
const DB_NAME = new URL(import.meta.url).searchParams.has('test')
  ? 'translation-reader-tests-v1' : 'translation-reader-web-v1';
let connection;
function openDB() {
  if (!connection) connection = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore('books', {keyPath:'id'});
      request.result.createObjectStore('states', {keyPath:'id'});
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('Close other reader tabs, then reload to update storage.'));
  });
  return connection;
}
async function read(store, key) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(store);
    const request = key === undefined ? tx.objectStore(store).getAll() : tx.objectStore(store).get(key);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export const listBooks = () => read('books');
export const getBook = id => read('books', id);
export const getState = async id => ({...emptyState(id), ...await read('states', id)});
export function emptyState(id) {
  return {id, revision:0, italics:{}, comments:{}, drafts:{}, current:null, positions:{}, offsets:{}, alignmentGroups:{}, times:{}, fontSize:19, sync:true, smart:true,
    wordsPerPage:null, reviewEnglish:{}, reviewMode:'chapter', reviewFontSize:19, legacyStorage:{}};
}
export function validateBook(book) {
  if (!book || typeof book.title !== 'string' || !book.title.trim() || !Array.isArray(book.chapters) || !book.chapters.length)
    throw new Error('Invalid book: a title and chapters are required.');
  const seen = new Set(), displayed = new Set();
  validateIllustration(book.illustration);
  for (const c of book.chapters) {
    if (!Number.isSafeInteger(c.no) || c.no < 0 || seen.has(c.no) || typeof c.title !== 'string'
        || !Array.isArray(c.paras) || c.paras.some(p => typeof p !== 'string'))
      throw new Error('Invalid or duplicate chapter in backup.');
    const volume=c.volume ?? '', number=c.number ?? c.no, identity=JSON.stringify([volume,number]);
    if (typeof volume !== 'string' || volume.length > 200 || (volume && !volume.trim()) || !Number.isSafeInteger(number) || number < 0)
      throw new Error('Invalid volume or displayed chapter number.');
    if (displayed.has(identity)) throw new Error('Duplicate chapter numbers within a volume.');
    displayed.add(identity);
    seen.add(c.no);
  }
}
export function validateState(state, book) {
  if (!state || !state.drafts || typeof state.drafts !== 'object' || Array.isArray(state.drafts)) throw new Error('Invalid draft data.');
  const result = emptyState('');
  for (const [key, value] of Object.entries(state.drafts)) {
    if (!book.chapters.some(c => String(c.no) === key) || typeof value !== 'string') throw new Error('Backup drafts do not match its chapters.');
    result.drafts[key] = value;
  }
  const italics = state.italics ?? {};
  if (!italics || typeof italics !== 'object' || Array.isArray(italics)) throw new Error('Invalid italic formatting.');
  for (const [chapter, ranges] of Object.entries(italics)) {
    if (!book.chapters.some(c => String(c.no) === chapter) || !Array.isArray(ranges)) throw new Error('Italic formatting does not match this book.');
    let previousEnd = 0;
    result.italics[chapter] = ranges.map(span => {
      if (!span || !Number.isSafeInteger(span.start) || !Number.isSafeInteger(span.end)
          || span.start < previousEnd || span.start >= span.end || span.end > (result.drafts[chapter] || '').length)
        throw new Error('Invalid italic range.');
      previousEnd = span.end;
      return {start:span.start, end:span.end};
    });
  }
  if (typeof state.commentAuthor === 'string') result.commentAuthor = state.commentAuthor.slice(0, 100);
  const comments = state.comments ?? {};
  if (!comments || typeof comments !== 'object' || Array.isArray(comments)) throw new Error('Invalid comments.');
  const commentIDs = new Set();
  for (const [chapter, notes] of Object.entries(comments)) {
    if (!book.chapters.some(c => String(c.no) === chapter) || !Array.isArray(notes)) throw new Error('Comments do not match this book.');
    result.comments[chapter] = notes.map(note => {
      if (!note || typeof note.id !== 'string' || !note.id || commentIDs.has(note.id)
          || !Number.isSafeInteger(note.start) || !Number.isSafeInteger(note.end) || note.start < 0 || note.end < note.start
          || typeof note.quote !== 'string' || typeof note.text !== 'string' || !note.text.trim() || note.text.length > 20000
          || (note.detached !== undefined && typeof note.detached !== 'boolean')) throw new Error('Invalid comment.');
      if ((note.resolved !== undefined && typeof note.resolved !== 'boolean')
          || (note.replies !== undefined && (!Array.isArray(note.replies) || note.replies.length > 100
            || note.replies.some(reply => typeof reply !== 'string' || !reply.trim() || reply.length > 20000))))
        throw new Error('Invalid comment thread.');
      commentIDs.add(note.id);
      return {...note};
    });
  }
  for (const [key, groups] of Object.entries(state.alignmentGroups || {})) {
    const chapter = book.chapters.find(c => String(c.no) === key);
    if (!chapter || !groups || typeof groups !== 'object' || Array.isArray(groups)) throw new Error('Invalid alignment groups.');
    result.alignmentGroups[key] = {};
    for (const [english, range] of Object.entries(groups)) {
      if (!/^[1-9][0-9]{0,14}$/.test(english) || !Array.isArray(range) || range.length !== 2
          || !range.every(Number.isSafeInteger) || range[0] < 1 || range[0] > range[1] || range[1] > chapter.paras.length)
        throw new Error('Invalid alignment range.');
      result.alignmentGroups[key][english] = range.slice();
    }
  }
  for (const field of ['positions','offsets','times']) {
    for (const [key, value] of Object.entries(state[field] || {})) {
      if (book.chapters.some(c => String(c.no) === key) && Number.isFinite(value)) result[field][key] = value;
    }
  }
  if (book.chapters.some(c => c.no === state.current)) result.current = state.current;
  if (Number.isFinite(state.fontSize)) result.fontSize = Math.max(14, Math.min(30, state.fontSize));
  for (const field of ['sync','smart']) if (typeof state[field] === 'boolean') result[field] = state[field];
  if (Number.isFinite(state.wordsPerPage)) result.wordsPerPage = Math.max(50, Math.min(1000, state.wordsPerPage));
  if (['chapter','prop','off'].includes(state.reviewMode)) result.reviewMode = state.reviewMode;
  if (Number.isFinite(state.reviewFontSize)) result.reviewFontSize = Math.max(13, Math.min(30, state.reviewFontSize));
  for (const [key, value] of Object.entries(state.reviewEnglish || {})) {
    if (!book.chapters.some(c => String(c.no) === key) || typeof value !== 'string') throw new Error('Review text does not match this book.');
    result.reviewEnglish[key] = value;
  }
  for (const [key, value] of Object.entries(state.legacyStorage || {})) {
    if (typeof value !== 'string') throw new Error('Invalid original-reader settings.');
    Object.defineProperty(result.legacyStorage, key, {value, enumerable:true, writable:true, configurable:true});
  }
  return result;
}
export async function importBooks(entries) {
  if (!Array.isArray(entries) || !entries.length) throw new Error('No books found in backup.');
  const records = entries.map(({book, state}) => {
    validateBook(book);
    const id = crypto.randomUUID();
    return {book:{id, title:book.title, chapters:book.chapters, createdAt:new Date().toISOString(),
      sourceName:typeof book.sourceName === 'string' ? book.sourceName : '', encoding:book.encoding || '', paragraphMode:book.paragraphMode || 'line',
      wordsPerPage:Number.isFinite(book.wordsPerPage) ? Math.max(50, Math.min(1000, book.wordsPerPage)) : undefined,
      headingRegex:typeof book.headingRegex === 'string' ? book.headingRegex : '',
      volumeHeadingRegex:typeof book.volumeHeadingRegex === 'string' ? book.volumeHeadingRegex : '',
      illustration:validateIllustration(book.illustration)},
    state:{...(state ? validateState(state, book) : emptyState(id)), id, revision:0}};
  });
  const db = await openDB();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(['books','states'], 'readwrite');
    for (const record of records) {
      tx.objectStore('books').add(record.book);
      tx.objectStore('states').add(record.state);
    }
    tx.oncomplete = resolve;
    tx.onabort = () => reject(tx.error || new Error('Import failed. No books were added.'));
  });
  return records.map(r => r.book);
}
export async function setIllustration(id, value) {
  const illustration = validateIllustration(value), db = await openDB();
  return new Promise((resolve,reject) => {
    const tx = db.transaction('books', 'readwrite'), store = tx.objectStore('books');
    const request = store.get(id); let updated;
    request.onsuccess = () => {
      if (!request.result) { tx.abort(); return; }
      updated = {...request.result, illustration}; store.put(updated);
    };
    tx.oncomplete = () => resolve(updated);
    tx.onabort = () => reject(tx.error || new Error('Could not save the GIF. The previous image has been kept.'));
  });
}
export async function saveState(state, expectedRevision) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('states', 'readwrite');
    const store = tx.objectStore('states');
    let failure;
    const request = store.get(state.id);
    request.onsuccess = () => {
      if ((request.result?.revision || 0) !== expectedRevision) {
        failure = new Error('This book changed in another tab. Download a backup of your work, then reload before editing again.');
        tx.abort(); return;
      }
      store.put({...state, revision:expectedRevision + 1});
    };
    tx.oncomplete = () => resolve(expectedRevision + 1);
    tx.onabort = () => reject(failure || tx.error || new Error('Saving failed. Download a backup before closing this page.'));
  });
}
export function backupPayload(entries) {
  return {format:'translation-reader', version:1, exportedAt:new Date().toISOString(), books:entries};
}
export function readBackup(text) {
  const data = JSON.parse(text);
  if (data.format !== 'translation-reader' || data.version !== 1 || !Array.isArray(data.books)) throw new Error('This is not a supported Translation Reader JSON backup.');
  return data.books;
}
export function download(name, contents, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([contents], {type}));
  const link = document.createElement('a');
  link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
export function filename(title) { return title.replace(/[^\p{L}\p{N}_-]+/gu, '-').slice(0, 70) || 'book'; }
export function stamp() { return new Date().toISOString().replace(/[:.]/g, '-'); }
