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
    assert page.locator('#preview-chapter option').all_text_contents() == [
        'Volume 1: Dawn · Chapter 1 · 开始',
        f'{night} · Chapter 1 · 后来',
        f'{night} · Chapter 2 · 结束',
    ]
    page.locator('#preview-chapter').select_option('2')
    expect(page.locator('#preview-text')).to_contain_text('第二卷的月光')
    expect(page.locator('#preview-text')).not_to_contain_text('Volume 2')
    page.locator('#confirm-import').click()
    card = page.locator('.book-card').filter(has=page.get_by_role('heading', name=title, exact=True))
    expect(card).to_contain_text('2 VOLUMES')
    card.get_by_role('link').click()
    entry = project(page)
    page.goto(base)
    page.locator('#restore-file').set_input_files({'name': 'volumes.json', 'mimeType': 'application/json', 'buffer': json.dumps({'format': 'translation-reader', 'version': 1, 'books': [entry]}).encode()})
    expect(page.locator('#message')).to_contain_text('Restored 1 book')
    cards = page.locator('.book-card').filter(has=page.get_by_role('heading', name=title, exact=True))
    expect(cards).to_have_count(2)
    expect(cards.nth(0)).to_contain_text('2 VOLUMES')


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
    card.get_by_role('button', name='Organize volumes', exact=True).click()
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
    card.get_by_role('button', name='Organize volumes', exact=True).click()
    expect(page.locator('#volumes-dialog')).to_be_visible()
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
    expect(page.locator('#message')).to_contain_text('Volume organization saved')
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
