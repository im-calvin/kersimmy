#!/usr/bin/env python3
"""
Chinese manuscript -> per-chapter reading pages for translation drafting.

Source assumptions (verified against this manuscript):
  - GB18030 encoded
  - chapter headings match ^第(\\d+)章\\s*(title)   [arabic numerals]
  - one paragraph per line, prefixed with fullwidth indent U+3000
  - blank lines are incidental, NOT paragraph separators

Usage:
  python3 generate.py SOURCE.txt OUTDIR [--chapters 1-5] [--all]
"""
import argparse
import html
import json
import os
import re
import sys

from chapter_structure import number as chapter_number, metadata
from tlconfig import load_config, parse_source, pick, source_path

PFX = 'tl'   # localStorage namespace; set from config in main()


CSS = """
:root{color-scheme:light;--fs:20px;--col:34rem;--ink:#1b1a17;--dim:#a8a29a;--bg:#faf8f4}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--ink)}
body{font-family:"Songti SC","Noto Serif CJK SC","Source Han Serif SC",Georgia,serif;
     -webkit-font-smoothing:antialiased}
header{position:sticky;top:0;z-index:5;background:#faf8f4f2;
       backdrop-filter:blur(6px);border-bottom:1px solid #eae5dc}
.bar{max-width:var(--col);margin:0 auto;padding:.7rem 1.1rem;display:flex;gap:.9rem;
     align-items:baseline;font-size:13px;color:var(--dim);
     font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif}
.bar b{color:var(--ink);font-weight:600;font-size:14px}
.bar .sp{flex:1}
.bar a,.bar button{font:inherit;color:var(--dim);background:none;border:0;
     padding:.1rem .3rem;cursor:pointer;border-radius:4px;text-decoration:none}
.bar a:hover,.bar button:hover{color:var(--ink);background:#f0ebe2}
.bar button[aria-pressed="true"]{color:var(--ink);background:#eee7da}
main{max-width:var(--col);margin:0 auto;padding:2.4rem 1.1rem 60vh}
h1{font-size:calc(var(--fs) * 1.15);font-weight:600;margin:0 0 2rem;line-height:1.6}
h1 small{display:block;font-size:12px;color:var(--dim);font-weight:400;margin-top:.5rem;
         letter-spacing:.06em;font-family:-apple-system,sans-serif}
p{font-size:var(--fs);line-height:1.95;margin:0 0 .55em;text-indent:1em;
  scroll-margin-top:4.5rem}
p:target{background:#fff3b0;border-radius:3px}
#prog{position:fixed;left:0;top:0;height:2px;background:#c9a227;width:0;z-index:9}
kbd{font:11px/1 -apple-system,sans-serif;color:var(--dim);border:1px solid #e2dcd2;
    border-radius:3px;padding:.15rem .3rem;background:#fff}
"""

JS = """
const KEY='__PFX__reader:ch%(no)d', GKEY='__PFX__reader:last';
const WIDTHS=['34rem','46rem','62rem','100%%'];
const clampf=v=>Math.max(14,Math.min(34,v));
function setvar(k,v,store){document.documentElement.style.setProperty(k,v);
  if(store)localStorage.setItem('__PFX__reader'+k,v);}
function fs(d){const c=parseFloat(getComputedStyle(document.documentElement)
  .getPropertyValue('--fs'));setvar('--fs',clampf(c+d)+'px',true);}
function width(){const c=getComputedStyle(document.documentElement)
  .getPropertyValue('--col').trim();
  setvar('--col',WIDTHS[(WIDTHS.indexOf(c)+1)%%WIDTHS.length],true);}
const f=localStorage.getItem('__PFX__reader--fs'); if(f)setvar('--fs',f);
const c=localStorage.getItem('__PFX__reader--col'); if(c)setvar('--col',c);
const prog=document.getElementById('prog'), pos=document.getElementById('pos');
function pct(){const h=document.documentElement.scrollHeight-innerHeight;
  return h>0?Math.min(1,Math.max(0,scrollY/h)):0;}
let t=null;
addEventListener('scroll',()=>{
  const p=pct();
  prog.style.width=(p*100)+'%%';
  pos.textContent=Math.round(p*100)+'%%';
  clearTimeout(t); t=setTimeout(()=>{
    localStorage.setItem(KEY,Math.round(scrollY));
    localStorage.setItem(GKEY,JSON.stringify(
      {ch:%(no)d,y:Math.round(scrollY),t:Date.now()}));
  },250);
},{passive:true});
addEventListener('keydown',e=>{
  if(e.metaKey||e.ctrlKey||e.altKey)return;
  const tg=e.target.tagName; if(tg==='INPUT'||tg==='TEXTAREA')return;
  if(e.key==='w'){width()}
  else if(e.key==='='||e.key==='+'){fs(1)}
  else if(e.key==='-'){fs(-1)}
});
requestAnimationFrame(()=>{
  if(!location.hash){
    const y=parseInt(localStorage.getItem(KEY)||'0',10);
    if(y>0)scrollTo({top:y});
  }
  dispatchEvent(new Event('scroll'));
});
"""

