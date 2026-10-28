"""Aggiorna l'interfaccia delle pagine pubbliche conservandone dati e contenuti."""
import hashlib
import json
from pathlib import Path
import re
import shutil

from nomi_pubblici import public_html
from sito_pages import video_content, catalog_video_content

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / 'docs'
cards = {c['video_id']: c for c in json.loads((DOCS / 'data/schede.json').read_text())}
videos = {v['id']: v for v in json.loads((DOCS / 'data/catalogo.json').read_text())['videos']}
books = json.loads((DOCS / 'data/libri.json').read_text())
script = (ROOT / 'sito/dist/app.js').read_bytes()
refinement = (ROOT / 'sito/dist/refinement.css').read_bytes()
script_hash = hashlib.sha256(script).hexdigest()[:12]
refine_hash = hashlib.sha256(refinement).hexdigest()[:12]
count = 0
for path in DOCS.rglob('*.html'):
    original = path.read_text()
    if '<header class="header wrap">' not in original:
        continue
    page = original
    if path.parent.name == 'video':
        ident = path.stem
        content = video_content(cards[ident], books) if ident in cards else catalog_video_content(videos[ident], books)
        page, replacements = re.subn(r'(<main id="contenuto">).*?(</main>)',
                                     lambda m: m[1] + public_html(content) + m[2], page, flags=re.S)
        assert replacements == 1, path
    if path.name == 'biblioteca.html':
        content = (ROOT / 'sito/templates/biblioteca.html').read_text().strip()
        page, replacements = re.subn(r'(<main id="contenuto">).*?(</main>)',
                                     lambda m: m[1] + content + m[2], page, flags=re.S)
        assert replacements == 1, path
    button = ('<button type="button" class="nav-toggle" aria-expanded="false" '
              'aria-controls="site-navigation" hidden>Menu <span aria-hidden="true">☰</span></button>\n'
              '    <nav id="site-navigation" aria-label="Navigazione principale">')
    page = page.replace('<nav aria-label="Navigazione principale">', button)
    if 'href="refinement.css' not in page and 'href="../refinement.css' not in page:
        page, replacements = re.subn(r'(<link rel="stylesheet" href="((?:\.\./)?)styles\.css[^\"]*">)',
                                    lambda m: m[1] + f'\n  <link rel="stylesheet" href="{m[2]}refinement.css?v={refine_hash}">', page)
        assert replacements == 1, path
    page = re.sub(r'href="((?:\.\./)?)refinement\.css(?:\?[^\"]*)?"',
                  lambda m: f'href="{m[1]}refinement.css?v={refine_hash}"', page)
    page = re.sub(r'src="((?:\.\./)?)app\.js(?:\?[^\"]*)?"',
                  lambda m: f'src="{m[1]}app.js?v={script_hash}"', page)
    if page != original:
        path.write_text(page)
        count += 1
for folder in [DOCS, DOCS / 'originale', DOCS / 'sala-lettura']:
    shutil.copyfile(ROOT / 'sito/dist/app.js', folder / 'app.js')
    shutil.copyfile(ROOT / 'sito/dist/refinement.css', folder / 'refinement.css')
print(json.dumps(dict(updated_pages=count, video_cards=len(cards), video_catalog=len(videos),
                      data_unchanged=True), indent=2))
