"""Additive volume metadata and shared, escaped chapter navigation markup."""
import html
import re

# Opt-in for file configurations; the upload form enables this for new books.
VOLUME_HEADING_REGEX = r'^\s*(?:第\s*[0-9０-９零〇一二两三四五六七八九十百千]+\s*[卷部]|(?i:Volume|Vol\.?)\s+[0-9０-９]+)(?:\s*[:：.、\-–—]\s*|\s+|$).*?\s*$'

# Some Word manuscripts repeat the volume on every chapter heading.
VOLUME_CHAPTER_HEADING = re.compile(
    r'^\s*(第\s*[0-9０-９零〇一二两三四五六七八九十百千]+\s*[卷部].{0,197}?)'
    r'\s+(第\s*[0-9０-９零〇一二两三四五六七八九十百千]+\s*[章回節节].*)$'
)


def number(chapter):
    return chapter.get('number', chapter['no'])


def metadata(chapter):
    return {key: chapter[key] for key in ('volume', 'number') if key in chapter}


def options(chapters, titles=True):
    result = []
    previous = None
    for chapter in chapters:
        volume = chapter.get('volume') or ''
        if volume != previous:
            if previous:
                result.append('</optgroup>')
            if volume:
                result.append('<optgroup label="{}">'.format(html.escape(volume, quote=True)))
            previous = volume
        label = '第{}章'.format(number(chapter))
        if titles and chapter['title']:
            label += ' ' + chapter['title']
        result.append('<option value="{}">{}</option>'.format(chapter['no'], html.escape(label)))
    if previous:
        result.append('</optgroup>')
    return ''.join(result)