PAGE = """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>第{number}章 {title_esc}</title>
<style>{css}</style>
</head>
<body>
<div id="prog"></div>
<header><div class="bar">
  {prev}<b>第{number}章</b><span>{title_esc}</span>{next}<span class="sp"></span>
  <span id="pos"></span>
  <button onclick="fs(-1)" title="smaller (-)">A&minus;</button>
  <button onclick="fs(1)" title="larger (+)">A+</button>
  <button onclick="width()" title="column width (w)">&#8596;</button>
</div></header>
<main>
{volume}<h1 id="c{no}">第{number}章 {title_esc}
  <small>{n_paras} paragraphs &middot; {n_chars} characters &middot;
  <kbd>w</kbd> width &middot; <kbd>+</kbd>/<kbd>&minus;</kbd> size</small>
</h1>
{body}
</main>
<script>{js}</script>
</body>
</html>
"""


INDEX = """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>Chapters</title>
<style>
:root{{color-scheme:light;--ink:#1b1a17;--dim:#a8a29a;--bg:#faf8f4}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:var(--bg);color:var(--ink)}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif}}
main{{max-width:40rem;margin:0 auto;padding:3rem 1.2rem 6rem}}
h1{{font-size:17px;font-weight:600;margin:0 0 .3rem}}
.meta{{font-size:13px;color:var(--dim);margin:0 0 1.6rem}}
#resume{{display:none;font-size:13px;margin:0 0 1.8rem;padding:.7rem .9rem;
  background:#fff;border:1px solid #eae5dc;border-radius:7px}}
#resume a{{color:#8a6f12;font-weight:600;text-decoration:none}}
#resume a:hover{{text-decoration:underline}}
ol{{list-style:none;margin:0;padding:0}}
li{{border-bottom:1px solid #f0ece4}}
li a{{display:flex;gap:.8rem;align-items:baseline;padding:.55rem .3rem;
  text-decoration:none;color:inherit}}
li a:hover{{background:#f3eee5}}
.no{{font-variant-numeric:tabular-nums;color:var(--dim);font-size:12px;
  min-width:3.1rem}}
.ti{{flex:1;font-family:"Songti SC","Noto Serif CJK SC",serif;font-size:15px}}
.ct{{color:var(--dim);font-size:11px;font-variant-numeric:tabular-nums}}
</style>
</head>
<body><main>
<h1>Chapters</h1>
<p class="meta">{n} chapters &middot; {chars} Chinese characters &middot;
  {paras} paragraphs</p>
<div id="resume"></div>
<ol>
{rows}
</ol>
</main>
<script>
try{{
  const l=JSON.parse(localStorage.getItem('__PFX__reader:last')||'null');
  if(l&&l.ch){{
    const d=document.getElementById('resume');
    const when=new Date(l.t).toLocaleString();
    d.innerHTML='Last read &middot; <a href="ch'+String(l.ch).padStart(3,'0')
      +'.html">\\u7b2c'+l.ch+'\\u7ae0</a> <span style="color:#a8a29a">'+when+'</span>';
    d.style.display='block';
  }}
}}catch(e){{}}
</script>
</body></html>
"""


