"""Le fonti visive devono restare attribuibili ai singoli fotogrammi."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fonti_schede
from aggiorna_schede import integrate
from sito_pages import video_content
import tests.test_aggiorna_schede as integration_fixture


class VisualSourceTests(unittest.TestCase):
    ident = 'nuovo'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'metadata'
        self.work.mkdir()
        self.base = self.root / 'archivio/analisi-visive' / self.ident
        self.base.mkdir(parents=True)
        self.frame = self.base / 'frame.png'
        self.frame.write_bytes(b'fixture frame bytes, never an exported image')
        self.document = dict(video_id=self.ident, source_type='analisi_fotogrammi_locali',
                             source_sha256='a' * 64, video_duration_seconds=90,
                             language='it', language_scope='lingua_delle_osservazioni_non_del_sonoro',
                             human_audio_review=False, human_visual_review=True,
                             partial_visual_sampling=True,
                             review_status='fotogrammi_letti_con_copertura_parziale',
                             frames=[dict(seconds=4, relative_path='frame.png',
                                          sha256=self.digest(self.frame))],
                             observations=[dict(start=4, end=4, text='Una scritta visibile.',
                                                frame_indexes=[0])])
        self.record = dict(relative_path=f'{self.ident}/fonte.json',
                           source_video_sha256='a' * 64, original_asr_json_sha256=None,
                           human_audio_review=False,
                           review_status='selezionata_dopo_lettura_fotogrammi')
        self.original = self.root / 'archivio/trascrizioni-locali' / self.ident / 'trascrizione.json'
        inventory = dict(videos=[dict(video_id=self.ident, video=dict(
            sha256='a' * 64, probe=dict(duration_seconds=90)))])
        (self.root / 'archivio/inventario.json').write_text(json.dumps(inventory))
        self.addCleanup(patch.stopall)
        patch.object(fonti_schede, 'ROOT', self.root).start()
        patch.object(fonti_schede, 'WORK', self.work).start()
        self.remote = patch.object(fonti_schede, 'fetch_for_analysis',
                                   side_effect=AssertionError('Unexpected network')).start()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def select(self):
        target = self.base / 'fonte.json'
        target.write_text(json.dumps(self.document))
        self.record['json_sha256'] = self.digest(target)
        (self.work / 'fonti-visive-selezionate.json').write_text(json.dumps(
            dict(sources={self.ident: self.record})))

    def source(self):
        self.select()
        return fonti_schede.read_source(self.ident)

    def test_visual_coverage_never_claims_audio_or_continuous_viewing(self):
        source = self.source()
        coverage = fonti_schede.coverage(source, 90)
        self.assertEqual(source['source_type'], 'analisi_fotogrammi_locali')
        self.assertEqual(source['cues'][0]['text'], 'Una scritta visibile.')
        self.assertNotIn('audio_duration_analyzed', coverage)
        self.assertTrue(coverage['partial_visual_sampling'])
        self.assertEqual(coverage['frame_times_seconds'], [4])
        self.assertIn('non visione continua', coverage['scope'])
        self.remote.assert_not_called()

    def test_original_automatic_source_is_preserved_and_changes_are_detected(self):
        self.original.parent.mkdir(parents=True)
        self.original.write_text('{"original": true}')
        original_bytes = self.original.read_bytes()
        self.record['original_asr_json_sha256'] = self.digest(self.original)
        self.source()
        self.assertEqual(self.original.read_bytes(), original_bytes)
        self.original.write_text('{"original": false}')
        with self.assertRaisesRegex(ValueError, 'ASR precedente'):
            fonti_schede.read_source(self.ident)

    def test_tampered_observation_document_is_rejected(self):
        self.source()
        (self.base / 'fonte.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Fonte visiva modificata'):
            fonti_schede.read_source(self.ident)

    def test_tampered_frame_is_rejected(self):
        self.source()
        self.frame.write_bytes(b'different image')
        with self.assertRaisesRegex(ValueError, 'Fotogramma'):
            fonti_schede.read_source(self.ident)

    def test_outside_frame_path_is_rejected_even_with_valid_hash(self):
        outside = self.base.parent / 'other.png'
        outside.write_bytes(self.frame.read_bytes())
        self.document['frames'][0]['relative_path'] = '../other.png'
        with self.assertRaisesRegex(ValueError, 'Fotogramma'):
            self.source()

    def test_wrong_video_or_unacknowledged_partial_scope_is_rejected(self):
        for key, value in [('video_id', 'wrong'), ('partial_visual_sampling', False),
                           ('human_audio_review', True), ('human_visual_review', False)]:
            with self.subTest(key=key):
                before = self.document[key]
                self.document[key] = value
                with self.assertRaises(ValueError):
                    self.source()
                self.document[key] = before

    def test_other_video_media_hash_is_rejected(self):
        self.document['source_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'Impronta del video'):
            self.source()

    def test_visual_and_asr_selections_cannot_ambiguously_override_each_other(self):
        self.select()
        (self.work / 'fonti-locali-selezionate.json').write_text(json.dumps(
            dict(sources={self.ident: {}})))
        with self.assertRaisesRegex(ValueError, 'Due fonti selezionate'):
            fonti_schede.read_source(self.ident)

    def test_duration_must_match_the_inventoried_video(self):
        self.document['video_duration_seconds'] = 900
        with self.assertRaisesRegex(ValueError, 'Durata visiva'):
            self.source()

    def test_observation_must_point_to_a_frame_in_its_time_interval(self):
        for mutation in [dict(frame_indexes=[]), dict(frame_indexes=[5]),
                         dict(start=7, end=8), dict(text='')]:
            with self.subTest(mutation=mutation):
                old = copy.deepcopy(self.document['observations'][0])
                self.document['observations'][0].update(mutation)
                with self.assertRaisesRegex(ValueError, 'Osservazione'):
                    self.source()
                self.document['observations'][0] = old

    def test_integration_accepts_bounded_visual_source_without_invented_audio(self):
        books, card, videos = integration_fixture.BibliographyIntegrationTest.inputs(self)
        card['source_type'] = 'analisi_fotogrammi_locali'
        card['source_coverage'] = fonti_schede.coverage(self.source(), 90)
        result, library = integrate([], books, [card], [], videos)
        self.assertEqual(result[0]['source_type'], 'analisi_fotogrammi_locali')
        self.assertEqual(library[0]['mentions'][0], books[0]['mentions'][0])
        self.assertFalse(library[0]['mentions'][1]['human_audio_review'])
        del card['source_coverage']['partial_visual_sampling']
        with self.assertRaisesRegex(ValueError, 'Copertura visiva'):
            integrate([], books, [card], [], videos)

    def test_visual_page_discloses_scope_without_automatic_transcript_claim(self):
        card = dict(video_id=self.ident, duration_seconds=90, title='Video',
                    summary='Descrizione circoscritta.', books=[], passages=[],
                    source_type='analisi_fotogrammi_locali')
        html = video_content(card, [])
        self.assertIn('campionamento parziale', html)
        self.assertIn('senza ascolto del sonoro', html)
        self.assertIn('Il contenuto del filmato', html)
        self.assertNotIn('Minutaggi ricavati da testi automatici', html)
        card['source_type'] = 'riconoscimento_vocale_locale'
        self.assertIn('Minutaggi ricavati da testi automatici', video_content(card, []))


if __name__ == '__main__':
    unittest.main()
