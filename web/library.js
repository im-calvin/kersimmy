import {dismissOnBackdrop} from './dialogs.js';
import {previewManuscript, getBundle, setVolumes} from './db.js';
const stripHeading = text => text.replace(/^\s*(?:Chapter|Ch\.?)\s+\d+[^\n]*\n/i, '').trim();
import {listBooks, serverMode, migrateBrowserLibrary, backupServer, serverStatus, getBook, getState, importBooks, backupPayload, readBackup, download, filename, stamp} from './db.js';
const $ = id => document.getElementById(id);
document.querySelectorAll('dialog').forEach(dismissOnBackdrop);
let preview = null, currentBook = null, parsingVersion = 0;
const message = (text, error = false) => { $('message').textContent = text; $('message').className = error ? 'error' : ''; };
function element(tag, text, className) {
  const el = document.createElement(tag); el.textContent = text;
  if (className) el.className = className;
  return el;
}
async function exportBooks(books) {
  const entries = await Promise.all(books.map(async book => ({book:await getBook(book.id) || book, state:await getState(book.id)})));
  download(`${books.length === 1 ? filename(books[0].title) : 'library'}-${stamp()}.json`, JSON.stringify(backupPayload(entries), null, 2));
  message('Backup downloaded. Restore it here or on another device to continue.');
}
async function renderLibrary() {
  const books = await listBooks();
  $('books').replaceChildren();
  $('backup-library').disabled = !books.length;
  if (!books.length) {
    const empty = element('div', '', 'empty-library');
    empty.append(element('span', '文 / A', 'empty-mark'), element('h2', 'Your library starts here'), element('p', 'Add a manuscript to see its chapters and begin translating.'));
    $('books').append(empty);
  }
  for (const book of books.sort((a,b) => b.createdAt.localeCompare(a.createdAt))) {
    const state = await getState(book.id);
    const drafted = Object.values(state.drafts).filter(t => stripHeading(t)).length;
    const card = element('article', '', 'book-card');
    const volumeCount=new Set(book.chapters.map(c=>c.volume).filter(Boolean)).size;
    card.append(element('p', `${volumeCount ? volumeCount + ' VOLUMES · ' : ''}${book.chapters.length} CHAPTERS`, 'eyebrow'), element('h2', book.title), element('p', `${drafted} chapters started · ${book.chapters.reduce((n,c) => n+c.paras.length, 0).toLocaleString()} source paragraphs`, 'book-meta'));
    const actions = element('div', '', 'card-actions');
    const link = element('a', drafted ? 'Continue translating →' : 'Open manuscript →', 'book-link');
    link.href = `/books/${encodeURIComponent(book.id)}/draft`;
    const backup = element('button', 'Backup', 'subtle');
    backup.onclick = () => exportBooks([book]).catch(e => message(e.message, true));
    const organize=element('button','Organize volumes','subtle');
    organize.onclick=async()=>{organize.disabled=true;try{await openVolumes(book.id)}catch(e){message(e.message,true)}finally{organize.disabled=false}};
    actions.append(link, organize, backup); card.append(actions); $('books').append(card);
  }
}
function invalidate() {
  parsingVersion++; preview = null; $('confirm-import').disabled = true; $('preview').hidden = true; $('import-error').textContent = '';
}
$('add-book').onclick = () => $('import-dialog').showModal();
$('close-import').onclick = () => $('import-dialog').close();
$('manuscript').onchange = () => {
  invalidate();
  const file = $('manuscript').files[0];
  if (file) $('book-title').value = file.name.replace(/\.(txt|docx)$/i, '');
};
for (const id of ['encoding','paragraph-mode','heading-mode','volume-mode']) $(id).onchange = invalidate;
$('heading-mode').onchange = () => { $('custom-heading').hidden = $('heading-mode').value !== 'custom'; invalidate(); };
$('heading-regex').oninput = invalidate;
$('parse').onclick = async () => {
  invalidate(); const version = parsingVersion;
  try {
    const file = $('manuscript').files[0];
    if (!file) throw new Error('Choose a manuscript first.');
    if (!/\.(txt|docx)$/i.test(file.name)) throw new Error('Choose a .txt or .docx file. Old .doc and PDF files need to be converted first.');
    if (file.size > 30 * 1024 * 1024) throw new Error('Choose a manuscript smaller than 30 MB.');
    $('parse').disabled = true;
    const parsed = await previewManuscript(file, {encoding:$('encoding').value, paragraphMode:$('paragraph-mode').value,
      headingMode:$('heading-mode').value, volumeMode:$('volume-mode').value, headingRegex:$('heading-regex').value});
    const decoded = {encoding:parsed.encoding};
    if (version !== parsingVersion) return;
    preview = {...parsed, encoding:decoded.encoding, sourceName:file.name};
    $('preview-chapter').replaceChildren(...preview.chapters.map(c => new Option(`${c.volume ? c.volume + ' · ' : ''}${c.no === 0 ? 'Preface' : 'Chapter ' + (c.number ?? c.no)} · ${c.title}`, c.no)));
    $('preview-summary').textContent = `${preview.chapters.length} chapters · ${preview.chapters.reduce((n,c) => n+c.paras.length, 0).toLocaleString()} paragraphs · ${decoded.encoding} · ${parsed.paragraphMode}`;
    $('preview-warnings').textContent = parsed.warnings.join(' ');
    showPreview(); $('preview').hidden = false; $('confirm-import').disabled = false;
  } catch (e) { $('import-error').textContent = e.message; }
  finally { $('parse').disabled = false; }
};
function showPreview() {
  const chapter = preview.chapters.find(c => c.no === Number($('preview-chapter').value));
  $('preview-text').replaceChildren(...chapter.paras.slice(0, 8).map(p => element('p', p)));
  if (chapter.paras.length > 8) $('preview-text').append(element('small', `… ${chapter.paras.length - 8} more paragraphs`));
}
$('preview-chapter').onchange = showPreview;
$('import-form').onsubmit = async e => {
  e.preventDefault();
  if (!preview) return;
  $('confirm-import').disabled = true;
  try {
    const [book] = await importBooks([{book:{...preview, title:$('book-title').value.trim()}}]);
    $('import-dialog').close(); $('import-form').reset(); $('custom-heading').hidden = true; invalidate();
    await renderLibrary(); message(`“${book.title}” is ready. Open it to start translating.`);
  } catch (error) { $('import-error').textContent = error.message; $('confirm-import').disabled = false; }
};
$('backup-library').onclick = async () => { try { await exportBooks(await listBooks()); } catch (e) { message(e.message, true); } };
$('restore').onclick = () => $('restore-file').click();
$('restore-file').onchange = async () => {
  try {
    const file = $('restore-file').files[0]; if (!file) return;
    if (file.size > 100 * 1024 * 1024) throw new Error('Backup is too large (maximum 100 MB).');
    const books = await importBooks(readBackup(await file.text()));
    await renderLibrary(); message(`Restored ${books.length} book${books.length === 1 ? '' : 's'} as new copies. Existing books were kept.`);
  } catch (e) { message(e.message, true); }
  finally { $('restore-file').value = ''; }
};
$('import-current').onclick = async () => {
  $('import-current').disabled = true;
  try {
    await importBooks([{book:currentBook}]); await renderLibrary();
    message('Manuscript added. For complete migration, use “full project backup” in the original reader and “Restore backup” here. Text-only backups can be imported inside a book.');
  } catch (e) { message(e.message, true); }
  finally { $('import-current').disabled = false; }
};
let organization=null, assignedVolumes={}, selectedChapters=new Set();
async function openVolumes(id) {
  organization=await getBundle(id);assignedVolumes={};selectedChapters=new Set();
  for(const chapter of organization.book.chapters)assignedVolumes[chapter.no]=chapter.volume||'';
  $('volumes-book').textContent=organization.book.title;
  $('volume-name').value='';$('volumes-error').textContent='';
  renderVolumes();$('volumes-dialog').showModal();
}
function renderVolumes() {
  const fragment=document.createDocumentFragment();
  for(const chapter of organization.book.chapters){
    const row=element('label','','volume-row'), checkbox=document.createElement('input');
    checkbox.type='checkbox';checkbox.dataset.chapter=chapter.no;checkbox.checked=selectedChapters.has(chapter.no);
    checkbox.setAttribute('aria-label',`Select ${chapter.volume ? chapter.volume + ' ' : ''}Chapter ${chapter.number ?? chapter.no}`);
    checkbox.onchange=()=>{if(checkbox.checked)selectedChapters.add(chapter.no);else selectedChapters.delete(chapter.no);updateSelectAll()};
    row.append(checkbox,element('span',`Chapter ${chapter.number ?? chapter.no} · ${chapter.title}`),element('small',assignedVolumes[chapter.no]||'No volume'));
    fragment.append(row);
  }
  $('volume-chapters').replaceChildren(fragment);
  $('volume-names').replaceChildren(...[...new Set(Object.values(assignedVolumes).filter(Boolean))].map(name=>new Option(name,name)));
  updateSelectAll();
}
function updateSelectAll(){
  const count=selectedChapters.size,total=organization.book.chapters.length;
  $('select-all-chapters').checked=count===total;
  $('select-all-chapters').indeterminate=count>0&&count<total;
}
$('select-all-chapters').onchange=e=>{
  selectedChapters=new Set(e.target.checked?organization.book.chapters.map(c=>c.no):[]);renderVolumes();
};
$('assign-volume').onclick=()=>{
  if(!selectedChapters.size){$('volumes-error').textContent='Select at least one chapter.';return}
  for(const no of selectedChapters)assignedVolumes[no]=$('volume-name').value.trim();
  $('volumes-error').textContent='';renderVolumes();
};
$('volumes-form').onsubmit=async e=>{
  e.preventDefault();$('save-volumes').disabled=true;
  try{
    await setVolumes(organization.book.id,assignedVolumes,organization.state.revision);
    $('volumes-dialog').close();await renderLibrary();message('Volume organization saved.');
  }catch(error){$('volumes-error').textContent=error.message}
  finally{$('save-volumes').disabled=false}
};
for(const id of ['close-volumes','cancel-volumes'])$(id).onclick=()=>$('volumes-dialog').close();
renderLibrary().catch(e => message(`Could not open browser storage: ${e.message}`, true));
fetch('current-book.json').then(async response => {
  if (!response.ok) return;
  currentBook = await response.json(); $('current-title').textContent = currentBook.title;
  $('original-reader').hidden = !currentBook.hasOriginalReader;
  $('current-project').hidden = false;
}).catch(() => {});

