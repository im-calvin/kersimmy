"""The original file reader is the reference for shared editor behavior."""
import json
from pathlib import Path

from playwright.sync_api import expect

DRAFT = 'Chapter 1\n\nFirst paragraph.\nSecond paragraph.\nThird paragraph.'


def open_exports(page):
    menu = page.locator('#exports-menu')
    if menu.get_attribute('open') is None:
        menu.get_by_text('Exports', exact=True).click()
    return menu


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
    moon = page.get_by_role('button', name='Switch to dark mode', exact=True)
    sun = page.get_by_role('button', name='Switch to light mode', exact=True)
    view = page.locator('.reader-options summary')
    page.emulate_media(color_scheme='light')
    expect(moon).to_be_hidden()
    view.click()
    expect(moon).to_have_text('☾')
    page.emulate_media(color_scheme='dark')
    expect(root).to_have_css('color-scheme', 'dark')
    expect(editor).to_have_css('background-color', 'rgb(25, 24, 28)')
    expect(editor).to_have_css('color', 'rgb(232, 214, 184)')
    expect(sun).to_have_text('☀\ufe0e')
    sun.click()
    expect(root).to_have_css('color-scheme', 'light')
    page.reload()
    expect(root).to_have_css('color-scheme', 'light')
    view.click()
    expect(moon).to_be_visible()
    moon.press('Space')
    expect(root).to_have_css('color-scheme', 'dark')
    page.emulate_media(color_scheme='light')
    expect(root).to_have_css('color-scheme', 'dark')
    expect(sun).to_be_visible()


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
    moon = page.get_by_role('button', name='Switch to dark mode', exact=True)
    sun = page.get_by_role('button', name='Switch to light mode', exact=True)
    moon.click()
    expect(root).to_have_css('background-color', 'rgb(32, 31, 34)')
    expect(root).to_have_css('color', 'rgb(232, 214, 184)')
    page.goto(f'{base}/books/{book_id}/draft')
    expect(root).to_have_css('color-scheme', 'dark')
    expect(sun).to_be_hidden()
    page.locator('.reader-options summary').click()
    expect(sun).to_be_visible()
    page.get_by_role('button', name='Glossary', exact=True).click()
    glossary = page.get_by_role('dialog', name='Glossary')
    expect(glossary).to_have_css('background-color', 'rgb(32, 31, 34)')
    glossary.get_by_role('button', name='Close').click()
    expect(page.get_by_role('link', name='Review', exact=True)).to_have_count(0)
    page.goto(f'{base}/books/{book_id}/review')
    expect(sun).to_be_visible()
    page.get_by_role('button', name='paste English', exact=True).click()
    expect(page.locator('#editor')).to_have_css('background-color', 'rgb(25, 24, 28)')
    expect(page.get_by_role('textbox')).to_have_css('color', 'rgb(232, 214, 184)')
    page.get_by_role('button', name='cancel', exact=True).click()
    sun.click()
    expect(root).to_have_css('color-scheme', 'light')
    page.get_by_role('link', name='Library').click()
    expect(moon).to_be_visible()


def test_draft_walkthrough_spotlights_each_step_and_can_be_reopened(reader):
    page = reader['page']
    walkthrough = page.get_by_role('complementary', name='Draft walkthrough')
    spotlight = page.locator('#draft-help-spotlight')
    expect(walkthrough).to_be_hidden()
    page.locator('.reader-options summary').click()
    page.get_by_role('button', name='Walkthrough', exact=True).click()
    expect(walkthrough.get_by_role('heading', name='Choose a chapter')).to_be_visible()
    expect(spotlight).not_to_have_css('box-shadow', 'none')
    walkthrough.get_by_role('button', name='Next').click()
    expect(walkthrough.get_by_role('heading', name='Write your translation')).to_be_visible()
    walkthrough.get_by_role('button', name='Back').click()
    expect(walkthrough.get_by_role('heading', name='Choose a chapter')).to_be_visible()
    walkthrough.get_by_role('button', name='Skip').click()
    expect(walkthrough).to_be_hidden()

    page.reload()
    if reader['mode'] == 'hosted':
        saved(reader)
    expect(walkthrough).to_be_hidden()
    page.locator('.reader-options summary').click()
    page.get_by_role('button', name='Walkthrough', exact=True).click()
    page.set_viewport_size({'width': 410, 'height': 720})
    steps = [
        ('Choose a chapter', '#sel'),
        ('Write your translation', '#ta'),
        ('Use italics', '#italic'),
        ('Link Chinese and English', '#sy'),
        ('Leave a comment', '#ta'),
        ('Export to Word', '#exports-trigger'),
    ]
    for index, (heading, target) in enumerate(steps):
        expect(walkthrough.get_by_role('heading')).to_have_text(heading)
        target_box = page.locator(target).bounding_box()
        spot_box = spotlight.bounding_box()
        assert spot_box['x'] <= target_box['x'] < spot_box['x'] + spot_box['width'] <= 410
        assert spot_box['y'] <= target_box['y'] < spot_box['y'] + spot_box['height'] <= 720
        if index < len(steps) - 1:
            walkthrough.get_by_role('button', name='Next').click()
    walkthrough.get_by_role('button', name='Start translating').click()
    expect(walkthrough).to_be_hidden()
    expect(page.get_by_role('textbox', name='Translation')).to_be_focused()


