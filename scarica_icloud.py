#!/usr/bin/env python3
"""Scarica il catalogo audio e i dieci video con scheda; copia in iCloud per lotti."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from archivio_tools import write_json, deferred_ids
from divago import ROOT, entries, read_catalog, scan_media

ARCHIVE = ROOT / 'archivio'
STATE = ARCHIVE / 'stato'
DEST = Path.home() / 'Library/Mobile Documents/com~apple~CloudDocs/Archivio-Dr-Divago'
STATUS = STATE / 'scaricamento-icloud.json'
TEXT = ROOT / 'STATO-SCARICAMENTO.txt'
STOP = STATE / 'ferma-scaricamento-icloud'


def targets():
    cards = json.loads((ROOT / 'sito/dist/data/schede.json').read_text())
    videos = list(dict.fromkeys(c['video_id'] for c in cards))[:10]
    audio = list(dict.fromkeys(videos + [v['id'] for v in entries(read_catalog(ARCHIVE))]))
    return audio, videos


def update(phase, detail=''):
    audio, videos = targets()
    saved_audio = scan_media(ARCHIVE / 'audio', {'.mp3'})
    saved_video = scan_media(ARCHIVE / 'video', {'.mp4', '.mkv', '.webm', '.mov'})
    record = {'updated_at': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(),
              'phase': phase, 'detail': detail, 'destination': str(DEST),
              'audio_saved': sum(i in saved_audio for i in audio), 'audio_target': len(audio),
              'video_saved': sum(i in saved_video for i in videos), 'video_target': len(videos),
              'remote_upload_confirmed': False, 'originals_deleted': False}
    write_json(STATUS, record)
    TEXT.write_text('CIRCOLO DEL DR DIVAGO — SCARICAMENTO ICLOUD\n\n'
        + 'Fase: ' + phase + '\n' + detail + '\n'
        + 'Audio completati: {audio_saved}/{audio_target}\nVideo completati: {video_saved}/{video_target}\n'.format(**record)
        + '\nDestinazione: ' + str(DEST)
        + '\nI file completati sono copiati e verificati per lotti. L’upload remoto va controllato nel Finder.\n'
        + 'I file locali originali sono conservati.\n'
        + 'Per una pausa dopo il lotto corrente: doppio clic su Ferma scaricamento.command.\n'
        + 'Resoconto dettagliato: archivio/logs/scaricamento-icloud.log\n', encoding='utf-8')


def copy():
    update('copia in iCloud', 'Copia dei media verificati; gli originali restano sul Mac.')
    return subprocess.run([sys.executable, '-B', str(ROOT / 'gestisci_archivio.py'),
                           'copia', '--dest', str(DEST)], cwd=ROOT).returncode


def review_only_failure(kind, ids):
    """Isola file dubbi o che richiedono accesso; gli errori di rete restano distinti."""
    try:
        path = STATE / ('ultimo-download-' + kind + '.json')
        last = json.loads((path if path.exists() else STATE / 'ultimo-download.json').read_text())
        data = json.loads((ARCHIVE / 'inventario.json').read_text())
        failures = set(last['failures'])
        rows = {row['video_id']: row for row in data['videos']}
        return (last['kind'] == kind and last['requested_ids'] == ids
                and not last.get('stopped') and bool(failures) and failures.issubset(ids)
                and all(rows[ident][kind]['status'] == 'needs_review'
                        or ident in deferred_ids(ARCHIVE, kind) for ident in failures))
    except (OSError, ValueError, KeyError, TypeError):
        return False


def pending_verification(audio, videos):
    data = json.loads((ARCHIVE / 'inventario.json').read_text())
    rows = {row['video_id']: row for row in data['videos']}
    return [kind + ':' + ident for kind, ids in [('audio', audio), ('video', videos)]
            for ident in ids if rows.get(ident, {}).get(kind, {}).get('status') != 'verified']


def batch(kind, ids):
    if STOP.exists() or (kind == 'video' and (STATE / 'ferma-scaricamento-video').exists()):
        update('in pausa', 'Pausa richiesta. Nessun altro lotto viene avviato.')
        return False
    update('download ' + kind, 'Lotto di {} file. ID: {}'.format(len(ids), ', '.join(ids)))
    result = subprocess.run([sys.executable, '-B', str(ROOT / 'divago.py'), kind,
                             *['--ids=' + ident for ident in ids]], cwd=ROOT).returncode
    copied = copy()
    if result == 1 and not copied and review_only_failure(kind, ids):
        print('File da verificare o con accesso richiesto lasciati in sospeso; continuo con gli altri.', flush=True)
        return True
    if result or copied:
        update('da controllare', 'Il lotto o la copia non è stato completato. Consulta archivio/logs/scaricamento-icloud.log; i file riusciti sono conservati.')
        return False
    return True


def run():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'scaricamento-icloud.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Scaricamento iCloud già in corso.')
        if STOP.exists():
            update('in pausa', 'Rimuovi il segnale di pausa prima di riprendere.')
            return
        audio, videos = targets()
        # Completa prima il campione di dieci contributi, poi continua gli altri audio.
        sample_audio = [i for i in videos if i not in scan_media(ARCHIVE / 'audio', {'.mp3'}) and i not in deferred_ids(ARCHIVE, 'audio')]
        if sample_audio and not batch('audio', sample_audio):
            return
        sample_video = [i for i in videos if i not in scan_media(ARCHIVE / 'video', {'.mp4', '.mkv', '.webm', '.mov'}) and i not in deferred_ids(ARCHIVE, 'video')]
        if sample_video and not batch('video', sample_video):
            return
        while True:
            present = scan_media(ARCHIVE / 'audio', {'.mp3'})
            deferred = deferred_ids(ARCHIVE, 'audio')
            remaining = [i for i in audio if i not in present and i not in deferred]
            if not remaining:
                if copy() == 0:
                    pending = pending_verification(audio, videos)
                    if pending:
                        update('verifiche da completare', 'Download terminati; {} file non ancora verificati, esclusi dalla copia. Consulta archivio/inventario.json.'.format(len(pending)))
                    else:
                        update('download completati', 'Tutti i file richiesti sono salvati localmente e copiati nella cartella iCloud. Verifica il completamento della sincronizzazione Apple.')
                else:
                    update('da controllare', 'Download completati; copia finale da controllare.')
                return
            if not batch('audio', remaining[:10]):
                return


def show_status():
    active = False
    lock_path = STATE / 'scaricamento-icloud.lock'
    if lock_path.exists():
        with lock_path.open('a+') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                active = True
    print('Processo attivo.' if active else 'Processo fermo. Per riprendere usa Riprendi scaricamento.command.')
    if STATUS.exists():
        print(TEXT.read_text(encoding='utf-8') if TEXT.exists() else STATUS.read_text())
    else:
        print('Nessuno scaricamento iCloud registrato.')


if __name__ == '__main__':
    if '--status' in sys.argv:
        show_status()
        raise SystemExit(0)
    try:
        run()
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        update('interrotto', str(exc))
        raise
