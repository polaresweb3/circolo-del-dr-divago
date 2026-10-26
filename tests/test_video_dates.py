import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from video_dates import normalize_publication_date, publication_dates


class PublicationDateTests(unittest.TestCase):
    def test_validate_dates_without_guessing_years(self):
        self.assertEqual(normalize_publication_date('20240229'), '2024-02-29')
        for value in (None, 2026, '2025-02-29', '20261301', '2026'):
            self.assertIsNone(normalize_publication_date(value))

    def test_previous_dates_survive_offline_rebuild_and_verified_cache_updates(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            public = root / 'catalogo.json'
            public.write_text(json.dumps({'videos': [{'id': 'a', 'upload_date': '2024-01-01'}, {'id': 'b', 'upload_date': None}]}))
            self.assertEqual(publication_dates(root, public), {'a': '2024-01-01'})
            (root / 'metadati').mkdir()
            (root / 'metadati/date-pubblicazione-video.json').write_text(json.dumps({'dates': {'a': {'upload_date': '2025-01-01'}, 'b': {'upload_date': 'bad'}}}))
            self.assertEqual(publication_dates(root, public), {'a': '2025-01-01'})
