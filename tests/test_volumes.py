"""Book/volume/chapter imports, navigation, revision checks and preservation."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest
from playwright.sync_api import expect

from conftest import ROOT
from chapter_structure import VOLUME_HEADING_REGEX
from tlconfig import load_config, parse_source
from test_comments import project, word, add_comment, select, word_passages
from test_reader_behavior import saved

SOURCE = 'Volume 1: Dawn\n第一章 开始\n第一卷的月光\nVolume 2: Night\n第一章 后来\n第二卷的月光\n第二章 结束\n最后一段'


@pytest.fixture(params=['local', 'hosted'])
def volume_reader(request, page, tmp_path, reader_environment):
    source = tmp_path / 'source.txt'
    source.write_text(SOURCE, encoding='utf-8')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'project': 'Volumes', 'source': str(source), 'encoding': 'utf-8',
        'paragraph_mode': 'line', 'storage_prefix': 'volumes-test', 'illustration': '',
        'volume_heading_regex': VOLUME_HEADING_REGEX}), encoding='utf-8')
    chapters = parse_source(load_config(str(config)))
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if request.param == 'local':
        output = tmp_path / 'local'
        output.mkdir()
        subprocess.run(['bash', str(ROOT / 'tools/regenerate.sh'), 'all'],
            env=dict(os.environ, CONFIG=str(config), OUTDIR=str(output)), check=True, capture_output=True, text=True)
        urls = {'draft': (output / 'draft.html').as_uri(), 'review': (output / 'sync.html').as_uri()}
    else:
        base = reader_environment['base']
        response = page.request.post(base + '/api/import', data={'books': [{'book': {'title': 'Volumes', 'chapters': chapters}}]})
        assert response.status == 201, response.text()
        book_id = response.json()[0]['id']
        urls = {kind: f'{base}/books/{book_id}/{kind}' for kind in ('draft', 'review')}
    page.goto(urls['draft'])
    yield {'page': page, 'urls': urls, 'mode': request.param}
    assert not errors, errors


def test_restarted_chapters_have_independent_drafts_and_portable_structure(volume_reader):
    reader = volume_reader
    page = reader['page']
    assert page.locator('#sel optgroup').evaluate_all('els=>els.map(el=>el.label)') == ['Volume 1: Dawn', 'Volume 2: Night']
    assert page.locator('#sel option').evaluate_all('els=>els.map(el=>el.value)') == ['1', '2', '3']
    page.locator('#ta').fill('Dawn translation.')
    saved(reader)
    page.locator('#sel').select_option('2')
    expect(page.locator('#cn')).to_contain_text('Volume 2: Night')
    expect(page.locator('#cn h2')).to_have_text('第1章 后来')
    expect(page.locator('#ta')).to_have_js_property('value', '')
    page.locator('#ta').fill('Night translation.')
    select(page, 0, 5)
    add_comment(page, 'Night term.')
    saved(reader)
    page.reload()
    expect(page.locator('#sel')).to_have_js_property('value', '2')
    expect(page.locator('#ta')).to_have_js_property('value', 'Night translation.')
    page.locator('#sel').select_option('1')
    expect(page.locator('#ta')).to_have_js_property('value', 'Dawn translation.')
    entry = project(page)
    assert [(c['no'], c['number'], c['volume']) for c in entry['book']['chapters']] == [
        (1, 1, 'Volume 1: Dawn'), (2, 1, 'Volume 2: Night'), (3, 2, 'Volume 2: Night')]
    assert entry['state']['drafts']['1'] == 'Dawn translation.'
    assert entry['state']['drafts']['2'] == 'Night translation.'
    document, notes = word(page)
    assert word_passages(document) == {'0': 'Night'}
    assert ''.join(notes.itertext()) == 'Night term.'
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs = [''.join(p.itertext()) for p in document.findall('.//w:body/w:p', ns)]
    assert paragraphs == ['Volume 1: Dawn', 'Chapter 1', 'Dawn translation.', 'Volume 2: Night', 'Chapter 1', 'Night translation.']
    page.goto(reader['urls']['review'])
    assert page.locator('#sel optgroup').count() == 2
    page.get_by_role('button', name='paste English', exact=True).click()
    page.locator('#ta').fill('Volume 1: Dawn\nChapter 1\nDawn review.\n\nVolume 2: Night\nChapter 1\nNight review.\nChapter 2\nEnding review.')
    page.get_by_role('button', name='save', exact=True).click()
    expect(page.locator('#en')).to_contain_text('Dawn review.')
    expect(page.locator('#en')).to_contain_text('Night review.')
    page.get_by_role('button', name='paste English', exact=True).click()
    page.get_by_role('button', name='save', exact=True).click()
    if reader['mode'] == 'hosted':
        saved(reader)
    page.reload()
    expect(page.locator('#en')).to_contain_text('Dawn review.')
    expect(page.locator('#en')).to_contain_text('Night review.')
    expect(page.locator('#en')).to_contain_text('Ending review.')
    page.goto(reader['urls']['draft'])
    state = project(page)['state']
    assert state['reviewEnglish'] == {'1': 'Dawn review.', '2': 'Night review.', '3': 'Ending review.'}


@pytest.mark.parametrize('source', [
    SOURCE,
    'Volume 1: Dawn\n第一章 开始\n第一卷的月光\n'
    '第2卷 Night 第一章 后来\n第二卷的月光\n第2卷 Night 第二章 结束\n最后一段',
], ids=['standalone-headings', 'combined-headings'])
def test_docx_volume_preview_import_and_restore(page, reader_environment, source):
    base = reader_environment['base']
    page.goto(base)
    page.get_by_role('button', name='Add manuscript').click()
    output = io.BytesIO()
    document = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document')
    body = ET.SubElement(document, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')
    for line in source.splitlines():
        paragraph = ET.SubElement(body, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
        run = ET.SubElement(paragraph, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r')
        ET.SubElement(run, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t').text = line
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', ET.tostring(document))
    title = 'Combined volumes' if '第2卷' in source else 'Standalone volumes'
    page.locator('#manuscript').set_input_files({'name': title + '.docx', 'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'buffer': output.getvalue()})
    with page.expect_response('**/api/preview') as preview_response:
        page.locator('#parse').click()
    assert preview_response.value.status == 200, preview_response.value.text()
    expect(page.locator('#preview-summary')).to_contain_text('3 chapters')
    night = '第2卷 Night' if '第2卷' in source else 'Volume 2: Night'
    assert page.locator('#preview-chapter optgroup').evaluate_all('groups => groups.map(g => g.label)') == [
        'Volume 1: Dawn', night,
    ]
    assert page.locator('#preview-chapter option').all_text_contents() == [
        'Chapter 1 · 开始',
        'Chapter 1 · 后来',
        'Chapter 2 · 结束',
    ]
    page.locator('#preview-chapter').select_option('2')
    expect(page.get_by_label('Chapter title', exact=True)).to_have_value('后来')
    page.get_by_label('Chapter title', exact=True).fill('新的标题')
    expect(page.locator('#preview-text')).to_contain_text('第二卷的月光')
    expect(page.locator('#preview-text')).not_to_contain_text('Volume 2')
    page.locator('#confirm-import').click()
    card = page.locator('.book-card').filter(has=page.get_by_role('heading', name=title, exact=True))
    expect(card).to_contain_text('3 chapters')
    card.get_by_role('link').click()
    entry = project(page)
    assert entry['book']['chapters'][1]['title'] == '新的标题'
    page.goto(base)
    page.locator('#restore-file').set_input_files({'name': 'volumes.json', 'mimeType': 'application/json', 'buffer': json.dumps({'format': 'translation-reader', 'version': 1, 'books': [entry]}).encode()})
    expect(page.locator('#message')).to_contain_text('Restored 1 book')
    cards = page.locator('.book-card').filter(has=page.get_by_role('heading', name=title, exact=True))
    expect(cards).to_have_count(2)
    expect(cards.nth(0)).to_contain_text('3 chapters')


def test_organizing_existing_book_preserves_state_and_rejects_stale_writes(page, reader_environment):
    base = reader_environment['base']
    state = {'drafts': {'1': 'First draft.', '2': 'Second draft.'}, 'times': {'1': 1234},
        'italics': {'1': [{'start': 0, 'end': 5}]}, 'offsets': {'1': -1},
        'comments': {'1': [{'id': 'note', 'start': 0, 'end': 5, 'quote': 'First', 'text': 'A note.'}]},
        'reviewEnglish': {'2': 'Separate review.'}}
    response = page.request.post(base + '/api/import', data={'books': [{'book': {'title': 'Organize existing', 'chapters': reader_environment['chapters']}, 'state': state}]})
    assert response.status == 201
    book_id = response.json()[0]['id']
    page.goto(base)
    card = page.locator('.book-card').filter(has=page.get_by_role('heading', name='Organize existing', exact=True))
    card.get_by_role('button', name='Settings', exact=True).click()
    expect(page.locator('#volumes-dialog')).to_be_visible()
    page.locator('#select-all-chapters').check()
    page.locator('#volume-name').fill('First volume <safe>')
    page.locator('#assign-volume').click()
    # A concurrent state write makes the organizer's revision stale.
    current = page.request.get(base + '/api/books/' + book_id + '/state').json()
    remote = dict(current, times={'1': 9999})
    response = page.request.put(base + '/api/books/' + book_id + '/state', data={'state': remote, 'expectedRevision': 0})
    assert response.status == 200
    page.locator('#save-volumes').click()
    expect(page.locator('#volumes-error')).to_contain_text('This book changed')
    page.locator('#cancel-volumes').click()
    card.get_by_role('button', name='Settings', exact=True).click()
    expect(page.locator('#volumes-dialog')).to_be_visible()
    page.get_by_role('textbox', name='Chapter 1', exact=True).fill('New title <safe>')
    page.locator('#volume-chapters input[data-chapter="1"]').check()
    page.locator('#volume-name').fill('First volume <safe>')
    page.locator('#assign-volume').click()
    expect(page.locator('#volume-chapters .volume-row').first.locator('small')).to_have_text('First volume <safe>')
    page.locator('#volume-chapters input[data-chapter="1"]').uncheck()
    page.locator('#volume-chapters input[data-chapter="2"]').check()
    page.locator('#volume-name').fill('Second volume')
    page.locator('#assign-volume').click()
    with page.expect_request('**/volumes') as volume_request:
        page.locator('#save-volumes').click()
    assert volume_request.value.post_data_json['volumes'] == {'1': 'First volume <safe>', '2': 'Second volume'}
    expect(page.locator('#message')).to_contain_text('Chapter changes saved')
    bundle = page.request.get(base + '/api/books/' + book_id + '/bundle').json()
    for key, value in state.items():
        assert bundle['state'][key] == (remote[key] if key == 'times' else value)
    assert bundle['state']['revision'] == 2
    assert [c['no'] for c in bundle['book']['chapters']] == [1, 2]
    assert [c['volume'] for c in bundle['book']['chapters']] == ['First volume <safe>', 'Second volume']
    response = page.request.put(base + '/api/books/' + book_id + '/state', data={'state': remote, 'expectedRevision': 1})
    assert response.status == 409
    page.goto(base + '/books/' + book_id + '/draft')
    expect(page.locator('#sel optgroup').first).to_have_attribute('label', 'First volume <safe>')
    expect(page.locator('#sel option').first).to_contain_text('New title <safe>')
    expect(page.locator('#ta em')).to_have_text('First')


def test_volume_parser_preserves_existing_numbering_and_optional_detection(tmp_path):
    from tlconfig import DEFAULTS
    source = tmp_path / 'source.txt'
    source.write_text('第一卷 晨光\n第七章 开始\n正文一\n第二卷 夜色\n第九章 后来\n正文二', encoding='utf-8')
    cfg = dict(DEFAULTS, source=str(source), encoding='utf-8', paragraph_mode='line')
    without = parse_source(cfg)
    assert [c['no'] for c in without] == [7, 9]
    assert without[0]['paras'] == ['正文一', '第二卷 夜色']
    with_volumes = parse_source(dict(cfg, volume_heading_regex=VOLUME_HEADING_REGEX))
    assert [c['no'] for c in with_volumes] == [7, 9]
    assert not any('number' in c for c in with_volumes)
    assert [c['volume'] for c in with_volumes] == ['第一卷 晨光', '第二卷 夜色']
    assert [c['paras'] for c in with_volumes] == [['正文一'], ['正文二']]
    source.write_text('第一卷 晨光\n第一章 开始\n正文一\n第一章 后来\n正文二', encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate chapter numbers within a volume'):
        parse_source(dict(cfg, volume_heading_regex=VOLUME_HEADING_REGEX))


def test_automatic_import_separates_numbered_bonus_stories():
    from base64 import b64encode
    from reader_server import parse_upload

    source = '第一卷·狐美人\n第1章 曜金三圣\n正文。\n番外篇\n番外篇 实体番外\n番外1 飞天猫\n番外正文。'
    preview = parse_upload({'name': 'sample.txt', 'content': b64encode(source.encode()).decode()})
    assert preview['chapters'] == [
        {'no': 1, 'number': 1, 'title': '曜金三圣', 'volume': '第一卷·狐美人', 'paras': ['正文。']},
        {'no': 2, 'number': 1, 'title': '飞天猫', 'volume': '番外篇 实体番外', 'paras': ['番外正文。']},
    ]


def test_volume_api_invalid_assignment_is_atomic_and_clean_reader_refreshes(page, reader_environment):
    base = reader_environment['base']
    chapters = [{'no': 1, 'number': 1, 'volume': 'One', 'title': 'A', 'paras': ['正文一']},
                {'no': 2, 'number': 1, 'volume': 'Two', 'title': 'B', 'paras': ['正文二']}]
    response = page.request.post(base + '/api/import', data={'books': [{'book': {'title': 'Revision volumes', 'chapters': chapters}, 'state': {'drafts': {'1': 'Saved draft.'}}}]})
    assert response.status == 201
    book_id = response.json()[0]['id']
    endpoint = base + '/api/books/' + book_id
    before = page.request.get(endpoint + '/bundle').json()
    for volumes in ({'1': 'Missing chapter'}, {'1': '', '2': ''}, {'1': 'Same', '2': 'Same'}, {'1': 'One', '2': 2}):
        response = page.request.put(endpoint + '/volumes', data={'volumes': volumes, 'expectedRevision': 0})
        assert response.status == 400, response.text()
        assert page.request.get(endpoint + '/bundle').json() == before
    page.goto(base + '/books/' + book_id + '/draft')
    expect(page.locator('#ta')).to_have_js_property('value', 'Saved draft.')
    response = page.request.put(endpoint + '/volumes', data={'volumes': {'1': 'Renamed one', '2': 'Renamed two'}, 'expectedRevision': 0})
    assert response.status == 200
    expect(page.locator('#sel optgroup').first).to_have_attribute('label', 'Renamed one', timeout=15000)
    expect(page.locator('#ta')).to_have_js_property('value', 'Saved draft.')


def test_recheck_import_updates_titles_only_when_source_matches(page, reader_environment):
    base = reader_environment['base']
    original = {'no': 1, 'title': '', 'paras': ['原稿内容。']}
    created = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Rechecked book', 'chapters': [original]},
        'state': {'drafts': {'1': 'Saved translation.'}, 'offsets': {'1': -1}},
    }]})
    assert created.status == 201
    endpoint = base + '/api/books/' + created.json()[0]['id']
    page.goto(base)
    card = page.locator('.book-card').filter(has=page.get_by_role('heading', name='Rechecked book', exact=True))
    card.get_by_role('button', name='Settings', exact=True).click()
    page.get_by_role('button', name='Recheck import').click()
    page.locator('#manuscript').set_input_files({
        'name': 'manuscript.txt', 'mimeType': 'text/plain', 'buffer': '第1章 新标题\n改动内容。'.encode(),
    })
    page.locator('#parse').click()
    expect(page.locator('#import-error')).to_contain_text('Chapter boundaries or source text changed')
    expect(page.locator('#confirm-import')).to_be_disabled()
    before = page.request.get(endpoint + '/bundle').json()
    invalid = page.request.put(endpoint + '/chapter-import', data={
        'preview': {'chapters': [{**original, 'paras': ['改动内容。']}]}, 'expectedRevision': 0,
    })
    assert invalid.status == 400
    assert page.request.get(endpoint + '/bundle').json() == before
    page.locator('#manuscript').set_input_files({
        'name': 'manuscript.txt', 'mimeType': 'text/plain', 'buffer': '第1章 新标题\n原稿内容。'.encode(),
    })
    page.locator('#parse').click()
    expect(page.get_by_label('Chapter title', exact=True)).to_have_value('新标题')
    page.get_by_role('button', name='Update existing book').click()
    expect(page.locator('#message')).to_contain_text('Manuscript import updated')
    after = page.request.get(endpoint + '/bundle').json()
    assert after['book']['chapters'] == [{**original, 'title': '新标题'}]
    assert after['state'] == {**before['state'], 'revision': 1}


def test_delete_book_requires_confirmation_and_current_revision(page, reader_environment):
    base = reader_environment['base']
    created = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Disposable deletion test', 'chapters': reader_environment['chapters']},
        'state': {'drafts': {'1': 'Saved draft.'}},
    }]})
    assert created.status == 201
    endpoint = base + '/api/books/' + created.json()[0]['id']
    page.goto(base)
    card = page.locator('.book-card').filter(has=page.get_by_role('heading', name='Disposable deletion test'))
    expect(card.get_by_role('button', name='Delete book', exact=True)).to_have_count(0)
    dialog = page.get_by_role('dialog', name='Book settings')
    delete = dialog.get_by_role('button', name='Delete book', exact=True)
    card.get_by_role('button', name='Settings', exact=True).click()
    expect(delete).to_be_hidden()
    dialog.get_by_text('Remove book', exact=True).click()

    page.once('dialog', lambda dialog: dialog.dismiss())
    delete.click()
    expect(card).to_be_visible()
    assert page.request.get(endpoint).ok

    page.once('dialog', lambda dialog: dialog.accept('wrong phrase'))
    delete.click()
    expect(page.locator('#volumes-error')).to_contain_text('The confirmation phrase did not match.')
    assert page.request.get(endpoint).ok

    state = page.request.get(endpoint + '/state').json()
    updated = page.request.put(endpoint + '/state', data={'state': state, 'expectedRevision': state['revision']})
    assert updated.ok
    rejected = page.request.delete(endpoint, data={'expectedRevision': updated.json()['revision']})
    assert rejected.status == 400
    page.once('dialog', lambda dialog: dialog.accept('I am an idiot sandwich'))
    delete.click()
    expect(page.locator('#volumes-error')).to_contain_text('This book changed')
    assert page.request.get(endpoint).ok

    page.reload()
    card.get_by_role('button', name='Settings', exact=True).click()
    dialog.get_by_text('Remove book', exact=True).click()
    page.once('dialog', lambda dialog: dialog.accept('I am an idiot sandwich'))
    delete.click()
    expect(card).to_have_count(0)
    expect(page.locator('#message')).to_contain_text('Deleted')
    assert page.request.get(endpoint).status == 404


def test_book_icon_and_library_refresh_keep_the_same_card(page, reader_environment):
    base = reader_environment['base']
    created = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'TTEOTM (English drafts for Chapters 2–6)', 'chapters': reader_environment['chapters']},
    }]})
    assert created.ok
    book_id = created.json()[0]['id']
    page.clock.install()
    page.goto(base)
    expect(page.locator('link[rel=icon]')).to_have_attribute('href', 'site-icon.png')
    expect(page.locator('.wordmark .site-icon')).to_be_visible()
    expect(page.locator('.intro')).to_have_count(0)
    card = page.locator('.book-card').filter(has=page.get_by_role('heading', name='TTEOTM', exact=True))
    expect(card).to_contain_text('2 chapters')
    expect(card).not_to_contain_text('source paragraphs')
    settings = card.get_by_role('button', name='Settings', exact=True)
    settings.click()
    dialog = page.get_by_role('dialog', name='Book settings')
    choose = dialog.get_by_role('button', name='Set book icon')
    with page.expect_file_chooser() as chooser:
        choose.click()
    chooser.value.set_files(ROOT / 'web' / 'site-icon.png')
    expect(page.locator('#book-settings-status')).to_have_text('Book icon saved.')
    image = card.locator('.book-card-icon')
    expect(image).to_be_visible()
    icon = image.get_attribute('src')
    assert icon.startswith('data:image/png;base64,')
    exported = page.request.get(base + '/api/export').json()
    assert next(entry for entry in exported['books'] if entry['book']['id'] == book_id)['book']['icon'] == icon
    with page.expect_download() as backup:
        dialog.get_by_role('button', name='Back up book').click()
    assert json.loads(Path(backup.value.path()).read_text())['books'][0]['book']['icon'] == icon
    dialog.get_by_role('button', name='Close', exact=True).click()
    settings.focus()
    settings.evaluate('button => { window.originalSettingsButton = button }')

    endpoint = f'{base}/api/books/{book_id}/state'
    state = page.request.get(endpoint).json()
    state['drafts']['1'] = 'Remote draft.'
    assert page.request.put(endpoint, data={'state': state, 'expectedRevision': state['revision']}).ok
    page.clock.fast_forward(10000)
    expect(card.get_by_role('link')).to_have_text('Continue')
    assert settings.evaluate('button => button === window.originalSettingsButton')
    expect(settings).to_be_focused()
    expect(image).to_have_attribute('src', icon)

    card.click(position={'x': 12, 'y': 12})
    expect(page.locator('link[rel=icon]')).to_have_attribute('href', '/site-icon.png')
    expect(page.locator('.reader-site-corner')).to_be_visible()
