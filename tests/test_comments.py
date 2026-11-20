"""Passage anchors and actual Word package contents in both reader modes."""
import base64
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import pytest
from playwright.sync_api import expect

from test_reader_behavior import saved

NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'w14': 'http://schemas.microsoft.com/office/word/2010/wordml',
    'w15': 'http://schemas.microsoft.com/office/word/2012/wordml',
}


def select(page, start, end):
    page.locator('#ta').focus()
    page.locator('#ta').evaluate('(el,range)=>el.setSelectionRange(...range)', [start, end])


def click_commented_passage(page, passage):
    page.locator('#comment-marks span').first.wait_for()
    rect = page.evaluate("""passage => commentRanges.find(({range})=>range.toString()===passage)
        .range.getClientRects()[0].toJSON()""", passage)
    page.mouse.click(rect['x'] + rect['width'] / 2, rect['y'] + rect['height'] / 2)


def add_comment(page, text):
    page.get_by_role('button', name='Add comment', exact=True).click()
    page.locator('#comment-text').fill(text)
    page.get_by_role('button', name='save comment', exact=True).click()
    expect(page.locator('#comments-dialog')).to_be_hidden()


def project(page):
    with page.expect_download() as download:
        page.get_by_role('button', name='full project backup', exact=True).click()
    return json.loads(Path(download.value.path()).read_text())['books'][0]


def word_parts(page):
    with page.expect_download() as download:
        page.get_by_role('button', name='Word', exact=True).click()
    assert download.value.suggested_filename.endswith('.docx')
    with zipfile.ZipFile(download.value.path()) as package:
        assert package.testzip() is None
        return {name: ET.fromstring(package.read(name)) for name in package.namelist()}


def word(page):
    parts = word_parts(page)
    document = parts['word/document.xml']
    comments = parts['word/comments.xml']
    references = document.findall('.//w:commentReference', NS)
    assert len(references) == len(comments)
    assert {r.get('{'+NS['w']+'}id') for r in references} == {n.get('{'+NS['w']+'}id') for n in comments}
    return document, comments



def word_passages(document):
    active = set()
    passages = {}
    prefix = '{' + NS['w'] + '}'
    for paragraph in document.findall('.//w:body/w:p', NS):
        for element in paragraph.iter():
            if element.tag == prefix + 'commentRangeStart':
                identity = element.get(prefix + 'id')
                active.add(identity)
                passages[identity] = ''
            elif element.tag == prefix + 'commentRangeEnd':
                active.remove(element.get(prefix + 'id'))
            elif element.tag == prefix + 't':
                for identity in active:
                    passages[identity] += element.text or ''
        for identity in active:
            passages[identity] += '\n'
    assert not active
    return passages


def test_comment_anchor_save_word_and_backup(reader):
    page = reader['page']
    text = 'Chapter 1\n\nMoonlight 月光 & stars.\nAnother line.'
    passage = 'Moonlight 月光 & stars.'
    page.locator('#ta').fill(text)
    select(page, text.index(passage), text.index(passage) + len(passage))
    add_comment(page, 'Check the term <月光> & spelling.')
    saved(reader)
    page.reload()
    click_commented_passage(page, passage)
    expect(page.locator('#comment-list')).to_contain_text('Check the term <月光> & spelling.')
    expect(page.locator('#comment-list blockquote')).to_have_text(passage)
    page.get_by_role('dialog', name='Comment', exact=True).get_by_role('button', name='close', exact=True).click()
    # Insert before the anchor; the note must follow the original passage.
    select(page, 0, 0)
    page.locator('#ta').press_sequentially('Preface\n')
    saved(reader)
    entry = project(page)
    note = entry['state']['comments']['1'][0]
    assert note['start'] == text.index(passage) + len('Preface\n')
    assert not note['detached']
    document, comments = word(page)
    assert 'Check the term <月光> & spelling.' == ''.join(comments.itertext())
    assert passage in ''.join(document.itertext())
    assert len(document.findall('.//w:commentRangeStart', NS)) == 1
    assert len(document.findall('.//w:commentRangeEnd', NS)) == 1
    assert word_passages(document) == {'0': passage}
    if reader['mode'] == 'hosted':
        # Restore is an independent book, with notes retained.
        base = reader['urls']['draft'].split('/books/')[0]
        response = page.request.post(base + '/api/import', data={'books': [entry]})
        assert response.status == 201, response.text()
        book_id = response.json()[0]['id']
        restored = page.request.get(base + '/api/books/' + book_id + '/state').json()
        assert restored['comments'] == entry['state']['comments']