def test_walkthrough_comment_step_opens_the_real_comment_composer(reader):
    page = reader['page']
    walkthrough = page.get_by_role('complementary', name='Draft walkthrough')
    page.locator('.reader-options summary').click()
    page.get_by_role('button', name='Walkthrough', exact=True).click()
    for _ in range(4):
        walkthrough.get_by_role('button', name='Next').click()
    expect(walkthrough.get_by_role('heading')).to_have_text('Leave a comment')
    add_comment = page.get_by_role('button', name='Add comment', exact=True)
    expect(add_comment).to_be_hidden()
    editor = page.get_by_role('textbox', name='Translation', exact=True)
    editor.click(position={'x': 40, 'y': 40})
    editor.fill('Try a real comment.')
    editor.press('Home')
    editor.press('Shift+End')
    expect(walkthrough).to_be_visible()
    expect(add_comment).to_be_visible()
    spot = page.locator('#draft-help-spotlight').bounding_box()
    button = add_comment.bounding_box()
    assert spot['x'] <= button['x'] and button['x'] + button['width'] <= spot['x'] + spot['width']
    assert spot['y'] <= button['y'] and button['y'] + button['height'] <= spot['y'] + spot['height']
    add_comment.click()
    expect(walkthrough).to_be_hidden()
    composer = page.get_by_role('dialog', name='Add comment', exact=True)
    expect(composer.locator('blockquote')).to_have_text('Try a real comment.')
    composer.get_by_label('Comment', exact=True).fill('A note from the walkthrough.')
    composer.get_by_role('button', name='save comment').click()
    expect(page.locator('#comment-marks span').first).to_be_visible()


def test_walkthrough_auto_opens_only_for_first_added_manuscript(page, reader_environment):
    base = reader_environment['base']
    walkthrough = page.get_by_role('complementary', name='Draft walkthrough')
    for name, show_tour in [('First upload', True), ('Second upload', False)]:
        page.goto(base)
        page.get_by_role('button', name='Add manuscript').click()
        page.locator('#manuscript').set_input_files({
            'name': name + '.txt', 'mimeType': 'text/plain', 'buffer': '第一章 测试\n正文'.encode(),
        })
        page.get_by_role('button', name='Preview manuscript').click()
        page.get_by_role('button', name='Add to library', exact=True).click()
        card = page.locator('.book-card').filter(has=page.get_by_role('heading', name=name, exact=True))
        card.get_by_role('link').click()
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        if show_tour:
            expect(walkthrough).to_be_visible()
        else:
            expect(walkthrough).to_be_hidden()
        page.reload()
        expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
        expect(walkthrough).to_be_hidden()


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
    expect(page.locator('#verdict')).to_have_text('3 matches in 3 source paragraphs across 2 chapters.')
    expect(page.locator('#hits')).to_contain_text('后来')
    dismiss(reader, '#find')
    expect(page.locator('#find')).not_to_have_class('on')


def test_exports_preserve_source_and_draft(reader):
    page = reader['page']
    page.set_viewport_size({'width': 410, 'height': 720})
    page.emulate_media(color_scheme='dark')
    page.locator('#ta').fill(DRAFT)
    saved(reader)
    for minutes in ('45', '70'):
        page.get_by_role('button', name='stats', exact=True).click()
        page.get_by_label('Current chapter time (minutes)').fill(minutes)
        page.get_by_role('button', name='Save time').click()
        dismiss(reader, '#stats')
        saved(reader)
    page.reload()
    page.get_by_role('button', name='stats', exact=True).click()
    expect(page.get_by_label('Current chapter time (minutes)')).to_have_value('70')
    expect(page.locator('#cards')).to_contain_text('1h 10m')
    dismiss(reader, '#stats')
    expect(page.get_by_role('button', name='Word', exact=True)).to_be_hidden()
    expect(page.get_by_role('button', name='Download recovery backup')).to_be_hidden()
    menu = open_exports(page)
    panel = menu.locator(':scope > div')
    expect(panel).to_have_css('background-color', 'rgb(32, 31, 34)')
    bounds = panel.bounding_box()
    assert 0 <= bounds['x'] < bounds['x'] + bounds['width'] <= 410
    assert 0 <= bounds['y'] < bounds['y'] + bounds['height'] <= 720
    expect(menu.get_by_label('Word comment author')).to_have_count(0)
    expect(menu.get_by_role('button', name='Copy for Google Docs')).to_be_visible()
    with page.expect_download() as event:
        menu.get_by_role('button', name='Draft text backup', exact=True).click()
    text = Path(event.value.path()).read_text(encoding='utf-8')
    assert text.count('Chapter 1') == 1
    assert 'Third paragraph.' in text
    with page.expect_download() as event:
        menu.get_by_role('button', name='Full project backup', exact=True).click()
    payload = json.loads(Path(event.value.path()).read_text(encoding='utf-8'))
    assert payload['version'] == 1
    entry = payload['books'][0]
    assert entry['state']['drafts']['1'] == DRAFT
    assert entry['state']['times'] == {'1': 4200000}
    assert entry['book']['chapters'][1]['paras'][0] == '后来月光'
    page.keyboard.press('Escape')
    expect(menu.get_by_role('button', name='Word', exact=True)).to_be_hidden()
    expect(page.locator('#exports-trigger')).to_be_focused()


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
