#!/usr/bin/env python3
"""Menu per preparare download a lotti e copie dell’archivio, senza pubblicazioni."""
import argparse
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
import sys

from archivio_tools import archive_lock, copy_verified, estimates, inventory, write_json
from divago import ROOT


def prepare(archive, rehash=False):
    with archive_lock(archive):
        data = inventory(archive, rehash=rehash)
        config_path = archive / 'stato/config-cloud.json'
        cloud = json.loads(config_path.read_text()) if config_path.exists() else {}
        active = False
        worker_lock = archive / 'stato/scaricamento-icloud.lock'
        if worker_lock.exists():
            with worker_lock.open('a+') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    active = True
        plan = {'phase': 'preparazione', 'batch_size': 10, 'order': ['audio', 'video', 'copia_cloud', 'copia_disco_esterno'],
                'cloud': cloud or 'Da scegliere; suggerimento: Google Drive 2 TB, oppure iCloud+ già disponibile.',
                'cloud_upload_active': None if cloud else False, 'cloud_copy_active': active,
                'automatic_download_active': active,
                **estimates(archive, data), 'verified': data['counts'], 'needs_review': data['needs_review']}
        write_json(archive / 'stato/piano-archivio.json', plan)
    print('\nARCHIVIO DEL CIRCOLO DEL DR DIVAGO')
    print('Verificati: {audio} audio · {video} video'.format(**data['counts']))
    print('Da controllare:', data['needs_review'])
    print('Catalogo:', plan['catalogued'], 'video · Spazio locale libero:', plan['local_free_GB'], 'GB')
    print('Audio totali stimati:', plan['audio_total_GB'], 'GB')
    if plan['video_estimate_GB'] is not None:
        print('Video totali: circa', plan['video_estimate_GB'], 'GB, estrapolati da', plan['video_sample_count'], 'file.')
        print('Per pianificare, considera margine fino al doppio della stima.')
    print('Inventario: ' + str(archive / 'inventario.csv'))
    return data


def next_batch(data, kind, size=10):
    priority_file = ROOT / 'sito/dist/data/schede.json'
    priority = [c['video_id'] for c in json.loads(priority_file.read_text())] if priority_file.exists() else []
    indexed = {r['video_id']: r for r in data['videos']}
    ordered = list(dict.fromkeys(priority + [r['video_id'] for r in data['videos']]))
    return [ident for ident in ordered if ident in indexed and indexed[ident][kind]['status'] == 'missing'][:size]


def download_batch(archive, kind):
    data = prepare(archive)
    chosen = next_batch(data, kind)
    if not chosen:
        print('Nessun nuovo file da scaricare per questa categoria.')
        return
    print('\nLotto:', len(chosen), kind, '· prima i video con scheda già redatta.')
    subprocess.run([sys.executable, '-B', str(ROOT / 'divago.py'), kind,
                    '--archive', str(archive), '--ids', *chosen], check=True)
    prepare(archive)


def folder_input():
    raw = input('Trascina qui la cartella cloud/disco, oppure scrivi il percorso: ').strip()
    if not raw:
        raise ValueError('Nessuna cartella selezionata.')
    if Path(raw).expanduser().exists():
        return Path(raw).expanduser()
    parts = shlex.split(raw)
    if len(parts) != 1:
        raise ValueError('Seleziona una sola cartella; puoi trascinarla dal Finder.')
    return Path(parts[0]).expanduser()


def copy_archive(archive, destination):
    with archive_lock(archive, wait=True):
        data = inventory(archive)
        report = copy_verified(archive, destination, data)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('\nCopia nella cartella controllata. Se è una cartella cloud, attendi la conferma di sincronizzazione del servizio.')
    print('Gli originali sul Mac sono conservati. Nessun file viene cancellato automaticamente.')


def menu(archive):
    print('Circolo del Dr Divago — archivio locale → cloud → disco esterno')
    while True:
        print('\n1  Riepilogo e piano (senza scaricare)\n2  Scarica i prossimi 10 audio\n3  Scarica i prossimi 10 video\n4  Verifica di nuovo impronte e file\n5  Copia i completati nel cloud o su disco\n6  Leggi la guida per domani\n0  Esci')
        choice = input('\nScegli un numero: ').strip()
        try:
            if choice == '0':
                return
            if choice == '1':
                prepare(archive)
            elif choice in ('2', '3'):
                download_batch(archive, 'audio' if choice == '2' else 'video')
            elif choice == '4':
                prepare(archive, rehash=True)
            elif choice == '5':
                base = folder_input()
                destination = base if base.name == 'Archivio-Dr-Divago' else base / 'Archivio-Dr-Divago'
                print('Destinazione:', destination)
                if input('Scrivi COPIA per avviare la copia verificata: ').strip() == 'COPIA':
                    copy_archive(archive, destination)
            elif choice == '6':
                print((ROOT / 'ARCHIVIO-DOMANI.txt').read_text(encoding='utf-8'))
            else:
                print('Scegli una voce del menu.')
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            print('\nOperazione interrotta:', exc)
        except KeyboardInterrupt:
            print('\nInterrotto: puoi riprendere dal menu.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['menu', 'prepara', 'verifica', 'copia'], default='menu')
    parser.add_argument('--archive', type=Path, default=ROOT / 'archivio')
    parser.add_argument('--dest', type=Path)
    args = parser.parse_args()
    archive = args.archive.expanduser().resolve()
    try:
        if args.command == 'menu':
            menu(archive)
        elif args.command in ('prepara', 'verifica'):
            prepare(archive, rehash=args.command == 'verifica')
        elif args.dest:
            copy_archive(archive, args.dest)
        else:
            parser.error('Per copia serve --dest /percorso/Archivio-Dr-Divago')
    except (ValueError, OSError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        raise SystemExit('Operazione non completata: ' + str(exc)) from exc


if __name__ == '__main__':
    main()
