"""Native editing, formatting persistence and interoperability with comments/Word."""
from playwright.sync_api import expect

from test_comments import add_comment, project, select, word, word_passages, NS
from test_reader_behavior import saved


def test_italics_preserve_text_and_survive_chapter_switch_and_word(reader):
    page = reader['page']
    text = 'Chapter 1\n\nThe moon & stars shine.'
    page.locator('#ta').fill(text)
    start = text.index('moon')
    select(page, start, start + len('moon & stars'))
    page.get_by_role('button', name='Italic', exact=True).click()
    expect(page.locator('#ta')).to_have_js_property('value', text)
    saved(reader)
    expect(page.locator('#ta i,#ta em')).to_have_text('moon & stars')
    add_comment(page, 'Use this phrase consistently.')
    saved(reader)
    page.locator('#sel').select_option('2')
    page.locator('#ta').fill('Unformatted second chapter.')
    saved(reader)
    page.locator('#sel').select_option('1')
    expect(page.locator('#ta em')).to_have_text('moon & stars')
    page.reload()
    expect(page.locator('#ta em')).to_have_text('moon & stars')
    expect(page.locator('#ta em')).to_have_css('font-style', 'italic')
    entry = project(page)
    assert entry['state']['drafts']['1'] == text
    assert entry['state']['italics']['1'] == [{'start': start, 'end': start + len('moon & stars')}]
    document, comments = word(page)
    italic_text = ''.join(''.join(run.itertext()) for run in document.findall('.//w:r', NS) if run.find('w:rPr/w:i', NS) is not None)
    assert italic_text == 'moon & stars'
    assert word_passages(document) == {'0': 'moon & stars'}
    assert ''.join(comments.itertext()) == 'Use this phrase consistently.'


