#!/usr/bin/env python3
"""
Emit corpus.js — every chapter's paragraphs, for whole-manuscript term lookup.

Loaded with <script src="corpus.js"> rather than fetch(), because fetch() of a
local file from a file:// page is blocked by Chrome; script tags are not.

Shape:  window.CORPUS = [[chapterNo, title, [para, para, ...], metadata?], ...]
Optional metadata contains volume and the original displayed chapter number.

Usage:
  python3 build_corpus.py SOURCE.txt corpus.js
"""
import argparse
import json
import sys

from chapter_structure import metadata
from tlconfig import load_config, parse_source


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--config', default=None)
    args = ap.parse_args()

    chapters = parse_source(load_config(args.config))
    if not chapters:
        sys.exit('no chapters matched')

    data = [[c['no'], c['title'], c['paras']] + ([metadata(c)] if metadata(c) else []) for c in chapters]
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

    with open(args.out, 'w', encoding='utf-8') as fh:
        fh.write('window.CORPUS=' + payload + ';\n')

    print('chapters   :', len(data))
    print('paragraphs :', sum(len(c[2]) for c in data))
    print('characters :', sum(sum(len(p) for p in c[2]) for c in data))
    print('wrote      : {} ({:.1f} MB)'.format(
        args.out, (len(payload) + 20) / 1e6))


if __name__ == '__main__':
    main()
