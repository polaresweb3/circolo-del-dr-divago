#!/usr/bin/env python3
"""Trascrive gli audio locali con il modello già installato, senza servizi esterni.

Questi testi automatici sono materiale privato di lavoro. Non sono importazioni
autorizzate alla distribuzione e non vengono inseriti nella cartella del sito.
"""
import argparse
import fcntl
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from divago import ROOT, write_json
from ricerca import stamp, validate_cues


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def bundle(video, cues, provenance):
    cues = validate_cues(cues)
    document = dict(provenance, schema_version=1, video_id=video['id'],
                    title=video['title'], url=video['url'], segments=cues,
                    human_audio_review=False, review_status='automatico_da_rivedere',
                    local_only=True, publication_authorized=False)
    header = (video['title'] + '\n' + video['url'] + '\n'
              'Trascrizione automatica locale · da rivedere · uso privato\n\n')
    plain = header + '\n'.join(f"[{stamp(c['start'])}] {c['text']}" for c in cues) + '\n'
    vtt = 'WEBVTT\n\n' + '\n\n'.join(
        f"{n}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}"
        for n, c in enumerate(cues, 1)) + '\n'
    return {'json': json.dumps(document, ensure_ascii=False, indent=2) + '\n',
            'txt': plain, 'vtt': vtt}


def cached(target, source_hash):
    if not target.exists():
        return None
    path = target / 'trascrizione.json'
    if not path.is_file():
        raise ValueError(f'Cartella incompleta, da controllare: {target}')
    saved = json.loads(path.read_text())
    if saved.get('source_sha256') != source_hash:
        raise ValueError(f'Audio cambiato: non sovrascrivo la trascrizione {target.name}')
    validate_cues(saved.get('segments'))
    for extension in ('txt', 'vtt'):
        if not (target / ('trascrizione.' + extension)).is_file():
            raise ValueError(f'Formato mancante nella trascrizione {target.name}')
    return saved


def save_bundle(target, contents):
    if target.exists():
        raise ValueError('Trascrizione già presente; nessuna sovrascrittura.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.trascrizione-', dir=target.parent) as temporary:
        stage = Path(temporary) / 'completa'
        stage.mkdir()
        for extension, content in contents.items():
            (stage / ('trascrizione.' + extension)).write_text(content, encoding='utf-8')
        stage.rename(target)


def select_videos(videos, ids, manifest, limit=None, order='catalog'):
    by_id = {video['id']: video for video in videos}
    if ids and set(ids) - set(by_id):
        raise ValueError('ID non presente nel catalogo.')
    completed = {item['video_id'] for item in manifest.get('items', [])}
    examined = completed | {item['video_id'] for item in manifest.get('skipped', [])}
    selected = [by_id[ident] for ident in ids] if ids else [
        video for video in videos if video['id'] not in examined and video.get('audio_saved')]
    if order == 'duration' and not ids:
        selected.sort(key=lambda video: video.get('duration') or 0)
    return selected[:limit] if limit is not None else selected


