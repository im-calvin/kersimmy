#!/usr/bin/env python3
"""
Shared configuration and source parsing for the translation reader.

Everything project-specific lives in config.json, so the same tools work on a
different manuscript, encoding, heading style and paragraph convention.
"""
import json
import os
import re
import sys

from chapter_structure import BONUS_CHAPTER_HEADING, BONUS_VOLUME_HEADING, VOLUME_CHAPTER_HEADING

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "project": "Project",
    "slug": "project",
    # storage_prefix namespaces browser localStorage. Two projects with
    # different prefixes can coexist; identical prefixes would overwrite
    # each other's drafts, because local files share one browser origin.
    "storage_prefix": "tl",
    "source": "../source/source.txt",
    "encoding": "auto",
    # capture group 1 = chapter number (arabic or Chinese numerals),
    # group 2 = optional title
    "heading_regex":
        r"^\s*第\s*([0-9０-９零〇一二三四五六七八九十百千]+)\s*[章回節节]\s*(.*?)\s*$",
    # line  = one paragraph per line (web-novel .txt, indented with U+3000)
    # blank = paragraphs separated by blank lines, may wrap across lines
    # auto  = decide from how many blank lines the file contains
    "paragraph_mode": "auto",
    # Optional volume headings; empty preserves existing parsing behavior.
    "volume_heading_regex": "",
    "words_per_page": 250,
    # filename of an image shown in the statistics panel; "" for none
    "illustration": "",
}

