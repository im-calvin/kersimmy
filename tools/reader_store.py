"""SQLite persistence and consistent snapshots for the original reader."""
import base64
import contextlib
import datetime as dt
import json
import logging
import re
from pathlib import Path
import sqlite3
import threading
import uuid

log = logging.getLogger('kersimmy')


class Store:
    def __init__(self, directory, interval=300, keep=96, *, portable_json=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'reader.sqlite3'
        self.backups = self.directory / 'backups'
        self.backups.mkdir(exist_ok=True)
        self.interval, self.keep = max(1, interval), max(2, keep)
        self.portable_json = portable_json
        self.backup_lock = threading.Lock()
        self.last_error = None
        self.changes = 0
        self.changes_lock = threading.Lock()
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY, book TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0)')
        self.backup()

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    def backup(self):
        with self.backup_lock:
            name = 'reader-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3'
            temp = self.backups / (name + '.tmp')
            portable = temp.with_name(name.removesuffix('.sqlite3') + '.json')
            portable_temp = portable.with_suffix('.json.tmp')
            try:
                with self.connect() as source:
                    with sqlite3.connect(temp) as target:
                        source.backup(target)
                        if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                            raise RuntimeError('Backup integrity check failed')
                        if self.portable_json:
                            with portable_temp.open('w', encoding='utf-8') as output:
                                json.dump({
                                    'format': 'translation-reader',
                                    'version': 1,
                                    'books': self.read_entries(target),
                                }, output, ensure_ascii=True)
                temp.replace(self.backups / name)
                for old in sorted(self.backups.glob('reader-*.sqlite3'), reverse=True)[self.keep:]:
                    old.unlink()
                if self.portable_json:
                    portable_temp.replace(portable)
                    for old in sorted(self.backups.glob('reader-*.json'), reverse=True)[self.keep:]:
                        old.unlink()
                self.last_error = None
                return name
            except Exception as error:
                temp.unlink(missing_ok=True)
                portable_temp.unlink(missing_ok=True)
                self.last_error = str(error)
                raise

    def changed(self):
        with self.changes_lock:
            self.changes += 1

    def run_backups(self, stop):
        while not stop.wait(self.interval):
            with self.changes_lock:
                changes, self.changes = self.changes, 0
            try:
                name = self.backup()
            except Exception as error:
                with self.changes_lock:
                    self.changes += changes
                log.error('Automatic snapshot failed: %s', error)
                continue
            if changes:
                log.info('Automatic snapshot %s (%d change%s since the last one)', name, changes, '' if changes == 1 else 's')
            else:
                log.debug('Automatic snapshot %s (no changes)', name)

    def entries(self):
        with self.connect() as db:
            return self.read_entries(db)

    @staticmethod
    def read_entries(db):
        return [
            {'book': json.loads(book), 'state': json.loads(state)}
            for book, state in db.execute('SELECT book,state FROM books ORDER BY rowid')
        ]

    def import_entries(self, entries):
        if not isinstance(entries, list) or not entries:
            raise ValueError('No books to import')
        records = []
        for entry in entries:
            book, state = entry['book'], entry.get('state') or {'drafts':{}}
            validate(book, state)
            book = dict(book, id=str(uuid.uuid4()), createdAt=dt.datetime.now(dt.timezone.utc).isoformat())
            state = dict(state, id=book['id'], revision=0)
            records.append((book,state))
        with self.connect() as db:
            for book,state in records:
                db.execute('INSERT INTO books(id,book,state) VALUES(?,?,?)', (book['id'],json.dumps(book),json.dumps(state)))
        return [book for book,state in records]


