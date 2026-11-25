#!/usr/bin/env python3
"""
Build a two-pane side-by-side reader: Chinese (from source) | English (pasted).

Chapter headings are the sync points. Scroll either pane and the other follows,
either jumping at chapter boundaries or tracking proportionally within a chapter.

The English pane holds whatever you paste, keyed by chapter, persisted in
localStorage — so nothing is lost on reload and no file pipeline is needed yet.

Usage:
  python3 build_sync.py SOURCE.txt OUT.html [--chapters 1-10] [--all]
"""
import argparse
import html
import json
import sys
from pathlib import Path

import reader_theme
from chapter_structure import options as chapter_options, number as chapter_number, metadata
from tlconfig import load_config, parse_source, pick

CSS = """
.volume{font:12px/1.5 -apple-system,sans-serif;color:var(--volume);margin:0 0 .6rem}

:root{--fs:18px}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);overflow:hidden}
body{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif}
header{height:44px;display:flex;align-items:center;gap:.7rem;padding:0 .9rem;
  border-bottom:1px solid var(--line);font-size:13px;color:var(--dim);
  background:var(--bg)}
header .sp{flex:1}
header b{color:var(--ink);font-size:13px;font-weight:600}
select,button{font:inherit;color:var(--dim);background:none;border:0;
  padding:.2rem .35rem;border-radius:4px;cursor:pointer}
select{color:var(--ink);border:1px solid var(--line);background:var(--control)}
button:hover{color:var(--ink);background:var(--hover)}
button[aria-pressed="true"]{color:var(--accent);background:var(--accent-soft)}
#wrap{display:flex;height:calc(100% - 44px)}
section{flex:1;overflow-y:auto;overflow-x:hidden;position:relative;
  padding:1.6rem 1.6rem 60vh;scroll-behavior:auto}
#cn{border-right:1px solid var(--line)}
section h2{font-size:calc(var(--fs) * .95);font-weight:600;margin:2.2rem 0 1.1rem;
  padding-top:.4rem;border-top:1px solid var(--line);color:var(--heading)}
section h2:first-of-type{margin-top:0;border-top:0}
section p{font-size:var(--fs);margin:0 0 .5em;text-indent:1em}
#cn p,#cn h2{font-family:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",serif;
  line-height:1.95}
#en p,#en h2{font-family:"Iowan Old Style",Georgia,"Times New Roman",serif;
  line-height:1.65}
#en p{text-indent:1.2em}
.empty{color:var(--dim);font-size:13px;font-family:-apple-system,sans-serif;
  text-indent:0;line-height:1.7;max-width:26rem}
.hit{background:var(--review-hit);border-radius:3px}
#editor{position:absolute;inset:44px 0 0 0;background:var(--surface);z-index:20;
  display:none;flex-direction:column;padding:1rem}
#editor.on{display:flex}
#editor textarea{flex:1;width:100%;font:14px/1.6 ui-monospace,SFMono-Regular,Menlo,
  monospace;padding:1rem;border:1px solid var(--line);border-radius:7px;
  resize:none;background:var(--control);color:var(--ink)}
#editor .row{display:flex;align-items:center;gap:.8rem;padding:.6rem 0 .8rem;
  font-size:13px;color:var(--dim)}
#editor button{border:1px solid var(--line);background:var(--control);padding:.35rem .8rem}
#editor .save{color:var(--ink);font-weight:600;border-color:var(--accent-line);background:var(--accent-soft)}
"""

