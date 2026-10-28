from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from dati_pubblici import public_dataset
from indici_lettura import write_reading_indexes
from sito_pages import build_site, PAGES, LEGAL_PAGES

ROOT = Path(__file__).resolve().parents[1]


class ReadingIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = ROOT / 'sito/dist/data'
        cls.catalog, cls.books, cls.cards = [json.loads((data / name).read_text())
                                             for name in ('catalogo.json', 'libri.json', 'schede.json')]

    def test_real_catalog_preserves_every_public_reference_without_mutating_sources(self):
        before = json.dumps([self.catalog, self.books, self.cards])
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            result = write_reading_indexes(directory, self.catalog, self.books, self.cards)
            index = json.loads((directory / result['datasets']['data/libri.json']).read_text())
            groups = {b['_details']: json.loads((directory / b['_details']).read_text()) for b in index}
            restored = [groups[b['_details']][b['id']] for b in index]
            self.assertEqual(restored, public_dataset('libri.json', self.books))
            self.assertEqual(len(index), len(self.books))
            for full, entry in zip(self.books, index):
                self.assertEqual([m['video_id'] for m in full['mentions']],
                                 [m['video_id'] for m in entry['mentions']])
                for field in ('id', 'title', 'subtitle', 'author', 'work_type', 'status', 'original_title',
                              'search_aliases', 'alternative_titles', 'aliases'):
                    if field in full:
                        self.assertEqual(full[field], entry[field])
            for name in result['files']:
                content = (directory / name).read_bytes()
                self.assertIn(hashlib.sha256(content).hexdigest()[:20], name)
                self.assertNotIn(b'"audio_file"', content)
                self.assertNotIn(b'"video_file"', content)
            small = sum((directory / path).stat().st_size for path in result['datasets'].values())
            old = sum((ROOT / 'sito/dist/data' / name).stat().st_size for name in ('catalogo.json', 'libri.json', 'schede.json'))
            self.assertLess(small, old * .15)
        self.assertEqual(before, json.dumps([self.catalog, self.books, self.cards]))

    def test_new_content_gets_new_urls_and_older_pages_still_have_their_files(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            first = write_reading_indexes(path, self.catalog, self.books[:2], self.cards[:2])
            same = write_reading_indexes(path, self.catalog, self.books[:2], self.cards[:2])
            self.assertEqual(first, same)
            changed = deepcopy(self.books[:2])
            changed[0]['mentions'][0]['note'] = 'Nuova precisazione per il lettore.'
            second = write_reading_indexes(path, self.catalog, changed, self.cards[:2])
            self.assertNotEqual(first['manifest'], second['manifest'])
            for name in first['files'] + second['files']:
                self.assertTrue((path / name).is_file())

    def test_generator_connects_online_pages_to_versioned_indexes_and_keeps_offline_data(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            templates = root / 'sito/templates'
            templates.mkdir(parents=True)
            for key in PAGES | LEGAL_PAGES:
                (templates / (key + '.html')).write_text('<h1>Pagina di prova</h1>')
            dist = root / 'sito/dist'
            (dist / 'data').mkdir(parents=True)
            for name, value in [('catalogo.json', {'videos': []}), ('libri.json', []), ('schede.json', [])]:
                (dist / 'data' / name).write_text(json.dumps(value))
            (dist / 'app.js').write_text('// runtime di prova')
            (dist / 'styles.css').write_text('body {color: black}')
            build_site(root)
            page = (dist / 'biblioteca.html').read_text()
            import re
            manifest_path = re.search(r'data-index-manifest="([^"]+)"', page)[1]
            manifest = json.loads((dist / manifest_path).read_text())
            for path in manifest['datasets'].values():
                self.assertTrue((dist / path).is_file())
            offline = (root / 'sito/anteprima-biblioteca.html').read_text()
            self.assertIn('id="embedded-data"', offline)
            self.assertIn('"data/libri.json": []', offline)


if __name__ == '__main__':
    unittest.main()
