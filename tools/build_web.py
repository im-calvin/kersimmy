#!/usr/bin/env python3
"""Assemble a portable static site; optionally include the current manuscript."""
import argparse
import json
from pathlib import Path
import shutil

from tlconfig import load_config, parse_source
from illustration import load_illustration

ROOT = Path(__file__).resolve().parent.parent


def build(output, include_current=True):
    output = Path(output).resolve()
    if output == ROOT or output == ROOT / 'web' or ROOT.is_relative_to(output):
        raise ValueError('Choose a separate output folder, such as dist/.')
    output.mkdir(parents=True, exist_ok=True)
    for obsolete in ('reader.html','reader.js','review.js','parser.js','translation.js','docx.js','importer.js','import-worker.js','tests.js','tests.html'):
        (output / obsolete).unlink(missing_ok=True)
    for file in (ROOT / 'web').iterdir():
        if file.is_file():
            shutil.copy2(file, output / file.name)
    if include_current:
        cfg = load_config(str(ROOT / 'tools' / 'config.json'))
        book = {'title': cfg['project'], 'chapters': parse_source(cfg),
                'sourceName': Path(cfg['source']).name, 'encoding': cfg['encoding'],
                'paragraphMode': cfg['paragraph_mode'], 'wordsPerPage': cfg['words_per_page'],
                'headingRegex': cfg['heading_regex'], 'volumeHeadingRegex': cfg.get('volume_heading_regex', ''),
                'illustration': load_illustration(ROOT, cfg.get('illustration')),
                'hasOriginalReader': (ROOT / 'index.html').is_file()}
        (output / 'current-book.json').write_text(json.dumps(book, ensure_ascii=False), encoding='utf-8')
        legacy = output / 'legacy'
        legacy.mkdir(exist_ok=True)
        for pattern in ('*.html', 'corpus.js', 'manifest.json'):
            for file in ROOT.glob(pattern):
                shutil.copy2(file, legacy / file.name)
        if cfg.get('illustration'):
            illustration = ROOT / cfg['illustration']
            if illustration.is_file():
                shutil.copy2(illustration, legacy / illustration.name)
    else:
        # Only remove artifacts this builder owns, never the user's source files.
        (output / 'current-book.json').unlink(missing_ok=True)
        if (output / 'legacy').exists():
            shutil.rmtree(output / 'legacy')
    print(f'Static site built: {output}', flush=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--without-current', action='store_true', help='Omit the bundled manuscript and original reader.')
    args = parser.parse_args()
    build(args.output, not args.without_current)