JS = r"""
const CH = __CHAPTERS__;                       // [{no,title}] present in Chinese
const EKEY='__PFX__sync:en', MKEY='__PFX__sync:mode', FKEY='__PFX__sync:fs';
const cn=document.getElementById('cn'), en=document.getElementById('en');
let mode=localStorage.getItem(MKEY)||'chapter';  // chapter | prop | off
let english=load();

function load(){ try{return JSON.parse(localStorage.getItem(EKEY)||'{}')}catch(e){return{}} }
function save(){ localStorage.setItem(EKEY,JSON.stringify(english)); }

/* ---------- English pane ---------- */
const HEAD=/^\s*(?:chapter|chap\.?|ch\.?|第)\s*(\d+)\s*[章.:、。-]*\s*(.*)$/i;

function parseEnglish(text, fallbackCh){
  const out={}; let cur=null,volume=null;
  for(const raw of text.replace(/\r/g,'').split('\n')){
    if(CH.some(c=>c.volume===raw.trim())){volume=raw.trim();cur=null;continue}
    const m=raw.match(HEAD);
    if(m){ const number=parseInt(m[1],10), chapter=volume?CH.find(c=>c.volume===volume&&(c.number??c.no)===number):null;
           cur=String(chapter?.no??number); out[cur]=out[cur]||[];
           if(m[2].trim())out[cur].push(m[2].trim()); continue; }
    if(cur===null){ if(!raw.trim())continue; cur=String(fallbackCh); out[cur]=out[cur]||[]; }
    if(raw.trim()) out[cur].push(raw.trim());
  }
  const res={}; for(const k in out) res[k]=out[k].join('\n');
  return res;
}
function chapterReference(n){const c=CH.find(c=>c.no===n);return (c?.volume?c.volume+' · ':'')+'ch '+(c?.number??n)}
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}

function renderEnglish(){
  const nums=CH.map(c=>c.no).filter(n=>english[String(n)]&&english[String(n)].trim());
  if(!nums.length){
    en.innerHTML='<p class="empty">No English yet.<br><br>'
      +'Click <b>paste English</b> above and drop in your draft. Put a line reading '
      +'<b>Chapter 3</b> (or <b>Ch 3</b>) before each chapter and they\'ll line up '
      +'automatically. Paste with no heading at all and it goes to the chapter '
      +'selected in the dropdown.<br><br>Saved in this browser, so it survives '
      +'reloads.</p>';
    return;
  }
  en.innerHTML=nums.map(n=>{
    const paras=english[String(n)].split('\n').filter(s=>s.trim());
    const chapter=CH.find(c=>c.no===n);
    return (chapter.volume?'<div class="volume">'+esc(chapter.volume)+'</div>':'')+'<h2 class="ch" data-ch="'+n+'">Chapter '+(chapter.number??n)+'</h2>'
      + paras.map(p=>'<p>'+esc(p)+'</p>').join('');
  }).join('');
  invalidate();
}

/* ---------- sync ---------- */
let tops={}, lock=0;
function invalidate(){ tops={}; }
function marks(pane){
  if(tops[pane.id])return tops[pane.id];
  return tops[pane.id]=[...pane.querySelectorAll('.ch')]
    .map(h=>({ch:+h.dataset.ch,top:h.offsetTop}))
    .sort((a,b)=>a.top-b.top);
}
function locate(pane){
  const m=marks(pane); if(!m.length)return null;
  const y=pane.scrollTop+10;
  let i=0; while(i<m.length&&m[i].top<=y)i++;
  i=Math.max(0,i-1);
  const start=m[i].top, end=i+1<m.length?m[i+1].top:pane.scrollHeight;
  const frac=end>start?(y-start)/(end-start):0;
  return {ch:m[i].ch,frac:Math.max(0,Math.min(1,frac))};
}
function go(pane,ch,frac,useFrac){
  const m=marks(pane); const j=m.findIndex(t=>t.ch===ch);
  if(j<0)return false;
  const start=m[j].top, end=j+1<m.length?m[j+1].top:pane.scrollHeight;
  pane.scrollTop = useFrac? start+frac*(end-start) : start;
  return true;
}
const lastCh={cn:null,en:null};
function onScroll(from,to){
  if(mode==='off')return;
  if(Date.now()<lock)return;
  const loc=locate(from); if(!loc)return;
  document.getElementById('now').textContent=chapterReference(loc.ch);
  if(mode==='prop'){ lock=Date.now()+90; go(to,loc.ch,loc.frac,true); }
  else if(loc.ch!==lastCh[from.id]){
    lastCh[from.id]=loc.ch; lastCh[to.id]=loc.ch;
    lock=Date.now()+260; go(to,loc.ch,0,false);
  }
}
cn.addEventListener('scroll',()=>onScroll(cn,en),{passive:true});
en.addEventListener('scroll',()=>onScroll(en,cn),{passive:true});
addEventListener('resize',invalidate);

/* ---------- controls ---------- */
function setMode(m){
  mode=m; localStorage.setItem(MKEY,m);
  for(const id of ['chapter','prop','off'])
    document.getElementById('m-'+id).setAttribute('aria-pressed',id===m);
}
function jump(n){
  n=+n; if(!n)return;
  lock=Date.now()+400; go(cn,n,0,false); go(en,n,0,false);
  lastCh.cn=lastCh.en=n;
  document.getElementById('now').textContent=chapterReference(n);
}
function fs(d){
  let v=parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs'));
  v=Math.max(13,Math.min(28,v+d));
  document.documentElement.style.setProperty('--fs',v+'px');
  localStorage.setItem(FKEY,v+'px'); invalidate();
}
function openEditor(){
  const ta=document.getElementById('ta');
  let previous='';
  ta.value=CH.filter(c=>english[String(c.no)]).map(c=>{
    const heading=(c.volume&&c.volume!==previous?c.volume+'\n\n':'')+'Chapter '+(c.number??c.no);
    previous=c.volume||'';return heading+'\n'+english[String(c.no)];
  }).join('\n\n');
  document.getElementById('editor').classList.add('on'); ta.focus();
}
function closeEditor(){document.getElementById('editor').classList.remove('on')}
function saveEditor(){
  const ta=document.getElementById('ta');
  const sel=+document.getElementById('sel').value||CH[0].no;
  english=parseEnglish(ta.value,sel);
  save(); renderEnglish(); closeEditor();
  const got=Object.keys(english).length;
  document.getElementById('cnt').textContent=got?got+' ch of English':'';
}
document.addEventListener('keydown',e=>{
  if(e.key==='Escape')closeEditor();
  if(e.target.tagName==='TEXTAREA')return;
  if(e.key==='='||e.key==='+')fs(1); else if(e.key==='-')fs(-1);
});

(function init(){
  const f=localStorage.getItem(FKEY);
  if(f)document.documentElement.style.setProperty('--fs',f);
  setMode(mode); renderEnglish();
  const got=Object.keys(english).length;
  document.getElementById('cnt').textContent=got?got+' ch of English':'';
})();
"""

