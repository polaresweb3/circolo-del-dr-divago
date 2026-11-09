from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from selezione_video import excluded_video_ids, selected_datasets, apply_to_directory


class PublicVideoSelectionTests(unittest.TestCase):
    def values(self):
        return ({'channel': 'Test', 'videos': [{'id': 'keep1234567'}, {'id': 'hide1234567'}]},
                [{'id': 'shared', 'title': 'Shared', 'mentions': [
                    {'video_id': 'keep1234567', 'seconds': 8, 'note': 'Uncertain'},
                    {'video_id': 'hide1234567', 'seconds': 10}]},
                 {'id': 'orphan', 'mentions': [{'video_id': 'hide1234567'}]}],
                [{'video_id': 'keep1234567', 'summary': 'Preserve'}, {'video_id': 'hide1234567'}])

    def test_shared_references_and_input_data_are_preserved(self):
        before = self.values()
        original = deepcopy(before)
        catalog, books, cards = selected_datasets(*before, {'hide1234567'})
        self.assertEqual(before, original)
        self.assertEqual(catalog, {'channel': 'Test', 'videos': [{'id': 'keep1234567'}]})
        self.assertEqual([b['id'] for b in books], ['shared'])
        self.assertEqual(books[0]['mentions'], [original[1][0]['mentions'][0]])
        self.assertEqual(cards, [original[2][0]])
        self.assertEqual(selected_datasets(catalog, books, cards, {'hide1234567'}),
                         (catalog, books, cards))

    def test_protected_video_cannot_be_excluded_and_missing_registry_keeps_everything(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(excluded_video_ids(root), set())
            (root / 'sito').mkdir()
            path = root / 'sito/selezione-video.json'
            path.write_text(json.dumps({'excluded_video_ids': ['hide1234567'],
                                        'protected_video_ids': ['hide1234567']}))
            with self.assertRaisesRegex(ValueError, 'conservare'):
                excluded_video_ids(root)

    def test_directory_export_remains_filtered_after_full_catalog_is_reintroduced(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'data').mkdir()
            for _ in range(2):
                for name, value in zip(('catalogo.json', 'libri.json', 'schede.json'), self.values()):
                    (root / 'data' / name).write_text(json.dumps(value))
                actual = apply_to_directory(root, {'hide1234567'})
                for name, expected in zip(('catalogo.json', 'libri.json', 'schede.json'), actual):
                    self.assertEqual(json.loads((root / 'data' / name).read_text()), expected)
                self.assertEqual(len(actual[0]['videos']), 1)
                self.assertEqual(len(actual[1]), 1)

    def test_catalog_export_filters_the_site_but_keeps_the_private_catalog(self):
        import divago
        with TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'archivio'
            (archive / 'metadati').mkdir(parents=True)
            (root / 'sito').mkdir()
            private = archive / 'metadati/canale.json'
            private.write_text(json.dumps({'entries': [
                {'id': 'keep1234567', 'title': 'Keep', 'duration': 60},
                {'id': 'hide1234567', 'title': 'Hide', 'duration': 60}]}))
            original = private.read_bytes()
            (root / 'sito/selezione-video.json').write_text(json.dumps({
                'excluded_video_ids': ['hide1234567'], 'protected_video_ids': ['keep1234567']}))
            with patch.object(divago, 'ROOT', root), patch.object(divago, 'build_preview'):
                videos = divago.export_catalog(archive)
            self.assertEqual([v['id'] for v in videos], ['keep1234567'])
            self.assertEqual(private.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
