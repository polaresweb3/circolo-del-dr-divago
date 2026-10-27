"""Test privati della proposta: fixture sintetiche, mai contenuti del filmato."""
import copy
import contextlib
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SHADOW = Path(__file__).resolve().parent
ROOT = (next(parent for parent in SHADOW.parents if (parent / 'divago.py').is_file())
        if (SHADOW / 'fonti_schede.py').is_file() else SHADOW.parent)
sys.path.insert(0, str(ROOT))
if (SHADOW / 'fonti_schede.py').is_file():
    sys.path.insert(0, str(SHADOW))
from PIL import Image
import fonti_schede
import aggiorna_schede
from aggiorna_schede import integrate
from sito_pages import video_content


class BrowserSourceTests(unittest.TestCase):
    ident = 'browser-fixture'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'metadata'
        self.work.mkdir()
        self.base = self.root / 'archivio/analisi-visive' / self.ident
        self.base.mkdir(parents=True)
        (self.base / 'fullpage-native').mkdir()
        self.frames = []
        self.native = []
        for seconds in (0, 10, 195):
            name = f'frame-{seconds:03d}.png'
            frame = self.base / 'fullpage-native' / name
            Image.new('RGB', (320, 240), color=(seconds, 10, 20)).save(frame)
            self.frames.append(dict(seconds=seconds, relative_path='fullpage-native/' + name,
                                    sha256=self.sha(frame)))
            self.native.append(dict(file=name, time=seconds, targetSecond=seconds, readyState=4))
        self.duration = [dict(row, duration=199.721) for row in self.native[:1]]
        self.save(self.base / 'fullpage-native/manifest.json', self.native)
        self.save(self.base / 'manifest-browser.json', self.duration)
        self.document = dict(video_id=self.ident, source_type='analisi_fotogrammi_browser',
            source_sha256=self.bundle(), source_capture_sha256=self.bundle(),
            source_hash_scope='campione_screenshot_browser_non_video_originale',
            source_video_sha256=None, video_duration_seconds=199.721, language='it',
            language_scope='lingua_delle_osservazioni_non_del_sonoro',
            human_audio_review=False, human_visual_review=True, partial_visual_sampling=True,
            review_status='fotogrammi_letti_con_copertura_parziale', frames=self.frames,
            observations=[dict(start=frame['seconds'], end=frame['seconds'],
                               text='Osservazione sintetica di test.', frame_indexes=[i])
                          for i, frame in enumerate(self.frames)],
            capture_provenance=dict(source_url='https://www.youtube.com/watch?v=' + self.ident,
                capture_method='browser_fullpage_native', original_video_bytes_available=False,
                ffprobe=None, native_manifest_relative_path='fullpage-native/manifest.json',
                native_manifest_sha256=self.sha(self.base / 'fullpage-native/manifest.json'),
                duration_manifest_relative_path='manifest-browser.json',
                duration_manifest_sha256=self.sha(self.base / 'manifest-browser.json')))
        self.record = dict(source_type='analisi_fotogrammi_browser',
            relative_path=f'{self.ident}/fonte.json', source_capture_sha256=self.bundle(),
            source_video_sha256=None, original_asr_json_sha256=None,
            human_audio_review=False, human_visual_review=True,
            review_status='selezionata_dopo_lettura_fotogrammi')
        self.save(self.root / 'archivio/inventario.json', dict(videos=[dict(
            video_id=self.ident, duration_seconds=200, video=dict(status='missing'))]))
        data = self.root / 'sito/dist/data'
        data.mkdir(parents=True)
        self.save(data / 'catalogo.json', dict(videos=[dict(id=self.ident, duration=200, title='Fixture')]))
        self.addCleanup(patch.stopall)
        patch.object(fonti_schede, 'ROOT', self.root).start()
        patch.object(fonti_schede, 'WORK', self.work).start()
        self.fetch = patch.object(fonti_schede, 'fetch_for_analysis',
                                 side_effect=AssertionError('Network/fallback forbidden')).start()
        self.select()

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def save(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

    def bundle(self):
        payload = [{key: frame[key] for key in ('seconds', 'relative_path', 'sha256')}
                   for frame in self.frames]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()

    def select(self):
        self.save(self.base / 'fonte.json', self.document)
        self.record['json_sha256'] = self.sha(self.base / 'fonte.json')
        self.save(self.work / 'fonti-visive-selezionate.json', dict(sources={self.ident: self.record}))

    def source(self):
        return fonti_schede.read_source(self.ident)

    def reject(self):
        self.select()
        with self.assertRaises(ValueError):
            self.source()
        self.fetch.assert_not_called()

    def test_valid_browser_with_missing_media_and_asr(self):
        source = self.source()
        self.assertEqual(source['source_type'], 'analisi_fotogrammi_browser')
        self.assertIsNone(source['source_video_sha256'])
        self.assertEqual(source['source_capture_sha256'], self.bundle())
        coverage = fonti_schede.coverage(source, 200)
        self.assertNotEqual(coverage['source_sha256'], coverage['source_capture_sha256'])
        self.assertNotIn('audio_duration_analyzed', coverage)
        self.assertIn('Campionamento visivo parziale', coverage['scope'])
        self.assertIn('browser', coverage['scope'])
        self.fetch.assert_not_called()

    def test_frame_tamper_fails_without_fallback(self):
        Image.new('RGB', (320, 240), 'white').save(self.base / self.frames[0]['relative_path'])
        self.reject()

    def test_native_jpeg_payload_is_preserved_without_conversion(self):
        path = self.base / self.frames[0]['relative_path']
        Image.new('RGB', (320, 240), 'blue').save(path, format='JPEG')
        self.frames[0]['sha256'] = self.sha(path)
        self.frames[0]['image_format'] = 'JPEG'
        self.document['source_sha256'] = self.document['source_capture_sha256'] = self.record['source_capture_sha256'] = self.bundle()
        self.select()
        self.assertEqual(self.source()['source_type'], 'analisi_fotogrammi_browser')
        self.fetch.assert_not_called()

    def test_unsupported_or_misdeclared_native_format_is_rejected(self):
        path = self.base / self.frames[0]['relative_path']
        Image.new('RGB', (320, 240), 'blue').save(path, format='GIF')
        self.frames[0]['sha256'] = self.sha(path)
        self.document['source_sha256'] = self.document['source_capture_sha256'] = self.record['source_capture_sha256'] = self.bundle()
        self.reject()
        Image.new('RGB', (320, 240), 'blue').save(path, format='JPEG')
        self.frames[0]['sha256'] = self.sha(path)
        self.frames[0]['image_format'] = 'PNG'
        self.document['source_sha256'] = self.document['source_capture_sha256'] = self.record['source_capture_sha256'] = self.bundle()
        self.reject()

    def test_manifest_tamper_fails_without_fallback(self):
        self.save(self.base / 'fullpage-native/manifest.json', [])
        self.reject()

    def test_changed_manifest_even_with_refreshed_hash_must_match_frames(self):
        self.native[0]['time'] = 1
        self.save(self.base / 'fullpage-native/manifest.json', self.native)
        self.document['capture_provenance']['native_manifest_sha256'] = self.sha(self.base / 'fullpage-native/manifest.json')
        self.reject()

    def test_fake_remote_video_sha_is_rejected(self):
        for where in (self.document, self.record):
            where['source_video_sha256'] = self.bundle()
            self.reject()
            where['source_video_sha256'] = None

    def test_frame_traversal_is_rejected(self):
        outside = self.base.parent / 'frame-000.png'
        outside.write_bytes((self.base / self.frames[0]['relative_path']).read_bytes())
        self.frames[0]['relative_path'] = '../frame-000.png'
        self.document['source_sha256'] = self.document['source_capture_sha256'] = self.record['source_capture_sha256'] = self.bundle()
        self.reject()

    def test_manifest_traversal_is_rejected(self):
        self.document['capture_provenance']['native_manifest_relative_path'] = '../manifest.json'
        self.reject()

    def test_duration_and_frame_boundaries(self):
        for duration in (float('nan'), True, 0, 190, 201.1):
            self.document['video_duration_seconds'] = duration
            self.reject()
        self.document['video_duration_seconds'] = 199.721
        self.frames[-1]['seconds'] = 199.721
        self.reject()

    def test_invalid_observation_indices_and_range(self):
        for mutation in (dict(frame_indexes=[]), dict(frame_indexes=[3]),
                         dict(frame_indexes=[True]), dict(start=1, end=2), dict(text='')):
            previous = copy.deepcopy(self.document['observations'][0])
            self.document['observations'][0].update(mutation)
            self.reject()
            self.document['observations'][0] = previous

    def test_duration_ui_and_url_and_no_probe_are_guarded(self):
        for key, value in [('source_url', 'https://example.com/other'),
                           ('ffprobe', {'duration_seconds':199.721}),
                           ('original_video_bytes_available', True),
                           ('capture_method', 'recomposed_image')]:
            provenance = self.document['capture_provenance']
            previous = provenance[key]
            provenance[key] = value
            self.reject()
            provenance[key] = previous
        self.duration[0]['duration'] = 198
        self.save(self.base / 'manifest-browser.json', self.duration)
        self.document['capture_provenance']['duration_manifest_sha256'] = self.sha(self.base / 'manifest-browser.json')
        self.reject()

    def test_bundle_and_source_document_tamper_are_rejected(self):
        self.document['source_capture_sha256'] = 'a'*64
        self.reject()
        self.document['source_capture_sha256'] = self.bundle()
        self.select()
        (self.base / 'fonte.json').write_text('{}')
        with self.assertRaises(ValueError):self.source()
        self.fetch.assert_not_called()

    def test_asr_conflict_and_unacknowledged_scope_rejected(self):
        for key, value in [('human_audio_review', True), ('human_visual_review', False),
                           ('partial_visual_sampling', False), ('source_hash_scope', 'video')]:
            previous = self.document[key]
            self.document[key] = value
            self.reject()
            self.document[key] = previous
        self.save(self.work / 'fonti-locali-selezionate.json', dict(sources={self.ident:{}}))
        self.reject()

    def card(self):
        return fonti_schede.make_card(self.ident, 'Sintesi sintetica di test.', ['a','b','c'],
            [(s, 'Passo di test', 'Descrizione di test.') for s in (0,10,195)])

    def test_make_card_integrate_and_banner_are_partial_and_audio_false(self):
        card = self.card()
        self.assertEqual(card['source_type'], 'analisi_fotogrammi_browser')
        self.assertEqual(card['editorial_status'], 'scheda_descrittiva_da_fotogrammi')
        self.assertFalse(card['human_audio_review'])
        self.assertTrue(all(p['human_audio_review'] is False for p in card['passages']))
        self.assertTrue(all(p['verification'] == 'riscontro_visivo' for p in card['passages']))
        self.assertIn('parziale', card['analysis_notes'][0])
        result, books = integrate([], [], [card], [], [dict(id=self.ident,duration=200,title='Fixture')])
        self.assertEqual(result, [card]);self.assertEqual(books, [])
        html = video_content(card, [])
        self.assertIn('alcune immagini del filmato', html)
        self.assertIn('Il sonoro non è verificato', html)
        self.assertIn('le didascalie visibili non attestano le parole pronunciate', html)
        self.assertNotIn('Minutaggi ricavati da testi automatici', html)
        self.assertNotIn('fullpage-native', html)
        self.fetch.assert_not_called()

    def test_main_indexes_browser_as_frames_not_audio_in_temporary_root(self):
        card = self.card()
        data = self.root / 'sito/dist/data'
        self.save(data / 'schede.json', [])
        self.save(data / 'libri.json', [])
        batch = self.root / 'batch.json'
        self.save(batch, [card])
        index = dict(videos=[dict(video_id=self.ident)])
        with patch.object(aggiorna_schede, 'ROOT', self.root), \
             patch.object(sys, 'argv', ['aggiorna_schede.py', str(batch)]), \
             patch('ricerca.make_index', return_value=index), \
             patch('ricerca.save_index') as save_index, \
             contextlib.redirect_stdout(io.StringIO()):
            aggiorna_schede.main()
        row = save_index.call_args.args[1]['videos'][0]
        self.assertEqual(row['analysis_status'], 'frames_analyzed')
        self.assertEqual(row['analysis_method'], 'editorial_browser_frame_sampling')
        self.assertFalse(row['audio_review_complete'])
        self.assertIn('browser', row['analysis_scope'])
        self.assertNotIn('audio_analyzed', str(row))
        self.fetch.assert_not_called()

    def test_integration_rejects_fake_video_hash_and_missing_capture_provenance(self):
        card = self.card()
        for mutation in (dict(source_video_sha256='b'*64), dict(source_capture_sha256='short'), dict(source_capture_sha256='z'*64),
                         dict(source_hash_scope='video'), dict(capture_method='other'),
                         dict(audio_duration_analyzed=199.721)):
            previous = copy.deepcopy(card['source_coverage'])
            card['source_coverage'].update(mutation)
            with self.assertRaises(ValueError):integrate([], [], [card], [], [dict(id=self.ident,duration=200,title='Fixture')])
            card['source_coverage'] = previous


if __name__ == '__main__':
    unittest.main()
