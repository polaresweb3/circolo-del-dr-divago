import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from trascrivi_audio import bundle, cached, save_bundle, select_videos


class PrivateTranscriptTest(unittest.TestCase):
    def test_next_batch_skips_completed_and_speechless_media_before_limit(self):
        videos = [{'id': ident, 'audio_saved': True} for ident in ('saved', 'music', 'next', 'last')]
        manifest = {'items': [{'video_id': 'saved'}],
                    'skipped': [{'video_id': 'music', 'status': 'no_speech_detected'}]}
        self.assertEqual([v['id'] for v in select_videos(videos, None, manifest, 1)], ['next'])
        self.assertEqual([v['id'] for v in select_videos(videos, ['saved'], manifest)], ['saved'])

    def test_duration_order_selects_shortest_pending_audio_before_limit(self):
        videos = [{'id': ident, 'audio_saved': True, 'duration': duration}
                  for ident, duration in [('long', 900), ('done', 10), ('short', 40)]]
        manifest = {'items': [{'video_id': 'done'}]}
        selected = select_videos(videos, None, manifest, 1, order='duration')
        self.assertEqual([v['id'] for v in selected], ['short'])

    def test_three_formats_are_saved_and_resume_rejects_a_changed_audio(self):
        video = {'id': 'abcdefghijk', 'title': 'Titolo di prova',
                 'url': 'https://www.youtube.com/watch?v=abcdefghijk'}
        cues = [{'start': 0, 'end': 2, 'text': 'Testo sintetico di prova.'}]
        digest = hashlib.sha256(b'audio sintetico').hexdigest()
        contents = bundle(video, cues, {'source_sha256': digest, 'language': 'it'})
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / video['id']
            save_bundle(target, contents)
            self.assertEqual(len(list(target.iterdir())), 3)
            document = cached(target, digest)
            self.assertEqual(document['segments'][0]['text'], cues[0]['text'])
            self.assertFalse(document['publication_authorized'])
            self.assertTrue(document['local_only'])
            with self.assertRaisesRegex(ValueError, 'Audio cambiato'):
                cached(target, 'impronta-diversa')
            with self.assertRaisesRegex(ValueError, 'sovrascrittura'):
                save_bundle(target, contents)
            self.assertEqual(json.loads((target / 'trascrizione.json').read_text()), document)


if __name__ == '__main__':
    unittest.main()
