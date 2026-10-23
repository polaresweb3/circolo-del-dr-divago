#!/usr/bin/env python3
"""Coda video completa, parallela alla coda audio; copie e inventari coordinati."""
import json
import os
from pathlib import Path
import subprocess
import sys

from archivio_tools import archive_lock, now, write_json, deferred_ids
from divago import ROOT, entries, read_catalog, scan_media
from scarica_icloud import DEST, STOP, review_only_failure

ARCHIVE = ROOT / 'archivio'
STATE = ARCHIVE / 'stato'
STATUS = STATE / 'scaricamento-video-icloud.json'
VIDEO_STOP = STATE / 'ferma-scaricamento-video'


def update(phase, detail='', ids=()):
    present = scan_media(ARCHIVE / 'video', {'.mkv', '.mp4', '.webm', '.mov'})
    targets = [v['id'] for v in entries(read_catalog(ARCHIVE))]
    write_json(STATUS, {'updated_at': now(), 'pid': os.getpid(), 'phase': phase,
                       'detail': detail, 'video_saved': sum(i in present for i in targets),
                       'video_target': len(targets), 'batch_ids': list(ids),
                       'destination': str(DEST), 'remote_upload_confirmed': False})


def run():
    with archive_lock(ARCHIVE, name='scaricamento-video-icloud'):
        update('avvio', 'In attesa di completare eventuali operazioni precedenti.')
        # Consente al lotto audio già avviato con il vecchio blocco globale di finire.
        with archive_lock(ARCHIVE, wait=True):
            pass
        targets = [v['id'] for v in entries(read_catalog(ARCHIVE))]
        while True:
            if STOP.exists() or VIDEO_STOP.exists():
                update('in pausa', 'Pausa richiesta: nessun altro lotto viene avviato.')
                return
            present = scan_media(ARCHIVE / 'video', {'.mkv', '.mp4', '.webm', '.mov'})
            deferred = deferred_ids(ARCHIVE, 'video')
            ids = [i for i in targets if i not in present and i not in deferred][:10]
            if ids:
                update('download video', 'Lotto video in parallelo agli audio.', ids)
                result = subprocess.run([sys.executable, '-B', str(ROOT / 'divago.py'), 'video',
                                         *['--ids=' + i for i in ids]], cwd=ROOT).returncode
            else:
                result = 0
            update('copia in iCloud', 'Copia dei file verificati; originali conservati.', ids)
            copied = subprocess.run([sys.executable, '-B', str(ROOT / 'gestisci_archivio.py'),
                                     'copia', '--dest', str(DEST)], cwd=ROOT).returncode
            if copied or (result and not (result == 1 and review_only_failure('video', ids))):
                update('da controllare', 'Errore nel lotto video o nella copia. Consulta il registro video.', ids)
                return
            if not ids:
                data = json.loads((ARCHIVE / 'inventario.json').read_text())
                pending = [r['video_id'] for r in data['videos'] if r['video']['status'] != 'verified']
                update('verifiche da completare' if pending else 'download completati',
                       f'{len(pending)} video da verificare.' if pending else
                       'Tutti i video verificati e copiati nella cartella iCloud; upload Apple da confermare.')
                return


if __name__ == '__main__':
    if '--status' in sys.argv:
        try:
            with archive_lock(ARCHIVE, name='scaricamento-video-icloud'):
                print('Coda video ferma.')
        except ValueError:
            print('Coda video attiva.')
        print(STATUS.read_text() if STATUS.exists() else 'Nessuna coda video registrata.')
        raise SystemExit(0)
    try:
        run()
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        update('interrotto', str(exc))
        raise
