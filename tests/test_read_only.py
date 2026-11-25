"""Read-only mode is a per-browser library switch that prevents hosted writes."""
from playwright.sync_api import expect


def hosted_book(page, base, chapters, drafts):
    response = page.request.post(base + '/api/import', data={'books': [{
        'book': {'title': 'Read-only book', 'chapters': chapters},
        'state': {'drafts': drafts},
    }]})
    assert response.status == 201, response.text()
    return response.json()[0]['id']


def test_read_only_library_and_draft(page, reader_environment):
    base = reader_environment['base']
    book_id = hosted_book(page, base, reader_environment['chapters'], {'1': 'Existing translation.'})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    page.goto(base + '/')
    switch = page.get_by_role('switch', name='Read-only')
    expect(switch).not_to_be_checked()
    switch.check()
    expect(page.locator('#message')).to_contain_text('Read-only is on')
    expect(page.locator('#add-book')).to_be_hidden()
    expect(page.locator('#restore')).to_be_hidden()
    card = page.locator('.book-card').filter(has_text='Read-only book')
    expect(card.get_by_role('button', name='Settings')).to_be_hidden()
    expect(card.locator('.book-link')).to_have_text('Read')

    writes = []
    page.on('request', lambda request: writes.append(request.url) if request.method != 'GET' else None)
    page.goto(f'{base}/books/{book_id}/draft')
    editor = page.locator('#ta')
    expect(editor).to_have_js_property('value', 'Existing translation.')
    expect(editor).to_have_attribute('contenteditable', 'false')
    expect(page.locator('header')).to_have_attribute('data-save-state', 'readonly')
    expect(page.locator('#reader-server-status')).to_contain_text('Read-only')
    assert page.title() == 'Read-only book · Read-only'

    editor.click()
    page.keyboard.type('Accidental typing')
    page.keyboard.press('Meta+a')
    page.keyboard.press('Meta+i')
    expect(editor).to_have_js_property('value', 'Existing translation.')
    expect(page.locator('#comment-add')).to_be_hidden()
    expect(page.locator('#choose-gif')).to_be_hidden()

    page.locator('#sel').select_option('2')
    page.wait_for_timeout(2500)
    assert writes == []
    state = page.request.get(f'{base}/api/books/{book_id}/state').json()
    assert state['revision'] == 0
    assert state['drafts'] == {'1': 'Existing translation.'}

    # Someone else's save refreshes the page without losing this reader's place.
    remote = page.request.put(f'{base}/api/books/{book_id}/state', data={
        'expectedRevision': 0, 'state': dict(state, drafts={'1': 'Existing translation.', '2': 'Edited elsewhere.'}),
    })
    assert remote.ok, remote.text()
    expect(editor).to_have_js_property('value', 'Edited elsewhere.', timeout=10000)
    expect(page.locator('#sel')).to_have_value('2')
    assert writes == []

    page.goto(base + '/')
    switch.uncheck()
    expect(page.locator('#add-book')).to_be_visible()
    page.goto(f'{base}/books/{book_id}/draft')
    expect(page.locator('#ta')).to_have_attribute('contenteditable', 'true')
    expect(page.locator('#reader-server-status')).to_have_text('Synced to server')
    assert not errors, errors