def test_docx_transfers_multiline_comment_italics_and_author(reader):
    page = reader['page']
    italic = 'Moonlight & 月光'
    passage = f'{italic}\nSecond 🌙 line.'
    text = f'Before. {passage} After.'
    note = 'Keep 月光 consistent.\nCheck the second line & punctuation.'
    page.locator('#ta').fill(text)
    start = text.index(italic)
    select(page, start, start + len(italic))
    page.get_by_role('button', name='Italic', exact=True).click()
    select(page, start, start + len(passage.encode('utf-16-le')) // 2)
    add_comment(page, note)
    page.locator('.reader-options summary').click()
    page.get_by_label('Word comment author').fill('Lin & 李')
    saved(reader)
    page.reload()

    parts = word_parts(page)
    relationships = parts['word/_rels/document.xml.rels']
    assert any(rel.get('Target') == 'comments.xml' and rel.get('Type').endswith('/comments')
               for rel in relationships)
    assert any(part.get('PartName') == '/word/comments.xml' and part.get('ContentType') ==
               'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml'
               for part in parts['[Content_Types].xml'])
    document = parts['word/document.xml']
    paragraphs = [''.join(p.itertext()) for p in document.findall('.//w:body/w:p', NS)]
    assert paragraphs[-2:] == text.splitlines()
    italic_runs = document.findall('.//w:r[w:rPr]', NS)
    assert ''.join(''.join(r.itertext()) for r in italic_runs if r.find('w:rPr/w:i', NS) is not None) == italic
    comment, = parts['word/comments.xml']
    comment_id = comment.get(f"{{{NS['w']}}}id")
    assert comment.get(f"{{{NS['w']}}}author") == 'Lin & 李'
    assert [''.join(p.itertext()) for p in comment.findall('w:p', NS)] == note.splitlines()
    assert word_passages(document) == {comment_id: passage}
    reference, = document.findall('.//w:commentReference', NS)
    assert reference.get(f"{{{NS['w']}}}id") == comment_id


def test_overlapping_comments_remain_accessible_from_the_passage(reader):
    page = reader['page']
    page.locator('#ta').fill('Moonlight crossed the courtyard.')
    for note in ('First note.', 'Second note.'):
        select(page, 0, len('Moonlight'))
        add_comment(page, note)
    click_commented_passage(page, 'Moonlight')
    popover = page.get_by_role('dialog', name='Comment', exact=True)
    expect(popover.locator('#comment-list p')).to_have_text(['First note.', 'Second note.'])
    page.once('dialog', lambda dialog: dialog.accept())
    popover.get_by_role('button', name='delete', exact=True).first.click()
    expect(popover.locator('#comment-list p')).to_have_text('Second note.')


def test_edited_passage_preserves_comment_and_can_reattach(reader):
    page = reader['page']
    page.locator('#ta').fill('Alpha beta gamma.')
    select(page, 6, 10)
    add_comment(page, 'Keep this note.')
    select(page, 6, 10)
    page.locator('#ta').press_sequentially('delta')
    saved(reader)
    page.reload()
    select(page, 6, 11)
    recovery = page.get_by_role('button', name='1 comment to reattach', exact=True)
    recovery.click()
    expect(page.locator('#comment-list')).to_contain_text('Passage changed.')
    expect(page.locator('#comment-list blockquote')).to_have_text('beta')
    page.get_by_role('button', name='reattach', exact=True).click()
    expect(page.get_by_role('dialog', name='Reattach comments')).to_be_hidden()
    click_commented_passage(page, 'delta')
    expect(page.locator('#comment-list blockquote')).to_have_text('delta')
    expect(page.locator('#comment-list')).not_to_contain_text('Passage changed.')
    page.get_by_role('button', name='edit', exact=True).click()
    page.locator('#comment-text').fill('Revised note.')
    page.get_by_role('button', name='save comment', exact=True).click()
    expect(page.get_by_role('dialog', name='Comment', exact=True)).to_be_hidden()
    expect(recovery).to_be_hidden()
    assert page.evaluate("commentRanges.map(({range})=>range.toString())") == ['delta']
    saved(reader)
    _, comments = word(page)
    assert ''.join(comments.itertext()) == 'Revised note.'
    page.locator('#sel').select_option('2')
    expect(recovery).to_be_hidden()
    expect(page.locator('#comment-marks span')).to_have_count(0)


def test_detached_comment_remains_in_word_and_can_be_deleted(reader):
    page = reader['page']
    page.locator('#ta').fill('First line.\nSecond line.')
    select(page, 6, 18)
    add_comment(page, 'A note spanning lines.')
    saved(reader)
    document, comments = word(page)
    assert ''.join(comments.itertext()) == 'A note spanning lines.'
    assert len(document.findall('.//w:p', NS)) >= 3
    assert word_passages(document) == {'0': 'line.\nSecond'}
    page.locator('#ta').fill('Replacement text.')
    saved(reader)
    _, comments = word(page)
    assert 'Passage changed; original passage: line.\nSecond' in ''.join(
        ''.join(p.itertext()) + '\n' for p in comments.findall('.//w:p', NS))
    assert 'A note spanning lines.' in ''.join(comments.itertext())
    page.get_by_role('button', name='1 comment to reattach', exact=True).click()
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_role('button', name='delete', exact=True).click()
    expect(page.get_by_role('dialog', name='Reattach comments')).to_be_hidden()
    saved(reader)
    page.reload()
    assert project(page)['state']['comments'].get('1') == []
    _, comments = word(page)
    assert len(comments) == 0


def test_hosted_comment_offline_recovery(page, reader_environment):
    base = reader_environment['base']
    response = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Offline notes', 'chapters': reader_environment['chapters']},
        'state': {'drafts': {'1': 'Offline passage.'}},
    }]})
    assert response.status == 201
    book_id = response.json()[0]['id']
    page.goto(base + '/books/' + book_id + '/draft')
    expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
    page.context.set_offline(True)
    try:
        select(page, 0, 7)
        add_comment(page, 'Note written without a connection.')
        expect(page.locator('#reader-server-status')).to_contain_text('Connection lost')
        recovery = page.evaluate("id=>JSON.parse(localStorage.getItem('original-reader-pending:'+id))", book_id)
        assert recovery['state']['comments']['1'][0]['text'] == 'Note written without a connection.'
    finally:
        page.context.set_offline(False)
    expect(page.locator('#reader-server-status')).to_have_text('Synced to server', timeout=15000)
    page.reload()
    click_commented_passage(page, 'Offline')
    expect(page.locator('#comment-list')).to_contain_text('Note written without a connection.')


