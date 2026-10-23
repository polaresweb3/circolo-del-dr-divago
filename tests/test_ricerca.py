"""Controlli su testi sintetici: nessun contenuto del canale in queste prove."""
import functools
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import ricerca
from avvia_sito import PreviewHandler


class CaptionTests(unittest.TestCase):
    def test_rolling_captions_preserve_new_words(self):
        text = 'WEBVTT\n\n00:00.000 --> 00:01.000\nUna frase\n\n00:01.000 --> 00:02.000\nUna frase nuova\n\n00:02.000 --> 00:03.000\nnuova &amp; chiara\n'
        cues = ricerca.parse_captions(text)
        self.assertEqual(' '.join(c['text'] for c in cues), 'Una frase nuova & chiara')
        self.assertEqual(cues[-1]['start'], 2)

    def test_srt_and_inline_vtt_tags(self):
        cues = ricerca.parse_captions('1\n00:01:02,400 --> 00:01:04,500\n<c>Un testo</c> <00:01:03.000>temporizzato\n')
        self.assertEqual(cues, [{'start': 62.4, 'end': 64.5, 'text': 'Un testo temporizzato'}])

    def test_authorized_import_preserves_repeated_words(self):
        cues = ricerca.parse_captions('1\n00:00:01,000 --> 00:00:02,000\nSì.\n\n2\n00:00:04,000 --> 00:00:05,000\nSì.\n', deduplicate=False)
        self.assertEqual([c['text'] for c in cues], ['Sì.', 'Sì.'])

    def test_invalid_caption_data_is_rejected(self):
        for text in ('WEBVTT\n\n', '00:00.200 --> 00:00.100\nTesto'):
            with self.assertRaises(ValueError):
                ricerca.parse_captions(text)
        with self.assertRaises(ValueError):
            ricerca.validate_cues([{'start': 2, 'end': 1, 'text': 'Errore'}])

    def test_homonymous_books_need_author_context(self):
        bibliography = [{'id': 'a', 'title': 'Destra e sinistra', 'author': 'Norberto Bobbio'},
                        {'id': 'b', 'title': 'Destra e sinistra', 'author': 'Domenico Conversa'}]
        cues = [{'start': 21, 'end': 30, 'text': 'Bobbio ha scritto Destra e sinistra.'}]
        self.assertEqual([m['book_id'] for m in ricerca.book_matches(cues, bibliography)], ['a'])
        self.assertEqual(ricerca.book_matches([{'start': 0, 'end': 1, 'text': 'Destra e sinistra.'}], bibliography), [])

    def test_bundle_identity_and_timestamps(self):
        bundle = ricerca.transcript_bundle('abcdefghijk', 'it', 'Prova sintetica',
            [{'start': 0.125, 'end': 1.5, 'text': 'Testo creato per questa prova.'}], 'Testo nostro', 'prova.vtt')
        self.assertIn(b'00:00:00.125 --> 00:00:01.500', bundle['vtt'])
        self.assertEqual(json.loads(bundle['json'])['video_id'], 'abcdefghijk')
        with self.assertRaises(ValueError):
            ricerca.transcript_bundle('abcdefghijk', '../../it', 'Prova', [], '', '')


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / 'archivio'
        (self.archive / 'metadati').mkdir(parents=True)
        (self.root / 'sito/dist/data').mkdir(parents=True)
        (self.archive / 'metadati/canale.json').write_text(json.dumps({'entries': [
            {'id': 'abcdefghijk', 'title': 'Prova sintetica', 'duration': 3},
            {'id': 'ABCDEFGHIJK', 'title': '=titolo non affidabile', 'duration': 4}]}))
        (self.root / 'sito/dist/data/libri.json').write_text('[]')
        self.root_patch = patch.object(ricerca, 'ROOT', self.root)
        self.root_patch.start()
        self.source = self.root / 'prova.vtt'
        self.source.write_text('WEBVTT\n\n00:00.000 --> 00:03.000\nFrase sintetica scritta per il test.\n')

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_private_import_and_public_metadata(self):
        saved = ricerca.import_transcript(self.archive, self.source, 'abcdefghijk', 'it', 'Testo sintetico di nostra creazione')
        self.assertEqual(set(saved['formats']), {'txt', 'json', 'vtt'})
        for relative in saved['formats'].values():
            self.assertTrue((self.archive / relative).exists())
            self.assertFalse((self.archive / relative).is_relative_to(self.root / 'sito/dist'))
        public = (self.root / 'sito/dist/data/ricerca.json').read_text()
        self.assertNotIn('Frase sintetica', public)
        self.assertNotIn('Testo sintetico di nostra creazione', public)
        self.assertEqual(json.loads(public)['counts']['transcripts_saved'], 1)
        self.assertIn("'=titolo", (self.archive / 'ricerca/indice.csv').read_text())
        with self.assertRaises(ValueError):
            ricerca.import_transcript(self.archive, self.source, 'abcdefghijk', 'it', 'Secondo tentativo')

    def test_mismatched_video_does_not_import(self):
        self.source = self.root / 'prova.json'
        self.source.write_text(json.dumps({'video_id': 'ABCDEFGHIJK', 'language': 'it',
            'segments': [{'start': 0, 'end': 1, 'text': 'Prova sintetica'}]}))
        with self.assertRaises(ValueError):
            ricerca.import_transcript(self.archive, self.source, 'abcdefghijk', 'it', 'Testo nostro')
        self.assertFalse((self.archive / 'trascrizioni-autorizzate/manifest.json').exists())

    def test_rate_limit_stops_and_resume_skips_completed(self):
        index = ricerca.make_index(self.archive)
        index['videos'][0]['analysis_status'] = 'caption_analyzed'
        ricerca.save_index(self.archive, index)
        with patch.object(ricerca, 'fetch_for_analysis', side_effect=ricerca.RateLimited()) as fetch:
            result = ricerca.run_analysis(self.archive)
        fetch.assert_called_once_with('ABCDEFGHIJK')
        self.assertEqual(result['videos'][0]['analysis_status'], 'caption_analyzed')
        self.assertEqual(result['videos'][1]['analysis_status'], 'rate_limited')
        with patch.object(ricerca, 'fetch_for_analysis') as fetch:
            ricerca.run_analysis(self.archive)
        fetch.assert_not_called()


class DownloadTests(unittest.TestCase):
    setUp = ArchiveTests.setUp
    tearDown = ArchiveTests.tearDown

    def test_loopback_download_and_path_restrictions(self):
        ricerca.import_transcript(self.archive, self.source, 'abcdefghijk', 'it', 'Testo nostro')
        handler = functools.partial(PreviewHandler, directory=str(self.root / 'sito/dist'), archive=self.archive)
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with urllib.request.urlopen(base + '/trascrizioni/abcdefghijk/it.txt') as response:
                self.assertEqual(response.status, 200)
                self.assertIn('attachment;', response.headers['Content-Disposition'])
                self.assertIn('Frase sintetica', response.read().decode())
            for route in ('/trascrizioni/ABCDEFGHIJK/it.txt', '/trascrizioni/abcdefghijk/../../metadati/canale.json',
                          '/archivio/trascrizioni-autorizzate/manifest.json'):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base + route)
                self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()


if __name__ == '__main__':
    unittest.main()
