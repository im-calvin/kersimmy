import * as local from './local-db.js';
export {emptyState, validateBook, validateState, backupPayload, readBackup, download, filename, stamp} from './local-db.js';
export const serverMode = true;
export const storageMode = 'server';
async function api(path, method = 'GET', body) {
  let response;
  try { response = await fetch('api/' + path,{method,headers:body ? {'Content-Type':'application/json'} : {},body:body ? JSON.stringify(body) : undefined,cache:'no-store'}); }
  catch { const error = new Error('Server unavailable. Your changes are kept on this device and will retry automatically.'); error.offline = true; throw error; }
  const result = await response.json();
  if (!response.ok) { const error = new Error(result.error || 'Server request failed'); error.conflict = response.status === 409; error.offline = response.status >= 500; throw error; }
  return result;
}
export const listBooks = () => api('books');
export const getBook = id => api('books/' + encodeURIComponent(id));
export const getState = async id => ({...local.emptyState(id),...await api('books/' + encodeURIComponent(id) + '/state')});
export async function importBooks(entries) {
  for (const {book,state} of entries) { local.validateBook(book); if (state) local.validateState(state,book); }
  return api('import','POST',{books:entries});
}
export const setIllustration = (id,illustration) => api('books/' + encodeURIComponent(id) + '/illustration','PUT',{illustration});
export async function saveState(state, expectedRevision) {
  return (await api('books/' + encodeURIComponent(state.id) + '/state','PUT',{state,expectedRevision})).revision;
}
export async function migrateBrowserLibrary() {
  const books = await local.listBooks();
  if (!books.length) return [];
  return importBooks(await Promise.all(books.map(async book => ({book,state:await local.getState(book.id)}))));
}
export const backupServer = () => api('backup','POST',{});
export const serverStatus = () => api('status');

export async function previewManuscript(file, options) {
  const content = await new Promise((resolve,reject) => {
    const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = () => reject(Error('Could not read manuscript.')); reader.readAsDataURL(file);
  });
  return api('preview','POST',{name:file.name,content,options});
}

export const getBundle = id => api('books/' + encodeURIComponent(id) + '/bundle');
export const setVolumes = (id, volumes, expectedRevision, titles) => api('books/' + encodeURIComponent(id) + '/volumes', 'PUT', {volumes, titles, expectedRevision});
export const updateImport = (id, preview, expectedRevision) => api('books/' + encodeURIComponent(id) + '/chapter-import', 'PUT', {preview, expectedRevision});
