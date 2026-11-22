import {dismissOnBackdrop} from './dialogs.js';
import {previewManuscript, getBundle, setVolumes, updateImport, deleteBook, setBookIcon} from './db.js';
const stripHeading = text => text.replace(/^\s*(?:Chapter|Ch\.?)\s+\d+[^\n]*\n/i, '').trim();
import {listBooks, serverMode, migrateBrowserLibrary, backupServer, serverStatus, getBook, getState, importBooks, backupPayload, readBackup, download, filename, stamp} from './db.js';
const $ = id => document.getElementById(id);
document.querySelectorAll('dialog').forEach(dismissOnBackdrop);
let preview = null, currentBook = null, parsingVersion = 0, importTarget = null;
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
const bookCards = new Map();
let libraryRefresh = 0;

async function readBookIcon(file) {
  if (file.size > 5 * 1024 * 1024) throw new Error('Choose an image smaller than 5 MB.');
  const image = await createImageBitmap(file);
  try {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 128;
    const scale = 128 / Math.max(image.width, image.height);
    const width = image.width * scale, height = image.height * scale;
    canvas.getContext('2d').drawImage(image, (128 - width) / 2, (128 - height) / 2, width, height);
    return canvas.toDataURL('image/png');
  } finally {
    image.close();
  }
}

function createBookCard(id) {
  const card = element('article', '', 'book-card');
  const counts = element('p', '', 'eyebrow');
  const heading = element('div', '', 'book-card-heading');
  const icon = document.createElement('img');
  icon.className = 'book-card-icon';
  icon.alt = '';
  icon.hidden = true;
  const title = element('h2', '');
  heading.append(icon, title);
  const actions = element('div', '', 'card-actions');
  const link = element('a', '', 'book-link');
  link.href = `/books/${encodeURIComponent(id)}/draft`;
  const settings = element('button', 'Settings', 'subtle');
  settings.onclick = async () => {
    settings.disabled = true;
    try { await openBookSettings(id); } catch (error) { message(error.message, true); }
    finally { settings.disabled = false; }
  };
  actions.append(link, settings);
  card.append(counts, heading, actions);

  function update(book, state) {
    const drafted = Object.values(state.drafts).some(text => stripHeading(text));
    const chapterCount = book.chapters.length;
    const displayTitle = book.title.replace(/^TTEOTM\s*(?:[–—:·-]\s*)?\(?\s*Eng(?:lish)?\.?\s+drafts?\s+for\s+chapte(?:rs?|s)\s+2\s*[–—-]\s*6\s*\)?$/i, 'TTEOTM');
    const labels = [
      [counts, `${chapterCount} ${chapterCount === 1 ? 'chapter' : 'chapters'}`],
      [title, displayTitle],
      [link, drafted ? 'Continue' : 'Open manuscript'],
    ];
    for (const [node, text] of labels) if (node.textContent !== text) node.textContent = text;
    link.setAttribute('aria-label', `${link.textContent} ${displayTitle}`);
    if (book.icon && icon.getAttribute('src') !== book.icon) icon.src = book.icon;
    if (!book.icon) icon.removeAttribute('src');
    icon.hidden = !book.icon;
  }
  return {card, update};
}

