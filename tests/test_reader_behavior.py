"""The original file reader is the reference for shared editor behavior."""
import json
from pathlib import Path

from playwright.sync_api import expect

DRAFT = 'Chapter 1\n\nFirst paragraph.\nSecond paragraph.\nThird paragraph.'


def saved(reader):
    page = reader['page']
    if reader['mode'] == 'hosted':
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
    else:
        expect(page.locator('#ind')).to_contain_text('saved')


def test_chapter_drafts_reload_and_alignment(reader):
    page = reader['page']
    page.locator('#ta').fill(DRAFT)
    saved(reader)
    page.locator('#ta').press('ControlOrMeta+End')
    page.locator('#ta').press('ArrowLeft')
    expect(page.locator('#cn p.hit')).to_have_attribute('id', 'c1p3')
    expect(page.locator('#al')).to_have_text('EN 3 ↔ 中文 3')
    page.locator('#sel').select_option('2')
    expect(page.locator('#ta')).to_have_js_property('value', '')
    page.locator('#ta').fill('A separate second chapter.')
    saved(reader)
    page.reload()
    expect(page.locator('#sel')).to_have_js_property('value', '2')
    expect(page.locator('#ta')).to_have_js_property('value', 'A separate second chapter.')
    page.locator('#sel').select_option('1')
    expect(page.locator('#ta')).to_have_js_property('value', DRAFT)


def dismiss(reader, panel):
    page = reader['page']
    if reader['mode'] == 'local':
        page.locator(panel).get_by_role('button', name='close', exact=True).click()
    else:
        # Backdrop dismissal is an additional hosted hook, absent in file output.
        page.mouse.click(2, 2)


def test_search_statistics_and_dismissal(reader):
    page = reader['page']
    page.locator('#ta').fill(DRAFT)
    saved(reader)
    page.get_by_role('button', name='stats', exact=True).click()
    expect(page.locator('#cards')).to_contain_text('english words')
    dismiss(reader, '#stats')
    expect(page.locator('#stats')).not_to_have_class('on')
    page.get_by_role('button', name='find', exact=True).click()
    page.locator('#q').fill('月光')
    expect(page.locator('#verdict')).to_contain_text('Appears')
    expect(page.locator('#hits')).to_contain_text('后来')
    dismiss(reader, '#find')
    expect(page.locator('#find')).not_to_have_class('on')


def test_exports_preserve_source_and_draft(reader):
    page = reader['page']
    page.locator('#ta').fill(DRAFT)
    saved(reader)
    with page.expect_download() as event:
        page.get_by_role('button', name='backup', exact=True).click()
    text = Path(event.value.path()).read_text(encoding='utf-8')
    assert text.count('Chapter 1') == 1
    assert 'Third paragraph.' in text
    with page.expect_download() as event:
        page.get_by_role('button', name='full project backup', exact=True).click()
    payload = json.loads(Path(event.value.path()).read_text(encoding='utf-8'))
    assert payload['version'] == 1
    entry = payload['books'][0]
    assert entry['state']['drafts']['1'] == DRAFT
    assert entry['book']['chapters'][1]['paras'][0] == '后来月光'


def test_review_text_is_separate_and_persistent(reader):
    page = reader['page']
    page.locator('#ta').fill(DRAFT)
    saved(reader)
    page.goto(reader['urls']['review'])
    page.get_by_role('button', name='paste English', exact=True).click()
    page.locator('#ta').fill('Chapter 1\nIndependent review text.')
    page.get_by_role('button', name='save', exact=True).click()
    expect(page.locator('#en')).to_contain_text('Independent review text.')
    if reader['mode'] == 'hosted':
        saved(reader)
    page.reload()
    expect(page.locator('#en')).to_contain_text('Independent review text.')
    page.get_by_role('button', name='proportional', exact=True).click()
    page.reload()
    expect(page.locator('#m-prop')).to_have_attribute('aria-pressed', 'true')
    page.goto(reader['urls']['draft'])
    expect(page.locator('#ta')).to_have_js_property('value', DRAFT)


def test_local_smart_punctuation_preference(reader):
    if reader['mode'] != 'local':
        import pytest
        pytest.skip('Hosted smart punctuation is intentionally disabled')
    page = reader['page']
    page.locator('#ta').press_sequentially('"Hello" --')
    expect(page.locator('#ta')).to_have_js_property('value', '“Hello” —')
    page.locator('.reader-options summary').click()
    page.locator('#sq').click()
    saved(reader)
    page.reload()
    expect(page.locator('#sq')).to_have_attribute('aria-pressed', 'false')
