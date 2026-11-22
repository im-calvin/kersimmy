"""Check a previous release, the working tree, and rollback on disposable data."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import time
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = 'The moon shines.'
PENDING = ORIGINAL + ' Pending.'


def build_site(repo, site):
    subprocess.run([
        sys.executable, str(repo / 'tools/build_web.py'), '--without-current',
        '--output', str(site),
    ], check=True)


@contextmanager
def serve(repo, site, data, port, version, log):
    base = f'http://127.0.0.1:{port}'
    with log.open('w+') as output:
        process = subprocess.Popen([
            sys.executable, str(repo / 'tools/reader_server.py'),
            '--port', str(port), '--site', str(site), '--data', str(data),
        ], stdout=output, stderr=subprocess.STDOUT,
            env={**os.environ, 'READER_RELEASE': version})
        try:
            for _ in range(100):
                if process.poll() is not None:
                    break
                try:
                    with urlopen(base + '/api/status', timeout=0.3):
                        break
                except (URLError, TimeoutError):
                    time.sleep(0.05)
            else:
                raise RuntimeError('Reader did not start in time')
            if process.poll() is not None:
                raise RuntimeError('Reader exited during startup')
            yield
        except Exception:
            output.seek(0)
            print(output.read(), file=sys.stderr)
            raise
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def check_release(previous_ref):
    with TemporaryDirectory(prefix='kersimmy-compatibility-') as directory:
        scratch = Path(directory)
        previous = scratch / 'previous'
        previous.mkdir()
        archive = subprocess.check_output(
            ['git', 'archive', '--format=tar', previous_ref, 'tools', 'web'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as packed:
            packed.extractall(previous, filter='data')
        old_site, new_site = scratch / 'old-site', scratch / 'new-site'
        build_site(previous, old_site)
        build_site(ROOT, new_site)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        data, log = scratch / 'db', scratch / 'reader.log'
        old_backup = scratch / 'previous-book-backup.json'
        state = {
            'drafts': {'2': ORIGINAL, '3': 'Second draft.'},
            'current': 2,
            'italics': {'2': [{'start': 4, 'end': 8}]},
            'comments': {'2': [{'id': 'note', 'start': 4, 'end': 8,
                                'quote': 'moon', 'text': 'Preserve this note.'}]},
            'alignmentGroups': {'2': {'1': [1, 2]}},
            'times': {'2': 120000},
            'reviewEnglish': {'3': 'Separate review text.'},
            'commentAuthor': 'Original Author',
        }
        book = {'title': 'Upgrade sample', 'chapters': [
            {'no': 2, 'title': '月光', 'volume': '第一卷', 'paras': ['月光。', '夜色。']},
            {'no': 3, 'title': '天明', 'volume': '第一卷', 'paras': ['天亮了。']},
        ]}
        with sync_playwright() as playwright, playwright.chromium.launch() as browser:
            client = browser.new_context()
            with serve(previous, old_site, data, port, '', log):
                created = client.request.post(base + '/api/import', data={
                    'books': [{'book': book, 'state': state}],
                })
                assert created.ok, created.text()
                book_id = created.json()[0]['id']
                endpoint = f'{base}/api/books/{book_id}'
                bookmark = f'{base}/books/{book_id}/draft'
                old_backup.write_bytes(client.request.get(base + '/api/export').body())
                assert json.loads(old_backup.read_text())['version'] == 1
                reader = client.new_page()
                reader.goto(bookmark)
                expect(reader.locator('#ta em')).to_have_text('moon')
                client.set_offline(True)
                editor = reader.locator('#ta')
                editor.evaluate('el => { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }')
                editor.press_sequentially(' Pending.')
                expect(editor).to_have_js_property('value', PENDING)
                expect(reader.locator('#reader-server-status')).to_contain_text('Connection lost')
                pending_state = reader.evaluate(
                    "id => JSON.parse(localStorage.getItem('original-reader-pending:' + id)).state",
                    book_id,
                )
                assert pending_state['times']['2'] >= state['times']['2']
                reader.close()

            client.set_offline(False)
            with serve(ROOT, new_site, data, port, 'a' * 40, log):
                version = client.request.get(base + '/api/status').json()['version']
                reader = client.new_page()
                reader.goto(bookmark)
                expect(reader.get_by_text(f'v{version}', exact=True)).to_be_visible()
                expect(reader.locator('#ta')).to_have_js_property('value', PENDING)
                expect(reader.locator('#reader-server-status')).to_have_text('Synced to server')
                reader.locator('#reader-save-menu summary').click()
                expect(reader.get_by_text('Available offline', exact=True)).to_be_visible()
                reader.locator('#reader-save-menu summary').click()
                expect(reader.locator('#ta em')).to_have_text('moon')
                upgraded = client.request.get(endpoint + '/bundle').json()
                assert upgraded['book']['chapters'] == book['chapters']
                for key in state:
                    assert upgraded['state'][key] == pending_state[key], key

                library = client.new_page()
                library.goto(base)
                expect(library.get_by_text(f'v{version}', exact=True)).to_be_visible()
                library.locator('#restore-file').set_input_files(str(old_backup))
                expect(library.locator('#message')).to_contain_text('Restored 1 book')
                library.close()
                reader.bring_to_front()

            with reader.expect_event('framenavigated', timeout=15000) as navigation:
                with serve(ROOT, new_site, data, port, 'b' * 40, log):
                    assert navigation.value.url == bookmark
                    expect(reader.locator('#reader-server-status')).to_have_text('Synced to server')
                    expect(reader.locator('#ta')).to_have_js_property('value', PENDING)
                    assert client.request.get(base + '/api/status').json()['release'] == 'b' * 40
                    editor = reader.locator('#ta')
                    editor.evaluate('el => { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }')
                    start = datetime.now(timezone.utc)
                    reader.clock.set_fixed_time(start)
                    editor.press_sequentially('!')
                    reader.clock.set_fixed_time(start + timedelta(minutes=1))
                    editor.press('Backspace')
                    expect(editor).to_have_js_property('value', PENDING)
                    expect(reader.locator('#reader-server-status')).to_have_text('Synced to server')
                    updated_times = {'2': pending_state['times']['2'] + 60000}
                    assert client.request.get(endpoint + '/state').json()['times'] == updated_times

            with serve(previous, old_site, data, port, '', log):
                reader.reload()
                expect(reader.locator('#ta')).to_have_js_property('value', PENDING)
                expect(reader.locator('#ta em')).to_have_text('moon')
                rolled_back = client.request.get(endpoint + '/bundle').json()
                assert rolled_back['book']['chapters'] == book['chapters']
                assert rolled_back['state']['times'] == updated_times
                for key in ('comments', 'alignmentGroups', 'reviewEnglish', 'commentAuthor'):
                    assert rolled_back['state'][key] == state[key], key
        print(f'Passed {previous_ref} → working tree → new release → {previous_ref}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-ref', required=True, help='Git tag or commit for the deployed release')
    check_release(parser.parse_args().previous_ref)