def test_native_italic_toggle_typing_undo_and_plain_paste(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.fill('Plain ')
    select(page, 6, 6)
    editor.press('ControlOrMeta+i')
    editor.press_sequentially('italic')
    expect(editor).to_have_js_property('value', 'Plain italic')
    saved(reader)
    editor.press('ControlOrMeta+i')
    editor.press_sequentially(' plain')
    saved(reader)
    entry = project(page)
    assert entry['state']['italics']['1'] == [{'start': 6, 'end': 12}]
    # Undo/redo a distinct native edit; typing-group sizes belong to the browser.
    select(page, len('Plain italic plain'), len('Plain italic plain'))
    editor.press('!')
    expect(editor).to_have_js_property('value', 'Plain italic plain!')
    editor.press('ControlOrMeta+z')
    expect(editor).to_have_js_property('value', 'Plain italic plain')
    saved(reader)
    editor.press('ControlOrMeta+Shift+z')
    expect(editor).to_have_js_property('value', 'Plain italic plain!')
    editor.press('ControlOrMeta+z')
    saved(reader)
    # Clipboard HTML is not injected into the editor; manuscript text stays literal.
    select(page, len('Plain italic plain'), len('Plain italic plain'))
    editor.evaluate(r'''el=>{
      const data=new DataTransfer();
      data.setData('text/plain','\n<script>literal</script>\nLast line.');
      data.setData('text/html','<img src=x onerror="throw Error(123)">');
      el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));
    }''')
    expect(editor).to_have_js_property('value', 'Plain italic plain\n<script>literal</script>\nLast line.')
    assert editor.locator('script,img').count() == 0
    saved(reader)
    page.reload()
    expect(editor).to_have_js_property('value', 'Plain italic plain\n<script>literal</script>\nLast line.')
    expect(editor.locator('em')).to_have_text('italic')


def test_native_line_breaks_offsets_and_formatting_replacement(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.fill('')
    editor.press_sequentially('First')
    editor.press('Enter')
    editor.press('Enter')
    editor.press_sequentially('Second')
    editor.press('Shift+Enter')
    editor.press_sequentially('Third')
    expect(editor).to_have_js_property('value', 'First\n\nSecond\nThird')
    editor.press('ArrowLeft')
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p3')
    select(page, 7, 13)
    editor.press('ControlOrMeta+i')
    saved(reader)
    assert project(page)['state']['italics']['1'] == [{'start': 7, 'end': 13}]
    # A normal edit before the italic passage must update its offsets.
    select(page, 0, 0)
    editor.press_sequentially('Hi ')
    saved(reader)
    assert project(page)['state']['italics']['1'] == [{'start': 10, 'end': 16}]
    page.reload()
    expect(editor).to_have_js_property('value', 'Hi First\n\nSecond\nThird')
    expect(editor.locator('em')).to_have_text('Second')
    select(page, 10, 16)
    editor.press('ControlOrMeta+i')
    saved(reader)
    assert project(page)['state']['italics']['1'] == []


def test_emoji_formatting_offsets_survive_restore(reader):
    page = reader['page']
    page.locator('#ta').fill('Moon 🌙 light.')
    # Browser selections use UTF-16 offsets; the emoji occupies two code units.
    select(page, 5, 7)
    page.locator('#ta').press('ControlOrMeta+i')
    saved(reader)
    entry = project(page)
    assert entry['state']['italics']['1'] == [{'start': 5, 'end': 7}]
    page.reload()
    expect(page.locator('#ta em')).to_have_text('🌙')
    if reader['mode'] == 'hosted':
        base = reader['urls']['draft'].split('/books/')[0]
        response = page.request.post(base + '/api/import', data={'books': [entry]})
        assert response.status == 201, response.text()
        book_id = response.json()[0]['id']
        page.goto(base + '/books/' + book_id + '/draft')
        expect(page.locator('#ta em')).to_have_text('🌙')


def test_hosted_formatting_recovery_and_text_import(page, reader_environment):
    base = reader_environment['base']
    response = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Formatting recovery', 'chapters': reader_environment['chapters']},
        'state': {'drafts': {'1': 'The moon shines.'}},
    }]})
    assert response.status == 201
    book_id = response.json()[0]['id']
    page.goto(base + '/books/' + book_id + '/draft')
    expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
    select(page, 4, 8)
    page.context.set_offline(True)
    try:
        page.locator('#ta').press('ControlOrMeta+i')
        expect(page.locator('#reader-server-status')).to_contain_text('Connection lost')
        recovery = page.evaluate("id=>JSON.parse(localStorage.getItem('original-reader-pending:'+id))", book_id)
        assert recovery['state']['italics']['1'] == [{'start': 4, 'end': 8}]
    finally:
        page.context.set_offline(False)
    expect(page.locator('#reader-server-status')).to_have_text('Synced to server', timeout=15000)
    page.reload()
    expect(page.locator('#ta em')).to_have_text('moon')
    # Importing a plain-text replacement must clear its old formatting.
    with page.expect_file_chooser() as chooser:
        page.get_by_role('button', name='import drafts', exact=True).click()
    page.once('dialog', lambda dialog: dialog.accept())
    chooser.value.set_files({'name': 'draft.txt', 'mimeType': 'text/plain', 'buffer': b'Chapter 1\nPlain replacement.'})
    expect(page.locator('#ta')).to_have_js_property('value', 'Plain replacement.')
    expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
    page.reload()
    expect(page.locator('#ta')).to_have_js_property('value', 'Plain replacement.')
    assert page.locator('#ta em,#ta i').count() == 0


def test_copy_for_docs_preserves_italics_and_selection(reader):
    page = reader['page']
    page.locator('#ta').fill('Chapter 1\n\nThe moon shines.')
    select(page, 15, 19)
    page.locator('#ta').press('ControlOrMeta+i')
    saved(reader)
    page.evaluate('''()=>window.addEventListener('copy',e=>{
      window.copied={text:e.clipboardData.getData('text/plain'),html:e.clipboardData.getData('text/html')};
    },{once:true})''')
    with page.expect_download():
        page.get_by_role('button', name='copy for Docs', exact=True).click()
    copied = page.evaluate('window.copied')
    assert copied['text'] == 'Chapter 1\n\nThe moon shines.\n'
    assert '<em>moon</em>' in copied['html']
    assert page.locator('#ta').evaluate('el=>[el.selectionStart,el.selectionEnd]') == [15, 19]


