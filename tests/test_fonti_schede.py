import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fonti_schede


class SelectedLocalSourceTests(unittest.TestCase):
    ident = 'abcdefghijk'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'metadata'
        self.work.mkdir()
        self.original = self.root / 'archivio/trascrizioni-locali' / self.ident / 'trascrizione.json'
        self.original.parent.mkdir(parents=True)
        self.old = dict(video_id=self.ident, language='he',
                        audio_duration_seconds=10, segments=[dict(start=0, end=1, text='Old source')])
        self.original.write_text(json.dumps(self.old))
        self.original_bytes = self.original.read_bytes()
        self.target = self.original.parent / 'rielaborazioni/en/trascrizione.json'
        self.target.parent.mkdir(parents=True)
        self.new = dict(video_id=self.ident, language='en', audio_duration_seconds=10,
                        source_type='riconoscimento_vocale_locale', human_audio_review=False,
                        language_forced=True, source_sha256='a' * 64,
                        original_json_sha256=self.digest(self.original),
                        segments=[dict(start=0, end=9, text='Recovered coherent source')])
        self.record = dict(relative_path=f'{self.ident}/rielaborazioni/en/trascrizione.json',
                           original_json_sha256=self.digest(self.original),
                           source_audio_sha256='a' * 64, human_audio_review=False,
                           review_status='selezionata_dopo_lettura_integrale_testuale')
        self.addCleanup(patch.stopall)
        patch.object(fonti_schede, 'ROOT', self.root).start()
        patch.object(fonti_schede, 'WORK', self.work).start()
        self.remote = patch.object(fonti_schede, 'fetch_for_analysis',
                                   side_effect=AssertionError('Unexpected remote access')).start()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def select(self, content=None, record=None, ident=None):
        self.target.write_text(json.dumps(content if content is not None else self.new))
        entry = copy.deepcopy(record if record is not None else self.record)
        entry['json_sha256'] = self.digest(self.target)
        (self.work / 'fonti-locali-selezionate.json').write_text(json.dumps(
            dict(schema_version=1, sources={ident or self.ident: entry})))

    def test_original_used_without_registry(self):
        result = fonti_schede.read_source(self.ident)
        self.assertEqual(result['cues'], self.old['segments'])
        self.assertEqual(result['language'], 'he')
        self.remote.assert_not_called()

    def test_unrelated_selection_does_not_change_source(self):
        self.select(ident='other_video')
        self.assertEqual(fonti_schede.read_source(self.ident)['cues'], self.old['segments'])

    def test_selected_alternative_preserves_original_and_automatic_status(self):
        self.select()
        result = fonti_schede.read_source(self.ident)
        self.assertEqual(result['cues'], self.new['segments'])
        self.assertEqual(result['language'], 'en')
        self.assertTrue(result['language_forced'])
        self.assertEqual(result['source_type'], 'riconoscimento_vocale_locale')
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        self.assertEqual(fonti_schede.coverage(result, 10)['segments_read'], 1)
        self.remote.assert_not_called()

    def test_changed_alternative_is_rejected(self):
        self.select()
        self.target.write_text(json.dumps(dict(self.new, language='it')))
        with self.assertRaises(ValueError):
            fonti_schede.read_source(self.ident)
        self.remote.assert_not_called()

    def test_changed_original_is_rejected(self):
        self.select()
        self.original.write_text(json.dumps(dict(self.old, language='en')))
        with self.assertRaises(ValueError):
            fonti_schede.read_source(self.ident)

    def test_path_outside_reprocessing_tree_is_rejected(self):
        for relative in ('/tmp/trascrizione.json', f'{self.ident}/trascrizione.json',
                         f'{self.ident}/rielaborazioni/../../elsewhere/trascrizione.json'):
            with self.subTest(relative=relative):
                self.select(record=dict(self.record, relative_path=relative))
                with self.assertRaises(ValueError):
                    fonti_schede.read_source(self.ident)

    def test_wrong_video_is_rejected_even_with_matching_file_hash(self):
        self.select(content=dict(self.new, video_id='other_video'))
        with self.assertRaises(ValueError):
            fonti_schede.read_source(self.ident)

    def test_human_review_claim_is_rejected_even_with_matching_hash(self):
        self.select(content=dict(self.new, human_audio_review=True))
        with self.assertRaises(ValueError):
            fonti_schede.read_source(self.ident)

    def test_empty_alternative_is_rejected(self):
        self.select(content=dict(self.new, segments=[]))
        with self.assertRaises(ValueError):
            fonti_schede.read_source(self.ident)

    def select_aligned(self):
        parent = self.root / 'archivio/trascrizioni-locali/parentvideo/trascrizione.json'
        parent.parent.mkdir(parents=True)
        parent.write_text(json.dumps(dict(video_id='parentvideo',
            source_type='riconoscimento_vocale_locale', human_audio_review=False,
            segments=[dict(start=0, end=3, text='Crosses the boundary'),
                      dict(start=3, end=8, text='Contained words'),
                      dict(start=8, end=15, text='Crosses the end boundary')])) )
        content = dict(self.new, source_variant='derivazione_asr_da_audio_allineato',
                       new_asr_run=False, segments=[dict(start=1, end=6, text='Contained words')],
                       derivation=dict(parent_video_id='parentvideo',
                           parent_json_relative_path='parentvideo/trascrizione.json',
                           parent_json_sha256=self.digest(parent),
                           timestamp_offset_subtracted_seconds=2))
        self.select(content=content)
        return parent, content

    def test_aligned_source_preserves_words_and_excludes_boundary_segments(self):
        _, content = self.select_aligned()
        result = fonti_schede.read_source(self.ident)
        self.assertEqual(result['cues'], content['segments'])
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        coverage = fonti_schede.coverage(result, 10)
        self.assertFalse(coverage['source_alignment']['new_asr_run'])
        self.assertIn('Tempi traslati', coverage['scope'])

    def test_aligned_source_rejects_changed_parent_even_if_child_is_untouched(self):
        parent, _ = self.select_aligned()
        parent.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Fonte madre'):
            fonti_schede.read_source(self.ident)

    def test_aligned_source_rejects_invented_words_even_with_new_child_hash(self):
        _, content = self.select_aligned()
        content['segments'][0]['text'] = 'Unrecognized added words'
        self.select(content=content)
        with self.assertRaisesRegex(ValueError, 'Segmenti non corrispondenti'):
            fonti_schede.read_source(self.ident)


if __name__ == '__main__':
    unittest.main()
