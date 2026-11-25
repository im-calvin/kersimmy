"""Serve the original Python-generated reader with a library and SQLite storage."""
import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
from functools import cache, partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import build_draft
import build_sync
from reader_store import Store, validate, validate_icon
from chapter_structure import VOLUME_HEADING_REGEX
from tlconfig import DEFAULTS, parse_source, read_source

ROOT = Path(__file__).resolve().parent.parent
APP_VERSION = '0.1'


@cache
def reader_release():
    release = os.environ.get('READER_RELEASE', '')
    if re.fullmatch(r'[0-9a-f]{40}', release):
        return release
    digest = hashlib.sha256()
    for directory, suffixes in (('tools', {'.py'}), ('web', {'.js', '.css', '.html', '.png'})):
        for path in sorted((ROOT / directory).iterdir()):
            if path.suffix in suffixes and path.is_file():
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_upload(data):
    name = data.get('name','')
    suffix = Path(name).suffix.lower()
    if suffix not in ('.txt','.docx'):
        raise ValueError('Choose a .txt or .docx manuscript.')
    raw = base64.b64decode(data['content'], validate=True)
    if len(raw) > 30 * 1024 * 1024:
        raise ValueError('Choose a manuscript smaller than 30 MB.')
    options = data.get('options',{})
    with tempfile.TemporaryDirectory(prefix='reader-import-') as directory:
        source = Path(directory) / ('manuscript' + suffix)
        source.write_bytes(raw)
        if suffix == '.docx':
            import zipfile
            with zipfile.ZipFile(source) as archive:
                if archive.getinfo('word/document.xml').file_size > 50 * 1024 * 1024:
                    raise ValueError('Word document text exceeds the 50 MB extraction limit.')
        cfg = dict(DEFAULTS, source=str(source), encoding=options.get('encoding','auto'), paragraph_mode=options.get('paragraphMode','auto'))
        if cfg['paragraph_mode'] not in ('auto','line','blank'):
            raise ValueError('Invalid paragraph mode.')
        volume_mode = options.get('volumeMode', 'auto')
        if volume_mode not in ('auto', 'none'):
            raise ValueError('Invalid volume mode.')
        cfg['volume_heading_regex'] = VOLUME_HEADING_REGEX if volume_mode == 'auto' else ''
        mode = options.get('headingMode','auto')
        if mode == 'custom':
            cfg['heading_regex'] = options.get('headingRegex','')
            if re.compile(cfg['heading_regex']).groups < 1:
                raise ValueError('Heading pattern needs chapter number in capture group 1.')
        elif mode == 'auto':
            cfg['combined_volume_headings'] = True
            cfg['heading_regex'] = r'^\s*(?:第\s*|(?i:Chapter)\s+)([0-9０-９零〇一二两三四五六七八九十百千]+)\s*(?:[章回節节]|\b)\s*[:.\-–—]?\s*(.*?)\s*$'
        elif mode == 'single':
            cfg['heading_regex'] = r'^__reader_single_chapter__$'
        else:
            raise ValueError('Invalid heading mode.')
        text,encoding = read_source(cfg)
        if mode == 'single':
            cfg['volume_heading_regex'] = ''
            # Preserve explicit Word paragraph boundaries after extracting its text.
            source = Path(directory) / 'single.txt'
            source.write_text('__reader_single_chapter__\n' + text,encoding='utf-8')
            cfg.update(source=str(source),encoding='utf-8',heading_regex=r'^(__reader_single_chapter__)()$')
            # The original parser requires a numeric chapter capture.
            source.write_text('第1章 Manuscript\n' + text,encoding='utf-8')
            cfg['heading_regex'] = DEFAULTS['heading_regex']
            if suffix == '.docx': cfg['paragraph_mode'] = 'line'
        chapters = parse_source(cfg)
        if not chapters:
            raise ValueError('No chapters found. Check the heading pattern or select One chapter.')
        numbers = [c['no'] for c in chapters]
        if len(numbers) != len(set(numbers)):
            raise ValueError('Duplicate chapter numbers found. Give each chapter a unique number.')
        paragraph_mode = 'line' if suffix == '.docx' else cfg['paragraph_mode']
        if paragraph_mode == 'auto':
            lines=text.splitlines()
            paragraph_mode='blank' if sum(not line.strip() for line in lines)/max(1,len(lines)) >= .15 else 'line'
        warnings=[]
        untitled = sum(not chapter['title'].strip() for chapter in chapters)
        if untitled:
            warnings.append(f'{untitled} chapter heading{"s have" if untitled != 1 else " has"} no title.')
        if any('number' in c for c in chapters):
            warnings.append('Chapter numbering restarts between volumes. Text backups use continuous chapter numbers to keep drafts distinct.')
        if any(b != a+1 for a,b in zip(numbers,numbers[1:])):
            warnings.append('Chapter numbering has gaps or is out of order.')
        warnings.append('The original parser excludes text before the first chapter heading.')
        return {'chapters':chapters,'encoding':encoding,'paragraphMode':paragraph_mode,'headingMode':mode,'volumeMode':volume_mode,'headingRegex':cfg['heading_regex'],'volumeHeadingRegex':cfg['volume_heading_regex'],'warnings':warnings,'sourceName':name}


