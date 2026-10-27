"""Composizione condivisa delle homepage delle proposte grafiche."""
from html import escape
from pathlib import Path

FEATURED = [
    ('sulla-stupidita-musil', 'Un invito a diffidare delle certezze, cominciando dalle proprie.'),
    ('minima-moralia-adorno', 'Un percorso fra vita quotidiana, cultura e pensiero critico.'),
    ('libri-della-mia-vita-salamov', 'Una biblioteca personale, una geografia della memoria.'),
    ('saggio-sulla-liberta-mill', 'Libertà di pensiero, autonomia e responsabilità nel confronto.'),
    ('avvenire-nostre-scuole-nietzsche', 'Che cosa chiediamo all’educazione e alla cultura?'),
    ('nel-ventre-della-balena-orwell', 'Scrittura, esperienza e libertà dello sguardo.'),
]


def book_cards(books):
    lookup = {b['id']: b for b in books}
    result = []
    for index, (ident, note) in enumerate(FEATURED):
        book = lookup[ident]
        cover = book['cover']
        loading = 'eager' if index < 3 else 'lazy'
        result.append(
            '<article class="editorial-book">'
            f'<a href="biblioteca.html#book-{escape(ident)}" class="editorial-book-link">'
            f'<div class="editorial-book-visual tone-{index + 1}"><img src="{escape(cover["src"], quote=True)}" '
            f'alt="" width="180" height="270" loading="{loading}" decoding="async"></div>'
            '<div class="editorial-book-copy">'
            f'<p class="editorial-book-author">{escape(book["author"])}</p><h3>{escape(book["title"])}</h3>'
            f'<p class="editorial-book-note">{escape(note)}</p>'
            '</div></a></article>')
    return ''.join(result)


def render_home(source, books, catalog, cards, *, book_renderer=book_cards):
    """Compila la sorgente autorevole della Home senza riusare una copia obsoleta."""
    home = Path(source).read_text(encoding='utf-8')
    if '{{editorial_books}}' in home:
        home = home.replace('{{editorial_books}}', book_renderer(books))
    counts = {
        'books_count': len(books),
        'videos_count': len(catalog.get('videos', [])),
        'cards_count': len(cards),
        'hours_count': round(sum(video.get('duration') or 0 for video in catalog.get('videos', [])) / 3600),
    }
    for name, count in counts.items():
        home = home.replace('{{' + name + '}}', f'{count:,}'.replace(',', '.'))
    return home