def write_index(chapters, generated, outdir):
    rows = []
    previous_volume = ''
    for c in chapters:
        if c.get('volume') and c['volume'] != previous_volume:
            rows.append('<li><h2>{}</h2></li>'.format(html.escape(c['volume'])))
        previous_volume = c.get('volume', '')
        label = '第{}章'.format(chapter_number(c))
        cnt = '{} ¶'.format(c['n_paras'] if 'n_paras' in c else len(c['paras']))
        np_ = c['n_paras'] if 'n_paras' in c else len(c['paras'])
        if c['no'] in generated:
            rows.append(
                '<li><a href="ch{:03d}.html"><span class="no">{}</span>'
                '<span class="ti">{}</span><span class="ct">{} &para;</span></a></li>'
                .format(c['no'], label, html.escape(c['title']), np_))
        else:
            rows.append(
                '<li><a style="opacity:.45;cursor:default"><span class="no">{}</span>'
                '<span class="ti">{}</span><span class="ct">{} &para;</span></a></li>'
                .format(label, html.escape(c['title']), np_))
    total_p = sum(len(c['paras']) for c in chapters)
    total_c = sum(sum(len(p) for p in c['paras']) for c in chapters)
    page = INDEX.format(n=len(chapters), chars='{:,}'.format(total_c),
                        paras='{:,}'.format(total_p), rows='\n'.join(rows))
    with open(os.path.join(outdir, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(page.replace('__PFX__', PFX))


def render(ch, have):
    body = '\n'.join(
        '<p id="c{}p{}">{}</p>'.format(ch['no'], n + 1, html.escape(p))
        for n, p in enumerate(ch['paras'])
    )
    prev = ('<a href="ch{:03d}.html" title="previous chapter">&larr;</a>'
            .format(ch['no'] - 1) if ch['no'] - 1 in have else '')
    nxt = ('<a href="ch{:03d}.html" title="next chapter">&rarr;</a>'
           .format(ch['no'] + 1) if ch['no'] + 1 in have else '')
    page = PAGE.format(
        no=ch['no'], number=chapter_number(ch), title_esc=html.escape(ch['title']),
        volume=('<div class="volume">{}</div>'.format(html.escape(ch['volume'])) if ch.get('volume') else ''),
        css=CSS, js=JS % {'no': ch['no']},
        n_paras=len(ch['paras']),
        n_chars=sum(len(p) for p in ch['paras']),
        body=body, prev=prev, next=nxt,
    )
    return page.replace('__PFX__', PFX)


def main():
    global PFX
    ap = argparse.ArgumentParser()
    ap.add_argument('outdir')
    ap.add_argument('--config', default=None)
    ap.add_argument('--chapters', default='1-5',
                    help='e.g. 1 or 1-5 or 1,7,9  (ignored with --all)')
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    cfg = load_config(args.config)
    PFX = cfg['storage_prefix']
    chapters = parse_source(cfg)
    if not chapters:
        sys.exit('no chapters matched — run "python3 tlconfig.py" to diagnose')
    want = pick(chapters, args.chapters, args.all)

    os.makedirs(args.outdir, exist_ok=True)
    written = []
    for ch in chapters:
        if ch['no'] not in want:
            continue
        fn = os.path.join(args.outdir, 'ch{:03d}.html'.format(ch['no']))
        with open(fn, 'w', encoding='utf-8') as fh:
            fh.write(render(ch, want))
        written.append((ch['no'], len(ch['paras']), sum(len(p) for p in ch['paras'])))

    manifest = {
        'project': cfg['project'],
        'source': os.path.basename(source_path(cfg)),
        'encoding': cfg['encoding'],
        'n_chapters': len(chapters),
        'generated': sorted(n for n, _, _ in written),
        'chapters': [
            {'no': c['no'], 'title': c['title'], 'n_paras': len(c['paras']),
             'n_chars': sum(len(p) for p in c['paras']), **metadata(c)}
            for c in chapters
        ],
    }
    with open(os.path.join(args.outdir, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)

    write_index(chapters, {n for n, _, _ in written}, args.outdir)

    nos = {c['no'] for c in chapters}
    gaps = [n for n in range(min(nos), max(nos) + 1) if n not in nos]
    print('chapters parsed : {} (第{}章 … 第{}章)'.format(
        len(chapters), min(nos), max(nos)))
    print('numbering gaps  :', gaps or 'none')
    print('pages written   :', len(written))
    for no, np_, nc in written:
        print('   ch{:03d}.html  {:>4} paragraphs  {:>6} chars'.format(no, np_, nc))


if __name__ == '__main__':
    main()