def test_scroll_sync_counts_paragraphs_when_english_wraps(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.fill(('A long translated sentence. ' * 200) + '\nSecond paragraph.\n' + ('Later paragraph.\n' * 30))
    saved(reader)
    page.reload()
    editor.evaluate('el=>el.scrollTop=200')
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p1')
    editor.locator(':scope > div').nth(1).evaluate(
        '(row, buffered)=>{const editor=row.parentElement; editor.scrollTop=row.offsetTop-(buffered?parseFloat(getComputedStyle(editor).lineHeight):0)}',
        reader['mode'] == 'hosted',
    )
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p2')


def test_changing_chapters_starts_editor_at_top(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.fill('First chapter line.\n' * 100)
    saved(reader)
    page.locator('#sel').select_option('2')
    editor.fill('Second chapter line.\n' * 100)
    saved(reader)
    page.locator('#sel').select_option('1')
    editor.evaluate('el=>el.scrollTop=300')
    expect(editor).to_have_js_property('scrollTop', 300)
    page.locator('#sel').select_option('2')
    expect(editor).to_have_js_property('scrollTop', 0)
    expect(editor).to_have_js_property('value', 'Second chapter line.\n' * 100)


def test_slash_italics_and_numbered_alignment(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.press_sequentially('A /moon/')
    expect(editor).to_have_js_property('value', 'A moon')
    expect(editor.locator('i,em')).to_have_text('moon')
    editor.fill('Chapter 1\n\nFirst\nSecond\nThird')
    if reader['mode'] == 'hosted':
        expect(page.locator('#alignment-dialog')).to_have_count(0)
        # Use the latest English paragraph in the editor itself.
        editor.press('ControlOrMeta+End')
        editor.press('!')
        expect(page.locator('#al')).to_have_text('EN 3 ↔ 中文 3')
        expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p3')
        expect(page.locator('#cn')).to_have_js_property('scrollTop', 0)
    else:
        page.locator('summary').get_by_text('View', exact=True).click()
        page.get_by_role('button', name='Aligned preview').click()
        rows = page.get_by_role('dialog', name='Aligned preview').locator('tbody tr')
        expect(rows).to_have_count(3)
        expect(rows.nth(2).locator('td').nth(2)).to_have_text('Third')


def test_file_reader_schedules_portable_snapshots(page, reader_environment):
    page.clock.install()
    page.add_init_script("""(() => {
        window.snapshotFiles = [];
        window.showDirectoryPicker = async () => ({
          getFileHandle: async name => ({
            createWritable: async () => ({
              write: async value => window.snapshotFiles.push({name, value:JSON.parse(value)}),
              close: async () => {},
            }),
          }),
        });
    })()""")
    page.goto((reader_environment['local'] / 'draft.html').as_uri())
    page.locator('#ta').fill('First version.')
    page.locator('summary').get_by_text('View', exact=True).click()
    page.get_by_label('Snapshot interval (minutes)').fill('1')
    page.get_by_role('button', name='Choose snapshot folder').click()
    expect(page.locator('#snapshot-status')).to_contain_text('Snapshot saved')
    page.locator('#ta').fill('Later version.')
    page.clock.fast_forward(61000)
    snapshots = page.evaluate('window.snapshotFiles')
    assert len(snapshots) == 2
    assert snapshots[0]['name'] != snapshots[1]['name']
    assert [snapshot['value']['books'][0]['state']['drafts']['1'] for snapshot in snapshots] == [
        'First version.', 'Later version.',
    ]


def test_one_english_paragraph_can_highlight_a_saved_source_range(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.fill('Combined translation.\nNext translation.')
    editor.evaluate("el=>el.setSelectionRange(3,3)")
    editor.press('ArrowRight')
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1')
    page.locator('#c1p3').click()
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1')
    editor.focus()
    editor.evaluate("el=>el.setSelectionRange(3,3)")
    page.locator('#c1p1').click(modifiers=['Alt'])
    page.locator('#c1p2').click(modifiers=['Shift'])
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1–2')
    assert page.locator('#cn p.hit').evaluate_all('nodes=>nodes.map(node=>node.id)') == ['c1p1', 'c1p2']
    editor.press('ArrowDown')
    expect(page.locator('#al')).to_contain_text('EN 2 ↔ 中文 3')
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p3')
    page.locator('#c1p2').click(modifiers=['Alt'])
    expect(page.locator('#al')).to_contain_text('EN 2 ↔ 中文 3')
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p3')
    saved(reader)
    assert project(page)['state']['alignmentGroups'] == {'1': {'1': [1, 2]}}
    page.locator('#c1p2').click()
    expect(editor).not_to_be_focused()
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1–2')
    assert page.evaluate("[...CSS.highlights.get('translation-reading')][0].toString()") == 'Combined translation.'
    editor.click()
    assert page.evaluate("CSS.highlights.has('translation-reading')") is False
    page.reload()
    expect(page.locator('#cn p.hit')).to_have_count(2)
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1–2')
    page.get_by_role('button', name='reset', exact=True).click()
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p1')


def test_source_range_can_extend_in_both_directions_with_option_held(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.fill('One translation for all three paragraphs.')
    editor.evaluate('el=>el.setSelectionRange(0,0)')
    page.locator('#c1p2').click(modifiers=['Alt'])
    expect(page.locator('#al')).to_contain_text('EN 1 ↔ 中文 2')
    page.locator('#c1p3').click(modifiers=['Alt', 'Shift'])
    expect(page.locator('#al')).to_contain_text('EN 1 ↔ 中文 2–3')
    page.locator('#c1p1').click(modifiers=['Shift'])
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1–3')
    expect(page.locator('#cn p.hit')).to_have_count(3)
    saved(reader)
    page.reload()
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1–3')
    expect(page.locator('#cn p.hit')).to_have_count(3)


def test_older_overlapping_links_are_read_in_forward_order(page, reader_environment):
    base = reader_environment['base']
    response = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Old alignment', 'chapters': [
            {'no': 1, 'title': '', 'paras': [f'中文 {n}' for n in range(1, 8)]}
        ]},
        'state': {'drafts': {'1': 'One\nTwo\nThree\nFour'},
                  'alignmentGroups': {'1': {'1': [1, 3], '2': [2, 2]}}},
    }]})
    assert response.status == 201, response.text()
    book = response.json()[0]
    page.goto(f"{base}/books/{book['id']}/draft")
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1–3')
    editor = page.locator('#ta')
    editor.focus()
    editor.evaluate('el=>el.setSelectionRange(4,4)')
    editor.press('ArrowRight')
    expect(page.locator('#al')).to_contain_text('EN 2 ↔ 中文 4')
    editor.evaluate('el=>el.setSelectionRange(14,14)')
    editor.press('ArrowRight')
    expect(page.locator('#al')).to_contain_text('EN 4 ↔ 中文 6')
    state = page.request.get(f"{base}/api/books/{book['id']}/state").json()
    assert state['alignmentGroups']['1']['2'] == [2, 2]


