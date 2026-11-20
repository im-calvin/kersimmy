"""Restore a SQLite snapshot while the application is stopped."""
import argparse
from pathlib import Path
import sqlite3
from reader_store import Store

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('snapshot',type=Path)
parser.add_argument('--data',type=Path,default=Path('/data'))
args=parser.parse_args()
if not args.snapshot.is_file(): parser.error('Snapshot does not exist')
with sqlite3.connect(f'file:{args.snapshot.resolve()}?mode=ro',uri=True) as source:
    if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok': parser.error('Snapshot integrity check failed')
    if not source.execute("SELECT name FROM sqlite_master WHERE name='books'").fetchone(): parser.error('Not a reader database')
    store=Store(args.data)
    with sqlite3.connect(store.path) as target: source.backup(target)
print('Restored snapshot. Start the application again.')