def generated_page(book, mode):
    cfg = dict(DEFAULTS, project=book['title'], slug='book',storage_prefix='book-' + book['id'] + ':',
               words_per_page=book.get('wordsPerPage') or 250,illustration='',inline_alignment=True)
    if mode == 'draft':
        page = build_draft.render_page(cfg, book['chapters'], book.get('illustration'))
        # The original rendering and algorithms stay in build_draft.py.
        # Keep explicit window.localStorage access for device-only display preferences.
        page = re.sub(r'(?<!\.)\blocalStorage\b', 'readerStorage', page)
        page = page.replace("let smart=readerStorage.getItem(SKEY)!=='0';",'let smart=false;')
        page = re.sub(r'<button id="sq".*?</button>', '<button id="sq" hidden></button>',page,flags=re.S)
        page = page.replace('<header>','<header data-save-state="saving"><a href="/">← Library</a><button type="button" id="open-glossary">Glossary</button>')
        page = page.replace('</head>', '<link rel="stylesheet" href="/glossary-poc.css"></head>')
        page = page.replace('onclick="fullProjectBackup()"','onclick="window.readerBackup()"')
        page = page.replace('<div class="cards" id="cards"></div>','<section id="artwork"><img id="project-gif" alt="Book GIF" hidden><div><button id="choose-gif">Choose GIF</button><button id="remove-gif">Remove GIF</button><input id="gif-file" type="file" accept=".gif,image/gif" hidden><p id="gif-status" role="status"></p></div></section><div class="cards" id="cards"></div>')
        page = page.replace('<!-- hosted-import-drafts -->', '<button onclick="window.readerImportDrafts()">Import drafts</button>')
        page = page.replace("let store=read(), pos=readPos(), cur=+readerStorage.getItem(CKEY)||CH[0].no;", "let store=read(), pos=readPos(), cur=Number(readerStorage.getItem(CKEY) ?? CH[0].no);")
        hook = 'window.readerHasUnsaved=()=>dirty||!!document.querySelector(".app-dialog[open]"); window.readerCommit=()=>{if(dirty)commit()}; window.readerInstallDrafts=(drafts)=>{if(dirty)commit();for(const n of Object.keys(drafts)){delete italics[n];for(const note of comments[n]||[])if(drafts[n].slice(note.start,note.end)!==note.quote)note.detached=true}Object.assign(store,drafts);readerStorage.setItem(KEY,JSON.stringify(store));readerStorage.setItem(IKEY,JSON.stringify(italics));readerStorage.setItem(NKEY,JSON.stringify(comments));load(cur)};'
        # Original overlays remain in their templates; clicking their surrounding
        # backdrop or empty outer panel closes them.
        hook += "for(const [id,close] of [['find',closeFind],['stats',closeStats]]){const panel=document.getElementById(id);panel.addEventListener('click',e=>{if(e.target===panel)close()})}"
        page = page.replace('</script>\n</body>', hook + '</script>\n</body>')
        page = page.replace('</body>', '''<aside id="glossary-tooltip" role="tooltip" hidden>
  <strong id="glossary-tooltip-english"></strong>
  <p id="glossary-tooltip-note"></p>
</aside>
<div class="app-dialog" role="dialog" hidden id="glossary-dialog" aria-labelledby="glossary-title">
  <h2 id="glossary-title">Glossary</h2>
  <p>Saved for this book in this browser.</p>
  <div class="glossary-table">
    <table>
      <thead><tr><th scope="col">Chinese</th><th scope="col">English</th><th scope="col">Usage note</th><th scope="col"></th></tr></thead>
      <tbody id="glossary-terms"></tbody>
    </table>
  </div>
  <p id="glossary-status" role="status"></p>
  <div class="glossary-actions">
    <button type="button" class="act" id="glossary-add">Add term</button>
    <button type="button" class="act" id="glossary-close">Close</button>
  </div>
</div>
<script type="module" src="/glossary-poc.js"></script>
</body>''')
    else:
        page = re.sub(r'(?<!\.)\blocalStorage\b', 'readerStorage', build_sync.render_page(cfg,book['chapters']))
        page = page.replace('<header>','<header><a href="/">← Library</a><a href="draft">Draft</a>')
        page = page.replace('</script>\n</body>', "window.readerUseDrafts=(text)=>{english=parseEnglish(text,CH[0].no);save();renderEnglish()};window.readerHasUnsaved=()=>document.getElementById('editor').classList.contains('on');document.getElementById('editor').addEventListener('click',e=>{if(e.target.id==='editor')closeEditor()});</script>\n</body>")
    page = page.replace('<script src="corpus.js"></script>','')
    # Run the original script only after the storage adapter has loaded its state.
    start = page.index('<script>')
    end = page.index('</script>',start)
    script = page[start+8:end]
    code = json.dumps(script, ensure_ascii=False).replace('<', '\\u003c')
    offline = '<script src="/reader-offline.js"></script>' if mode == 'draft' else ''
    config = {'id':book['id'],'mode':mode,'prefix':cfg['storage_prefix'],
              'version':APP_VERSION,'release':reader_release()}
    page = page[:start] + offline + '<script src="/reader-storage.js"></script><script>window.readerStart(' + json.dumps(config) + ',()=>{const script=document.createElement("script");script.textContent=' + code + ';document.body.append(script)});</script>' + page[end+9:]
    extra = '''<style>[hidden]{display:none!important}header{height:auto;min-height:44px;flex-wrap:wrap;padding:8px 12px}header a{font:13px sans-serif;color:var(--heading);text-decoration:none;margin-right:12px}#wrap{flex:1;min-height:0;height:auto}body{display:flex;flex-direction:column}#find,#stats{position:fixed;inset:0;background:var(--scrim);padding:5vh 5vw;z-index:40}#find.on{display:flex}#find>.top,#find>#verdict,#find>#hits,#stats>.top,#stats>.body{background:var(--bg);padding:12px 22px}#stats{width:100%;max-height:none;border:0;border-radius:0;box-shadow:none}#stats>.top,#stats>.body{width:min(760px,100%);margin:0 auto}#stats>.top{border-radius:12px 12px 0 0}#stats>.body{border-radius:0 0 12px 12px;padding-bottom:30px}#artwork{display:flex;flex-wrap:wrap;align-items:center;gap:24px;margin:0 0 22px}#project-gif{width:150px;height:150px;object-fit:contain}#reader-server-status{font:12px sans-serif;padding:6px 12px;background:var(--status-bg);color:var(--status)}#reader-server-status.error{color:var(--error);background:var(--error-bg)}</style>'''
    if mode == 'draft':
        extra += '''<style>
header[data-save-state]{--save-color:var(--status);background:var(--status-bg)}
header[data-save-state="saving"]{
  --save-color:var(--accent);background:var(--accent-soft)}
header[data-save-state="offline"]{--save-color:var(--heading);background:var(--control)}
header[data-save-state="error"]{--save-color:var(--error);background:var(--error-bg)}
header #reader-server-status{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;
  clip-path:inset(50%);white-space:nowrap}
#reader-save-menu summary{display:grid;place-items:center;width:24px;height:24px;
  border-radius:4px;list-style:none;color:var(--save-color)}
#reader-save-menu summary::-webkit-details-marker{display:none}
#reader-save-menu summary::before{content:"";box-sizing:border-box;width:10px;height:10px;
  border:2px solid currentColor;border-radius:50%}
header[data-save-state="saved"] #reader-save-menu summary::before{background:currentColor}
@media(forced-colors:active){
  #reader-save-menu summary::before{forced-color-adjust:none;color:ButtonText}
}
#reader-save-menu summary:hover{background:var(--hover)}
#reader-save-menu>div{width:min(19rem,calc(100vw - 2rem));display:grid;gap:.4rem;
  border-radius:6px;padding:.65rem;color:var(--ink)}
#reader-save-menu p{margin:0}
#reader-save-menu button{text-align:left;color:var(--ink)}
#reader-offline-status,.reader-version{color:var(--dim);font-size:11px}
</style>'''
    brand = '<link rel="icon" href="/site-icon.png" type="image/png"><link rel="stylesheet" href="/site-brand.css">'
    page = page.replace('>← Library</a>', '><img class="site-icon" src="/site-icon.png" alt=""> Library</a>', 1)
    return page.replace('</head>',brand+extra+'</head>').replace(
        '</body>', '<img class="site-corner reader-site-corner" src="/site-icon.png" alt=""></body>', 1)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,store,**kwargs):
        self.store=store
        super().__init__(*args,**kwargs)

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Kersimmy-Release',reader_release())
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()

    def reply(self,data,status=200):
        self.content(json.dumps(data,allow_nan=False).encode(),'application/json',status)

    def content(self,payload,content_type,status=200):
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def get_entry(self,id):
        with self.store.connect() as db:
            row=db.execute('SELECT book,state,revision FROM books WHERE id=?',(id,)).fetchone()
        return (json.loads(row[0]),json.loads(row[1]),row[2]) if row else None

    def do_GET(self):
        path=urlparse(self.path).path
        try:
            if path=='/reader.html':
                from urllib.parse import parse_qs
                id=parse_qs(urlparse(self.path).query).get('book',[''])[0]
                self.send_response(302);self.send_header('Location','/books/'+id+'/draft');self.end_headers();return
            parts=path.split('/')
            if len(parts)==4 and parts[1]=='books' and parts[3] in ('draft','review'):
                entry=self.get_entry(parts[2])
                if not entry: return self.reply({'error':'Book not found'},404)
                return self.content(generated_page(entry[0],parts[3]).encode(),'text/html; charset=utf-8')
            if not path.startswith('/api/'): return super().do_GET()
            if path=='/api/status':
                backups=sorted(self.store.backups.glob('reader-*.sqlite3'))
                return self.reply({'storage':'sqlite','reader':'original-python','version':APP_VERSION,'release':reader_release(),'backupIntervalSeconds':self.store.interval,'backupCount':len(backups),'lastBackup':backups[-1].name if backups else None,'backupError':self.store.last_error})
            if path=='/api/books': return self.reply([e['book'] for e in self.store.entries()])
            if path=='/api/export': return self.reply({'format':'translation-reader','version':1,'books':self.store.entries()})
            if len(parts) in (4,5) and parts[2]=='books':
                entry=self.get_entry(parts[3])
                if not entry: return self.reply({'error':'Book not found'},404)
                if len(parts)==5 and parts[4] not in ('state','bundle'):return self.reply({'error':'Not found'},404)
                return self.reply({'book':entry[0],'state':entry[1]} if parts[-1]=='bundle' else entry[1] if parts[-1]=='state' else entry[0])
            self.reply({'error':'Not found'},404)
        except Exception as error:
            print('Read failed:',error,flush=True);self.reply({'error':'Could not load the book'},500)

    def do_POST(self): self.mutate()
    def do_PUT(self): self.mutate()
    def do_DELETE(self): self.mutate()

    def mutate(self):
        origin=self.headers.get('Origin')
        if (origin and urlparse(origin).netloc!=self.headers.get('Host')) or self.headers.get('Sec-Fetch-Site')=='cross-site':return self.reply({'error':'Cross-origin writes are not allowed'},403)
        if self.headers.get_content_type()!='application/json':return self.reply({'error':'JSON required'},415)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=100*1024*1024:return self.reply({'error':'Invalid request size'},413)
            data=json.loads(self.rfile.read(length),parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid number')))
            path=urlparse(self.path).path
            if self.command=='POST' and path=='/api/preview':
                # Isolate custom regex parsing and Word extraction with a hard timeout.
                result=subprocess.run([sys.executable,__file__,'--parse'],input=json.dumps(data),capture_output=True,text=True,timeout=15)
                if result.returncode:raise ValueError(result.stderr.strip() or 'Could not parse manuscript')
                return self.reply(json.loads(result.stdout))
            if self.command=='POST' and path=='/api/import':return self.reply(self.store.import_entries(data['books']),201)
            if self.command=='POST' and path=='/api/backup':return self.reply({'backup':self.store.backup()})
            parts=path.split('/')
            if self.command=='DELETE' and len(parts)==4 and parts[1:3]==['api','books']:
                if data.get('confirmation') != 'I am an idiot sandwich':
                    raise ValueError('The confirmation phrase did not match.')
                expected = data.get('expectedRevision')
                if type(expected) is not int:
                    raise ValueError('A book revision is required.')
                with self.store.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    row = db.execute('SELECT revision FROM books WHERE id=?', (parts[3],)).fetchone()
                    if not row: return self.reply({'error':'Book not found'},404)
                    if expected != row[0]:
                        return self.reply({'error':'This book changed. Check the latest version before deleting it.','conflict':True},409)
                    db.execute('DELETE FROM books WHERE id=?', (parts[3],))
                return self.reply({'deleted':True})
            if self.command!='PUT' or len(parts)!=5 or parts[2]!='books':return self.reply({'error':'Not found'},404)
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT book,state,revision FROM books WHERE id=?',(parts[3],)).fetchone()
                if not row:return self.reply({'error':'Book not found'},404)
                book,state,revision=json.loads(row[0]),json.loads(row[1]),row[2]
                if parts[4]=='state':
                    if type(data.get('expectedRevision')) is not int or data['expectedRevision']!=revision:return self.reply({'error':'This book changed on another device. Your local changes are still here.','conflict':True},409)
                    state=data['state'];validate(book,state)
                    state=dict(state,id=parts[3],revision=revision+1)
                    db.execute('UPDATE books SET state=?,revision=? WHERE id=?',(json.dumps(state),revision+1,parts[3]));result={'revision':revision+1}
                elif parts[4] in ('volumes','chapter-import'):
                    if type(data.get('expectedRevision')) is not int or data['expectedRevision']!=revision:
                        return self.reply({'error':'This book changed. Reopen book settings to load the latest version.','conflict':True},409)
                    if parts[4]=='chapter-import':
                        preview = data['preview']
                        chapters = preview['chapters']
                        if not isinstance(chapters,list) or (
                            [(c['no'], c['paras']) for c in chapters] !=
                            [(c['no'], c['paras']) for c in book['chapters']]
                        ):
                            raise ValueError('Chapter boundaries or source text changed. Add this file as a new manuscript to keep existing work safe.')
                        chapter_fields = {'title','number','volume'}
                        chapters = [
                            {**{key:value for key,value in old.items() if key not in chapter_fields},
                             **{key:new[key] for key in chapter_fields if key in new}}
                            for old,new in zip(book['chapters'], chapters)
                        ]
                        fields = ('encoding','paragraphMode','headingMode','volumeMode',
                                  'headingRegex','volumeHeadingRegex','warnings','sourceName')
                        book = dict(book, chapters=chapters, **{key:preview[key] for key in fields if key in preview})
                    else:
                        volumes = data.get('volumes')
                        titles = data.get('titles', {})
                        if 'bookTitle' in data:
                            book_title = data['bookTitle']
                            if not isinstance(book_title,str) or not 1<=len(book_title.strip())<=200:
                                raise ValueError('Book name must be between 1 and 200 characters.')
                            book['title'] = book_title.strip()
                        numbers = {str(c['no']) for c in book['chapters']}
                        if not isinstance(volumes,dict) or set(volumes)!=numbers:
                            raise ValueError('Volume assignments must include each chapter exactly once.')
                        if not isinstance(titles,dict) or set(titles)-numbers:
                            raise ValueError('Chapter titles must refer to existing chapters.')
                        chapters = []
                        for chapter in book['chapters']:
                            no = str(chapter['no'])
                            volume = volumes[no]
                            if not isinstance(volume,str) or len(volume.strip())>200:
                                raise ValueError('Volume names must be 200 characters or fewer.')
                            chapter = {k:v for k,v in chapter.items() if k!='volume'}
                            if volume.strip(): chapter['volume'] = volume.strip()
                            if no in titles:
                                title = titles[no]
                                if not isinstance(title,str) or len(title.strip())>200:
                                    raise ValueError('Chapter titles must be 200 characters or fewer.')
                                chapter['title'] = title.strip()
                            chapters.append(chapter)
                        book = dict(book, chapters=chapters)
                    state = dict(state, revision=revision+1)
                    validate(book,state)
                    db.execute('UPDATE books SET book=?,state=?,revision=? WHERE id=?',
                               (json.dumps(book),json.dumps(state),revision+1,parts[3]))
                    result = {'book':book,'revision':revision+1}
                elif parts[4]=='illustration':
                    from reader_store import validate_image
                    book['illustration']=validate_image(data.get('illustration'))
                    db.execute('UPDATE books SET book=? WHERE id=?',(json.dumps(book),parts[3]));result=book
                elif parts[4]=='icon':
                    icon = validate_icon(data['icon'])
                    book['icon'] = icon
                    db.execute('UPDATE books SET book=? WHERE id=?',(json.dumps(book),parts[3]))
                    result = {'icon': icon}
                else:return self.reply({'error':'Not found'},404)
            self.reply(result)
        except subprocess.TimeoutExpired:self.reply({'error':'Parsing took too long. Simplify the heading pattern.'},400)
        except (ValueError,KeyError,TypeError,AttributeError) as error:self.reply({'error':str(error)},400)
        except Exception as error:
            print('Save failed:',error,flush=True);self.reply({'error':'Could not save. Keep your recovery backup.'},500)


def main():
    if '--parse' in sys.argv:
        try: print(json.dumps(parse_upload(json.load(sys.stdin))))
        except (Exception,SystemExit) as error: print(str(error),file=sys.stderr);sys.exit(1)
        return
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--data',default=os.environ.get('READER_DATA',str(ROOT/'data')))
    parser.add_argument('--site',default=str(ROOT/'dist'))
    args=parser.parse_args()
    store=Store(args.data,int(os.environ.get('BACKUP_INTERVAL_SECONDS','300')),
                int(os.environ.get('BACKUP_KEEP','96')),
                portable_json=os.environ.get('PORTABLE_JSON_SNAPSHOTS')=='1')
    stop=threading.Event();threading.Thread(target=store.run_backups,args=(stop,),daemon=True).start()
    server=ThreadingHTTPServer((args.host,args.port),partial(Handler,store=store,directory=args.site))
    def shutdown(signum,frame):
        stop.set();threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    print(f'Original Python reader: http://{args.host}:{args.port} · {store.path}',flush=True)
    try:server.serve_forever()
    finally:stop.set();server.server_close();store.backup()

if __name__=='__main__':main()
