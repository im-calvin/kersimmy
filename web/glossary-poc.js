const dialog = document.getElementById('glossary-dialog');
const table = document.getElementById('glossary-terms');
const status = document.getElementById('glossary-status');
const add = document.getElementById('glossary-add');
const storageKey = 'reader-glossary-poc:' + location.pathname.split('/')[2];
const fields = [
  ['chinese', 'Chinese', 200],
  ['english', 'English', 400],
  ['note', 'Usage note', 1000],
];
let terms = [];
let lastSaved = null;

function save(next) {
  try {
    if (window.localStorage.getItem(storageKey) !== lastSaved) {
      status.textContent = 'This glossary changed in another tab. Reopen it to load the latest terms.';
      return false;
    }
    const encoded = JSON.stringify(next);
    window.localStorage.setItem(storageKey, encoded);
    lastSaved = encoded;
    terms = next;
    status.textContent = 'Saved in this browser.';
    return true;
  } catch {
    status.textContent = 'Could not save this change. Browser storage is unavailable or full.';
    return false;
  }
}

function render() {
  table.replaceChildren();
  if (!terms.length) {
    const cell = table.insertRow().insertCell();
    cell.colSpan = 4;
    cell.textContent = 'No terms yet.';
  }
  terms.forEach((term, index) => {
    const row = table.insertRow();
    for (const [field, label, maxLength] of fields) {
      const input = document.createElement('input');
      input.maxLength = maxLength;
      input.setAttribute('aria-label', label + ' for term ' + (index + 1));
      input.value = term[field];
      input.addEventListener('input', () => {
        const updated = terms.map((entry, i) => i === index ? {...entry, [field]: input.value} : entry);
        if (!save(updated)) input.value = terms[index][field];
      });
      row.insertCell().append(input);
    }
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', 'Remove term ' + (index + 1));
    remove.addEventListener('click', () => {
      if (save(terms.filter((_, i) => i !== index))) {
        render();
        (table.rows[index]?.querySelector('input') || add).focus();
      }
    });
    row.insertCell().append(remove);
  });
}

document.getElementById('open-glossary').addEventListener('click', () => {
  status.textContent = '';
  add.disabled = false;
  try {
    lastSaved = window.localStorage.getItem(storageKey);
    terms = JSON.parse(lastSaved ?? '[]');
    render();
  } catch {
    terms = [];
    render();
    add.disabled = true;
    status.textContent = 'Could not read the glossary from browser storage.';
  }
  dialog.showModal();
});
add.addEventListener('click', () => {
  if (save([...terms, {chinese: '', english: '', note: ''}])) {
    render();
    table.lastElementChild.querySelector('input').focus();
  }
});
document.getElementById('glossary-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('keydown', event => event.stopPropagation());

const source = document.getElementById('cn');
const tooltip = document.getElementById('glossary-tooltip');
const tooltipEnglish = document.getElementById('glossary-tooltip-english');
const tooltipNote = document.getElementById('glossary-tooltip-note');
const termDetails = new WeakMap();
let activeTerm;

function hideGlossaryTooltip() {
  activeTerm?.removeAttribute('aria-describedby');
  activeTerm = null;
  tooltip.hidden = true;
}

function showGlossaryTooltip(event) {
  const mark = event.target.closest('.glossary-term');
  if (!mark || mark === activeTerm || dialog.open) return;
  const definition = termDetails.get(mark);
  hideGlossaryTooltip();
  activeTerm = mark;
  tooltipEnglish.textContent = definition.english;
  tooltipNote.textContent = definition.note;
  tooltip.hidden = false;
  mark.setAttribute('aria-describedby', tooltip.id);
  const {clientX, clientY} = event;
  const anchor = [...mark.getClientRects()].find(rect => clientX >= rect.left && clientX <= rect.right
    && clientY >= rect.top && clientY <= rect.bottom) || mark.getBoundingClientRect();
  const {offsetWidth, offsetHeight} = tooltip;
  const gap = 8, edge = 12;
  const below = anchor.bottom + gap;
  const top = below + offsetHeight <= innerHeight - edge ? below : anchor.top - gap - offsetHeight;
  tooltip.style.left = Math.max(edge, Math.min(anchor.left, innerWidth - offsetWidth - edge)) + 'px';
  tooltip.style.top = Math.max(edge, top) + 'px';
}

source.addEventListener('pointerover', showGlossaryTooltip);
source.addEventListener('focusin', showGlossaryTooltip);
source.addEventListener('pointerout', event => {
  if (activeTerm?.contains(event.target) && !activeTerm.contains(event.relatedTarget)) hideGlossaryTooltip();
});
source.addEventListener('focusout', event => {
  if (event.target === activeTerm) hideGlossaryTooltip();
});
source.addEventListener('scroll', hideGlossaryTooltip, {passive: true});
window.addEventListener('resize', hideGlossaryTooltip);
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') hideGlossaryTooltip();
});

function markGlossaryTerms() {
  hideGlossaryTooltip();
  let saved;
  try { saved = JSON.parse(window.localStorage.getItem(storageKey) ?? '[]'); }
  catch { return; }
  if (!Array.isArray(saved)) return;
  const definitions = new Map();
  for (const term of saved) {
    if (typeof term?.chinese !== 'string') continue;
    const key = term.chinese.trim();
    const english = typeof term.english === 'string' ? term.english.trim() : '';
    const note = typeof term.note === 'string' ? term.note.trim() : '';
    if (key && (english || note)) definitions.set(key, {english, note});
  }
  const keys = [...definitions.keys()].sort((a, b) => b.length - a.length);
  for (const paragraph of source.querySelectorAll('p')) {
    const text = paragraph.textContent;
    const parts = document.createDocumentFragment();
    let written = 0;
    for (let index = 0; keys.length && index < text.length;) {
      const key = keys.find(candidate => text.startsWith(candidate, index));
      if (!key) { index++; continue; }
      parts.append(text.slice(written, index));
      const mark = document.createElement('span');
      mark.className = 'glossary-term';
      mark.textContent = key;
      mark.tabIndex = 0;
      termDetails.set(mark, definitions.get(key));
      parts.append(mark);
      index += key.length;
      written = index;
    }
    if (written || paragraph.querySelector('.glossary-term')) {
      parts.append(text.slice(written));
      paragraph.replaceChildren(parts);
    }
  }
}
new MutationObserver(markGlossaryTerms).observe(source, {childList:true});
dialog.addEventListener('close', markGlossaryTerms);
window.addEventListener('storage', event => {
  if (event.key === storageKey) markGlossaryTerms();
});
markGlossaryTerms();
