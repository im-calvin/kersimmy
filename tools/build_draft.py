#!/usr/bin/env python3
"""
Build the drafting surface: Chinese source (left) | minimal editor with italics (right).

One chapter at a time. The editor autosaves per chapter to localStorage, but
localStorage is treated as scratch, not as the archive — the durable store is
Google Docs, reached via Exports → Copy for Google Docs.

Scroll sync works on PARAGRAPH INDEX, not proportion: your Nth English paragraph
maps to the Nth Chinese paragraph, which is valid from the first line onward
because translation is sequential. Drift from merges/splits is corrected by
clicking the Chinese paragraph that actually matches — that sets a per-chapter
offset. (Proportional mapping, by contrast, is meaningless mid-chapter and is
only used in the review page, sync.html.)

Usage:
  python3 build_draft.py SOURCE.txt OUT.html [--chapters 1-10] [--all]
"""
import argparse
import html
import json
import sys
from pathlib import Path

from tlconfig import load_config, parse_source, pick
from illustration import load_illustration
import draft_comments
import draft_editor
import reader_theme
from chapter_structure import options as chapter_options

CSS = """
.volume{font:12px/1.5 -apple-system,sans-serif;color:var(--volume);margin:0 0 .6rem}

:root{--fs:19px}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);overflow:hidden}
body{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif}
header{height:44px;display:flex;align-items:center;gap:.6rem;padding:0 .9rem;
  border-bottom:1px solid var(--line);font-size:13px;color:var(--dim)}
header .sp{flex:1}
header b{color:var(--ink);font-size:13px}
select,button{font:inherit;color:var(--dim);background:none;border:0;
  padding:.2rem .4rem;border-radius:4px;cursor:pointer}
select{color:var(--ink);border:1px solid var(--line);background:var(--control);
  max-width:14rem}
button:hover{color:var(--ink);background:var(--hover)}
button[aria-pressed="true"]{color:var(--accent);background:var(--accent-soft)}
button.act{border:1px solid var(--line);background:var(--control)}
#wrap{display:flex;height:calc(100% - 44px)}
@media(max-width:750px){
  body{display:flex;flex-direction:column}
  header{height:auto;min-height:44px;flex-wrap:wrap;padding:.45rem .9rem}
  #wrap{flex:1;min-height:0;height:auto}
}
#cn{flex:1;overflow-y:auto;padding:1.7rem 1.7rem 50vh;border-right:1px solid var(--line);
  font-family:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",serif}
#cn h2{font-size:calc(var(--fs) * .95);font-weight:600;margin:0 0 1.3rem;color:var(--heading)}
#cn p{font-size:var(--fs);line-height:1.95;margin:0 0 .5em;text-indent:1em;
  border-radius:3px;transition:background .12s ease}
#cn p.hit{background:var(--reading);box-shadow:-.6rem 0 0 -.55rem var(--accent-line)}
#cn p{cursor:pointer;user-select:text}
#alignment-dialog{width:min(65rem,94vw);max-height:80vh;color:var(--ink);background:var(--bg);border:1px solid var(--line)}
#alignment-dialog table{width:100%;border-collapse:collapse;table-layout:fixed}
#alignment-dialog th,#alignment-dialog td{text-align:left;vertical-align:top;padding:.5rem;border-bottom:1px solid var(--line);overflow-wrap:anywhere;white-space:pre-wrap}
#alignment-dialog th:first-child{width:4rem}
.reader-menu summary{cursor:pointer}
.reader-menu>div{position:absolute;right:1rem;z-index:35;background:var(--bg);border:1px solid var(--line);padding:.4rem}
.exports-menu>div{display:grid;gap:.45rem;width:min(17rem,calc(100vw - 2rem));
  max-height:65vh;overflow:auto;padding:.65rem}
.exports-menu button{text-align:left;color:var(--ink)}
.reader-menu label{display:grid;gap:.25rem;color:var(--heading)}
.reader-options label{margin-top:.45rem}
.reader-menu input{width:100%;font:inherit;color:var(--ink);background:var(--control);
  border:1px solid var(--line);border-radius:4px;padding:.3rem .4rem}
#snapshot-options:not([hidden]){display:grid;gap:.35rem;border-top:1px solid var(--line);padding-top:.45rem}
#snapshot-status{margin:0;color:var(--heading)}
#snapshot-status:empty{display:none}
#pane{position:relative;flex:1;display:flex;flex-direction:column;min-width:0}
#draft-help{position:fixed;inset:0;z-index:42;pointer-events:none;overflow:hidden}
#draft-help-spotlight{position:absolute;border-radius:6px;outline:2px solid #a9d4ff;
  box-shadow:0 0 0 200vmax rgb(12 14 19 / .72)}
#draft-help-card{position:absolute;pointer-events:auto;
  width:min(24rem,calc(100% - 24px));max-height:calc(100% - 24px);overflow:auto;
  padding:1rem;border:1px solid var(--line);border-radius:.5rem;
  background:var(--bg);color:var(--ink);box-shadow:0 6px 20px #29241e20;
  font-size:14px;line-height:1.45}
#draft-help h2{margin:0;font-size:17px}
#draft-help p{margin:.5rem 0 1rem}
#draft-help .actions{display:flex;align-items:center;justify-content:flex-end;gap:.5rem}
#draft-help button{color:var(--ink)}
#ta{flex:1;width:100%;border:0;outline:0;resize:none;background:var(--surface);
  padding:1.7rem 1.7rem 40vh;font-family:"Iowan Old Style",Georgia,serif;
  font-size:var(--fs);line-height:1.7;color:var(--ink)}
#ta::placeholder{color:var(--placeholder)}
#ta::highlight(translation-reading){background:var(--reading)}
#foot{height:30px;display:flex;align-items:center;gap:.8rem;padding:0 .9rem;
  border-top:1px solid var(--line);font-size:11.5px;color:var(--dim);
  background:var(--bg)}
#foot .sp{flex:1}
#al{white-space:nowrap;color:var(--ink);font-variant-numeric:tabular-nums}
#ind{font-variant-numeric:tabular-nums}
#ind.dirty{color:var(--accent)}
#warn{display:none;color:var(--error);font-weight:600}
#find{position:absolute;inset:44px 0 0 0;background:var(--surface);z-index:30;
  display:none;flex-direction:column;padding:1rem 1.2rem}
#find.on{display:flex}
#find .top{display:flex;flex-wrap:wrap;gap:.7rem;align-items:center;padding-bottom:.9rem}
#q{flex:1;font:17px/1.5 "Songti SC","Noto Serif CJK SC",serif;padding:.5rem .7rem;
  border:1px solid var(--line);border-radius:7px;background:var(--control);color:var(--ink)}
#find .top button{border:1px solid var(--line);background:var(--control);padding:.4rem .8rem}
#verdict{font-size:15px;font-weight:600;color:var(--ink);padding:.2rem 0 .1rem}
#verdict.none{color:var(--status)}
#verdict.recur{color:var(--accent)}
#hits{flex:1;overflow-y:auto;border-top:1px solid var(--line);padding-top:.6rem}
#hits .h{display:flex;gap:.8rem;padding:.4rem 0;border-bottom:1px solid var(--line)}
#hits .ref{flex:0 0 5.6rem;font-size:11.5px;color:var(--dim);
  font-variant-numeric:tabular-nums;padding-top:.2rem}
#hits .tx{flex:1;font-family:"Songti SC","Noto Serif CJK SC",serif;
  font-size:15px;line-height:1.75}
#hits .more{font-size:12px;color:var(--dim);padding:.7rem 0}
#stats{position:absolute;left:0;top:44px;width:min(52%,37rem);
  max-height:calc(100% - 52px);background:var(--surface);z-index:30;display:none;
  flex-direction:column;border-right:1px solid var(--line);
  border-bottom:1px solid var(--line);border-bottom-right-radius:10px;
  box-shadow:0 10px 30px -14px rgba(0,0,0,.22)}
#stats.on{display:flex}
#stats .top{display:flex;gap:.8rem;align-items:center;padding:.8rem 1rem;
  border-bottom:1px solid var(--line);font-size:13px;color:var(--dim)}
#stats .top b{color:var(--ink);font-size:14px}
#stats .top .sp{flex:1}
#wpp{width:5rem;font:inherit;color:var(--ink);border:1px solid var(--line);
  border-radius:5px;padding:.25rem .4rem;background:var(--control);text-align:right}
#stats .body{flex:1;overflow-y:auto;padding:1rem}
.cards{display:grid;gap:.6rem;padding-bottom:1.1rem;
  grid-template-columns:repeat(3,1fr)}
.card{border:1px solid var(--line);border-radius:10px;background:var(--control);
  padding:.8rem .85rem;aspect-ratio:1/.82;display:flex;flex-direction:column;
  justify-content:center}
.card .k{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;
  color:var(--dim);line-height:1.35}
.card .v{font-size:25px;font-weight:600;padding-top:.3rem;line-height:1.1;
  font-variant-numeric:tabular-nums}
.card .s{font-size:11px;color:var(--dim);padding-top:.25rem;line-height:1.4}
#gifcell{border:1px solid var(--line);border-radius:10px;overflow:hidden;
  aspect-ratio:1/.82;background:var(--control)}
#gifcell img{width:100%;height:100%;object-fit:cover;display:block}
#bar{height:7px;border-radius:4px;background:var(--subtle);overflow:hidden;
  margin:0 0 1.4rem}
#bar i{display:block;height:100%;background:var(--accent-line)}
"""

