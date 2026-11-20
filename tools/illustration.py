"""Portable GIF data for web builds and full original-reader backups."""
import base64
from pathlib import Path


def load_illustration(root, filename):
    if not filename:
        return None
    path = Path(root) / filename
    if not path.is_file() or path.suffix.lower() != '.gif':
        return None
    data = path.read_bytes()
    if len(data) > 5 * 1024 * 1024 or len(data) < 13 or data[:6] not in (b'GIF87a', b'GIF89a'):
        raise ValueError('The configured GIF must be valid and no larger than 5 MB.')
    width, height = int.from_bytes(data[6:8], 'little'), int.from_bytes(data[8:10], 'little')
    if not width or not height or width * height > 16_000_000:
        raise ValueError('The configured GIF must be smaller than 16 megapixels.')
    return {'name': path.name, 'dataUrl': 'data:image/gif;base64,' + base64.b64encode(data).decode('ascii')}
