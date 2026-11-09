"""Applica la selezione del sito senza intervenire sull’archivio o su YouTube."""
from copy import deepcopy
import json
from pathlib import Path
import re


def excluded_video_ids(root):
    path = Path(root) / 'sito/selezione-video.json'
    if not path.exists():
        return set()
    selection = json.loads(path.read_text(encoding='utf-8'))
    excluded = selection['excluded_video_ids']
    protected = selection.get('protected_video_ids', [])
    if (not isinstance(excluded, list) or len(excluded) != len(set(excluded))
            or not all(isinstance(ident, str) and re.fullmatch(r'[A-Za-z0-9_-]{11}', ident)
                       for ident in excluded + protected)):
        raise ValueError('Identificatori non validi nella selezione del sito.')
    if set(excluded) & set(protected):
        raise ValueError('Un video da conservare compare anche fra le esclusioni.')
    return set(excluded)


def selected_datasets(catalog, books, cards, excluded):
    """Conserva metadati e riferimenti superstiti, senza modificare gli input."""
    catalog, books, cards = deepcopy(catalog), deepcopy(books), deepcopy(cards)
    catalog['videos'] = [v for v in catalog.get('videos', []) if v['id'] not in excluded]
    cards = [c for c in cards if c['video_id'] not in excluded]
    selected_books = []
    for book in books:
        previous = book.get('mentions', [])
        book['mentions'] = [m for m in previous if m['video_id'] not in excluded]
        # Elimina i riferimenti rimasti collegati soltanto a video esclusi.
        if previous and not book['mentions']:
            continue
        selected_books.append(book)
    return catalog, selected_books, cards


def apply_to_directory(directory, excluded):
    directory = Path(directory)
    names = ('catalogo.json', 'libri.json', 'schede.json')
    values = [json.loads((directory / 'data' / name).read_text(encoding='utf-8'))
              for name in names]
    selected = selected_datasets(*values, excluded)
    for name, before, after in zip(names, values, selected):
        if before != after:
            (directory / 'data' / name).write_text(
                json.dumps(after, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return selected