JS = r"""
const CH = __CHAPTERS__;
const KEY='__PFX__draft:en', PKEY='__PFX__draft:pos', SKEY='__PFX__draft:smart',
      FKEY='__PFX__draft:fs', CKEY='__PFX__draft:cur';
const cn=document.getElementById('cn'), ta=document.getElementById('ta'),
      sel=document.getElementById('sel'), ind=document.getElementById('ind'),
      wc=document.getElementById('wc');
let store=read(), pos=readPos(), cur=+localStorage.getItem(CKEY)||CH[0].no;
/* per-chapter active time. A gap longer than IDLE is treated as away-from-desk;
   anything shorter counts, because staring at a line is the work. */
const TKEY='__PFX__draft:time', IDLE=180000;
let times=readTimes(), lastIn=0;
function readTimes(){try{return JSON.parse(localStorage.getItem(TKEY)||'{}')}
  catch(e){return{}}}
function bumpTime(){
  const now=Date.now();
  if(lastIn)times[cur]=(times[cur]||0)+Math.min(now-lastIn,IDLE);
  lastIn=now;
}
let smart=localStorage.getItem(SKEY)!=='0';
let dirty=false, timer=null;

function read(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return{}}}
function readPos(){try{return JSON.parse(localStorage.getItem(PKEY)||'{}')}catch(e){return{}}}
function chap(n){return CH.find(c=>c.no===n)}

/* ---------- persistence ---------- */
function commit(){
  store[cur]=ta.value;
  try{
    const write=()=>{
      localStorage.setItem(KEY,JSON.stringify(store));
      localStorage.setItem(PKEY,JSON.stringify(pos));
      localStorage.setItem(TKEY,JSON.stringify(times));
      localStorage.setItem(NKEY,JSON.stringify(comments));
      localStorage.setItem(IKEY,JSON.stringify(italics));
    };
    if(localStorage.batch)localStorage.batch(write);else write();
    dirty=false; ind.classList.remove('dirty');
    ind.textContent='saved '+new Date().toLocaleTimeString([],
      {hour:'2-digit',minute:'2-digit'});
    sizeCheck();
  }catch(err){
    ind.textContent='SAVE FAILED';
    const w=document.getElementById('warn');
    w.style.display='inline';
    w.textContent='storage full — copy this chapter into Docs now';
  }
}
function recordEdit(){
  dirty=true; ind.classList.add('dirty'); ind.textContent='unsaved…';
  bumpTime(); count(); clearTimeout(timer); timer=setTimeout(commit,400);
}
function touch(){
  clearReadingHighlight();
  trackFormatting();
  trackCommentEdits();
  drawCommentHighlights();
  recordEdit();
  tick(false);
}
function sizeCheck(){
  const bytes=new Blob([JSON.stringify(store)]).size;
  const w=document.getElementById('warn');
  if(bytes>2e6){ w.style.display='inline';
    w.textContent='local draft store is '+(bytes/1e6).toFixed(1)
      +'MB — dump older chapters into Docs'; }
  else if(w.textContent.indexOf('storage full')<0){ w.style.display='none'; }
}
addEventListener('beforeunload',e=>{ if(dirty){ commit(); e.preventDefault();
  e.returnValue=''; } });
document.addEventListener('visibilitychange',()=>{ if(dirty)commit(); });
ta.addEventListener('blur',()=>{ if(dirty)commit(); });

/* ---------- chapter switching ---------- */
function load(n){
  if(n!==cur&&!closeComments(false)){sel.value=cur;return}
  if(dirty)commit();
  pos[cur]=cn.scrollTop;
  cur=n; lastIn=0; localStorage.setItem(CKEY,n);
  const c=chap(n);
  cn.innerHTML=(c.volume?'<div class="volume">'+esc(c.volume)+'</div>':'')+'<h2>第'+(c.number??c.no)+'章 '+esc(c.title)+'</h2>'
    + c.paras.map((p,i)=>'<p id="c'+c.no+'p'+(i+1)+'">'+esc(p)+'</p>').join('');
  sourceScrollTarget=null;
  cn.scrollTop=pos[n]||0;
  clearReadingHighlight();
  currentEnglish=1;
  ta.value=store[n]||'';
  englishScrollTop=ta.scrollTop;
  annotationText=ta.value;
  for(const note of chapterComments())if(ta.value.slice(note.start,note.end)!==note.quote)note.detached=true;
  drawCommentHighlights();
  sel.value=n;
  highlights=[];
  ind.classList.remove('dirty'); ind.textContent=store[n]?'saved':'empty';
  count();
  if(syncOn&&ta.value.trim())updateSync(true);
  else document.getElementById('al').textContent='';
}
function step(d){
  const i=CH.findIndex(c=>c.no===cur)+d;
  if(i>=0&&i<CH.length)load(CH[i].no);
}
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}

function chapterInfo(n){
  const row=(window.CORPUS||[]).find(r=>r[0]===n);
  return CH.find(c=>c.no===n)||(row?{no:row[0],title:row[1],...row[3]}:{no:n});
}
function chapterReference(n){const c=chapterInfo(n);return (c.volume?c.volume+' · ':'')+'第'+(c.number??c.no)+'章'}
function copyHeading(){const c=chap(cur);return (c.volume?c.volume+'\n\n':'')+'Chapter '+(c.number??c.no)}
function count(){
  const t=bodyText();
  const words=t?t.split(/\s+/).length:0;
  const c=chap(cur);
  const src=c.paras.reduce((a,p)=>a+p.length,0);
  wc.textContent=words.toLocaleString()+' words · '+src.toLocaleString()
    +' source chars'+(words?' · '+(words/src).toFixed(2)+' w/char':'');
  const mins=(times[cur]||0)/60000, rt=document.getElementById('rt');
  rt.textContent=(mins>=1&&words)
    ? Math.round(words/(mins/60)).toLocaleString()+' w/h · '
      +(mins>=60?(mins/60).toFixed(1)+'h':Math.round(mins)+'m')
    : '';
}

/* ---------- typography ---------- */
ta.addEventListener('beforeinput',e=>{
  if(e.defaultPrevented||e.isComposing||e.inputType!=='insertText')return;
  if(e.data==='/'&&ta.selectionStart===ta.selectionEnd){
    const end=ta.selectionStart;
    const match=/(?:^|[\s([{“‘])\/([^/\n]+)$/.exec(ta.value.slice(0,end));
    const phrase=match?.[1];
    if(phrase&&phrase.trim()===phrase&&!/^(?:https?:|www\.)/i.test(phrase)){
      e.preventDefault();
      ta.setSelectionRange(end-phrase.length-1,end);
      document.execCommand('insertHTML',false,'<i>'+esc(phrase)+'</i>');
      return;
    }
  }
  if(!smart)return;
  const d=e.data, s=ta.selectionStart, prev=ta.value[s-1]||'';
  let rep=null, from=s;
  if(d==='"'){ rep=(s===0||/[\s([{—‘“]/.test(prev))?'“':'”'; }
  else if(d==="'"){ rep=(s===0||/[\s([{—]/.test(prev))?'‘':'’'; }
  else if(d==='-'&&prev==='-'){ rep='—'; from=s-1; }
  if(rep===null)return;
  e.preventDefault();
  ta.setRangeText(rep,from,ta.selectionEnd,'end');
  touch();
});
ta.addEventListener('input',touch);
function toggleSmart(){
  smart=!smart; localStorage.setItem(SKEY,smart?'1':'0');
  document.getElementById('sq').setAttribute('aria-pressed',smart);
}

/* ---------- paragraph-index scroll sync ---------- */
const YKEY='__PFX__draft:sync', OKEY='__PFX__draft:off', GKEY='__PFX__draft:alignment-groups';
let syncOn=localStorage.getItem(YKEY)!=='0';
let offs=readOffs(), alignmentGroups={}, highlights=[], raf=0;
let englishScrollTop=ta.scrollTop, scrollPending=false, readingEnglish=null, currentEnglish=1;
try{alignmentGroups=JSON.parse(localStorage.getItem(GKEY)||'{}')||{}}catch{}
function saveAlignmentGroups(){localStorage.setItem(GKEY,JSON.stringify(alignmentGroups))}
function orderedAlignmentGroups(){
  const groups=alignmentGroups[cur]||{};
  const ordered=[];
  let previousEnglish=0, previousEnd=offs[cur]|0;
  for(const english of Object.keys(groups).map(Number).sort((a,b)=>a-b)){
    const [savedStart,savedEnd]=groups[english];
    // Older drafts may contain overlaps. Read them in forward order
    // without overwriting the saved links.
    const earliest=english===1?1:Math.max(1,previousEnd+english-previousEnglish);
    const start=Math.max(savedStart,earliest), end=Math.max(start,savedEnd);
    ordered.push({english,start,end});
    previousEnglish=english;previousEnd=end;
  }
  return ordered;
}
function sourceRange(english, ordered=orderedAlignmentGroups()){
  let previousEnglish=0, previousEnd=offs[cur]|0;
  for(const group of ordered){
    if(group.english>english)break;
    if(group.english===english)return [group.start,group.end];
    previousEnglish=group.english;previousEnd=group.end;
  }
  const source=previousEnd+english-previousEnglish;
  return [source,source];
}
function canAlign(english,start,end){
  const ordered=orderedAlignmentGroups();
  const lower=english===1?1:Math.max(1,sourceRange(english-1,ordered)[1]+1);
  const next=ordered.find(group=>group.english>english);
  const upper=next?next.start-(next.english-english):chap(cur).paras.length;
  return start>=lower&&end<=upper;
}
function setSourceHighlights(elements){
  for(const element of highlights)if(!elements.includes(element))element.classList.remove('hit');
  for(const element of elements)element.classList.add('hit');
  highlights=elements;
}
function readOffs(){try{return JSON.parse(localStorage.getItem(OKEY)||'{}')}
  catch(e){return{}}}
function saveOffs(){localStorage.setItem(OKEY,JSON.stringify(offs))}

/* A leading "Chapter 2" line is scaffolding, not a paragraph: it must not
   consume an index, or every chapter is misaligned by one from the first
   keystroke. Ignored here, and re-emitted canonically on export. */
function isHead(l){
  const s=l.trim();
  return s.length<60 && /^(?:chapter|chap\.?|ch\.?|第)\s*\d+\b/i.test(s);
}
/* count real paragraphs among lines[0..upto-1], skipping blanks and a
   leading heading. Blank lines are ignored, so double-spacing is harmless. */
function idxBefore(lines,upto){
  let n=0, skippedHeading=false;
  for(let i=0;i<upto;i++){
    const l=lines[i];
    if(!l.trim())continue;
    if(n===0&&!skippedHeading&&isHead(l)){skippedHeading=true;continue}
    n++;
  }
  return n;
}
function paraAt(off){
  const lines=ta.value.slice(0,off).split('\n');
  return idxBefore(lines,lines.length-1);
}
function enCaret(){ return paraAt(ta.selectionStart) }
function visibleTranslationAtEdge(snapshot,upward,pane){
  const lines=[...translationLines(snapshot.text)];
  // Look at rendered text rather than hit-testing the top edge, which can
  // resolve to the previous paragraph when it lands on a blank line.
  let start=0,end=lines.length;
  while(start<end){
    const middle=(start+end)>>>1;
    const line=lines[middle];
    const range=editorRange(line.start,line.end,snapshot);
    const bounds=range.getBoundingClientRect();
    if(upward?bounds.top<pane.bottom:bounds.bottom<=pane.top)start=middle+1;
    else end=middle;
  }
  const line=lines[upward?start-1:start];
  if(!line)return null;
  const range=editorRange(line.start,line.end,snapshot);
  const bounds=range.getBoundingClientRect();
  return bounds.bottom>pane.top&&bounds.top<pane.bottom?{...line,range}:null;
}
function hasEditorSelection(){
  const selection=getSelection();
  return !!selection?.anchorNode&&ta.contains(selection.anchorNode)&&ta.contains(selection.focusNode);
}
function caretInView(pane=ta.getBoundingClientRect()){
  if(!hasEditorSelection())return false;
  const offset=ta.selectionStart, snapshot=editorSnapshot();
  const range=editorRange(offset,offset,snapshot);
  const container=range.startContainer;
  const box=range.getClientRects()[0]||(container!==ta&&container.nodeType===1?container.getBoundingClientRect():null);
  return !!box&&box.bottom>pane.top&&box.top<pane.bottom;
}
function moveCaretToVisibleLine(visible,snapshot,upward,pane){
  const selection=getSelection();
  if(document.activeElement!==ta||!selection?.isCollapsed||!hasEditorSelection())return;
  let start=visible.start,end=visible.end;
  // Locate the character at the visible edge even within a wrapped paragraph.
  while(start<end){
    const middle=(start+end)>>>1;
    const bounds=editorRange(middle,middle+1,snapshot).getBoundingClientRect();
    if(upward?bounds.top<pane.bottom:bounds.bottom<=pane.top)start=middle+1;
    else end=middle;
  }
  let character=upward?start-1:start;
  if(character<visible.start||character>=visible.end)return;
  const isLowSurrogate=offset=>/[\uDC00-\uDFFF]/.test(snapshot.text.charAt(offset));
  if(isLowSurrogate(character))character--;
  const after=character+(isLowSurrogate(character+1)?2:1);
  let caretOffset=upward?after:character;
  const caret=editorRange(caretOffset,caretOffset,snapshot).getClientRects()[0];
  if(caret&&(caret.bottom<=pane.top||caret.top>=pane.bottom)){
    caretOffset=upward?character:after;
  }
  ta.setSelectionRange(caretOffset,caretOffset);
}
function updateSync(force,fromScroll,reading=null){
  const al=document.getElementById('al');
  const delta=fromScroll?ta.scrollTop-englishScrollTop:0;
  const upward=delta<0;
  const viewport=ta.getBoundingClientRect();
  const lineHeight=parseFloat(getComputedStyle(ta).lineHeight)||24;
  const buffer=alignedInPanes&&delta?Math.min(lineHeight,viewport.height/4):0;
  let edge={top:viewport.top+(upward?0:buffer),bottom:viewport.bottom-(upward?buffer:0)};
  const visibleCaret=!fromScroll||caretInView(edge);
  const snapshot=fromScroll?editorSnapshot():null;
  let visible=visibleCaret?null:visibleTranslationAtEdge(snapshot,upward,edge);
  if(!visible&&!visibleCaret&&buffer){
    edge=viewport;
    visible=visibleTranslationAtEdge(snapshot,upward,edge);
  }
  if(syncOn&&alignedInPanes&&visible)moveCaretToVisibleLine(visible,snapshot,upward,edge);
  const english=reading??(visibleCaret?enCaret()+1:visible?.english);
  if(english!==undefined)currentEnglish=english;
  if(fromScroll){
    englishScrollTop=ta.scrollTop;
    if(syncOn&&alignedInPanes&&delta){
      sourceScrollTarget=null;
      cn.scrollTo({top:cn.scrollTop+delta,behavior:'instant'});
    }
  }
  if(!syncOn){ al.textContent=''; return; }
  if(english===undefined){
    al.textContent='';
    setSourceHighlights([]);
    setReadingHighlight(null);
    return;
  }
  const c=chap(cur);
  const [start,end]=sourceRange(english);
  const elements=[];
  for(let number=Math.max(1,start);number<=Math.min(c.paras.length,end);number++){
    const paragraph=document.getElementById('c'+cur+'p'+number);
    if(paragraph)elements.push(paragraph);
  }
  const first=elements[0], offset=start-english;
  const label=start===end?String(start):start+'–'+end;
  al.textContent='EN '+english+' ↔ 中文 '+(first?label:'—')
    +(offset?' (offset '+(offset>0?'+':'')+offset+')':'');
  setSourceHighlights(elements);
  if(fromScroll){
    setReadingHighlight(first&&(visible?.range??translationRange(english,snapshot)));
  }
  if(!first||reading!==null)return;
  if(alignedInPanes){
    if(!fromScroll||!visibleCaret)followSourceRange(first,elements.at(-1),force);
  }else{
    const desiredTop=cn.getBoundingClientRect().top+cn.clientHeight*.28;
    const adjustment=first.getBoundingClientRect().top-desiredTop;
    if(force||Math.abs(adjustment)>1)cn.scrollTop+=adjustment;
  }
}
function tick(fromScroll){
  scrollPending||=!!fromScroll;
  if(raf)return;
  raf=requestAnimationFrame(()=>{
    raf=0;
    const scrolled=scrollPending;
    scrollPending=false;
    updateSync(false,scrolled);
  });
}
ta.addEventListener('keyup',()=>{clearReadingHighlight();tick(false)});
ta.addEventListener('click',()=>{clearReadingHighlight();tick(false)});
ta.addEventListener('scroll',()=>{
  if(readingEnglish!==null&&ta.scrollTop===englishScrollTop)return;
  readingEnglish=null;
  tick(true);
},{passive:true});
function toggleSync(){
  englishScrollTop=ta.scrollTop;
  syncOn=!syncOn; localStorage.setItem(YKEY,syncOn?'1':'0');
  document.getElementById('sy').setAttribute('aria-pressed',syncOn);
  cn.classList.toggle('linked',syncOn);
  if(!syncOn){
    setSourceHighlights([]);
    clearReadingHighlight();
    sourceScrollTarget=null;
    cn.scrollTo({top:cn.scrollTop,behavior:'instant'});
  }
  updateSync(true);
}
function setReadingHighlight(range){
  if(!globalThis.CSS?.highlights)return;
  if(range&&globalThis.Highlight)CSS.highlights.set('translation-reading',new Highlight(range));
  else CSS.highlights.delete('translation-reading');
}
function clearReadingHighlight(){
  readingEnglish=null;
  setReadingHighlight(null);
}
function* translationLines(text){
  let english=0, offset=0, skippedHeading=false;
  for(const line of text.split('\n')){
    const start=offset;
    offset+=line.length+1;
    if(!line.trim())continue;
    if(!english&&!skippedHeading&&isHead(line)){skippedHeading=true;continue}
    yield {english:++english,start,end:start+line.length};
  }
}
function translationRange(english,snapshot){
  for(const line of translationLines(snapshot.text)){
    if(line.english===english)return editorRange(line.start,line.end,snapshot);
  }
  return null;
}
function readMatchingTranslation(source){
  const snapshot=editorSnapshot(), ordered=orderedAlignmentGroups();
  for(const {english,start,end} of translationLines(snapshot.text)){
    const [first,last]=sourceRange(english,ordered);
    if(source<first||source>last)continue;
    const range=editorRange(start,end,snapshot);
    const firstLine=range.getClientRects()[0];
    if(!firstLine)return;
    readingEnglish=english;
    setReadingHighlight(range);
    // Scroll only the English pane. Don't place a caret or focus the editor.
    const bounds=ta.getBoundingClientRect();
    if(firstLine.top<bounds.top||firstLine.bottom>bounds.bottom){
      ta.scrollTop+=firstLine.top-bounds.top-24;
    }
    englishScrollTop=ta.scrollTop;
    scrollPending=false;
    if(raf){cancelAnimationFrame(raf);raf=0}
    updateSync(false,false,english);
    return;
  }
}
/* Ordinary reading clicks must never change saved alignment. */
function isAlignmentGesture(event){
  return syncOn&&event.button===0
    &&!event.ctrlKey&&!event.metaKey&&(event.altKey||event.shiftKey);
}
cn.addEventListener('mousedown',event=>{
  if(isAlignmentGesture(event)&&event.target.closest('p[id]'))event.preventDefault();
});
cn.addEventListener('click',e=>{
  if(!syncOn||e.button!==0)return;
  const paragraph=e.target.closest('p[id]');
  const match=paragraph?.id.match(/^c\d+p(\d+)$/);
  if(!match)return;
  if(!isAlignmentGesture(e)){
    if(!e.altKey&&!e.shiftKey&&!e.metaKey&&!e.ctrlKey&&getSelection()?.isCollapsed){
      readMatchingTranslation(Number(match[1]));
    }
    return;
  }
  const english=readingEnglish??(caretInView()?enCaret()+1:currentEnglish), source=Number(match[1]);
  const groups=alignmentGroups[cur]||{};
  if(e.shiftKey||Object.keys(groups).length){
    const [start,end]=sourceRange(english), sourceCount=chap(cur).paras.length;
    const canExtend=e.shiftKey&&start>=1&&end<=sourceCount;
    const first=canExtend?Math.min(start,source):source;
    const last=canExtend?Math.max(end,source):source;
    if(canAlign(english,first,last)){
      groups[english]=[first,last];
      alignmentGroups[cur]=groups;
      saveAlignmentGroups();
    }
  }else{
    offs[cur]=source-english;
    saveOffs();
  }
  updateSync(true,false,english);
});
const alignedInPanes=__ALIGN_IN_PANES__;
let sourceScrollTarget=null;
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
function followSourceRange(first,last,force){
  const pane=cn.getBoundingClientRect(), margin=16;
  const top=first.getBoundingClientRect().top, bottom=last.getBoundingClientRect().bottom;
  const above=top<pane.top, below=bottom>pane.bottom;
  let adjustment;
  if(above||(below&&bottom-top>cn.clientHeight-2*margin)){
    adjustment=top-pane.top-margin;
  }else if(below){
    adjustment=bottom-pane.bottom+margin;
  }else{
    // The translation is still alongside its source. Leave both panes alone.
    if(sourceScrollTarget!==null&&Math.abs(cn.scrollTop-sourceScrollTarget)<1)sourceScrollTarget=null;
    return;
  }
  const destination=Math.max(0,Math.min(cn.scrollHeight-cn.clientHeight,cn.scrollTop+adjustment));
  if(Math.abs(cn.scrollTop-destination)<1)return;
  if(!force&&sourceScrollTarget!==null&&Math.abs(sourceScrollTarget-destination)<1)return;
  sourceScrollTarget=destination;
  cn.scrollTo({top:destination,behavior:reducedMotion.matches?'instant':'smooth'});
}
cn.addEventListener('scrollend',()=>{sourceScrollTarget=null;});
function openAlignment(){
  const chinese=chap(cur).paras, english=bodyText().split('\n').filter(line=>line.trim());
  const offset=offs[cur]|0, dialog=document.getElementById('alignment-dialog');
  const rows=dialog.querySelector('tbody');
  rows.replaceChildren();
  const ordered=orderedAlignmentGroups();
  const pairs=english.map((text,index)=>({text,range:sourceRange(index+1,ordered)}));
  const linked=new Set();
  for(const {range:[start,end]} of pairs){
    for(let n=Math.max(1,start);n<=Math.min(chinese.length,end);n++)linked.add(n);
  }
  const entries=pairs.map(({text,range:[start,end]})=>[start,end,text]);
  chinese.forEach((_,index)=>{if(!linked.has(index+1))entries.push([index+1,index+1,''])});
  entries.sort((a,b)=>a[0]-b[0]);
  for(const [start,end,text] of entries){
    const row=rows.insertRow();
    row.insertCell().textContent=start===end?String(start):start+'–'+end;
    row.insertCell().textContent=chinese.slice(Math.max(0,start-1),Math.max(0,end)).join('\n');
    row.insertCell().textContent=text;
  }
  dialog.querySelector('p').textContent='Draft paragraph offset: '+offset+'. Blank lines and the chapter heading are skipped.';
  document.querySelector('.reader-options').open=false;
  dialog.showModal();
}
function resetAlign(){
  const groups=alignmentGroups[cur], english=currentEnglish;
  if(groups?.[english]){
    delete groups[english];
    if(!Object.keys(groups).length)delete alignmentGroups[cur];
    saveAlignmentGroups();
  }else{
    offs[cur]=0;
    saveOffs();
  }
  updateSync(true,false,english);
}

/* ---------- term lookup across the whole manuscript ---------- */
function openFind(){
  if(dirty)commit();
  const s=(window.getSelection()?String(window.getSelection()):'').trim();
  const f=document.getElementById('find'), q=document.getElementById('q');
  f.classList.add('on');
  if(s&&s.length<=24)q.value=s;
  q.focus(); q.select(); runFind();
}
function closeFind(){
  document.getElementById('find').classList.remove('on'); ta.focus();
}
function findMatches(corpus,query,translation){
  const results=[];
  for(const [no,,source] of corpus){
    const paragraphs=translation?stripHead(store[no]||'').split('\n').filter(p=>p.trim()):source;
    for(let i=0;i<paragraphs.length;i++){
      const paragraph=paragraphs[i];
      let matches=0;
      for(let index=paragraph.indexOf(query);index!==-1;
          index=paragraph.indexOf(query,index+query.length))matches++;
      if(matches)results.push([no,i+1,paragraph,matches]);
    }
  }
  return results;
}
let findLimit=40;
function runFind(more=false){
  if(more!==true)findLimit=40;
  else findLimit+=40;
  const q=document.getElementById('q').value.trim();
  const V=document.getElementById('verdict'), R=document.getElementById('hits');
  V.className=''; R.innerHTML='';
  if(!q){V.textContent=''; return}
  const C=window.CORPUS;
  if(!C){V.textContent='corpus.js not loaded — keep it beside this file.'; return}
  let translation=!/\p{Script=Han}/u.test(q);
  let results=findMatches(C,q,translation);
  if(!results.length){
    translation=!translation;
    results=findMatches(C,q,translation);
  }
  const count=results.length;
  const matches=results.reduce((total,hit)=>total+hit[3],0);
  const chapters=new Set(results.map(hit=>hit[0])).size;
  const side=translation?'translation':'source';
  V.className=count?'recur':'none';
  V.textContent=count?matches+(matches===1?' match':' matches')+' in '+count+' '+side+(count===1?' paragraph':' paragraphs')
    +' across '+chapters+(chapters===1?' chapter.':' chapters.'):'No matches in the source or translation.';
  const CAP=findLimit;
  R.innerHTML=results.slice(0,CAP).map(h=>
    '<div class="h"><div class="ref">'+esc(chapterReference(h[0]))+' &para;'+h[1]+'</div>'
    +'<div class="tx">'+esc(h[2])+'</div></div>').join('')
    +(results.length>CAP?'<div class="more">…and '+(results.length-CAP)
      +' more. <button type="button" onclick="runFind(true)">show more</button></div>':'');
}

/* ---------- project statistics ---------- */
const WKEY='__PFX__draft:wpp';
function allBodies(){
  return Object.keys(store).map(Number).filter(n=>!isNaN(n))
    .sort((a,b)=>a-b).map(n=>[n,stripHead(store[n])]).filter(x=>x[1]);
}
function words(t){ return t.split(/\s+/).filter(Boolean) }
function fmtDur(ms){
  const m=Math.round(ms/60000);
  return m<60? m+'m' : Math.floor(m/60)+'h '+String(m%60).padStart(2,'0')+'m';
}
function openStats(){
  document.getElementById('stats').classList.add('on'); renderStats();
}
function closeStats(){ document.getElementById('stats').classList.remove('on'); }
function setWpp(){
  const v=Math.max(50,Math.min(1000,+document.getElementById('wpp').value||__WPP__));
  localStorage.setItem(WKEY,v); renderStats();
}
function renderStats(){
  if(dirty)commit();
  const bodies=allBodies();
  const wpp=+localStorage.getItem(WKEY)||__WPP__;
  document.getElementById('wpp').value=wpp;

  /* totals */
  let wTotal=0, cjk=0;
  const byNo={}; (window.CORPUS||[]).forEach(r=>byNo[r[0]]=r[2]);
  bodies.forEach(([n,b])=>{
    wTotal+=words(b).length;
    if(byNo[n])cjk+=byNo[n].reduce((a,p)=>a+p.length,0);
  });
  const srcTotal=Object.keys(byNo).reduce((a,k)=>
    a+byNo[k].reduce((x,p)=>x+p.length,0),0);
  const msTotal=Object.keys(times).reduce((a,k)=>a+(times[k]||0),0);
  const pct=srcTotal?cjk/srcTotal*100:0;
  const nCh=Object.keys(byNo).length;

  const card=(k,v,s)=>'<div class="card"><div class="k">'+k+'</div><div class="v">'
    +v+'</div>'+(s?'<div class="s">'+s+'</div>':'')+'</div>';
  document.getElementById('cards').innerHTML=
     card('time on project',fmtDur(msTotal),'recorded chapter time')
    +card('english words',wTotal.toLocaleString(),
          bodies.length+(bodies.length===1?' chapter':' chapters')+' drafted')
    +card('chinese translated',cjk.toLocaleString(),
          'of '+srcTotal.toLocaleString()+' characters')
    +card('pages',Math.ceil(wTotal/wpp).toLocaleString(),'at '+wpp+' words/page')
    +card('progress',pct.toFixed(1)+'%',bodies.length+' of '+nCh+' chapters')
    +'__GIF__';
  document.getElementById('bar').innerHTML='<i style="width:'+pct.toFixed(2)+'%"></i>';

}

/* ---------- export ---------- */
/* strip any heading the user typed, so export emits exactly one canonical
   "Chapter N" — absolute numbering, never duplicated, never per-volume */
function stripHead(t){
  const lines=(t||'').replace(/\r/g,'').split('\n');
  let i=0;
  while(i<lines.length&&!lines[i].trim())i++;
  if(i<lines.length&&isHead(lines[i]))i++;
  return lines.slice(i).join('\n').trim();
}
function bodyText(){ return stripHead(ta.value) }
function payload(){ return copyHeading()+'\n\n'+bodyText()+'\n'; }
function copyDocs(){
  if(dirty)commit();
  const selection=[ta.selectionStart,ta.selectionEnd];
  const t=payload(), tmp=document.createElement('textarea');
  tmp.value=t; document.body.appendChild(tmp); tmp.select();
  const body=bodyText(), start=ta.value.indexOf(body), shift=(copyHeading()+'\n\n').length-start;
  const formats=(italics[cur]||[]).map(r=>({start:Math.max(start,r.start)+shift,end:Math.min(start+body.length,r.end)+shift})).filter(r=>r.start<r.end);
  const copy=e=>{e.clipboardData.setData('text/plain',t);e.clipboardData.setData('text/html',editorFormattedHTML(t,formats));e.preventDefault()};
  document.addEventListener('copy',copy);
  let ok=false; try{ ok=document.execCommand('copy'); }catch(e){}
  finally{document.removeEventListener('copy',copy)}
  document.body.removeChild(tmp);
  document.getElementById('exports-menu').open=false;
  ta.focus();ta.setSelectionRange(...selection);
  backup();   /* snapshot every time a chapter goes out to Docs */
  ind.textContent=ok?'copied ch '+cur+' — paste into Docs (backup saved)'
                   :'copy failed';
}
/* every drafted chapter in one timestamped .txt. Old snapshots are left alone
   on purpose: a single overwritten file would carry corruption into the only
   copy, and a page cannot delete downloads anyway. */
function stamp(){
  const d=new Date(), p=x=>String(x).padStart(2,'0');
  return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())
    +'-'+p(d.getHours())+p(d.getMinutes());
}
function backup(){
  if(dirty)commit();
  const nums=Object.keys(store).map(Number)
    .filter(n=>!isNaN(n)&&stripHead(store[n])).sort((a,b)=>a-b);
  if(!nums.length){ind.textContent='nothing to back up yet'; return}
  let words=0;
  const parts=nums.map(n=>{
    const b=stripHead(store[n]);
    words+=b.split(/\s+/).filter(Boolean).length;
    return 'Chapter '+n+'\n\n'+b;
  });
  const s=stamp();
  const head='__PROJ__ draft backup · '+s.replace(/-(\d{4})$/,' $1')+' · '
    +nums.length+(nums.length===1?' chapter · ':' chapters · ')
    +words.toLocaleString()+' words\nchapters: '+nums.join(', ')
    +'\n\n'+'='.repeat(64)+'\n\n';
  const b=new Blob([head+parts.join('\n\n\n')+'\n'],
    {type:'text/plain;charset=utf-8'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(b);
  a.download='__SLUG__-draft-'+s+'.txt';
  a.click(); URL.revokeObjectURL(a.href);
}
/* A portable snapshot for migration to the web library. Keep the text backup
   above unchanged, and never rename or remove existing browser storage keys. */
function projectSnapshot(){
  if(dirty)commit();
  pos[cur]=cn.scrollTop;
  const corpus=window.CORPUS;
  if(!corpus||!corpus.length){ind.textContent='corpus.js is needed for a full project backup';return}
  const readJSON=(key,fallback)=>{try{return JSON.parse(localStorage.getItem(key)||'null')||fallback}catch(e){return fallback}};
  const legacyStorage={};
  for(let i=0;i<localStorage.length;i++){
    const key=localStorage.key(i);
    if(key.startsWith('__PFX__draft:')||key.startsWith('__PFX__sync:')||key.startsWith('__PFX__reader'))legacyStorage[key]=localStorage.getItem(key);
  }
  const wpp=+localStorage.getItem(WKEY)||__WPP__;
  const book={title:'__PROJ__',sourceName:'',wordsPerPage:wpp,illustration:__ILLUSTRATION_DATA__,
    chapters:corpus.map(row=>({no:row[0],title:row[1],paras:row[2],...row[3]}))};
  const state={drafts:store,comments:comments,commentAuthor:localStorage.getItem(AUTHOR_KEY)||'',italics:italics,current:cur,positions:pos,offsets:offs,alignmentGroups:alignmentGroups,times:times,
    fontSize:parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs'))||19,
    smart:smart,sync:syncOn,wordsPerPage:wpp,
    reviewEnglish:readJSON('__PFX__sync:en',{}),
    reviewMode:localStorage.getItem('__PFX__sync:mode')||'chapter',
    reviewFontSize:parseFloat(localStorage.getItem('__PFX__sync:fs'))||19,
    legacyStorage:legacyStorage};
  return {format:'translation-reader',version:1,exportedAt:new Date().toISOString(),books:[{book:book,state:state}]};
}
function fullProjectBackup(){
  const data=projectSnapshot();
  if(!data)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='__SLUG__-full-project-'+stamp()+'.json';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
  ind.textContent='full project saved — use Restore backup in the web library';
}
let snapshotTimer, snapshotDirectory, snapshotWriting=false;
const snapshotOptions=document.getElementById('snapshot-options');
const snapshotButton=document.getElementById('snapshot-toggle');
const snapshotInterval=document.getElementById('snapshot-minutes');
const snapshotStatus=document.getElementById('snapshot-status');
snapshotOptions.hidden=!!window.readerStart||typeof window.showDirectoryPicker!=='function';

function stopSnapshots(message){
  clearInterval(snapshotTimer);
  snapshotDirectory=null;
  snapshotButton.textContent='Choose snapshot folder';
  snapshotInterval.disabled=false;
  snapshotStatus.textContent=message;
}
async function writeProjectSnapshot(){
  if(!snapshotDirectory||snapshotWriting)return;
  snapshotWriting=true;
  const directory=snapshotDirectory;
  let writer;
  try{
    const data=projectSnapshot();
    if(!data)throw new Error('Keep corpus.js beside the reader to make snapshots.');
    const timestamp=data.exportedAt.replace(/[:.]/g,'-');
    const file=await directory.getFileHandle('__SLUG__-snapshot-'+timestamp+'.json',{create:true});
    writer=await file.createWritable();
    await writer.write(JSON.stringify(data));
    await writer.close();
    if(snapshotDirectory===directory)snapshotStatus.textContent='Snapshot saved at '+new Date().toLocaleTimeString()+'.';
  }catch(error){
    try{await writer?.abort()}catch{}
    if(snapshotDirectory===directory)stopSnapshots('Snapshots stopped. '+error.message);
  }finally{snapshotWriting=false;}
}
snapshotButton.addEventListener('click',async()=>{
  if(snapshotDirectory){stopSnapshots('Snapshots stopped.');return}
  if(!snapshotInterval.reportValidity())return;
  const minutes=snapshotInterval.valueAsNumber;
  snapshotButton.disabled=true;
  try{
    snapshotDirectory=await window.showDirectoryPicker({mode:'readwrite'});
    snapshotButton.textContent='Stop snapshots';
    snapshotInterval.disabled=true;
    await writeProjectSnapshot();
    if(snapshotDirectory)snapshotTimer=setInterval(writeProjectSnapshot,minutes*60000);
  }catch(error){
    if(error.name!=='AbortError')stopSnapshots('Could not open the snapshot folder. '+error.message);
  }finally{snapshotButton.disabled=false;}
});
function fs(d){
  let v=parseFloat(getComputedStyle(document.documentElement)
    .getPropertyValue('--fs'));
  v=Math.max(14,Math.min(30,v+d));
  document.documentElement.style.setProperty('--fs',v+'px');
  localStorage.setItem(FKEY,v+'px');
  paintCommentHighlights();
}
const viewMenu=document.querySelector('.reader-options');
const readerMenus=document.querySelectorAll('.reader-menu');
document.addEventListener('click',event=>{
  for(const menu of readerMenus){
    if(menu.open&&!menu.contains(event.target))menu.open=false;
  }
});
const draftHelp=document.getElementById('draft-help');
const helpSpotlight=document.getElementById('draft-help-spotlight');
const helpCard=document.getElementById('draft-help-card');
const helpSteps=[...draftHelp.querySelectorAll('section')];
const helpBack=document.getElementById('draft-help-back');
const helpNext=document.getElementById('draft-help-next');
const helpKey='translation-reader:draft-help-v1';
let helpStep=0;
function guidingComment(){
  return !draftHelp.hidden&&helpSteps[helpStep].dataset.target==='#comment-add';
}
function positionDraftHelp(){
  if(draftHelp.hidden)return;
  const target=guidingComment()&&commentAdd.hidden
    ?ta:document.querySelector(helpSteps[helpStep].dataset.target);
  const bounds=target.getBoundingClientRect();
  const edge=12, gap=16, padding=5;
  const left=Math.max(0,bounds.left-padding);
  const top=Math.max(0,bounds.top-padding);
  const right=Math.min(innerWidth,target===ta?Math.min(bounds.right,bounds.left+360):bounds.right+padding);
  const bottom=Math.min(innerHeight,target===ta?Math.min(bounds.bottom,bounds.top+104):bounds.bottom+padding);
  Object.assign(helpSpotlight.style,{left:left+'px',top:top+'px',
    width:Math.max(0,right-left)+'px',height:Math.max(0,bottom-top)+'px'});
  const x=Math.max(edge,Math.min(left,innerWidth-helpCard.offsetWidth-edge));
  const height=helpCard.offsetHeight;
  const below=bottom+gap, above=top-gap-height;
  const y=below+height<=innerHeight-edge?below:above>=edge?above:innerHeight-height-edge;
  Object.assign(helpCard.style,{left:x+'px',top:Math.max(edge,y)+'px'});
}
function showDraftHelpStep(){
  helpSteps.forEach((step,index)=>step.hidden=index!==helpStep);
  helpBack.hidden=helpStep===0;
  helpNext.textContent=helpStep===helpSteps.length-1?'Start translating':'Next';
  positionDraftHelp();
}
function closeDraftHelp(focusEditor=false){
  if(draftHelp.hidden)return;
  draftHelp.hidden=true;
  try{window.localStorage.setItem(helpKey,'1')}catch{}
  if(focusEditor)ta.focus();
}
document.getElementById('open-draft-help').addEventListener('click',()=>{
  viewMenu.open=false;
  helpStep=0;
  draftHelp.hidden=false;
  showDraftHelpStep();
  helpNext.focus();
});
helpBack.addEventListener('click',()=>{
  helpStep--;
  showDraftHelpStep();
  if(helpBack.hidden)helpNext.focus();
});
helpNext.addEventListener('click',()=>{
  if(helpStep===helpSteps.length-1){closeDraftHelp(true);return}
  helpStep++;
  showDraftHelpStep();
});
document.getElementById('draft-help-skip').addEventListener('click',()=>closeDraftHelp(true));
document.addEventListener('pointerdown',event=>{
  if(guidingComment()&&ta.contains(event.target))return;
  if(!draftHelp.contains(event.target))closeDraftHelp();
});
ta.addEventListener('focus',()=>{if(!guidingComment())closeDraftHelp()});
document.getElementById('comment-add').addEventListener('click',()=>closeDraftHelp());
const helpLayout=new ResizeObserver(positionDraftHelp);
helpLayout.observe(draftHelp);
helpLayout.observe(ta);
addEventListener('keydown',e=>{
  if(e.target.closest('dialog'))return;
  if(e.key==='Escape'&&!draftHelp.hidden){e.preventDefault();closeDraftHelp(true);return}
  if(e.key==='Escape'){
    const menu=document.querySelector('.reader-menu[open]');
    if(menu){menu.open=false;menu.querySelector('summary').focus();return}
  }
  if((e.metaKey||e.ctrlKey)&&e.key==='s'){e.preventDefault();commit();return}
  if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){e.preventDefault();copyDocs();return}
  if((e.metaKey||e.ctrlKey)&&e.shiftKey&&e.key.toLowerCase()==='f'){
    e.preventDefault();openFind();return}
  if(e.key==='Escape'){closeFind();return}
  if(e.target===ta||e.target.tagName==='INPUT')return;
  if(e.key==='='||e.key==='+')fs(1); else if(e.key==='-')fs(-1);
});

(function init(){
  const f=localStorage.getItem(FKEY);
  if(f)document.documentElement.style.setProperty('--fs',f);
  sel.innerHTML=__CHAPTER_OPTIONS__;
  document.getElementById('sq').setAttribute('aria-pressed',smart);
  document.getElementById('sy').setAttribute('aria-pressed',syncOn);
  cn.classList.toggle('linked',syncOn);
  if(!chap(cur))cur=CH[0].no;
  load(cur); sizeCheck();
  try{
    const pendingKey='translation-reader:draft-help-book';
    const pendingBook=window.localStorage.getItem(pendingKey);
    if(window.readerStart&&pendingBook===location.pathname.split('/')[2]&&window.localStorage.getItem(helpKey)!=='1'){
      window.localStorage.setItem(helpKey,'1');
      window.localStorage.removeItem(pendingKey);
      draftHelp.hidden=false;
    }
  }catch{}
  showDraftHelpStep();
})();
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Draft</title>
<script data-reader-theme>{theme_script}</script>
<style>{css}</style>
</head>
<body>
<header>
  <button class="act" onclick="step(-1)" title="previous chapter">&larr;</button>
  <select id="sel" onchange="load(+this.value)"></select>
  <button class="act" onclick="step(1)" title="next chapter">&rarr;</button>
  <span class="sp"></span>
  <button id="sy" onclick="toggleSync()"
    title="Click Chinese text to read its translation. Option/Alt-click to set alignment or Shift-click to extend the range.">
    sync</button>
  <details class="reader-menu reader-options"><summary>View</summary><div>
{alignment_button}
  <button id="sq" onclick="toggleSmart()" title="curly quotes and em dashes as you type">
    &ldquo;&nbsp;&rdquo;</button>
  <button onclick="fs(-1)">A&minus;</button>
  <button onclick="fs(1)">A+</button>
  {theme_control}
  <button type="button" id="open-draft-help" aria-controls="draft-help">Walkthrough</button>
  <label>Word comment author <input id="comment-author" maxlength="100" placeholder="Translator"></label>
  </div></details>
  <details class="reader-menu exports-menu" id="exports-menu"><summary id="exports-trigger">Exports</summary><div>
  <button onclick="exportWord()" title="export all drafted chapters with comments">Word</button>
  <button onclick="copyDocs()" title="copy with Chapter heading (Cmd+Enter)">Copy for Google Docs</button>
  <button onclick="backup()" title="download every drafted chapter as one timestamped .txt">Draft text backup</button>
  <button onclick="fullProjectBackup()"
    title="source, drafts, timings, settings and review text for the web library">Full project backup</button>
  <!-- hosted-import-drafts -->
  <section id="snapshot-options" hidden>
    <label>Snapshot interval (minutes) <input type="number" id="snapshot-minutes" min="1" max="1440" value="15" required></label>
    <button type="button" id="snapshot-toggle">Choose snapshot folder</button>
    <p id="snapshot-status" role="status"></p>
  </section>
  </div></details>
  <button id="italic" type="button" aria-label="Italic" title="italic (Cmd/Ctrl+I)" aria-pressed="false" onmousedown="event.preventDefault()" onclick="toggleItalic()">I</button>
  <button class="act" onclick="openStats()" title="project statistics">stats</button>
  <button class="act" onclick="openFind()"
    title="Find across the book (Cmd+Shift+F, uses your selection)">find</button>
</header>
<div id="wrap">
  <div id="cn"></div>
  <div id="pane">
    <div id="ta" contenteditable="true" role="textbox" aria-label="Translation" aria-multiline="true" spellcheck="true"></div>
    <div id="comment-marks" aria-hidden="true"></div>
    <div id="foot">
      <span id="ind">&nbsp;</span>
      <span id="wc"></span>
      <button id="reattach-comments" type="button" onmousedown="event.preventDefault()" hidden></button>
      <span class="sp"></span>
      <span id="rt" title="total active time on this chapter, all sessions"></span>
      <span id="al"></span>
      <button onclick="resetAlign()" title="Remove the current range, or reset the chapter offset">reset</button>
      <span id="warn"></span>
    </div>
  </div>
</div>
<aside id="draft-help" aria-label="Draft walkthrough" hidden>
  <div id="draft-help-spotlight" aria-hidden="true"></div>
  <div id="draft-help-card">
    <div aria-live="polite">
      <section data-target="#sel">
        <h2>Choose a chapter</h2>
        <p>Use the chapter list or the arrows to move between chapters.</p>
      </section>
      <section data-target="#ta" hidden>
        <h2>Write your translation</h2>
        <p>Read the Chinese on the left and type your English on the right. Drafts save automatically.</p>
      </section>
      <section data-target="#italic" hidden>
        <h2>Use italics</h2>
        <p>Select text and click Italic, or press Cmd/Ctrl+I.</p>
      </section>
      <section data-target="#sy" hidden>
        <h2>Link Chinese and English</h2>
        <p>With sync on, click a Chinese paragraph to see its English. To link several Chinese paragraphs to one English line, put the cursor in that line, Option/Alt-click the first Chinese paragraph, then Shift-click the last.</p>
      </section>
      <section data-target="#comment-add" hidden>
        <h2>Leave a comment</h2>
        <p>Select English text to reveal the Add comment bubble beside it. If the draft is empty, type a few words first. Click the bubble to add a note.</p>
      </section>
      <section data-target="#exports-trigger" hidden>
        <h2>Export to Word</h2>
        <p>Open Exports and choose Word to download your drafts as a DOCX with italics and comments.</p>
      </section>
    </div>
    <div class="actions">
      <button type="button" id="draft-help-skip">Skip</button>
      <button type="button" id="draft-help-back" hidden>Back</button>
      <button type="button" id="draft-help-next" class="act">Next</button>
    </div>
  </div>
</aside>
{alignment}
<div id="find">
  <div class="top">
    <input id="q" aria-label="Term to look up" placeholder="term to look up" oninput="runFind()" spellcheck="false">
    <button onclick="closeFind()">close</button>
  </div>
  <div id="verdict" role="status"></div>
  <div id="hits"></div>
</div>
<div id="stats">
  <div class="top">
    <b>Project statistics</b>
    <span class="sp"></span>
    <label>words per page <input id="wpp" type="number" min="50" max="1000"
      onchange="setWpp()"></label>
    <button onclick="closeStats()">close</button>
  </div>
  <div class="body">
    <div class="cards" id="cards"></div>
    <div id="bar"></div>
  </div>
</div>
<script src="corpus.js"></script>
<script>{js}</script>
</body>
</html>
"""