def test_click_underlined_comment_and_export_author(reader):
    page = reader['page']
    editor = page.locator('#ta')
    editor.fill('The moon shines.')
    select(page, 4, 8)
    add_comment(page, 'Check the word.')
    page.locator('#c1p1').click()
    right, center_y = editor.evaluate("""el=>{
      const rect=commentRanges[0].range.getBoundingClientRect();
      return [rect.right, rect.y+rect.height/2];
    }""")
    dialog = page.get_by_role('dialog', name='Comment', exact=True)
    page.mouse.click(right + 1, center_y)
    expect(dialog).to_be_hidden()
    page.mouse.click(right - 1, center_y)
    expect(dialog).to_contain_text('Check the word.')
    assert not dialog.evaluate("el=>el.matches(':modal')")
    expect(dialog.get_by_label('Comment', exact=True)).to_be_hidden()
    expect(page.get_by_role('button', name='resolve', exact=True)).to_have_count(0)
    page.get_by_role('button', name='edit', exact=True).click()
    dialog.get_by_label('Comment', exact=True).fill('Check the phrase.')
    dialog.get_by_label('Comment', exact=True).press('Enter')
    expect(dialog).to_be_hidden()
    page.locator('.reader-options summary').click()
    expect(page.get_by_role('button', name='Chapter comments', exact=True)).to_have_count(0)
    page.get_by_label('Word comment author').fill('A & B')
    saved(reader)
    page.reload()
    _, comments = word(page)
    assert ''.join(comments.itertext()) == 'Check the phrase.'
    assert comments.find('w:comment', NS).get('{'+NS['w']+'}author') == 'A & B'