PAGE = """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Side by side</title>
<script data-reader-theme>{theme_script}</script>
<style>{dialog_css}</style>
<script data-app-dialogs>{dialog_script}</script>
<style>{css}</style>
</head>
<body>
<header>
  <b>side by side</b>
  <select id="sel" onchange="jump(this.value)">{options}</select>
  <span class="sp"></span>
  <span id="cnt"></span>
  <span id="now"></span>
  <span>sync</span>
  <button id="m-chapter" onclick="setMode('chapter')" title="jump at chapter boundaries">chapter</button>
  <button id="m-prop" onclick="setMode('prop')" title="track proportionally inside a chapter">proportional</button>
  <button id="m-off" onclick="setMode('off')">off</button>
  <button onclick="fs(-1)">A&minus;</button>
  <button onclick="fs(1)">A+</button>
  {theme_control}
  <button onclick="openEditor()" title="paste or edit your English">paste English</button>
</header>
<div id="wrap">
  <section id="cn">{cn}</section>
  <section id="en"></section>
</div>
<div id="editor">
  <div class="row">
    <b style="color:var(--ink)">Paste your English</b>
    <span>separate chapters with a line reading <b>Chapter 4</b> &mdash;
      no heading means it goes to the chapter in the dropdown. If numbering restarts, include the volume heading before its chapters.</span>
    <span class="sp" style="flex:1"></span>
    <button onclick="closeEditor()">cancel</button>
    <button class="save" onclick="saveEditor()">save</button>
  </div>
  <textarea id="ta" spellcheck="false" placeholder="Chapter 1&#10;Your first paragraph…"></textarea>
</div>
<script>{js}</script>
</body>
</html>
"""


def render_page(cfg, chapters):
    """Render the original review page from already parsed chapters."""
    cn = []
    previous_volume = ''
    for c in chapters:
        if c.get('volume') and c['volume'] != previous_volume:
            cn.append('<div class="volume">{}</div>'.format(html.escape(c['volume'])))
        previous_volume = c.get('volume', '')
        cn.append('<h2 class="ch" data-ch="{}">第{}章 {}</h2>'.format(c['no'], chapter_number(c), html.escape(c['title'])))
        cn.extend('<p id="c{}p{}">{}</p>'.format(c['no'], i + 1, html.escape(p)) for i, p in enumerate(c['paras']))
    options = chapter_options(chapters, titles=False)
    meta = json.dumps([{'no':c['no'], 'title':c['title'], **metadata(c)} for c in chapters], ensure_ascii=False).replace('<', '\\u003c')
    return PAGE.format(css=reader_theme.CSS + CSS, theme_script=reader_theme.SCRIPT,
                       dialog_css=(Path(__file__).resolve().parent.parent / 'web/dialogs.css').read_text(encoding='utf-8'),
                       dialog_script=(Path(__file__).resolve().parent.parent / 'web/dialogs.js').read_text(encoding='utf-8'),
                       theme_control=reader_theme.CONTROL,
                       js=JS.replace('__CHAPTERS__', meta).replace('__PFX__', cfg['storage_prefix']),
                       cn='\n'.join(cn), options=options)


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

    page = render_page(cfg, use)
    with open(args.out, 'w', encoding='utf-8') as fh:
        fh.write(page)

    print('chapters in page :', len(use),
          '(第{}章 … 第{}章)'.format(use[0]['no'], use[-1]['no']))
    print('paragraphs       :', sum(len(c['paras']) for c in use))
    print('characters       :', sum(sum(len(p) for p in c['paras']) for c in use))
    print('wrote            :', args.out)


if __name__ == '__main__':
    main()