def test_hosted_source_scrolls_with_english_while_the_highlight_follows_the_caret(page, reader_environment):
    base = reader_environment['base']
    paragraphs = [f'English paragraph {n}.' for n in range(1, 41)]
    response = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Scroll follow', 'chapters': [
            {'no': 1, 'title': '', 'paras': [f'中文段落 {n}' for n in range(1, 41)]},
        ]},
        'state': {'drafts': {'1': '\n'.join(paragraphs)}},
    }]})
    assert response.status == 201, response.text()
    book_id = response.json()[0]['id']
    page.goto(f'{base}/books/{book_id}/draft')
    source = page.locator('#cn')
    editor = page.locator('#ta')
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1')
    editor.focus()
    editor.press('ArrowDown')
    expect(page.locator('#al')).to_have_text('EN 2 ↔ 中文 2')
    expect(source).to_have_js_property('scrollTop', 0)
    caret_offset = len('\n'.join(paragraphs[:7])) + 1
    editor.evaluate('(el, offset)=>el.setSelectionRange(offset, offset)', caret_offset)
    editor.press('ArrowRight')
    expect(page.locator('#al')).to_have_text('EN 8 ↔ 中文 8')
    with page.expect_event('console', predicate=lambda message: message.text == 'test scroll rendered'):
        editor.evaluate("""el=>{
          el.addEventListener('scroll',()=>requestAnimationFrame(()=>console.log('test scroll rendered')),{once:true});
          el.scrollTop=96;
        }""")
    expect(page.locator('#al')).to_have_text('EN 8 ↔ 中文 8')
    expect(source).to_have_js_property('scrollTop', 96)
    assert page.evaluate("[...CSS.highlights.get('translation-reading')][0].toString()") == paragraphs[7]
    editor.evaluate("""el=>{
      const caret=getSelection().getRangeAt(0).getBoundingClientRect();
      el.scrollTop+=caret.bottom-el.getBoundingClientRect().top-5;
    }""")
    expect(page.locator('#al')).to_have_text('EN 9 ↔ 中文 9')
    editor.evaluate("el=>el.scrollTop=el.scrollHeight")
    page.wait_for_function("""() => {
      const source=document.querySelector('#cn');
      const hit=source.querySelector('.hit');
      return source.scrollTop>0 && Number(hit?.id.split('p').at(-1))>=20
        && hit.getBoundingClientRect().bottom<=source.getBoundingClientRect().bottom;
    }""")
    expect(editor).to_be_focused()
    active = int(page.locator('#cn .hit').get_attribute('id').split('p')[-1])
    assert page.evaluate("[...CSS.highlights.get('translation-reading')][0].toString()") == paragraphs[active - 1]
    expected_offset = len('\n'.join(paragraphs[:active - 1])) + 1
    expect(editor).to_have_js_property('selectionStart', expected_offset)
    bottom_visible = editor.evaluate("""el=>{
      el.scrollTop=0;
      const pane=el.getBoundingClientRect();
      return [...el.children].filter(row=>{
        const range=document.createRange();
        range.selectNodeContents(row);
        const bounds=range.getBoundingClientRect();
        const buffer=Math.min(parseFloat(getComputedStyle(el).lineHeight),pane.height/4);
        return bounds.bottom>pane.top&&bounds.top<pane.bottom-buffer;
      }).length;
    }""")
    expect(page.locator('#al')).to_have_text(f'EN {bottom_visible} ↔ 中文 {bottom_visible}')
    expect(editor).to_have_js_property('selectionStart', len('\n'.join(paragraphs[:bottom_visible])))
    assert page.evaluate("[...CSS.highlights.get('translation-reading')][0].toString()") == paragraphs[bottom_visible - 1]
    source.locator('#c1p2').click()
    expect(page.locator('#al')).to_have_text('EN 2 ↔ 中文 2')
    assert page.evaluate("[...CSS.highlights.get('translation-reading')][0].toString()") == paragraphs[1]
    editor.locator(':scope > div').nth(7).click()
    expect(editor).to_be_focused()
    expect(page.locator('#al')).to_have_text('EN 8 ↔ 中文 8')
    source.locator('#c1p32').click()
    expect(page.locator('#al')).to_have_text('EN 32 ↔ 中文 32')
    page.wait_for_function("""() => {
      const editor = document.getElementById('ta');
      const range = [...CSS.highlights.get('translation-reading')][0];
      const line = range.getBoundingClientRect();
      const pane = editor.getBoundingClientRect();
      return editor.scrollTop > 0 && line.top >= pane.top && line.bottom <= pane.bottom;
    }""")