def test_comment_highlight_is_visible_in_rendered_pixels(reader):
    page = reader['page']
    editor = page.get_by_role('textbox', name='Translation')
    text = 'Loremipsum dolor sit amet.'
    editor.fill(text)
    expect(editor).to_have_attribute('spellcheck', 'true')
    passage = 'Loremipsum'
    select(page, 0, len(passage))
    add_comment(page, 'Check this word.')
    saved(reader)
    page.reload()
    expect(editor).to_have_js_property('value', text)
    page.locator('#c1p1').click()
    clip = page.evaluate("""() => {
      const rect=commentRanges[0].range.getBoundingClientRect();
      return {x:Math.ceil(rect.left),y:Math.ceil(rect.top),
        width:Math.floor(rect.width)-1,height:Math.floor(rect.height)-1};
    }""")
    screenshot = base64.b64encode(page.screenshot(clip=clip, scale='css')).decode()
    purple_pixels = page.evaluate("""async png => {
      const picture=new Image();
      picture.src='data:image/png;base64,'+png;
      await picture.decode();
      const canvas=document.createElement('canvas');
      canvas.width=picture.width; canvas.height=picture.height;
      const context=canvas.getContext('2d');
      context.drawImage(picture,0,0);
      const pixels=context.getImageData(0,0,canvas.width,canvas.height).data;
      let purple=0;
      for(let i=0;i<pixels.length;i+=4){
        const [red,green,blue]=pixels.subarray(i,i+3);
        if(red>=170&&blue>=205&&red-green>=10&&blue-green>=14)purple++;
      }
      return purple/(pixels.length/4);
    }""", screenshot)
    assert purple_pixels > 0.5


def test_comment_highlight_color_changes_and_survives_reload(reader):
    page = reader['page']
    page.locator('#ta').fill('The moon shines.')
    select(page, 4, 8)
    add_comment(page, 'Check the word.')
    saved(reader)
    marker = page.locator('#comment-marks span').first
    setting = page.get_by_label('Comment highlight')
    expect(marker).to_have_css('background-color', 'rgb(237, 207, 255)')
    page.locator('.reader-options summary').click()
    expect(setting).to_have_value('light-purple')
    setting.select_option('light-blue')
    expect(marker).to_have_css('background-color', 'rgb(204, 229, 255)')
    page.reload()
    expect(marker).to_have_css('background-color', 'rgb(204, 229, 255)')
    page.locator('.reader-options summary').click()
    expect(setting).to_have_value('light-blue')


def test_comment_controls_follow_the_passage_and_leave_it_visible(reader):
    page = reader['page']
    editor = page.locator('#ta')
    line = 'A moonlit night.'
    editor.fill('\n'.join([line] * 12))
    button = page.get_by_role('button', name='Add comment', exact=True)
    dialog = page.get_by_role('dialog', name='Add comment', exact=True)
    for start in (2, 2 + 10 * (len(line) + 1)):
        select(page, start, start + 7)
        expect(button).to_be_visible()
        passage = editor.evaluate('el => getSelection().getRangeAt(0).getBoundingClientRect().toJSON()')
        position = button.bounding_box()
        assert 0 < position['x'] - passage['right'] <= 8
        assert abs(position['y'] - passage['top']) <= 8
        button.click()
        expect(dialog).to_be_visible()
        box = dialog.bounding_box()
        assert 0 < box['x'] - passage['right'] <= 14
        pane = editor.bounding_box()
        lowest_top = pane['y'] + pane['height'] - box['height'] - 12
        expected_top = max(pane['y'] + 12, min(passage['top'] - 12, lowest_top))
        assert abs(box['y'] - expected_top) <= 1
        dialog.get_by_role('button', name='close', exact=True).click()

    wide_passage = 'W' * 28
    editor.fill(wide_passage)
    select(page, 0, len(wide_passage))
    passage = editor.evaluate('el => getSelection().getRangeAt(0).getBoundingClientRect().toJSON()')
    button.click()
    expect(dialog).to_be_visible()
    box = dialog.bounding_box()
    assert box['y'] >= passage['bottom'] or box['y'] + box['height'] <= passage['top']


