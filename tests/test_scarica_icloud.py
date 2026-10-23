import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import divago
import scarica_icloud as worker


class CloudWorkerTests(unittest.TestCase):
    def test_access_restricted_file_can_be_deferred_without_claiming_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'stato').mkdir()
            (root / 'stato/ultimo-download-audio.json').write_text(json.dumps({
                'kind': 'audio', 'requested_ids': ['abcdefghijk'],
                'failures': ['abcdefghijk'], 'stopped': None}))
            (root / 'inventario.json').write_text(json.dumps({'videos': [
                {'video_id': 'abcdefghijk', 'audio': {'status': 'missing'}}]}))
            with patch.object(worker, 'ARCHIVE', root), patch.object(worker, 'STATE', root / 'stato'):
                self.assertFalse(worker.review_only_failure('audio', ['abcdefghijk']))
                (root / 'stato/download-rinviati.json').write_text(json.dumps({
                    'audio': {'abcdefghijk': {'reason': 'age_restricted'}}}))
                self.assertTrue(worker.review_only_failure('audio', ['abcdefghijk']))
                self.assertEqual(worker.pending_verification(['abcdefghijk'], []), ['audio:abcdefghijk'])

    def test_isolated_review_can_continue_but_rate_limit_cannot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'stato').mkdir()
            last = {'kind': 'audio', 'requested_ids': ['abcdefghijk'],
                    'failures': ['abcdefghijk'], 'stopped': None}
            (root / 'stato/ultimo-download.json').write_text(json.dumps(last))
            (root / 'inventario.json').write_text(json.dumps({'videos': [
                {'video_id': 'abcdefghijk', 'audio': {'status': 'needs_review'}}]}))
            with patch.object(worker, 'ARCHIVE', root), patch.object(worker, 'STATE', root / 'stato'):
                self.assertTrue(worker.review_only_failure('audio', ['abcdefghijk']))
                self.assertFalse(worker.review_only_failure('audio', ['differentid']))
                last['stopped'] = 'YouTube HTTP 429'
                (root / 'stato/ultimo-download.json').write_text(json.dumps(last))
                self.assertFalse(worker.review_only_failure('audio', ['abcdefghijk']))

    def test_unverified_files_prevent_completion_even_when_present(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'inventario.json').write_text(json.dumps({'videos': [
                {'video_id': 'abcdefghijk', 'audio': {'status': 'needs_review'},
                 'video': {'status': 'verified'}}]}))
            with patch.object(worker, 'ARCHIVE', root):
                self.assertEqual(worker.pending_verification(['abcdefghijk'], ['abcdefghijk']),
                                 ['audio:abcdefghijk'])

    def test_batch_preserves_ids_starting_with_hyphen_through_cli(self):
        ids = ['1ZnNXVl_l8I', '-5PRCHDGiU8', 'Pifjoex6eHI']

        def parse_command(command, **kwargs):
            # Usa il vero parser del programma figlio, senza rete né media.
            with patch('sys.argv', [*command[2:], '--dry-run']), patch.object(divago, 'download') as download:
                divago.main()
                self.assertEqual(download.call_args.args[0].ids, ids)
            return Mock(returncode=0)

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(worker, 'STOP', Path(folder) / 'absent'), patch.object(worker, 'update'), \
                    patch.object(worker.subprocess, 'run', side_effect=parse_command), \
                    patch.object(worker, 'copy', return_value=0):
                self.assertTrue(worker.batch('audio', ids))

    def test_pause_prevents_new_downloads(self):
        with tempfile.TemporaryDirectory() as folder:
            stop = Path(folder) / 'stop'
            stop.touch()
            with patch.object(worker, 'STOP', stop), patch.object(worker, 'update'), patch.object(worker.subprocess, 'run') as run:
                self.assertFalse(worker.batch('audio', ['abcdefghijk']))
                run.assert_not_called()

    def test_video_only_pause_keeps_audio_downloads_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            (state / 'ferma-scaricamento-video').touch()
            with patch.object(worker, 'STATE', state), patch.object(worker, 'STOP', state / 'absent'), \
                    patch.object(worker, 'update'), patch.object(worker, 'copy', return_value=0), \
                    patch.object(worker.subprocess, 'run', return_value=Mock(returncode=0)) as run:
                self.assertFalse(worker.batch('video', ['abcdefghijk']))
                run.assert_not_called()
                self.assertTrue(worker.batch('audio', ['abcdefghijk']))
                self.assertEqual(run.call_args.args[0][3], 'audio')

    def test_download_failure_still_copies_successful_files_and_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(worker, 'STOP', Path(folder) / 'absent'), patch.object(worker, 'update'), \
                    patch.object(worker.subprocess, 'run', return_value=Mock(returncode=1)), \
                    patch.object(worker, 'copy', return_value=0) as copy:
                self.assertFalse(worker.batch('audio', ['abcdefghijk']))
                copy.assert_called_once_with()

    def test_copy_failure_stops_next_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(worker, 'STOP', Path(folder) / 'absent'), patch.object(worker, 'update'), \
                    patch.object(worker.subprocess, 'run', return_value=Mock(returncode=0)), \
                    patch.object(worker, 'copy', return_value=1):
                self.assertFalse(worker.batch('video', ['abcdefghijk']))


if __name__ == '__main__':
    unittest.main()