def test_scroll_handoff_skips_blank_lines_and_highlights_visible_english(page, reader_environment):
    base = reader_environment['base']
    text = 'First.\nSecond.\n\n\n' + ('Third paragraph wraps. ' * 30) + '\nFourth.'
    response = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Blank line handoff', 'chapters': [
            {'no': 1, 'title': '', 'paras': ['中文一', '中文二', '中文三', '中文四']},
        ]},
        'state': {'drafts': {'1': text}},
    }]})
    assert response.status == 201
    page.goto(f"{base}/books/{response.json()[0]['id']}/draft")
    editor = page.locator('#ta')
    editor.focus()
    editor.press('ArrowRight')
    expect(page.locator('#al')).to_have_text('EN 1 ↔ 中文 1')
    editor.evaluate("""el=>{
      const range=document.createRange();
      range.selectNodeContents(el.children[1]);
      el.scrollTop=Math.ceil(range.getBoundingClientRect().bottom-el.getBoundingClientRect().top)+4;
    }""")
    expect(page.locator('#al')).to_have_text('EN 3 ↔ 中文 3')
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p3')
    assert page.evaluate("""() => {
      const range=[...CSS.highlights.get('translation-reading')][0];
      const pane=document.getElementById('ta').getBoundingClientRect();
      return range.toString().startsWith('Third paragraph wraps.')
        && [...range.getClientRects()].some(rect=>rect.bottom>pane.top&&rect.top<pane.bottom);
    }""")

    start = len('First.\nSecond.\n\n\n')
    expect(editor).to_have_js_property('selectionStart', start)
    editor.evaluate("""el=>{
      const row=el.children[4], range=document.createRange();
      range.selectNodeContents(row);
      const rect=range.getClientRects()[0];
      el.scrollTop+=Math.ceil(rect.bottom-el.getBoundingClientRect().top)+4;
    }""")
    page.wait_for_function("""({start}) => {
      const editor=document.getElementById('ta'), selection=getSelection(), pane=editor.getBoundingClientRect();
      const rect=selection.getRangeAt(0).getClientRects()[0];
      return editor.selectionStart>start && rect?.bottom>pane.top && rect?.top<pane.bottom;
    }""", arg={'start': start})
    expect(page.locator('#al')).to_have_text('EN 3 ↔ 中文 3')