@pytest.mark.parametrize('shortcut', [None, 'Meta+Shift+M', 'Control+Shift+M'],
                         ids=['bubble', 'mac-shortcut', 'windows-shortcut'])
def test_quip_style_comment_workflow_survives_reload_and_exports_exact_passage(reader, shortcut):
    page = reader['page']
    editor = page.get_by_role('textbox', name='Translation')
    add = page.get_by_role('button', name='Add comment', exact=True)
    passage = 'Moonlight'
    note = 'Keep 月光 consistent.'
    editor.fill(f'{passage} crossed the courtyard.')
    editor.press('Home')
    expect(add).to_be_hidden()
    for _ in passage:
        editor.press('Shift+ArrowRight')
    expect(add).to_be_visible()
    icon = add.bounding_box()
    assert icon['x'] > page.viewport_size['width'] / 2
    assert icon['x'] + icon['width'] <= page.viewport_size['width']
    if shortcut:
        editor.press(shortcut)
    else:
        add.click()
    composer = page.get_by_role('dialog', name='Add comment', exact=True)
    expect(composer.locator('blockquote')).to_have_text(passage)
    field = composer.get_by_role('textbox', name='Comment')
    expect(field).to_be_focused()
    field.fill(note)
    field.press('Enter')
    expect(composer).to_be_hidden()
    saved(reader)

    page.reload()
    rect = editor.evaluate("""() => commentRanges[0].range
        .getBoundingClientRect().toJSON()""")
    page.mouse.click(rect['x'] + rect['width'] / 2, rect['y'] + rect['height'] / 2)
    comment = page.get_by_role('dialog', name='Comment', exact=True)
    expect(comment).to_contain_text(note)
    expect(comment.get_by_role('textbox')).to_have_count(0)
    expect(comment.get_by_role('button', name='resolve')).to_have_count(0)
    comment.get_by_role('button', name='close', exact=True).click()

    document, comments = word(page)
    assert word_passages(document) == {'0': passage}
    assert [''.join(comment.itertext()) for comment in comments] == [note]


def test_quip_style_notes_on_two_phrases_open_and_edit_independently(reader):
    page = reader['page']
    editor = page.get_by_role('textbox', name='Translation')
    text = 'Moonlight reached the gate before dawn.'
    editor.fill(text)
    for passage, note in [('Moonlight', 'Check the light.'), ('gate', 'Check the entrance.')]:
        start = text.index(passage)
        select(page, start, start + len(passage))
        add_comment(page, note)

    comment = page.get_by_role('dialog', name='Comment', exact=True)
    for passage, note in [('gate', 'Check the entrance.'), ('Moonlight', 'Check the light.')]:
        click_commented_passage(page, passage)
        expect(comment.locator('#comment-list blockquote')).to_have_text(passage)
        expect(comment.locator('#comment-list p')).to_have_text(note)
        if passage == 'gate':
            comment.get_by_role('button', name='edit', exact=True).click()
            field = comment.get_by_role('textbox', name='Comment')
            expect(field).to_have_value(note)
            field.fill('Use the same term for gate.')
            comment.get_by_role('button', name='save comment', exact=True).click()
        else:
            comment.get_by_role('button', name='close', exact=True).click()
        expect(comment).to_be_hidden()

    saved(reader)
    page.reload()
    expect(editor).to_have_js_property('value', text)
    document, comments = word(page)
    assert word_passages(document) == {'0': 'Moonlight', '1': 'gate'}
    assert [''.join(comment.itertext()) for comment in comments] == [
        'Check the light.', 'Use the same term for gate.',
    ]


