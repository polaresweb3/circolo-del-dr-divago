import unittest

from aggiorna_schede import integrate


class BibliographyIntegrationTest(unittest.TestCase):
    def inputs(self):
        books = [{'id': 'opera', 'title': 'Opera', 'author': 'Autore', 'edition_cited': None,
                  'status': 'citazione_esplicita',
                  'mentions': [{'video_id': 'precedente', 'seconds': 12, 'verification': 'identificazione_probabile'}]}]
        card = {'video_id': 'nuovo', 'title': 'Video', 'summary': 'Sintesi originale.',
                'duration_seconds': 90, 'language': 'it',
                'topics': ['a', 'b', 'c'], 'human_audio_review': False,
                'source_type': 'sottotitoli_automatici_youtube',
                'source_coverage': {'source_sha256': 'abc', 'segments_read': 5, 'last_end': 89},
                'passages': [{'seconds': s, 'human_audio_review': False} for s in (0, 30, 60)],
                'books': [{'book_id': 'opera', 'seconds': 35, 'title_seconds': 36,
                           'evidence': 'Titolo nel testo automatico.', 'confidence': 'riscontro_testuale',
                           'verified': False, 'human_audio_review': False}]}
        return books, card, [{'id': 'nuovo', 'duration': 90, 'title': 'Video'}]

    def test_shared_book_preserves_all_previous_references_and_uncertainties(self):
        books, card, videos = self.inputs()
        cards, updated = integrate([], books, [card], [], videos)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]['mentions'][0], books[0]['mentions'][0])
        self.assertEqual([m['video_id'] for m in updated[0]['mentions']], ['precedente', 'nuovo'])
        self.assertFalse(updated[0]['mentions'][1]['verified'])
        self.assertEqual(len(books[0]['mentions']), 1)  # Gli input non sono modificati.
        again_cards, again_books = integrate(cards, updated, [card], [], videos)
        self.assertEqual((again_cards, again_books), (cards, updated))

    def test_title_only_reference_gains_timestamp_without_losing_origin(self):
        books, card, videos = self.inputs()
        original = {'video_id': 'nuovo', 'seconds': None, 'evidence': 'video_title', 'verified': False}
        books[0]['mentions'].append(original)
        _, updated = integrate([], books, [card], [], videos)
        mentions = updated[0]['mentions']
        self.assertEqual(len(mentions), 2)
        self.assertEqual(mentions[1]['seconds'], 35)
        self.assertEqual(mentions[1]['previous_evidence'], original)

    def test_missing_book_fails_before_mutating_existing_data(self):
        books, card, videos = self.inputs()
        card['books'][0]['book_id'] = 'sconosciuto'
        with self.assertRaisesRegex(ValueError, 'registrare'):
            integrate([], books, [card], [], videos)
        self.assertEqual(len(books[0]['mentions']), 1)


if __name__ == '__main__':
    unittest.main()