def validate(book, state):
    if not isinstance(book, dict) or not isinstance(book.get('title'), str) or not book['title'].strip():
        raise ValueError('Book title is required')
    chapters = book.get('chapters')
    if not isinstance(chapters, list) or not chapters:
        raise ValueError('Chapters are required')
    validate_image(book.get('illustration'))
    validate_icon(book.get('icon'))
    numbers = set()
    displayed = set()
    for chapter in chapters:
        no = chapter.get('no')
        if type(no) is not int or no < 0 or no in numbers or not isinstance(chapter.get('title'), str):
            raise ValueError('Invalid chapter number or title')
        if not isinstance(chapter.get('paras'), list) or any(not isinstance(p,str) for p in chapter['paras']):
            raise ValueError('Invalid paragraphs')
        volume = chapter.get('volume', '')
        number = chapter.get('number', no)
        if not isinstance(volume, str) or len(volume) > 200 or (volume and not volume.strip()):
            raise ValueError('Invalid volume name')
        if type(number) is not int or not 0 <= number <= 9007199254740991:
            raise ValueError('Invalid displayed chapter number')
        if (volume, number) in displayed:
            raise ValueError('Duplicate chapter numbers within a volume')
        displayed.add((volume, number))
        numbers.add(no)
    if not isinstance(state,dict) or not isinstance(state.get('drafts'),dict):
        raise ValueError('Invalid draft state')
    for field in ('drafts','reviewEnglish'):
        values = state.get(field,{})
        if not isinstance(values,dict) or any(str(c) not in {str(n) for n in numbers} or not isinstance(t,str) for c,t in values.items()):
            raise ValueError('Draft chapters do not match the book')


    alignment_groups = state.get('alignmentGroups', {})
    if not isinstance(alignment_groups, dict):
        raise ValueError('Invalid paragraph alignment groups')
    lengths = {str(chapter['no']): len(chapter['paras']) for chapter in chapters}
    for chapter, groups in alignment_groups.items():
        if chapter not in lengths or not isinstance(groups, dict):
            raise ValueError('Paragraph alignment groups do not match the book')
        for english, group in groups.items():
            if (not re.fullmatch(r'[1-9][0-9]{0,14}', english)
                    or not isinstance(group, list) or len(group) != 2
                    or any(type(number) is not int for number in group)
                    or not 1 <= group[0] <= group[1] <= lengths[chapter]):
                raise ValueError('Invalid paragraph alignment range')

    italics = state.get('italics', {})
    if not isinstance(italics, dict):
        raise ValueError('Invalid italic formatting')
    for chapter, ranges in italics.items():
        if chapter not in {str(n) for n in numbers} or not isinstance(ranges, list):
            raise ValueError('Italic formatting does not match the book')
        length = len(state['drafts'].get(chapter, '').encode('utf-16-le', errors='surrogatepass')) // 2
        previous_end = 0
        for span in ranges:
            if (not isinstance(span, dict) or type(span.get('start')) is not int
                    or type(span.get('end')) is not int
                    or not previous_end <= span['start'] < span['end'] <= length):
                raise ValueError('Invalid italic range')
            previous_end = span['end']

    comments = state.get('comments', {})
    if not isinstance(comments, dict):
        raise ValueError('Invalid comments')
    ids = set()
    for chapter, notes in comments.items():
        if chapter not in {str(n) for n in numbers} or not isinstance(notes, list):
            raise ValueError('Comments do not match the book')
        for note in notes:
            if (not isinstance(note, dict) or not isinstance(note.get('id'), str)
                    or not note['id'] or note['id'] in ids
                    or type(note.get('start')) is not int or type(note.get('end')) is not int
                    or not 0 <= note['start'] <= note['end'] <= 9007199254740991
                    or not isinstance(note.get('quote'), str)
                    or not isinstance(note.get('text'), str) or not note['text'].strip()
                    or len(note['text']) > 20000
                    or type(note.get('detached', False)) is not bool):
                raise ValueError('Invalid comment')
            replies = note.get('replies', [])
            if (not isinstance(replies, list) or len(replies) > 100
                    or any(not isinstance(reply, str) or not reply.strip() or len(reply) > 20000 for reply in replies)
                    or type(note.get('resolved', False)) is not bool):
                raise ValueError('Invalid comment thread')
            ids.add(note['id'])



def validate_icon(icon):
    if icon is None:
        return None
    prefix = 'data:image/png;base64,'
    if not isinstance(icon, str) or not icon.startswith(prefix) or len(icon) > 100_000:
        raise ValueError('Invalid book icon.')
    raw = base64.b64decode(icon[len(prefix):], validate=True)
    if (len(raw) < 33 or raw[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
            or not all(1 <= int.from_bytes(raw[i:i+4], 'big') <= 128 for i in (16, 20))):
        raise ValueError('Invalid book icon.')
    return icon


def validate_image(image):
    if image is None: return None
    if not isinstance(image,dict) or not isinstance(image.get('name'),str) or not isinstance(image.get('dataUrl'),str) or len(image['dataUrl'])>7_000_000 or not image['dataUrl'].startswith('data:image/gif;base64,'):
        raise ValueError('Choose a GIF smaller than 5 MB.')
    raw=base64.b64decode(image['dataUrl'].split(',',1)[1],validate=True)
    if len(raw)<13 or len(raw)>5*1024*1024 or raw[:6] not in (b'GIF87a',b'GIF89a'):
        raise ValueError('Invalid GIF image.')
    width,height=int.from_bytes(raw[6:8],'little'),int.from_bytes(raw[8:10],'little')
    if not width or not height or width*height>16_000_000: raise ValueError('GIF dimensions exceed 16 megapixels.')
    return {'name':image['name'][:200],'dataUrl':image['dataUrl']}
