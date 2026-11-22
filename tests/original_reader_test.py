"""End-to-end checks for the original Python generators and SQLite adapter."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import tempfile
import urllib.request
import zipfile
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url',default='http://127.0.0.1:8002')
args=parser.parse_args();base=args.base_url.rstrip('/')
artifacts=Path(tempfile.mkdtemp(prefix='original-reader-checks-'))
test_gif=base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(channel=os.environ.get('READER_BROWSER_CHANNEL', 'chrome') or None,headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    try:
        page.goto(base)
        page.get_by_role('button',name='Add manuscript').click()
        page.locator('#manuscript').set_input_files({'name':'New book.txt','mimeType':'text/plain','buffer':'第一章 开始\n第一段月光\n第二段月光\n第三段\n第二章 后来\n后来月光'.encode()})
        title="New book's </script> test"
        page.locator('#book-title').fill(title)
        page.locator('#paragraph-mode').select_option('line')
        page.locator('#parse').click()
        expect(page.locator('#preview-summary')).to_contain_text('2 chapters')
        expect(page.locator('#preview-text')).to_contain_text('第一段月光')
        page.locator('#confirm-import').click()
        page.locator('.book-card').filter(has=page.get_by_role('heading',name=title,exact=True)).first.get_by_role('link').click()
        expect(page.locator('#ta')).to_be_visible()
        assert '/books/' in page.url and page.url.endswith('/draft')
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        assert page.locator('#smart').count()==0
        assert not page.get_by_text('YOUR TRANSLATION',exact=True).count()
        page.locator('#ta').fill('Chapter 1\n\nFirst paragraph.\nSecond paragraph.\nThird paragraph.')
        page.locator('#ta').press('End')
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        page.locator('#ta').evaluate("el=>{el.setSelectionRange(el.value.length,el.value.length);el.dispatchEvent(new KeyboardEvent('keyup',{key:'ArrowRight'}))}")
        expect(page.locator('#cn p.hit')).to_have_attribute('id','c1p3')
        with page.expect_download() as event:page.get_by_role('button',name='backup',exact=True).click()
        assert Path(event.value.path()).read_text().count('Chapter 1')==1
        page.reload()
        expect(page.locator('#ta')).to_have_js_property('value', 'Chapter 1\n\nFirst paragraph.\nSecond paragraph.\nThird paragraph.')
        print('PASS: Python parsing/import, original generated editor, alignment, normalized exports, persistence',flush=True)
        draft_url=page.url
        page.get_by_role('button',name='stats',exact=True).click()
        expect(page.locator('#cards')).to_contain_text('english words')
        page.locator('#gif-file').set_input_files({'name':'test.gif','mimeType':'image/gif','buffer':test_gif})
        expect(page.locator('#gif-status')).to_have_text('GIF saved with this book.')
        page.wait_for_function("document.getElementById('project-gif').naturalWidth>0")
        page.screenshot(path=str(artifacts/'original-stats.png'),full_page=True)
        page.mouse.click(2,2)
        expect(page.locator('#stats')).not_to_have_class('on')
        page.get_by_role('button',name='find',exact=True).click()
        page.locator('#q').fill('月光')
        expect(page.locator('#verdict')).to_contain_text('Appears')
        page.mouse.click(2,2)
        expect(page.locator('#find')).not_to_have_class('on')
        print('PASS: original statistics, GIF customization, contextual search, click-outside dismissal',flush=True)
        page.goto(draft_url.removesuffix('/draft')+'/review')
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        page.get_by_role('button',name='use current drafts',exact=True).click()
        expect(page.locator('#en')).to_contain_text('Third paragraph.')
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        page.reload()
        expect(page.locator('#en')).to_contain_text('Third paragraph.')
        page.get_by_role('button',name='paste English',exact=True).click()
        page.locator('#ta').fill('Chapter 2\nReview text stored separately.')
        page.get_by_role('button',name='save',exact=True).click()
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        page.goto(draft_url)
        expect(page.locator('#ta')).to_have_js_property('value', 'Chapter 1\n\nFirst paragraph.\nSecond paragraph.\nThird paragraph.')
        print('PASS: original review page, draft import, separate English review persistence',flush=True)
        other_context=browser.new_context()
        other=other_context.new_page();other.goto(draft_url)
        expect(other.locator('#ta')).to_be_visible()
        page.locator('#ta').fill('Updated from first browser.')
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        expect(other.locator('#ta')).to_have_js_property('value', 'Updated from first browser.',timeout=15000)
        context.set_offline(True)
        page.locator('#ta').fill('Pending offline text.')
        expect(page.locator('#reader-server-status')).to_contain_text('Connection lost')
        context.set_offline(False)
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server',timeout=15000)
        expect(other.locator('#ta')).to_have_js_property('value', 'Pending offline text.',timeout=15000)
        other_context.close()
        result=page.evaluate('''async()=>{
          const id=location.pathname.split('/')[2];
          const state=await fetch('/api/books/'+id+'/state').then(r=>r.json());
          return (await fetch('/api/books/'+id+'/state',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({state,expectedRevision:-1})})).status;
        }''')
        assert result==409
        print('PASS: separate-browser sync, offline recovery/retry, stale-write conflict rejection',flush=True)
        with page.expect_download() as event:page.get_by_role('button',name='Download recovery backup').click()
        payload=json.loads(Path(event.value.path()).read_text())
        state=payload['books'][0]['state']
        assert state['drafts']['1']=='Pending offline text.'
        assert state['reviewEnglish']['2']=='Review text stored separately.'
        assert payload['books'][0]['book']['illustration']['name']=='test.gif'
        page.goto(base)
        page.locator('#restore-file').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':json.dumps(payload).encode()})
        expect(page.locator('#message')).to_contain_text('Restored 1 book')
        print('PASS: compatible full backup/restore preserves draft/review/GIF data',flush=True)
        xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Part 1: Dawn</w:t></w:r></w:p><w:p><w:r><w:t>Text </w:t></w:r><w:del><w:r><w:delText>DELETED</w:delText></w:r></w:del><w:ins><w:r><w:t>INSERTED</w:t></w:r></w:ins></w:p></w:body></w:document>'
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:archive.writestr('word/document.xml',xml)
        page.get_by_role('button',name='Add manuscript').click()
        page.locator('#manuscript').set_input_files({'name':'Word.docx','mimeType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','buffer':output.getvalue()})
        page.locator('#heading-mode').select_option('custom')
        page.locator('#heading-regex').fill(r'^Part (\d+): (.*)$')
        page.locator('#parse').click()
        expect(page.locator('#preview-summary')).to_contain_text('1 chapters')
        expect(page.locator('#preview-text')).to_contain_text('INSERTED')
        expect(page.locator('#preview-text')).not_to_contain_text('DELETED')
        print('PASS: original Python DOCX extraction and custom headings',flush=True)
        assert not errors,errors
        print('All checks passed. Artifacts:',artifacts,flush=True)
    except Exception:
        page.screenshot(path=str(artifacts/'failure.png'),full_page=True)
        print('Artifacts:',artifacts,flush=True)
        raise
    finally:context.close();browser.close()
