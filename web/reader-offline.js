// An offline copy belongs to this browser and origin. Keep source and state
// separate so saving a draft does not rewrite the whole manuscript.
window.readerOffline = function readerOffline(id) {
  if (!navigator.serviceWorker || !window.indexedDB || !window.caches) return null;
  const database = new Promise((resolve, reject) => {
    const open = indexedDB.open('kersimmy-offline', 1);
    open.onupgradeneeded = () => open.result.createObjectStore('records');
    open.onsuccess = () => resolve(open.result);
    open.onerror = () => reject(open.error);
    open.onblocked = () => reject(new Error('Offline storage is blocked.'));
  });
  // The editor can keep working online if the browser refuses offline storage.
  database.catch(() => {});
  const bookKey = id + ':book', stateKey = id + ':state';
  async function remember(state, book) {
    const db = await database;
    return new Promise((resolve, reject) => {
      const transaction = db.transaction('records', 'readwrite');
      const records = transaction.objectStore('records');
      const current = records.get(stateKey);
      current.onsuccess = () => {
        if ((current.result?.revision ?? -1) > (state.revision ?? 0)) return;
        if (book) records.put(book, bookKey);
        records.put(state, stateKey);
      };
      transaction.oncomplete = resolve;
      transaction.onabort = () => reject(transaction.error);
    });
  }
  async function load() {
    const db = await database;
    return new Promise((resolve, reject) => {
      const transaction = db.transaction('records');
      const records = transaction.objectStore('records');
      const book = records.get(bookKey), state = records.get(stateKey);
      transaction.oncomplete = () => resolve(book.result && state.result
        ? {book:book.result, state:state.result} : null);
      transaction.onabort = () => reject(transaction.error);
    });
  }
  async function prepare() {
    await navigator.serviceWorker.register('/reader-worker.js');
    await navigator.serviceWorker.ready;
    // The first navigation may have happened before the worker was installed.
    const cache = await caches.open('kersimmy-draft-pages-v1');
    if (await cache.match(location.pathname)) return;
    const response = await fetch(location.pathname, {cache:'no-store'});
    if (!response.ok || response.redirected) throw new Error('Draft page could not be saved offline.');
    await cache.put(location.pathname, response);
  }
  return {remember, load, prepare};
};