def run(args):
    # Importazioni pesanti solo all'avvio dell'analisi, non per consultare --help.
    import numpy as np
    from faster_whisper import WhisperModel
    import faster_whisper

    archive = args.archive.resolve()
    destination = archive / 'trascrizioni-locali'
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / '.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Una trascrizione locale è già in corso.')
        videos = json.loads((ROOT / 'sito/dist/data/catalogo.json').read_text())['videos']
        if args.pending_cards and not args.ids:
            prepared = {card['video_id'] for card in json.loads((ROOT / 'sito/dist/data/schede.json').read_text())}
            videos = [video for video in videos if video['id'] not in prepared]
        manifest_path = destination / 'manifest.json'
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
            'schema_version': 1, 'local_only': True, 'items': []}
        items = {item['video_id']: item for item in manifest['items']}
        skipped = {item['video_id']: item for item in manifest.get('skipped', [])}
        requested = select_videos(videos, args.ids, manifest, args.limit, args.order)
        models = sorted((archive / 'modelli/models--Systran--faster-whisper-small/snapshots').glob('*'))
        if not models:
            raise ValueError('Modello locale small non trovato; nessun download automatico.')
        model = None
        stop = destination / 'FERMA'
        for number, video in enumerate(requested, 1):
            if stop.exists():
                print('Interruzione richiesta. Le trascrizioni completate sono conservate.', flush=True)
                break
            ident = video['id']
            source = (archive / 'audio' / Path(video.get('audio_file', '')).name).resolve()
            if not source.is_file() or not source.is_relative_to((archive / 'audio').resolve()):
                print(f'Audio locale assente: {ident}', flush=True)
                continue
            digest = sha256(source)
            target = destination / ident
            document = cached(target, digest)
            if document is None:
                if model is None:
                    model = WhisperModel(str(models[-1]), device='cpu', compute_type='int8',
                                         cpu_threads=args.threads, num_workers=1, local_files_only=True)
                print(f'[{number}/{len(requested)}] {ident}: {video["title"]}', flush=True)
                started = now()
                with tempfile.TemporaryDirectory(prefix='divago-pcm-') as temporary:
                    pcm = Path(temporary) / 'audio.f32'
                    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source),
                                    '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', str(pcm)],
                                   check=True, capture_output=True)
                    audio = np.memmap(pcm, dtype=np.float32, mode='r')
                    audio_duration = len(audio) / 16000
                    stream, info = model.transcribe(
                        audio, language=args.language, beam_size=args.beam_size, best_of=1,
                        condition_on_previous_text=False, vad_filter=True,
                        vad_parameters={'min_silence_duration_ms': 700})
                    cues = []
                    for segment in stream:
                        if segment.text.strip():
                            cues.append({'start': round(segment.start, 3), 'end': round(segment.end, 3),
                                         'text': segment.text.strip()})
                    del audio
                if not cues:
                    skipped[ident] = {'video_id': ident, 'status': 'no_speech_detected',
                                      'source_sha256': digest, 'checked_at': now()}
                    manifest.update(updated_at=now(), skipped=list(skipped.values()))
                    write_json(manifest_path, manifest)
                    print(f'{ident}: nessun parlato riconosciuto; nessun testo inventato.', flush=True)
                    continue
                provenance = {'source_type': 'riconoscimento_vocale_locale', 'source_sha256': digest,
                              'source_file': source.name, 'started_at': started, 'created_at': now(),
                              'engine': 'faster-whisper', 'engine_version': faster_whisper.__version__,
                              'model': 'Systran/faster-whisper-small', 'model_revision': models[-1].name,
                              'compute_type': 'int8', 'beam_size': args.beam_size, 'vad_filter': True,
                              'condition_on_previous_text': False, 'language': info.language,
                              'language_probability': info.language_probability,
                              'audio_duration_seconds': audio_duration}
                contents = bundle(video, cues, provenance)
                save_bundle(target, contents)
                document = json.loads(contents['json'])
            items[ident] = {'video_id': ident, 'language': document['language'],
                            'source_sha256': digest, 'created_at': document['created_at'],
                            'segments': len(document['segments']),
                            'audio_duration_seconds': document['audio_duration_seconds'],
                            'human_audio_review': False, 'local_only': True,
                            'files': {ext: str((target / ('trascrizione.' + ext)).relative_to(archive))
                                      for ext in ('txt', 'vtt', 'json')},
                            'sha256': {ext: sha256(target / ('trascrizione.' + ext))
                                       for ext in ('txt', 'vtt', 'json')}}
            skipped.pop(ident, None)
            manifest.update(updated_at=now(), items=list(items.values()), skipped=list(skipped.values()))
            write_json(manifest_path, manifest)
            print(f'{ident}: salvati TXT, VTT e JSON ({len(document["segments"])} segmenti).', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'archivio')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--ids', nargs='+')
    selection.add_argument('--all', action='store_true', help='Audio senza trascrizione locale, in ordine di catalogo')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--language', default=None, help='it, en oppure rilevamento automatico')
    parser.add_argument('--order', choices=['catalog', 'duration'], default='catalog')
    parser.add_argument('--pending-cards', action='store_true', help='Dai precedenza alle fonti ancora senza scheda')
    parser.add_argument('--beam-size', type=int, default=3)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit deve essere positivo')
    if args.threads < 1:
        parser.error('--threads deve essere positivo')
    if args.beam_size < 1:
        parser.error('--beam-size deve essere positivo')
    run(args)


if __name__ == '__main__':
    main()
