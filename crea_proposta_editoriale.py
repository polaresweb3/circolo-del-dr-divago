#!/usr/bin/env python3
"""Crea una proposta grafica separata, senza modificare o pubblicare il sito scelto."""
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit
import zipfile

from sito_pages import PAGES, LEGAL_PAGES, build_site

ROOT = Path(__file__).resolve().parent
PROPOSAL = ROOT / 'proposte/editoriale'
SOURCE = PROPOSAL / 'sorgenti'
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
            '<span class="editorial-book-action">Libro e riferimenti <span aria-hidden="true">→</span></span>'
            '</div></a></article>')
    return ''.join(result)


class References(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.paths = []
        self.ids = []
        self.h1_count = 0
        self.in_nav = False
        self.nav_count = self.nav_current = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'h1':
            self.h1_count += 1
        if tag == 'nav' and attrs.get('aria-label') == 'Navigazione principale':
            self.in_nav = True
        if tag == 'a' and self.in_nav:
            self.nav_count += 1
            self.nav_current += attrs.get('aria-current') == 'page'
        for attr in ('href', 'src'):
            value = attrs.get(attr)
            if value:
                parts = urlsplit(value)
                if parts.path and not parts.scheme and not parts.netloc:
                    self.paths.append(parts.path)

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.in_nav = False


def create(proposal=PROPOSAL, source=SOURCE, label='PROPOSTA EDITORIALE',
           slug='editoriale', reference='https://www.adelphi.it/',
           book_renderer=book_cards, home_page='editoriale'):
    # Dati già ripuliti per la versione pubblica: nessun archivio privato o credenziale.
    public = ROOT / 'pubblicazione/circolo-del-dr-divago/dist'
    dist = proposal / 'sito/dist'
    templates = proposal / 'sito/templates'
    dist.mkdir(parents=True, exist_ok=True)
    templates.mkdir(parents=True, exist_ok=True)
    shutil.copytree(public / 'assets', dist / 'assets', dirs_exist_ok=True)
    shutil.copytree(public / 'data', dist / 'data', dirs_exist_ok=True)
    for retired_data in ('blog.json', 'ricerca.json'):
        (dist / 'data' / retired_data).unlink(missing_ok=True)
    shutil.copy2(ROOT / 'sito/dist/app.js', dist / 'app.js')
    for original in (ROOT / 'sito/templates').glob('*.html'):
        shutil.copy2(original, templates / original.name)
    books = json.loads((dist / 'data/libri.json').read_text())
    catalog = json.loads((dist / 'data/catalogo.json').read_text())
    cards = json.loads((dist / 'data/schede.json').read_text())
    home = (source / 'home.html').read_text()
    home = home.replace('{{editorial_books}}', book_renderer(books))
    home = home.replace('{{books_count}}', str(len(books))).replace('{{videos_count}}', str(len(catalog['videos'])))
    home = home.replace('{{cards_count}}', str(len(cards)))
    (templates / 'home.html').write_text(home)
    # La cascata è esplicita: componenti comuni nel primo livello, tema nel secondo.
    base = (ROOT / 'sito/dist/styles.css').read_text()
    theme = (source / 'theme.css').read_text()
    (dist / 'styles.css').write_text('@layer componenti, proposta;\n@layer componenti {\n' + base
                                    + '\n}\n@layer proposta {\n' + theme + '\n}\n')
    pages = {'home': ('index.html', 'Home', PAGES['home'][2], [])}
    pages.update({key: PAGES[key] for key in ('video', 'biblioteca', 'blog', 'eventi', 'progetto')})
    manifest = build_site(proposal, pages=pages)
    for item in manifest['pages']:
        for file in (dist / item['path'], proposal / 'sito' / item['preview']):
            html = file.read_text()
            html = html.replace('>ANTEPRIMA LOCALE<', '>' + escape(label) + '<')
            if item['page'] == 'home':
                # La vetrina è statica: nessuna attesa dei dati e nessun JS aggiuntivo.
                html = html.replace('data-page="home"', 'data-page="' + home_page + '"')
            file.write_text(html)
    for item in manifest['pages']:
        for root, name in ((dist, item['path']), (proposal / 'sito', item['preview'])):
            file = root / name
            html = file.read_text()
            if any(marker in html for marker in ('/Users/', 'file:///', '"audio_file"', '"video_file"')):
                raise ValueError('Percorso privato nella proposta: ' + name)
            if '{{' in html:
                raise ValueError('Segnaposto non sostituito: ' + name)
            checked = References(html)
            if checked.h1_count != 1 or len(checked.ids) != len(set(checked.ids)):
                raise ValueError('Struttura della pagina non valida: ' + name)
            if checked.nav_count != len(pages) or checked.nav_current != (0 if item['page'] in LEGAL_PAGES else 1):
                raise ValueError('Navigazione della pagina non valida: ' + name)
            for relative in checked.paths:
                target = (file.parent / relative).resolve()
                if not target.is_relative_to(root.resolve()) or not target.is_file():
                    raise ValueError('Collegamento non valido: ' + relative)
    output = ROOT / ('condivisione/Circolo-del-Dr-Divago-proposta-' + slug + '.zip')
    folder = 'Circolo-proposta-' + slug + '/'
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in manifest['pages']:
            path = proposal / 'sito' / item['preview']
            archive.write(path, folder + path.name)
        archive.writestr(folder + 'LEGGIMI.txt',
            'Apri anteprima.html dopo avere estratto tutti i file.\n'
            + label + ': ' + str(len(manifest['pages'])) + ' pagine.\n'
            'Le opere in biblioteca sono riferimenti alle edizioni dei rispettivi editori.\n'
            'Apri un video per guardarlo e consultare la scheda nello stesso luogo.\n'
            'Le analisi non ancora preparate sono indicate esplicitamente.\n'
            'Nessun audio, video, trascrizione integrale o credenziale è incluso.\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Pacchetto non integro.')
    report = {'status': 'local_proposal_not_published', 'pages': len(manifest['pages']),
              'source_reference': reference, 'original_design_preserved': True,
              'publisher_status': 'sezione temporaneamente ritirata', 'zip': str(output),
              'internal_links_checked': True, 'local_media_included': False, 'new_libraries': 0}
    (proposal / 'preparazione.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    create()
