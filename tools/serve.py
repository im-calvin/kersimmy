#!/usr/bin/env python3
"""Build the library and start the original Python reader with SQLite."""
from build_web import ROOT, build
from reader_server import main

if __name__ == '__main__':
    build(ROOT / 'dist')
    main()
