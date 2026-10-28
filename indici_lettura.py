"""Indici pubblici compatti e riferimenti completi caricati per gruppi di opere."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from dati_pubblici import public_dataset


def compact(value):
    return (json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True) + '\n').encode('utf-8')


def write_reading_indexes(destination, catalog, books, cards, *, chunk_size=24):
    """Non modifica i sorgenti; i nomi dipendono dal contenuto, anche per la cache."""
    destination = Path(destination)
    directory = destination / 'data/indici'
    directory.mkdir(parents=True, exist_ok=True)
    files = []

    def write(label, value):
        content = compact(value)
        name = f'data/indici/{label}.{hashlib.sha256(content).hexdigest()[:20]}.json'
        (destination / name).write_bytes(content)
        files.append(name)
        return name

    public_books = public_dataset('libri.json', books)
    public_cards = public_dataset('schede.json', cards)
    public_catalog = deepcopy(catalog)
    for video in public_catalog.get('videos', []):
        video.pop('audio_file', None)
        video.pop('video_file', None)
    # Accosta le opere dello stesso autore: la prima pagina richiede pochi gruppi.
    def order(book):
        value = f"{book.get('author', '')} {book.get('title', '')} {book['id']}".casefold()
        return ''.join(c for c in unicodedata.normalize('NFD', value) if not unicodedata.combining(c))

    ordered = sorted(public_books, key=order)
    details = {}
    for start in range(0, len(ordered), chunk_size):
        group = ordered[start:start + chunk_size]
        path = write('riferimenti', {book['id']: book for book in group})
        details.update({book['id']: path for book in group})
    fields = {'id', 'title', 'subtitle', 'author', 'work_type', 'status', 'original_title',
              'search_aliases', 'alternative_titles', 'aliases'}
    index_books = [dict({k: v for k, v in book.items() if k in fields},
                        mentions=[{'video_id': mention['video_id']} for mention in book['mentions']],
                        _details=details[book['id']]) for book in public_books]
    index_cards = [dict(video_id=card['video_id'], title=card.get('title', ''),
                        topics=card.get('topics', []),
                        books=[{k: ref[k] for k in ('book_id', 'title', 'author', 'role') if k in ref}
                               for ref in card.get('books', [])]) for card in public_cards]
    datasets = {'data/catalogo.json': write('catalogo', public_catalog),
                'data/libri.json': write('biblioteca', index_books),
                'data/schede.json': write('video', index_cards)}
    manifest = write('manifest', {'schema': 1, 'datasets': datasets})
    return {'manifest': manifest, 'datasets': datasets, 'files': files}


def optimize_directory(destination):
    """Aggiorna solo indici e collegamenti alla cache delle pagine già generate."""
    destination = Path(destination)
    data = destination / 'data'
    result = write_reading_indexes(destination, *[json.loads((data / name).read_text())
                                  for name in ('catalogo.json', 'libri.json', 'schede.json')])
    script = (destination / 'app.js').read_bytes()
    version = hashlib.sha256(script).hexdigest()[:12]
    for path in destination.rglob('*.html'):
        # Non entra nelle altre versioni eventualmente presenti sotto la stessa radice.
        if any(part in {'originale', 'sala-lettura'} for part in path.relative_to(destination).parts[:-1]):
            continue
        text = path.read_text()
        text = re.sub(r' data-index-manifest="[^"]*"', '', text)
        text = text.replace('<body ', '<body data-index-manifest="' + result['manifest'] + '" ', 1)
        text = re.sub(r'(<script\b[^>]*\bsrc="(?:\.\./)?app\.js)(?:\?[^" ]*)?("[^>]*>)',
                      lambda m: m[1] + '?v=' + version + m[2], text)
        if text != path.read_text():
            path.write_text(text)
    return result