def test_library_keeps_comments_and_drafts_separate_between_manuscripts(page, reader_environment):
    base = reader_environment['base']
    chapters = reader_environment['chapters']
    first, second = 'Comment isolation first manuscript', 'Comment isolation second manuscript'
    response = page.request.post(base + '/api/import', data={'books': [
        {'book': {'title': first, 'chapters': chapters}, 'state': {'drafts': {'1': 'Moonlight at dusk.'}}},
        {'book': {'title': second, 'chapters': chapters}, 'state': {'drafts': {'1': 'Sunlight at dawn.'}}},
    ]})
    assert response.status == 201, response.text()
    page.goto(base)
    editor = page.get_by_role('textbox', name='Translation')

    def open_book(title):
        card = page.get_by_role('article').filter(has=page.get_by_role('heading', name=title, exact=True))
        card.get_by_role('link', name='Continue translating').click()

    open_book(first)
    expect(editor).to_have_js_property('value', 'Moonlight at dusk.')
    select(page, 0, len('Moonlight'))
    add_comment(page, 'First manuscript only.')
    saved({'mode': 'hosted', 'page': page})

    page.get_by_role('link', name='Library').click()
    open_book(second)
    expect(editor).to_have_js_property('value', 'Sunlight at dawn.')
    assert editor.evaluate("() => commentRanges.length") == 0
    _, comments = word(page)
    assert len(comments) == 0

    page.get_by_role('link', name='Library').click()
    open_book(first)
    expect(editor).to_have_js_property('value', 'Moonlight at dusk.')
    document, comments = word(page)
    assert word_passages(document) == {'0': 'Moonlight'}
    assert [''.join(comment.itertext()) for comment in comments] == ['First manuscript only.']


def test_existing_comment_threads_still_export_to_word(reader):
    page = reader['page']
    replies = ['Keep it as written.', 'Checked 月光 & spelling.']
    state = {
        'drafts': {'1': 'A moonlit night.'},
        'comments': {'1': [{
            'id': 'existing-comment', 'start': 2, 'end': 9, 'quote': 'moonlit',
            'text': 'Check this wording.', 'replies': replies, 'resolved': True,
        }]},
    }
    if reader['mode'] == 'hosted':
        base = reader['urls']['draft'].split('/books/')[0]
        imported = page.request.post(base + '/api/import', data={
            'books': [{'book': project(page)['book'], 'state': state}],
        })
        assert imported.ok
        page.goto(base + '/books/' + imported.json()[0]['id'] + '/draft')
    else:
        page.evaluate("""state => {
          localStorage.setItem(KEY, JSON.stringify(state.drafts));
          localStorage.setItem(NKEY, JSON.stringify(state.comments));
        }""", state)
        page.reload()

    click_commented_passage(page, 'moonlit')
    expect(page.locator('#comment-list')).to_contain_text(replies[0])
    expect(page.get_by_role('button', name='reopen', exact=True)).to_have_count(0)
    page.get_by_role('button', name='close', exact=True).filter(visible=True).click()
    parts = word_parts(page)
    comments = parts['word/comments.xml']
    assert [''.join(note.itertext()) for note in comments] == ['Check this wording.', *replies]
    comment_ids = [note.get(f"{{{NS['w']}}}id") for note in comments]
    document = parts['word/document.xml']
    references = document.findall('.//w:commentReference', NS)
    assert [ref.get(f"{{{NS['w']}}}id") for ref in references] == comment_ids
    assert word_passages(document) == dict.fromkeys(comment_ids, 'moonlit')
    root_paragraph, *reply_paragraphs = [note[-1].get(f"{{{NS['w14']}}}paraId") for note in comments]
    assert len({root_paragraph, *reply_paragraphs}) == len(comments)
    w15 = f"{{{NS['w15']}}}"
    parent_extension, *reply_extensions = parts['word/commentsExtended.xml']
    assert parent_extension.attrib == {w15 + 'paraId': root_paragraph, w15 + 'done': '1'}
    assert [reply.attrib for reply in reply_extensions] == [
        {w15 + 'paraId': paragraph, w15 + 'paraIdParent': root_paragraph, w15 + 'done': '1'}
        for paragraph in reply_paragraphs
    ]
