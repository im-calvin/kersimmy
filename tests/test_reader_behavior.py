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


def test_draft_theme_follows_system_and_remembers_an_override(reader):
    page = reader['page']
    root = page.locator('html')
    editor = page.get_by_role('textbox', name='Translation')
    page.emulate_media(color_scheme='dark')
    expect(root).to_have_css('color-scheme', 'dark')
    expect(editor).to_have_css('background-color', 'rgb(25, 24, 28)')
    expect(editor).to_have_css('color', 'rgb(232, 214, 184)')
    page.locator('.reader-options summary').click()
    theme = page.get_by_label('Theme', exact=True)
    expect(theme).to_have_value('system')
    theme.select_option('light')
    expect(root).to_have_css('color-scheme', 'light')
    page.reload()
    expect(root).to_have_css('color-scheme', 'light')
    page.locator('.reader-options summary').click()
    expect(theme).to_have_value('light')
    theme.select_option('system')
    expect(root).to_have_css('color-scheme', 'dark')
    page.emulate_media(color_scheme='light')
    expect(root).to_have_css('color-scheme', 'light')


def test_theme_is_shared_by_hosted_library_draft_and_review(page, reader_environment):
    base = reader_environment['base']
    imported = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Theme test', 'chapters': reader_environment['chapters']},
    }]})
    assert imported.status == 201, imported.text()
    book_id = imported.json()[0]['id']
    page.emulate_media(color_scheme='light')
    page.goto(base)
    root = page.locator('html')
    theme = page.get_by_label('Theme', exact=True)
    theme.select_option('dark')
    expect(root).to_have_css('background-color', 'rgb(32, 31, 34)')
    expect(root).to_have_css('color', 'rgb(232, 214, 184)')
    page.goto(f'{base}/books/{book_id}/draft')
    expect(root).to_have_css('color-scheme', 'dark')
    page.get_by_role('button', name='Glossary', exact=True).click()
    glossary = page.get_by_role('dialog', name='Glossary')
    expect(glossary).to_have_css('background-color', 'rgb(32, 31, 34)')
    glossary.get_by_role('button', name='Close').click()
    expect(page.get_by_role('link', name='Review', exact=True)).to_have_count(0)
    page.goto(f'{base}/books/{book_id}/review')
    expect(theme).to_have_value('dark')
    page.get_by_role('button', name='paste English', exact=True).click()
    expect(page.locator('#editor')).to_have_css('background-color', 'rgb(25, 24, 28)')
    expect(page.get_by_role('textbox')).to_have_css('color', 'rgb(232, 214, 184)')
    page.get_by_role('button', name='cancel', exact=True).click()
    theme.select_option('light')
    expect(root).to_have_css('color-scheme', 'light')
    page.get_by_role('link', name='Library').click()
    expect(theme).to_have_value('light')


def test_draft_walkthrough_can_be_skipped_and_reopened(reader):
    page = reader['page']
    walkthrough = page.get_by_role('complementary', name='Draft walkthrough')
    expect(walkthrough.get_by_role('heading', name='Start your draft')).to_be_visible()
    walkthrough.get_by_role('button', name='Next').click()
    expect(walkthrough).to_contain_text('Shift-click the last')
    walkthrough.get_by_role('button', name='Back').click()
    expect(walkthrough.get_by_role('heading', name='Start your draft')).to_be_visible()
    walkthrough.get_by_role('button', name='Skip').click()
    expect(walkthrough).to_be_hidden()

    page.reload()
    if reader['mode'] == 'hosted':
        saved(reader)
    expect(walkthrough).to_be_hidden()
    page.locator('.reader-options summary').click()
    page.get_by_role('button', name='Walkthrough', exact=True).click()
    expect(walkthrough.get_by_role('heading', name='Start your draft')).to_be_visible()
    for _ in range(2):
        walkthrough.get_by_role('button', name='Next').click()
    expect(walkthrough.get_by_role('heading', name='Comment and export')).to_be_visible()
    walkthrough.get_by_role('button', name='Start translating').click()
    expect(walkthrough).to_be_hidden()
    expect(page.get_by_role('textbox', name='Translation')).to_be_focused()


def test_chapter_drafts_reload_and_alignment(reader):
    page = reader['page']
    page.locator('#ta').fill(DRAFT)
    expect(page.get_by_role('complementary', name='Draft walkthrough')).to_be_hidden()
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