ALIGNMENT_BUTTON = '<button type="button" aria-controls="alignment-dialog" onclick="openAlignment()">Aligned preview</button>'
ALIGNMENT_DIALOG = """<dialog id="alignment-dialog" aria-labelledby="alignment-title">
  <h2 id="alignment-title">Aligned preview</h2>
  <p></p>
  <div class="alignment-rows">
    <table>
      <thead><tr><th scope="col">#</th><th scope="col">Chinese</th><th scope="col">English</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
  <form method="dialog"><button class="act">Close</button></form>
</dialog>"""


def render_page(cfg, chapters, illustration=None):
    """Render the same drafting surface for a local file or the Python service."""
    payload = json.dumps(chapters, ensure_ascii=False).replace('<', '\\u003c')
    js = JS.replace('(function init(){', draft_editor.JS + '\n' + draft_comments.JS + '\n(function init(){')
    inline_alignment = cfg.get('inline_alignment', False)
    js = js.replace('__ALIGN_IN_PANES__', json.dumps(inline_alignment))
    js = js.replace('__CHAPTERS__', payload)
    js = js.replace('__CHAPTER_OPTIONS__', json.dumps(chapter_options(chapters), ensure_ascii=False).replace('<', '\\u003c'))
    js = js.replace("'__PROJ__'", json.dumps(cfg['project'], ensure_ascii=False).replace('<', '\\u003c'))
    js = js.replace('__PFX__', cfg['storage_prefix']).replace('__WPP__', str(int(cfg['words_per_page'])))
    js = js.replace('__SLUG__', cfg['slug']).replace('__ILLUSTRATION_DATA__', json.dumps(illustration, ensure_ascii=False).replace('<', '\\u003c'))
    gif = ('<div id="gifcell"><img src="{}" alt=""></div>'.format(html.escape(cfg['illustration'], quote=True)) if cfg.get('illustration') else '')
    js = js.replace("'__PROJ__ draft backup · '", json.dumps(cfg['project'] + ' draft backup · ', ensure_ascii=False).replace('<', '\\u003c'))
    js = js.replace('__GIF__', gif)
    return PAGE.replace('<script src="corpus.js"></script>', draft_comments.HTML + '<script src="corpus.js"></script>').format(css=reader_theme.CSS + CSS + draft_comments.CSS + draft_editor.CSS, js=js,
            theme_script=reader_theme.SCRIPT, theme_control=reader_theme.CONTROL,
            alignment='' if inline_alignment else ALIGNMENT_DIALOG,
            alignment_button='' if inline_alignment else ALIGNMENT_BUTTON)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--config', default=None)
    ap.add_argument('--chapters', default='1-10')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    cfg = load_config(args.config)
    chapters = parse_source(cfg)
    if not chapters:
        sys.exit('no chapters matched — run "python3 tlconfig.py" to diagnose')
    want = pick(chapters, args.chapters, args.all)

    use = [c for c in chapters if c['no'] in want]

    page = render_page(cfg, use, load_illustration(Path(args.out).resolve().parent, cfg.get('illustration')))
    with open(args.out, 'w', encoding='utf-8') as fh:
        fh.write(page)

    print('chapters in page :', len(use),
          '(第{}章 … 第{}章)'.format(use[0]['no'], use[-1]['no']))
    print('paragraphs       :', sum(len(c['paras']) for c in use))
    print('wrote            :', args.out)


if __name__ == '__main__':
    main()
