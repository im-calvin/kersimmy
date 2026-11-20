"""Whole-book grep shows earlier/current context and translated vocabulary too."""
from playwright.sync_api import expect

from test_reader_behavior import saved


def test_source_search_shows_all_chapters_and_retains_future_mode(reader):
    page = reader['page']
    page.locator('#sel').select_option('2')
    page.get_by_role('button', name='find', exact=True).click()
    page.locator('#q').fill('月光')
    expect(page.locator('#verdict')).to_contain_text('Never appears again')
    expect(page.locator('#hits')).to_be_empty()
    page.get_by_role('combobox', name='Search scope', exact=True).select_option('book')
    expect(page.locator('#verdict')).to_have_text('Found in 3 paragraphs across 2 chapters.')
    expect(page.locator('#hits')).to_contain_text('第一段月光')
    expect(page.locator('#hits')).to_contain_text('第二段月光')
    expect(page.locator('#hits')).to_contain_text('后来月光')


def test_translation_search_uses_drafts_without_changing_them(reader):
    page = reader['page']
    page.locator('#ta').fill('Chapter 1\nMoonlight over the lake.\nMoonlight again.')
    saved(reader)
    page.locator('#sel').select_option('2')
    page.locator('#ta').fill('The lake <script> & stars.')
    saved(reader)
    page.get_by_role('button', name='find', exact=True).click()
    page.get_by_role('combobox', name='Search text', exact=True).select_option('translation')
    page.get_by_role('combobox', name='Search scope', exact=True).select_option('book')
    page.locator('#q').fill('lake')
    expect(page.locator('#verdict')).to_have_text('Found in 2 paragraphs across 2 chapters.')
    expect(page.locator('#hits')).to_contain_text('Moonlight over the lake.')
    expect(page.locator('#hits')).to_contain_text('The lake <script> & stars.')
    assert page.locator('#hits script').count() == 0
    page.locator('#q').fill('Moonlight')
    expect(page.locator('#verdict')).to_have_text('Found in 2 paragraphs across 1 chapter.')
    page.locator('#find').get_by_role('button', name='close', exact=True).click()
    expect(page.locator('#ta')).to_have_js_property('value', 'The lake <script> & stars.')


def test_all_vocabulary_context_can_be_expanded(reader):
    page = reader['page']
    page.locator('#ta').fill('\n'.join(f'Moonlight passage {n}.' for n in range(85)))
    saved(reader)
    page.get_by_role('button', name='find', exact=True).click()
    page.get_by_role('combobox', name='Search text', exact=True).select_option('translation')
    page.get_by_role('combobox', name='Search scope', exact=True).select_option('book')
    page.locator('#q').fill('Moonlight')
    expect(page.locator('#hits .h')).to_have_count(40)
    page.get_by_role('button', name='show more', exact=True).click()
    expect(page.locator('#hits .h')).to_have_count(80)
    page.get_by_role('button', name='show more', exact=True).click()
    expect(page.locator('#hits .h')).to_have_count(85)
    expect(page.locator('#hits')).to_contain_text('Moonlight passage 84.')
