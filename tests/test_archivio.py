"""Prove di integrità, copie e coda usando file sintetici, senza download."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import archivio_tools as archive
import divago
import gestisci_archivio


class ArchiveWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'lavoro'
        (self.source / 'metadati').mkdir(parents=True)
        (self.source / 'audio').mkdir()
        (self.source / 'video').mkdir()
        self.catalog = {'entries': [{'id': 'abcdefghijk', 'title': '=Titolo sintetico', 'duration': 3},
                                    {'id': 'ABCDEFGHIJK', 'title': 'Secondo esempio', 'duration': 4},
                                    {'id': 'abcdefghijl', 'title': 'Terzo esempio', 'duration': 4}]}
        (self.source / 'metadati/canale.json').write_text(json.dumps(self.catalog))
        self.media = self.source / 'audio/Prova [abcdefghijk].mp3'
        self.media.write_bytes(b'media sintetico originale')
        self.probe = patch.object(archive, 'probe_media', return_value={'duration_seconds': 3, 'streams': [{'codec_type': 'audio'}]})
        self.probe.start()

    def tearDown(self):
        self.probe.stop()
        self.temp.cleanup()

    def test_inventory_excludes_partials_and_escapes_csv_formulas(self):
        (self.source / 'video/Prova [ABCDEFGHIJK].mkv.part').write_bytes(b'incompleto')
        data = archive.inventory(self.source)
        self.assertEqual(data['counts'], {'audio': 1, 'video': 0})
        self.assertIn("'=Titolo", (self.source / 'inventario.csv').read_text())
        self.assertEqual(len(data['videos'][0]['audio']['sha256']), 64)

    def test_audio_and_video_can_run_together_without_duplicate_same_kind(self):
        with archive.archive_lock(self.source, name='download-audio'):
            with archive.archive_lock(self.source, name='download-video'):
                with archive.archive_lock(self.source):
                    pass
            with self.assertRaises(ValueError):
                with archive.archive_lock(self.source, name='download-audio'):
                    self.fail('Due download audio contemporanei non consentiti')

    def test_inventory_never_verifies_a_file_still_being_processed(self):
        (self.source / 'stato').mkdir()
        marker = self.source / 'stato/attivo-audio.json'
        marker.write_text(json.dumps({'pid': os.getpid(), 'video_id': 'abcdefghijk'}))
        result = archive.inventory(self.source)
        self.assertEqual(result['videos'][0]['audio']['status'], 'in_progress')
        self.assertEqual(result['counts']['audio'], 0)
        marker.unlink()
        self.assertEqual(archive.inventory(self.source)['counts']['audio'], 1)

    def test_local_budget_includes_cloud_copy_and_pauses_without_deleting(self):
        cloud = self.root / 'icloud'
        cloud.mkdir()
        (cloud / 'copia.mp3').write_bytes(b'copia cloud')
        archive.write_json(self.source / 'stato/limite-spazio.json',
                           {'cloud_directory': str(cloud), 'limit_bytes': 1000000})
        used = archive.local_budget(self.source)['used_bytes']
        self.assertGreaterEqual(used, self.media.stat().st_size + (cloud / 'copia.mp3').stat().st_size)
        with self.assertRaises(ValueError):
            archive.enforce_budget(self.source, additional=1000000)
        self.assertTrue((self.source / 'stato/ferma-scaricamento-icloud').exists())
        self.assertTrue(self.media.exists())
        self.assertTrue((cloud / 'copia.mp3').exists())

    def test_recheck_detects_changes_and_preserves_original_hash(self):
        before = archive.inventory(self.source)['videos'][0]['audio']['sha256']
        self.media.write_bytes(b'contenuto modificato')
        record = archive.inventory(self.source, rehash=True)['videos'][0]['audio']
        self.assertEqual(record['status'], 'needs_review')
        self.assertEqual(record['sha256'], before)
        self.assertNotEqual(record['actual_sha256'], before)

    def test_copy_is_repeatable_keeps_originals_and_does_not_claim_cloud_upload(self):
        data = archive.inventory(self.source)
        destination = self.root / 'copia'
        report = archive.copy_verified(self.source, destination, data)
        target = destination / 'audio' / self.media.name
        self.assertEqual(archive.sha256(target), archive.sha256(self.media))
        self.assertTrue(self.media.exists())
        self.assertFalse(report['remote_upload_confirmed'])
        repeat = archive.copy_verified(self.source, destination, data)
        self.assertEqual(repeat['files_copied'], 0)
        self.assertEqual(repeat['files_already_equal'], 1)
        self.assertEqual(len(list((destination / 'indici').iterdir())), 2)

    def test_copy_does_not_replace_conflicting_destination(self):
        data = archive.inventory(self.source)
        destination = self.root / 'copia'
        target = destination / 'audio' / self.media.name
        target.parent.mkdir(parents=True)
        target.write_bytes(b'altra copia da conservare')
        with self.assertRaises(FileExistsError):
            archive.copy_verified(self.source, destination, data)
        self.assertEqual(target.read_bytes(), b'altra copia da conservare')

    def test_copy_rejects_source_changed_after_inventory(self):
        data = archive.inventory(self.source)
        self.media.write_bytes(b'cambiato dopo il controllo')
        destination = self.root / 'copia'
        with self.assertRaises(ValueError):
            archive.copy_verified(self.source, destination, data)
        self.assertFalse((destination / 'audio' / self.media.name).exists())

    def test_copy_rejects_nested_destination(self):
        with self.assertRaises(ValueError):
            archive.copy_verified(self.source, self.source / 'backup', archive.inventory(self.source))

    def test_dry_run_skips_existing_before_applying_limit(self):
        args = SimpleNamespace(archive=self.source, command='audio', all=True, ids=None, limit=1, dry_run=True)
        output = io.StringIO()
        with patch.object(divago, 'run_download_command') as run, redirect_stdout(output):
            divago.download(args)
        run.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['video_ids'], ['ABCDEFGHIJK'])
        self.assertFalse((self.source / 'logs').exists())

    def test_http_429_stops_before_next_video(self):
        args = SimpleNamespace(archive=self.source, command='audio', all=True, ids=None, limit=10, dry_run=False)
        with patch.object(divago, 'run_download_command', return_value=(1, True)) as run, patch.object(divago, 'report'), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                divago.download(args)
        self.assertEqual(run.call_count, 1)
        self.assertTrue((self.source / 'stato/pausa-download.json').exists())
        with patch.object(divago, 'run_download_command') as run:
            with self.assertRaises(ValueError):
                divago.download(args)
            run.assert_not_called()

    def test_http_403_retries_only_once_and_records_the_attempt(self):
        folder = self.source / 'logs'
        folder.mkdir()
        command = ['yt-dlp', '--extract-audio', 'https://www.youtube.com/watch?v=ABCDEFGHIJK']
        def fail(command, log):
            log.write('ERROR: unable to download video data: HTTP Error 403: Forbidden\n')
            return 1, False
        with (folder / 'retry.log').open('w', encoding='utf-8') as log, \
                patch.object(divago, 'run_download_command', side_effect=fail) as run, \
                patch.object(divago.time, 'sleep') as sleep, redirect_stdout(io.StringIO()):
            self.assertEqual(divago.run_download_with_recovery(command, log), (1, False))
            self.assertEqual(run.call_count, 2)
            self.assertEqual(divago.run_download_with_recovery(command, log), (1, False))
            self.assertEqual(run.call_count, 3)
            sleep.assert_called_once_with(10)
        data = json.loads((self.source / 'stato/riprese-403.json').read_text())
        self.assertEqual(data['audio:ABCDEFGHIJK']['attempts'], 1)
        self.assertEqual(data['audio:ABCDEFGHIJK']['status'], 'retry_failed')

    def test_http_403_does_not_retry_during_other_queue_rate_limit(self):
        folder = self.source / 'logs'
        folder.mkdir()
        command = ['yt-dlp', '--extract-audio', 'https://www.youtube.com/watch?v=ABCDEFGHIJK']
        def limited_elsewhere(command, log):
            log.write('HTTP Error 403\n')
            archive.write_json(self.source / 'stato/pausa-download.json', {'retry_after': '2099-01-01T00:00:00+00:00'})
            return 1, False
        with (folder / 'retry.log').open('w', encoding='utf-8') as log, \
                patch.object(divago, 'run_download_command', side_effect=limited_elsewhere) as run, \
                patch.object(divago.time, 'sleep') as sleep:
            self.assertEqual(divago.run_download_with_recovery(command, log), (1, False))
            run.assert_called_once()
            sleep.assert_not_called()

    def test_curated_videos_have_priority_without_repeating_existing_media(self):
        data = archive.inventory(self.source)
        (self.root / 'sito/dist/data').mkdir(parents=True)
        (self.root / 'sito/dist/data/schede.json').write_text(json.dumps([{'video_id': 'abcdefghijl'}, {'video_id': 'abcdefghijk'}]))
        with patch.object(gestisci_archivio, 'ROOT', self.root):
            self.assertEqual(gestisci_archivio.next_batch(data, 'audio', 1), ['abcdefghijl'])


if __name__ == '__main__':
    unittest.main()
