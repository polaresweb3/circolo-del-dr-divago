"""Il progetto diventa catalogo senza copertine, uscite o acquisti inventati."""
import base64
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import prepara_versione_online as publication
from sito_pages import PAGES, build_site, editorial_catalog

ROOT = Path(__file__).resolve().parents[1]


class EditorialCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / 'sito/dist'
        image = self.source / 'assets/volumi/prova.png'
        image.parent.mkdir(parents=True)
        image.write_bytes(base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jS1sAAAAASUVORK5CYII='))
        self.volume = {
            'year': 2015,
            'title': 'Titolo di prova',
            'description': 'Descrizione di prova dei contenuti.',
            'cover': {'src': 'assets/volumi/prova.png'},
            'purchase_links': [{'label': 'Acquista il volume', 'url': 'https://example.com/volume'}],
        }

    def test_empty_catalogue_has_preparation_state_without_purchase_or_fake_image(self):
        page = editorial_catalog([], self.source)
        self.assertIn('Si comincia dal 2015.', page)
        self.assertIn('Il progetto è in preparazione', page)
        self.assertNotIn('<img', page)
        self.assertNotIn('<a ', page)

    def test_newest_volume_is_featured_and_every_volume_keeps_its_cover_and_purchase(self):
        newer = deepcopy(self.volume)
        newer.update(year=2016, title='Secondo titolo di prova')
        newer['purchase_links'][0]['url'] = 'https://example.com/secondo'
        original = deepcopy([self.volume, newer])
        page = editorial_catalog([self.volume, newer], self.source)
        self.assertLess(page.index('volume-title-2016'), page.index('volume-title-2015'))
        self.assertEqual(page.count('project-volume-featured'), 1)
        self.assertEqual(page.count('<img '), 2)
        self.assertIn('https://example.com/volume', page)
        self.assertIn('https://example.com/secondo', page)
        self.assertNotIn('in preparazione', page)
        self.assertEqual([self.volume, newer], original)

    def test_editorial_text_is_escaped(self):
        self.volume['title'] = 'Titolo <inedito> & altre parole'
        self.volume['description'] = '<script>contenuto</script>'
        page = editorial_catalog([self.volume], self.source)
        self.assertIn('Titolo &lt;inedito&gt; &amp; altre parole', page)
        self.assertNotIn('<script>', page)

    def test_incomplete_books_and_invalid_purchase_links_are_rejected(self):
        invalid = []
        for field in ('title', 'description', 'cover', 'purchase_links'):
            volume = deepcopy(self.volume)
            volume.pop(field)
            invalid.append(volume)
        for url in ('javascript:alert(1)', '/acquista', 'https:///senza-host'):
            volume = deepcopy(self.volume)
            volume['purchase_links'][0]['url'] = url
            invalid.append(volume)
        for volume in invalid:
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                editorial_catalog([volume], self.source)
        with self.assertRaises(ValueError):
            editorial_catalog([self.volume, deepcopy(self.volume)], self.source)

    def test_missing_covers_and_paths_outside_cover_directory_are_rejected(self):
        for src in ('assets/volumi/mancante.png', 'assets/volumi/../../../README.md'):
            volume = deepcopy(self.volume)
            volume['cover']['src'] = src
            with self.subTest(src=src), self.assertRaises(ValueError):
                editorial_catalog([volume], self.source)

    def test_generation_keeps_catalogue_on_project_page_and_embeds_cover_offline(self):
        templates = self.root / 'sito/templates'
        templates.mkdir()
        for name in ('progetto', 'privacy', 'crediti'):
            shutil.copyfile(ROOT / 'sito/templates' / (name + '.html'), templates / (name + '.html'))
        data = self.source / 'data'
        data.mkdir()
        (data / 'volumi.json').write_text(json.dumps([self.volume]))
        (self.source / 'styles.css').write_text('body { color: black; }')
        (self.source / 'app.js').write_text('')
        manifest = build_site(self.root, pages={'progetto': PAGES['progetto']})
        self.assertEqual({item['path'] for item in manifest['pages']}, {'progetto.html', 'privacy.html', 'crediti.html'})
        online = (self.source / 'progetto.html').read_text()
        offline = (self.root / 'sito/anteprima-progetto.html').read_text()
        self.assertIn('src="assets/volumi/prova.png"', online)
        self.assertIn('src="data:image/png;base64,', offline)
        for page in (online, offline):
            self.assertIn('Jorge Luis Borges', page)
            self.assertIn('https://example.com/volume', page)
            self.assertNotIn('{{editorial_catalog}}', page)
            self.assertNotIn('Il progetto è in preparazione', page)

    def test_hosting_export_includes_editorial_cover_and_catalogue(self):
        data = self.source / 'data'
        data.mkdir()
        for name, value in [('catalogo.json', {'videos': []}), ('libri.json', []),
                            ('schede.json', []), ('volumi.json', [self.volume])]:
            (data / name).write_text(json.dumps(value))
        (self.source / 'index.html').write_text('<a href="progetto.html">Progetto</a>')
        (self.source / 'progetto.html').write_text(editorial_catalog([self.volume], self.source))
        (self.source / 'styles.css').write_text('')
        (self.source / 'app.js').write_text('')
        manifest = {'pages': [{'path': 'index.html'}, {'path': 'progetto.html'}]}
        with patch.object(publication, 'ROOT', self.root), \
                patch.object(publication, 'build_site', return_value=manifest), \
                patch.object(publication, 'verify_covers', create=True), redirect_stdout(io.StringIO()):
            destination = publication.prepare()
        self.assertEqual((destination / 'assets/volumi/prova.png').read_bytes(),
                         (self.source / 'assets/volumi/prova.png').read_bytes())
        self.assertEqual(json.loads((destination / 'data/volumi.json').read_text()), [self.volume])


if __name__ == '__main__':
    unittest.main()
