import json
from pathlib import Path
import unittest
from dati_pubblici import public_dataset, source_urls

ROOT = Path(__file__).resolve().parents[1]


class PublicDataTests(unittest.TestCase):
    def test_work_notes_are_removed_without_mutating_source(self):
        source = [{'video_id': 'example', 'title': 'Titolo', 'summary': 'Sintesi',
                   'analysis_notes': ['Da rivedere'], 'source_coverage': {'segments': [1]},
                   'verified': False, 'human_audio_review': False, 'partial_visual_sampling': True,
                   'contextual_verification_sources': [{'label': 'Fonte', 'url': 'https://example.org'}],
                   'passages': [{'seconds': 12, 'label': 'Tema', 'verified': False, 'source_type': 'interno'}],
                   'books': [{'book_id': 'book', 'seconds': 20, 'confidence': 'identificazione_probabile',
                              'evidence': 'Attribuzione probabile', 'reason': 'Aggiungere al catalogo'}]}]
        before = json.dumps(source)
        exported = public_dataset('schede.json', source)
        self.assertEqual(before, json.dumps(source))
        self.assertNotIn('analysis_notes', exported[0])
        self.assertNotIn('source_coverage', exported[0])
        self.assertNotIn('reason', exported[0]['books'][0])
        self.assertFalse(exported[0]['verified'])
        self.assertFalse(exported[0]['human_audio_review'])
        self.assertTrue(exported[0]['partial_visual_sampling'])
        self.assertEqual(source[0]['contextual_verification_sources'], exported[0]['contextual_verification_sources'])
        self.assertEqual('identificazione_probabile', exported[0]['books'][0]['confidence'])

    def test_real_books_preserve_sources_uncertainties_and_image_credits(self):
        source = json.loads((ROOT / 'sito/dist/data/libri.json').read_text())
        exported = public_dataset('libri.json', source)
        self.assertEqual(len(source), len(exported))
        for original, public in zip(source, exported):
            for key in ('id', 'title', 'author', 'status', 'source', 'references', 'bibliographic_verified', 'edition_cited'):
                self.assertEqual(original[key], public[key])
            for key in ('src', 'source_page', 'edition_confirmed_in_video', 'credit', 'image_credit',
                        'credit_line', 'copyright_credit', 'license', 'license_url', 'rights', 'rights_note', 'license_note'):
                if key in original['cover']:
                    self.assertEqual(original['cover'][key], public['cover'][key])
            self.assertEqual(len(original['mentions']), len(public['mentions']))
            for old, new in zip(original['mentions'], public['mentions']):
                for key in ('video_id', 'seconds', 'title_seconds', 'note', 'verification', 'human_audio_review', 'verified'):
                    if key in old:
                        self.assertEqual(old[key], new[key])
            self.assertNotIn('asset_sha256', public['cover'])
            self.assertNotIn('visual_review', public['cover'])

    def test_real_cards_preserve_references_passages_and_reliability(self):
        source = json.loads((ROOT / 'sito/dist/data/schede.json').read_text())
        exported = public_dataset('schede.json', source)
        self.assertEqual(len(source), len(exported))
        for old, new in zip(source, exported):
            for key in ('video_id', 'title', 'summary', 'duration_seconds', 'references', 'contextual_verification_sources',
                        'verified', 'human_audio_review', 'human_visual_review', 'partial_visual_sampling'):
                if key in old:
                    self.assertEqual(old[key], new[key])
            self.assertEqual(len(old['passages']), len(new['passages']))
            self.assertEqual(len(old['books']), len(new['books']))
            for a, b in zip(old['books'], new['books']):
                for key in ('book_id', 'seconds', 'title_seconds', 'evidence', 'confidence', 'verified', 'human_audio_review', 'references'):
                    if key in a:
                        self.assertEqual(a[key], b[key])

    def test_sources_inside_work_notes_remain_public_as_links(self):
        source = [{'video_id': 'example', 'passages': [], 'books': [],
                   'analysis_notes': ['Da controllare: https://example.org/source.']}]
        exported = public_dataset('schede.json', source)[0]
        self.assertNotIn('analysis_notes', exported)
        self.assertEqual([{'label': 'example.org', 'url': 'https://example.org/source'}], exported['verification_sources'])
        for name in ('libri.json', 'schede.json'):
            rows = json.loads((ROOT / 'sito/dist/data' / name).read_text())
            for before, after in zip(rows, public_dataset(name, rows)):
                self.assertEqual(source_urls(before), source_urls(after))

    def test_export_is_idempotent(self):
        for name in ('libri.json', 'schede.json'):
            source = json.loads((ROOT / 'sito/dist/data' / name).read_text())
            once = public_dataset(name, source)
            self.assertEqual(once, public_dataset(name, once))


if __name__ == '__main__':
    unittest.main()
