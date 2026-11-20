"""Disposable local output and hosted storage; never use the real manuscript/DB."""
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_web import build
from reader_server import Handler
from reader_store import Store
from tlconfig import load_config, parse_source


@pytest.fixture(scope='session')
def reader_environment(tmp_path_factory):
    directory = tmp_path_factory.mktemp('readers')
    source = directory / 'source.txt'
    source.write_text('第一章 开始\n第一段月光\n第二段月光\n第三段\n第二章 后来\n后来月光\n最后一段', encoding='utf-8')
    config = directory / 'config.json'
    config.write_text(json.dumps({
        'project': 'Test manuscript', 'slug': 'test', 'source': str(source),
        'encoding': 'utf-8', 'paragraph_mode': 'line',
        'storage_prefix': 'playwright-test', 'illustration': '',
    }), encoding='utf-8')
    local = directory / 'local'
    local.mkdir()
    # Exercise the real CLI entry points without regenerating root output.
    import os
    subprocess.run(['bash', str(ROOT / 'tools/regenerate.sh'), 'all'],
                   env=dict(os.environ, CONFIG=str(config), OUTDIR=str(local)), check=True,
                   capture_output=True, text=True)
    site = build(directory / 'site', include_current=False)
    store = Store(directory / 'data')
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, store=store, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield {'local': local, 'base': f'http://127.0.0.1:{server.server_port}',
               'chapters': parse_source(load_config(str(config)))}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture(params=['local', 'hosted'])
def reader(request, page, reader_environment):
    env = reader_environment
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    if request.param == 'local':
        urls = {kind: (env['local'] / name).as_uri()
                for kind, name in [('draft', 'draft.html'), ('review', 'sync.html')]}
    else:
        response = page.request.post(env['base'] + '/api/import', data={'books': [{
            'book': {'title': 'Test manuscript', 'chapters': env['chapters']},
            'state': {'drafts': {}},
        }]})
        assert response.status == 201, response.text()
        book_id = response.json()[0]['id']
        urls = {kind: f"{env['base']}/books/{book_id}/{kind}" for kind in ('draft', 'review')}
    page.goto(urls['draft'])
    yield {'page': page, 'urls': urls, 'mode': request.param}
    assert not errors, errors