if (serverMode) {
  document.querySelector('.file-box small').textContent = 'Plain text or Word .docx · up to 30 MB · saved on your server';
  document.querySelector('.device-label').textContent = 'Shared server library · automatic sync';
  document.querySelector('.library footer').replaceChildren(element('p','Books and drafts are saved on your server. Open the same server address on another device to continue.'));
  const actions = document.querySelector('.library-actions');
  const migrate = element('button','Import browser library');
  migrate.onclick = async () => {
    migrate.disabled = true;
    try { const books = await migrateBrowserLibrary(); await renderLibrary(); message(books.length ? `Copied ${books.length} browser books to the server. Original browser copies are kept.` : 'No books in this browser. Use Restore backup to import a JSON export from your old address.'); }
    catch(e) { message(e.message,true); } finally { migrate.disabled = false; }
  };
  const backup = element('button','Back up server now');
  backup.onclick = async () => { try { const result = await backupServer(); message('SQLite snapshot created: ' + result.backup); } catch(e) { message(e.message,true); } };
  actions.append(migrate,backup);
  serverStatus().then(status => message(status.backupError ? 'Automatic backup error: ' + status.backupError : `Server storage active · automatic SQLite backup every ${Math.round(status.backupIntervalSeconds / 60)} minutes · ${status.backupCount} snapshots.`,!!status.backupError)).catch(()=>{});
  setInterval(() => { if (!document.hidden && !document.querySelector('dialog[open]')) renderLibrary().catch(()=>{}); },10000);
}