CN_DIGITS = {'零': 0, '〇': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
             '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
CN_UNITS = {'十': 10, '百': 100, '千': 1000}
FULLWIDTH = {chr(0xFF10 + i): str(i) for i in range(10)}
ENCODINGS = ('utf-8-sig', 'utf-8', 'gb18030', 'big5', 'utf-16')


def load_config(path=None):
    path = path or os.path.join(HERE, 'config.json')
    cfg = dict(DEFAULTS)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            cfg.update(json.load(fh))
    else:
        sys.stderr.write('note: no config.json, using defaults\n')
    cfg['_dir'] = os.path.dirname(os.path.abspath(path))
    return cfg


def source_path(cfg):
    p = cfg['source']
    return p if os.path.isabs(p) else os.path.normpath(
        os.path.join(cfg['_dir'], p))


def docx_text(path):
    """Extract paragraphs from a .docx as one line each.

    Word marks paragraphs explicitly, so this is more reliable than guessing
    from blank lines. Text deleted under tracked changes is dropped; inserted
    text is kept, i.e. the result reads as if all revisions were accepted.
    """
    import xml.etree.ElementTree as ET
    import zipfile
    try:
        with zipfile.ZipFile(path) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
    except (zipfile.BadZipFile, KeyError, ET.ParseError):
        sys.exit('not a readable .docx: {}\n'
                 '(old binary .doc is not supported — re-save as .docx)'
                 .format(path))
    namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    def content(node, paragraph):
        if node.tag in (namespace+'del', namespace+'moveFrom'):
            return ''
        if node is not paragraph and node.tag == namespace+'p':
            return ''
        if node.tag == namespace+'t':
            return node.text or ''
        if node.tag == namespace+'tab':
            return '\t'
        if node.tag in (namespace+'br', namespace+'cr'):
            return '\n'
        return ''.join(content(child, paragraph) for child in node)
    return '\n'.join(content(paragraph, paragraph).strip() for paragraph in root.iter(namespace+'p'))


def read_source(cfg):
    """Return (text, encoding_used). 'auto' tries encodings in turn."""
    path = source_path(cfg)
    if not os.path.exists(path):
        sys.exit('source not found: {}'.format(path))
    if path.lower().endswith('.docx'):
        return docx_text(path), 'docx'
    raw = open(path, 'rb').read()
    encs = ENCODINGS if cfg['encoding'] == 'auto' else (cfg['encoding'],)
    for enc in encs:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        if '�' not in text:
            return text, enc
    sys.exit('could not decode {} — set "encoding" in config.json'.format(path))


def to_int(s):
    """'12', '１２' and '一百四十' all become integers."""
    s = ''.join(FULLWIDTH.get(c, c) for c in s)
    if s.isdigit():
        return int(s)
    total = section = num = 0
    for c in s:
        if c in CN_DIGITS:
            num = CN_DIGITS[c]
        elif c in CN_UNITS:
            section += (num or 1) * CN_UNITS[c]
            num = 0
        else:
            return None
    return total + section + num


def cjk_ratio(s):
    if not s:
        return 0.0
    return sum(1 for c in s if '一' <= c <= '鿿') / len(s)


def paragraphs(lines, mode, joiner):
    if mode == 'line':
        return [l.strip('　 \t') for l in lines if l.strip()]
    out, buf = [], []
    for l in lines:
        if l.strip():
            buf.append(l.strip('　 \t'))
        elif buf:
            out.append(joiner.join(buf))
            buf = []
    if buf:
        out.append(joiner.join(buf))
    return out


def parse_source(cfg, verbose=False):
    text, enc = read_source(cfg)
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    head = re.compile(cfg['heading_regex'])
    volume_head = re.compile(cfg['volume_heading_regex']) if cfg.get('volume_heading_regex') else None
    volume = ''
    recognize_bonus = volume_head is not None and cfg.get('combined_volume_headings')
    bonus_volume = False

    mode = cfg['paragraph_mode']
    if enc == 'docx':
        mode = 'line'       # Word paragraphs are explicit; never guess
    elif mode == 'auto':
        blanks = sum(1 for l in lines if not l.strip())
        mode = 'blank' if blanks / max(1, len(lines)) >= 0.15 else 'line'
    joiner = '' if cjk_ratio(text[:20000]) > 0.3 else ' '

    chapters, cur, bad = [], None, []
    for l in lines:
        combined = VOLUME_CHAPTER_HEADING.match(l) if cfg.get('combined_volume_headings') else None
        if combined:
            bonus_volume = False
            volume_label, chapter_heading = combined.groups()
            if volume_head:
                volume = volume_label.strip()
                if len(volume) > 200:
                    raise ValueError('Volume headings must be 200 characters or fewer.')
            m = head.match(chapter_heading)
        elif recognize_bonus and BONUS_VOLUME_HEADING.fullmatch(l):
            volume = l.strip()
            bonus_volume = True
            cur = None
            continue
        elif volume_head and volume_head.fullmatch(l):
            volume = l.strip()
            if len(volume) > 200:
                raise ValueError('Volume headings must be 200 characters or fewer.')
            bonus_volume = False
            cur = None
            continue
        else:
            m = head.match(l)
            if m is None and bonus_volume:
                m = BONUS_CHAPTER_HEADING.fullmatch(l)
        if m:
            n = to_int(m.group(1))
            if n is None:
                bad.append(l.strip()[:40])
                continue
            title = (m.group(2) if m.lastindex and m.lastindex >= 2 else '') or ''
            cur = {'no': n, 'title': title, 'lines': []}
            if volume:
                cur['volume'] = volume
            chapters.append(cur)
            continue
        if cur is not None:
            cur['lines'].append(l)

    for c in chapters:
        c['paras'] = paragraphs(c.pop('lines'), mode, joiner)
    chapters = [c for c in chapters if c['paras']]

    if volume_head and len({c['no'] for c in chapters}) != len(chapters):
        # New imports may restart numbering in each volume. Keep displayed numbers
        # separately; all existing saved books retain their original numeric keys.
        identities = {(c.get('volume', ''), c['no']) for c in chapters}
        if len(identities) != len(chapters):
            raise ValueError('Duplicate chapter numbers within a volume. Check chapter or volume headings.')
        for index, chapter in enumerate(chapters, 1):
            chapter['number'] = chapter['no']
            chapter['no'] = index

    if verbose:
        nos = [c['no'] for c in chapters]
        print('source          :', source_path(cfg))
        print('encoding        :', enc)
        print('paragraph mode  :', mode,
              '(joiner {})'.format('none' if joiner == '' else 'space'))
        print('chapters        :', len(chapters),
              '({} … {})'.format(min(nos), max(nos)) if nos else '')
        gaps = [n for n in range(min(nos), max(nos) + 1)
                if n not in set(nos)] if nos else []
        if not gaps:
            print('numbering gaps  : none')
        elif len(gaps) <= 12:
            print('numbering gaps  :', gaps)
        else:
            print('numbering gaps  : {} missing, e.g. {}…{} '
                  '(fine if your source skips numbers)'.format(
                      len(gaps), gaps[:5], gaps[-1]))
        dupes = sorted({n for n in nos if nos.count(n) > 1})
        print('duplicate nos   :', dupes or 'none')
        print('paragraphs      :', sum(len(c['paras']) for c in chapters))
        print('characters      :',
              sum(sum(len(p) for p in c['paras']) for c in chapters))
        if bad:
            print('unparsed heads  :', bad[:5])
        if chapters:
            print('first titles    :', [c['title'][:18] for c in chapters[:3]])
    return chapters


def pick(chapters, chapters_arg, want_all):
    if want_all:
        return {c['no'] for c in chapters}
    want = set()
    for part in str(chapters_arg).split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-')
            want |= set(range(int(a), int(b) + 1))
        elif part:
            want.add(int(part))
    return want


if __name__ == '__main__':
    cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    print('project         :', cfg['project'], '(slug {})'.format(cfg['slug']))
    print('storage prefix  :', cfg['storage_prefix'])
    parse_source(cfg, verbose=True)