async function renderLibrary() {
  const refresh = ++libraryRefresh;
  const books = (await listBooks()).sort((a,b) => b.createdAt.localeCompare(a.createdAt));
  const states = await Promise.all(books.map(book => getState(book.id)));
  if (refresh !== libraryRefresh) return;
  const container = $('books');
  $('backup-library').disabled = !books.length;
  const ids = new Set(books.map(book => book.id));
  for (const [id, {card}] of bookCards) {
    if (!ids.has(id)) {
      card.remove();
      bookCards.delete(id);
    }
  }
  const placeholder = container.querySelector('.empty-library');
  if (!books.length) {
    if (!placeholder) {
      const empty = element('div', '', 'empty-library');
      empty.append(element('span', '文 / A', 'empty-mark'), element('h2', 'Your library starts here'), element('p', 'Add a manuscript to see its chapters and begin translating.'));
      container.append(empty);
    }
    return;
  }
  placeholder?.remove();
  let next = container.firstChild;
  books.forEach((book, index) => {
    if (!bookCards.has(book.id)) bookCards.set(book.id, createBookCard(book.id));
    const {card, update} = bookCards.get(book.id);
    update(book, states[index]);
    if (card !== next) container.insertBefore(card, next);
    next = card.nextSibling;
  });
}
function invalidate() {
  parsingVersion++; preview = null; $('confirm-import').disabled = true; $('preview').hidden = true; $('import-error').textContent = '';
}
function openImport(target = null) {
  importTarget = target;
  $('import-form').reset();
  invalidate();
  const book = target?.book;
  $('import-title').textContent = book ? 'Recheck manuscript import' : 'Add a manuscript';
  $('confirm-import').textContent = book ? 'Update existing book' : 'Add to library';
  $('book-title').readOnly = !!book;
  if (book) {
    $('book-title').value = book.title;
    for (const [id, value] of [
      ['encoding', book.encoding], ['paragraph-mode', book.paragraphMode],
      ['heading-mode', book.headingMode], ['volume-mode', book.volumeMode],
    ]) {
      if ([...$(id).options].some(option => option.value === value)) $(id).value = value;
    }
    $('heading-regex').value = book.headingRegex || '';
  }
  $('custom-heading').hidden = $('heading-mode').value !== 'custom';
  $('import-dialog').showModal();
}
$('add-book').onclick = () => openImport();
$('close-import').onclick = () => $('import-dialog').close();
$('manuscript').onchange = () => {
  invalidate();
  const file = $('manuscript').files[0];
  if (file && !importTarget) $('book-title').value = file.name.replace(/\.(txt|docx)$/i, '');
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
    if (version !== parsingVersion) return;
    preview = parsed;
    const existing = importTarget?.book.chapters;
    const compatible = !existing || (existing.length === parsed.chapters.length && existing.every((old,index) => {
      const chapter = parsed.chapters[index];
      return old.no === chapter.no && old.paras.length === chapter.paras.length
        && old.paras.every((text,p) => text === chapter.paras[p]);
    }));
    if (existing && compatible) parsed.chapters.forEach((chapter,index) => {chapter.title ||= existing[index].title;});
    renderPreviewChapters(parsed.chapters);
    $('preview-chapter').selectedIndex = 0;
    $('preview-summary').textContent = `${parsed.chapters.length} chapters · ${parsed.chapters.reduce((n,c) => n+c.paras.length, 0).toLocaleString()} paragraphs · ${parsed.encoding} · ${parsed.paragraphMode}`;
    $('preview-warnings').textContent = parsed.warnings.join(' ');
    showPreview(); $('preview').hidden = false; $('confirm-import').disabled = !compatible;
    if (!compatible) $('import-error').textContent = 'Chapter boundaries or source text changed. Add this file as a new manuscript to keep existing work safe.';
  } catch (e) { $('import-error').textContent = e.message; }
  finally { $('parse').disabled = false; }
};
function chapterLabel(chapter) {
  const number = chapter.no === 0 ? 'Preface' : 'Chapter ' + (chapter.number ?? chapter.no);
  return [number, chapter.title].filter(Boolean).join(' · ');
}
function renderPreviewChapters(chapters) {
  const fragment = document.createDocumentFragment();
  let volume, group = fragment;
  for (const chapter of chapters) {
    if (chapter.volume !== volume) {
      volume = chapter.volume;
      group = fragment;
      if (volume) {
        group = document.createElement('optgroup');
        group.label = volume;
        fragment.append(group);
      }
    }
    group.append(new Option(chapterLabel(chapter), chapter.no));
  }
  $('preview-chapter').replaceChildren(fragment);
}
function selectedPreviewChapter() {
  return preview.chapters[$('preview-chapter').selectedIndex];
}
function showPreview() {
  const chapter = selectedPreviewChapter();
  $('preview-chapter-title').value = chapter.title;
  $('preview-text').replaceChildren(...chapter.paras.slice(0, 8).map(p => element('p', p)));
  if (chapter.paras.length > 8) $('preview-text').append(element('small', `… ${chapter.paras.length - 8} more paragraphs`));
}
$('preview-chapter').onchange = showPreview;
$('preview-chapter-title').oninput = event => {
  const chapter = selectedPreviewChapter();
  chapter.title = event.target.value.trim();
  $('preview-chapter').selectedOptions[0].textContent = chapterLabel(chapter);
};
$('import-form').onsubmit = async e => {
  e.preventDefault();
  if (!preview || $('confirm-import').disabled) return;
  $('confirm-import').disabled = true;
  try {
    if (importTarget) {
      await updateImport(importTarget.book.id, preview, importTarget.state.revision);
      message('Manuscript import updated.');
    } else {
      const [book] = await importBooks([{book:{...preview, title:$('book-title').value.trim()}}]);
      try {
        if (window.localStorage.getItem('translation-reader:draft-help-v1') !== '1'
          && !window.localStorage.getItem('translation-reader:draft-help-book')) {
          window.localStorage.setItem('translation-reader:draft-help-book', book.id);
        }
      } catch { /* The walkthrough can still be opened manually. */ }
      message(`“${book.title}” is ready. Open it to start translating.`);
    }
    $('import-dialog').close();
    await renderLibrary();
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
let organization=null, assignedVolumes={}, editedTitles={}, selectedChapters=new Set();
async function openBookSettings(id) {
  organization=await getBundle(id);assignedVolumes={};editedTitles={};selectedChapters=new Set();
  $('book-settings-danger').open=false;
  $('book-settings-status').textContent='';
  showSettingsIcon(organization.book.icon);
  for(const chapter of organization.book.chapters)assignedVolumes[chapter.no]=chapter.volume||'';
  $('volumes-book').textContent=organization.book.title;
  $('volume-name').value='';$('volumes-error').textContent='';
  renderVolumes();$('volumes-dialog').showModal();
}
function showSettingsIcon(icon) {
  const image = $('book-settings-icon');
  if (icon) image.src = icon;
  else image.removeAttribute('src');
  image.hidden = !icon;
}
$('choose-book-icon').onclick = () => $('book-icon-file').click();
$('book-icon-file').onchange = async () => {
  const input = $('book-icon-file'), file = input.files[0];
  input.value = '';
  if (!file) return;
  const target = organization;
  const button = $('choose-book-icon');
  button.disabled = true;
  try {
    const {icon} = await setBookIcon(target.book.id, await readBookIcon(file));
    target.book.icon = icon;
    if (organization === target) {
      showSettingsIcon(icon);
      $('book-settings-status').textContent = 'Book icon saved.';
    }
    await renderLibrary();
  } catch (error) {
    if (organization === target) $('volumes-error').textContent = error.message;
    else message(error.message, true);
  } finally { button.disabled = false; }
};
$('backup-book').onclick = async () => {
  const target = organization;
  try {
    await exportBooks([target.book]);
    if (organization === target) $('book-settings-status').textContent = 'Backup downloaded.';
  } catch (error) {
    if (organization === target) $('volumes-error').textContent = error.message;
    else message(error.message, true);
  }
};
function renderVolumes() {
  const fragment=document.createDocumentFragment();
  for(const chapter of organization.book.chapters){
    const row=element('div','','volume-row'), checkbox=document.createElement('input');
    checkbox.type='checkbox';checkbox.dataset.chapter=chapter.no;checkbox.checked=selectedChapters.has(chapter.no);
    checkbox.setAttribute('aria-label',`Select ${chapter.volume ? chapter.volume + ' ' : ''}Chapter ${chapter.number ?? chapter.no}`);
    checkbox.onchange=()=>{if(checkbox.checked)selectedChapters.add(chapter.no);else selectedChapters.delete(chapter.no);updateSelectAll()};
    const label=element('label',`Chapter ${chapter.number ?? chapter.no}`);
    const title=document.createElement('input');
    title.maxLength=200;title.placeholder='Optional title';title.value=editedTitles[chapter.no]??chapter.title;
    title.oninput=()=>{editedTitles[chapter.no]=title.value.trim();};
    label.append(title);
    row.append(checkbox,label,element('small',assignedVolumes[chapter.no]||'No volume'));
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
$('delete-book').onclick=async()=>{
  const target=organization;
  const {id,title}=target.book;
  const confirmation=prompt(`To delete “${title}” and its saved drafts and comments, type I am an idiot sandwich`);
  if(confirmation===null)return;
  if(confirmation!=='I am an idiot sandwich'){
    $('volumes-error').textContent='The confirmation phrase did not match.';
    return;
  }
  const button=$('delete-book');
  button.disabled=true;
  try {
    await deleteBook(id,target.state.revision,confirmation);
    try {
      const key='translation-reader:draft-help-book';
      if(window.localStorage.getItem(key)===id)window.localStorage.removeItem(key);
    } catch {}
    libraryRefresh++;
    bookCards.get(id)?.card.remove();
    bookCards.delete(id);
    if(organization===target)$('volumes-dialog').close();
    message(`Deleted “${title}”.`);
    await renderLibrary();
  } catch(error) {
    if(organization===target&&$('volumes-dialog').open)$('volumes-error').textContent=error.message;
    else message(error.message,true);
  } finally {
    button.disabled=false;
  }
};
$('volumes-form').onsubmit=async e=>{
  e.preventDefault();$('save-volumes').disabled=true;
  try{
    await setVolumes(organization.book.id,assignedVolumes,organization.state.revision,editedTitles);
    $('volumes-dialog').close();await renderLibrary();message('Chapter changes saved.');
  }catch(error){$('volumes-error').textContent=error.message}
  finally{$('save-volumes').disabled=false}
};
for(const id of ['close-volumes','cancel-volumes'])$(id).onclick=()=>$('volumes-dialog').close();
$('recheck-import').onclick=()=>{$('volumes-dialog').close();openImport(organization);};
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
  const versionLabel = element('p', '');
  document.querySelector('.library footer').replaceChildren(
    element('p','Books and drafts are saved on your server. Open the same server address on another device to continue.'),
    versionLabel,
  );
  versionLabel.hidden = true;
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
  let libraryRelease;
  serverStatus().then(status => {
    libraryRelease = status.release;
    if (status.version) {
      versionLabel.textContent = 'v' + status.version;
      versionLabel.hidden = false;
    }
    message(status.backupError ? 'Automatic backup error: ' + status.backupError : `Server storage active · automatic SQLite backup every ${Math.round(status.backupIntervalSeconds / 60)} minutes · ${status.backupCount} snapshots.`,!!status.backupError);
  }).catch(()=>{});
  setInterval(async () => {
    if (document.hidden || document.querySelector('dialog[open]')) return;
    try {
      const status = await serverStatus();
      if (document.hidden || document.querySelector('dialog[open]')) return;
      if (libraryRelease && status.release !== libraryRelease) location.reload();
      else {
        libraryRelease = status.release;
        await renderLibrary();
      }
    } catch { /* Try again on the next refresh. */ }
  },10000);
}
