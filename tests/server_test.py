import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest

spec = importlib.util.spec_from_file_location('reader_store', Path(__file__).resolve().parents[1] / 'tools/reader_store.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class StorageTests(unittest.TestCase):
    def test_portable_snapshot_keeps_comments_and_offsets(self):
        with tempfile.TemporaryDirectory() as temp:
            store = app.Store(temp, keep=2, portable_json=True)
            state = {
                'drafts': {'1': 'Moon'},
                'offsets': {'1': 1},
                'comments': {'1': [{'id': 'note', 'start': 0, 'end': 4,
                                    'quote': 'Moon', 'text': 'Check term', 'detached': False}]},
                'commentAuthor': 'Reviewer',
            }
            book = {'title': 'Test', 'chapters': [{'no': 1, 'title': '', 'paras': ['月']}]}
            store.import_entries([{'book': book, 'state': state}])
            store.backup()
            name = store.backup()
            files = sorted(store.backups.glob('reader-*.json'))
            self.assertEqual(len(files), 2)
            self.assertEqual(files[-1].stem, Path(name).stem)
            payload = json.loads(files[-1].read_text())
            self.assertEqual(payload['format'], 'translation-reader')
            self.assertEqual(payload['version'], 1)
            copied = store.import_entries(payload['books'])[0]
            restored = next(entry['state'] for entry in store.entries()
                            if entry['book']['id'] == copied['id'])
            for field, expected in state.items():
                self.assertEqual(restored[field], expected)

    def test_persistence_backup_retention_and_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            store = app.Store(temp, interval=1, keep=2)
            book = store.import_entries([{'book':{'title':'Test','chapters':[{'no':1,'title':'One','paras':['正文']}]},'state':{'drafts':{'1':'English'},'times':{'1':500}}}])[0]
            reopened = app.Store(temp, interval=1, keep=2)
            self.assertEqual(reopened.entries()[0]['state']['drafts']['1'],'English')
            stop = threading.Event()
            worker = threading.Thread(target=store.run_backups,args=(stop,))
            worker.start()
            time.sleep(1.2)
            stop.set(); worker.join()
            store.backup()
            files = list(store.backups.glob('*.sqlite3'))
            self.assertEqual(len(files),2)
            with sqlite3.connect(sorted(files)[-1]) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(json.loads(db.execute('SELECT book FROM books').fetchone()[0])['id'],book['id'])

    def test_comments_persist_and_invalid_import_is_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            store = app.Store(temp)
            book = {'title': 'Notes', 'chapters': [{'no': 1, 'title': 'One', 'paras': ['正文']}]}
            note = {'id': 'note-1', 'start': 0, 'end': 5, 'quote': 'Hello', 'text': 'Check wording.', 'detached': False}
            state = {'drafts': {'1': 'Hello world.'}, 'comments': {'1': [note]}}
            store.import_entries([{'book': book, 'state': state}])
            self.assertEqual(app.Store(temp).entries()[0]['state']['comments'], state['comments'])
            invalid_states = [
                {'drafts': {}, 'comments': []},
                {'drafts': {}, 'comments': {'99': [note]}},
                {'drafts': {}, 'comments': {'1': [dict(note, start=-1)]}},
                {'drafts': {}, 'comments': {'1': [dict(note, end=True)]}},
                {'drafts': {}, 'comments': {'1': [dict(note, text=' ')]}},
                {'drafts': {}, 'comments': {'1': [note, note]}},
            ]
            for invalid in invalid_states:
                with self.subTest(state=invalid), self.assertRaises(ValueError):
                    store.import_entries([{'book': book, 'state': state}, {'book': book, 'state': invalid}])
                self.assertEqual(len(store.entries()), 1)

    def test_italic_ranges_use_browser_offsets_and_reject_invalid_data(self):
        with tempfile.TemporaryDirectory() as temp:
            store = app.Store(temp)
            book = {'title': 'Italic', 'chapters': [{'no': 1, 'title': 'One', 'paras': ['正文']}]}
            # JS selection offsets count UTF-16 code units, including emoji pairs.
            state = {'drafts': {'1': 'A 🌙'}, 'italics': {'1': [{'start': 2, 'end': 4}]}}
            store.import_entries([{'book': book, 'state': state}])
            self.assertEqual(app.Store(temp).entries()[0]['state']['italics'], state['italics'])
            for ranges in ([{'start': -1, 'end': 1}], [{'start': 2, 'end': 5}],
                           [{'start': True, 'end': 4}], [{'start': 2, 'end': 2}],
                           [{'start': 2, 'end': 4}, {'start': 1, 'end': 3}]):
                with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                    store.import_entries([{'book': book, 'state': dict(state, italics={'1': ranges})}])
            self.assertEqual(len(store.entries()), 1)

    def test_volume_metadata_survives_snapshots_and_rejects_ambiguous_numbers(self):
        with tempfile.TemporaryDirectory() as temp:
            store = app.Store(temp)
            chapters = [{'no': 1, 'number': 1, 'volume': 'Dawn', 'title': 'A', 'paras': ['一']},
                        {'no': 2, 'number': 1, 'volume': 'Night', 'title': 'B', 'paras': ['二']}]
            book = {'title': 'Volumes', 'chapters': chapters}
            store.import_entries([{'book': book, 'state': {'drafts': {'1': 'First', '2': 'Second'}}}])
            name = store.backup()
            with sqlite3.connect(store.backups / name) as db:
                saved_book, saved_state = db.execute('SELECT book,state FROM books').fetchone()
            self.assertEqual(json.loads(saved_book)['chapters'], chapters)
            self.assertEqual(json.loads(saved_state)['drafts'], {'1': 'First', '2': 'Second'})
            for change in ({'volume': []}, {'volume': ' '}, {'volume': 'X' * 201},
                           {'number': True}, {'number': -1}, {'volume': 'Dawn'}):
                invalid = dict(book, chapters=[chapters[0], dict(chapters[1], **change)])
                with self.subTest(change=change), self.assertRaises(ValueError):
                    store.import_entries([{'book': invalid}])
            self.assertEqual(len(store.entries()), 1)

    def test_atomic_import(self):
        with tempfile.TemporaryDirectory() as temp:
            store = app.Store(temp)
            with self.assertRaises(ValueError):
                store.import_entries([{'book':{'title':'Good','chapters':[{'no':1,'title':'One','paras':[]}]},'state':{'drafts':{}}},{'book':{'title':'Bad','chapters':[]}}])
            self.assertEqual(store.entries(),[])

if __name__ == '__main__': unittest.main()
