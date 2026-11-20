from playwright.sync_api import expect


def test_user_glossary_shows_term_details_on_hover_and_removes_deleted_marks(page, reader_environment):
    base = reader_environment['base']
    response = page.request.post(base + '/api/import', data={'books': [
        {'book': {'title': 'Glossary test', 'chapters': reader_environment['chapters']}}
    ]})
    assert response.status == 201
    page.goto(base + '/books/' + response.json()[0]['id'] + '/draft')
    page.get_by_role('button', name='Glossary', exact=True).click()
    page.get_by_role('button', name='Add term', exact=True).click()
    page.get_by_role('textbox', name='Chinese for term 1').fill('月光')
    page.get_by_role('textbox', name='English for term 1').fill('moonlight')
    page.get_by_role('textbox', name='Usage note for term 1').fill('Keep lowercase')
    page.get_by_role('button', name='Close', exact=True).filter(visible=True).click()
    mark = page.locator('#cn .glossary-term').first
    tip = page.get_by_role('tooltip')
    expect(mark).to_have_css('text-decoration-line', 'underline')
    expect(tip).to_be_hidden()
    mark.hover()
    expect(tip).to_be_visible()
    expect(tip.locator('strong')).to_have_text('moonlight')
    expect(tip.locator('p')).to_have_text('Keep lowercase')
    expect(page.get_by_role('dialog', name='Glossary')).to_be_hidden()
    page.locator('#cn h2').hover()
    expect(tip).to_be_hidden()
    page.reload()
    mark.focus()
    expect(tip).to_be_visible()
    expect(tip).to_contain_text('Keep lowercase')
    page.keyboard.press('Escape')
    expect(tip).to_be_hidden()
    page.get_by_role('button', name='Glossary', exact=True).click()
    page.get_by_role('button', name='Remove term 1', exact=True).click()
    page.get_by_role('button', name='Close', exact=True).filter(visible=True).click()
    expect(page.locator('#cn .glossary-term')).to_have_count(0)
    expect(tip).to_be_hidden()
