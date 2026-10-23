"""Inventario locale, controllo dei media e copie verificabili dell’archivio."""
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import uuid

KINDS = {'audio': {'.mp3'}, 'video': {'.mkv', '.mp4', '.webm', '.mov'}}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def local_budget(archive):
    config = archive / 'stato/limite-spazio.json'
    if not config.exists():
        return None
    settings = json.loads(config.read_text())
    seen = set()
    used = 0
    for root in [archive, Path(settings['cloud_directory'])]:
        if not root.exists():
            continue
        for file in root.rglob('*'):
            try:
                stat = file.stat()
                if not file.is_file() or (stat.st_dev, stat.st_ino) in seen:
                    continue
                seen.add((stat.st_dev, stat.st_ino))
                # Conta anche i file iCloud, senza presumere che Apple li abbia rimossi dal Mac.
                used += max(stat.st_size, stat.st_blocks * 512)
            except FileNotFoundError:
                pass
    return {**settings, 'used_bytes': used}


def enforce_budget(archive, additional=0, headroom=0):
    budget = local_budget(archive)
    if budget and budget['used_bytes'] + additional + headroom > budget['limit_bytes']:
        message = ('Pausa: limite locale complessivo di {:g} GB, inclusa la cartella iCloud. '
                   'Nessun originale cancellato.').format(budget['limit_bytes'] / 1_000_000_000)
        (archive / 'stato/ferma-scaricamento-icloud').touch()
        write_json(archive / 'stato/limite-raggiunto.json', {'checked_at': now(), **budget, 'reason': message})
        raise ValueError(message)


def deferred_ids(archive, kind):
    path = archive / 'stato/download-rinviati.json'
    return set(json.loads(path.read_text()).get(kind, {})) if path.exists() else set()


def defer_age_restricted(archive, kind, ident):
    with archive_lock(archive, wait=True):
        path = archive / 'stato/download-rinviati.json'
        data = json.loads(path.read_text()) if path.exists() else {}
        data.setdefault(kind, {})[ident] = {'reason': 'age_restricted', 'recorded_at': now(),
                                           'url': 'https://www.youtube.com/watch?v=' + ident,
                                           'detail': 'Richiede accesso e conferma età su YouTube; nessun cookie utilizzato.'}
        write_json(path, data)


@contextmanager
def archive_lock(archive, name='operazione', wait=False):
    path = archive / ('stato/' + name + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            raise ValueError('Un’altra operazione sta già usando questo archivio.')
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def probe_media(path, kind, expected):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
        'format=duration:stream=codec_type,codec_name,width,height', '-of', 'json', str(path)],
        capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise ValueError('Il contenitore non è leggibile da ffprobe.')
    data = json.loads(result.stdout)
    duration = float(data.get('format', {}).get('duration', 0))
    types = {s.get('codec_type') for s in data.get('streams', [])}
    required = {'audio'} if kind == 'audio' else {'audio', 'video'}
    if not math.isfinite(duration) or duration <= 0 or not required.issubset(types):
        raise ValueError('Durata o tracce multimediali mancanti.')
    if expected and abs(duration - expected) > max(3, expected * .002):
        raise ValueError('Durata non coerente con il catalogo: serve un controllo.')
    return {'duration_seconds': duration, 'streams': data.get('streams', [])}


def inventory(archive, rehash=False):
    from divago import entries, read_catalog, scan_media
    path = archive / 'inventario.json'
    old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'videos': []}
    previous = {r['video_id']: r for r in old['videos']}
    media = {kind: scan_media(archive / kind, extensions) for kind, extensions in KINDS.items()}
    active = {}
    for kind in KINDS:
        try:
            marker = json.loads((archive / ('stato/attivo-' + kind + '.json')).read_text())
            os.kill(marker['pid'], 0)
            active[kind] = marker['video_id']
        except (OSError, ValueError, KeyError, TypeError):
            pass
    rows = []
    for video in entries(read_catalog(archive)):
        ident = video['id']
        row = {'video_id': ident, 'title': video.get('title', ident),
               'url': 'https://www.youtube.com/watch?v=' + ident, 'duration_seconds': video.get('duration')}
        for kind in KINDS:
            file = media[kind].get(ident)
            before = previous.get(ident, {}).get(kind) or {}
            if active.get(kind) == ident:
                row[kind] = {'status': 'in_progress', 'previous_sha256': before.get('sha256') or before.get('previous_sha256')}
                continue
            if not file:
                row[kind] = {'status': 'missing', **({'previous_sha256': before.get('sha256') or before.get('previous_sha256')} if before else {})}
                continue
            stat = file.stat()
            record = {'path': file.relative_to(archive).as_posix(), 'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
            if (not rehash and before.get('status') == 'verified' and before.get('bytes') == stat.st_size
                    and before.get('mtime_ns') == stat.st_mtime_ns and before.get('path') == record['path']):
                row[kind] = before
                continue
            checksum = sha256(file)
            baseline = before.get('sha256') or before.get('previous_sha256')
            record.update(sha256=baseline or checksum, checked_at=now())
            try:
                record['probe'] = probe_media(file, kind, video.get('duration'))
                if baseline and checksum != baseline:
                    record.update(status='needs_review', actual_sha256=checksum, error='Il contenuto è cambiato rispetto all’impronta conservata.')
                else:
                    record['status'] = 'verified'
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                record.update(status='needs_review', error=str(exc))
            row[kind] = record
        rows.append(row)
    result = {'updated_at': now(), 'method': 'ffprobe: tracce e durata; SHA-256: impronta dei byte. Non è una decodifica integrale.',
              'counts': {kind: sum(r[kind]['status'] == 'verified' for r in rows) for kind in KINDS},
              'needs_review': sum(r[k]['status'] == 'needs_review' for r in rows for k in KINDS), 'videos': rows}
    write_json(path, result)
    csv_path = archive / 'inventario.csv'
    with csv_path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['video_id', 'titolo', 'url', 'audio_stato', 'audio_file', 'audio_bytes', 'audio_sha256',
                         'video_stato', 'video_file', 'video_bytes', 'video_sha256'])
        for row in rows:
            values = [row['video_id'], row['title'], row['url']]
            for kind in KINDS:
                values += [row[kind].get(k, '') for k in ('status', 'path', 'bytes', 'sha256')]
            writer.writerow(["'" + str(v) if str(v).startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in values])
    sums = []
    for row in rows:
        for kind in KINDS:
            record = row[kind]
            if record['status'] == 'verified':
                name = record['path']
                escaped = '\\' in name or '\n' in name
                name = name.replace('\\', '\\\\').replace('\n', '\\n')
                sums.append(('\\' if escaped else '') + record['sha256'] + '  ' + name)
    (archive / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n', encoding='utf-8')
    return result


def estimates(archive, data):
    from divago import entries, read_catalog
    videos = entries(read_catalog(archive))
    total = sum(v.get('duration') or 0 for v in videos)
    samples = [r for r in data['videos'] if r['video']['status'] == 'verified' and r.get('duration_seconds')]
    seconds = sum(r['duration_seconds'] for r in samples)
    size = sum(r['video']['bytes'] for r in samples)
    return {'catalogued': len(videos), 'audio_total_GB': round(total * 20000 / 1e9, 1),
            'video_sample_count': len(samples), 'video_estimate_GB': round(total * size / seconds / 1e9, 1) if seconds else None,
            'local_free_GB': round(shutil.disk_usage(archive).free / 1e9, 1),
            'note': 'Stima dei video estrapolata dal campione, non misura completa. Riserva di pianificazione: fino al doppio della stima.'}


def copy_verified(archive, destination, data):
    archive, destination = archive.resolve(), destination.expanduser().resolve()
    if destination == archive or destination.is_relative_to(archive) or archive.is_relative_to(destination):
        raise ValueError('Scegli una cartella separata dall’archivio di lavoro.')
    if str(destination).startswith('/Volumes/'):
        volume = Path('/Volumes') / destination.relative_to('/Volumes').parts[0]
        if not volume.is_mount():
            raise ValueError('Il disco di destinazione non è montato.')
    assets = []
    for row in data['videos']:
        for kind in KINDS:
            record = row[kind]
            if record['status'] == 'verified':
                assets.append((archive / record['path'], record['path'], record['sha256']))
                source = archive / record['path']
                for suffix in ('.description', '.info.json'):
                    sidecar = source.with_suffix(suffix)
                    if sidecar.is_file():
                        assets.append((sidecar, sidecar.relative_to(archive).as_posix(), sha256(sidecar)))
    if not assets:
        raise ValueError('Nessun file multimediale verificato da copiare.')
    destination.mkdir(parents=True, exist_ok=True)
    copied = reused = 0
    # Ogni nome definitivo compare solo dopo copia e controllo dell’impronta.
    # Il client cloud resta responsabile dell’upload: una copia locale non ne prova il completamento.
    for original, relative, checksum in assets:
        target = (destination / relative).resolve()
        if not target.is_relative_to(destination):
            raise ValueError('Percorso di destinazione non valido.')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256(target) != checksum:
                raise FileExistsError('File diverso già presente, non sovrascritto: ' + str(target))
            reused += 1
            continue
        if shutil.disk_usage(destination).free < original.stat().st_size + 1_000_000_000:
            raise OSError('Spazio insufficiente nella destinazione; gli originali sono conservati.')
        enforce_budget(archive, additional=original.stat().st_size)
        temp = target.with_name('.' + target.name + '.copia-' + uuid.uuid4().hex + '.tmp')
        try:
            shutil.copy2(original, temp)
            if sha256(temp) != checksum:
                raise ValueError('Impronta della copia non corrispondente: ' + relative)
            temp.replace(target)
            copied += 1
        finally:
            temp.unlink(missing_ok=True)
    metadata = [archive / name for name in ('inventario.json', 'inventario.csv', 'SHA256SUMS.txt', 'libri-citati.txt') if (archive / name).is_file()]
    for folder in ('metadati', 'ricerca', 'trascrizioni', 'trascrizioni-autorizzate'):
        metadata.extend(p for p in (archive / folder).rglob('*') if p.is_file())
    enforce_budget(archive, additional=sum(max(p.stat().st_blocks * 512, p.stat().st_size) + 4096 for p in metadata), headroom=10_000_000)
    snapshot = destination / 'indici' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    snapshot.mkdir(parents=True)
    for name in ('inventario.json', 'inventario.csv', 'SHA256SUMS.txt', 'libri-citati.txt'):
        original = archive / name
        if original.exists():
            shutil.copy2(original, snapshot / name)
    for folder in ('metadati', 'ricerca', 'trascrizioni', 'trascrizioni-autorizzate'):
        if (archive / folder).exists():
            shutil.copytree(archive / folder, snapshot / folder)
    report = {'created_at': now(), 'destination': str(destination), 'files_copied': copied,
              'verified_counts': data['counts'],
              'files_already_equal': reused, 'media_copied': len([1 for r in data['videos'] for k in KINDS if r[k]['status'] == 'verified']),
              'verification': 'SHA-256 dei file nella cartella di destinazione; upload remoto da confermare nel servizio cloud.',
              'remote_upload_confirmed': False, 'source_files_deleted': False}
    write_json(snapshot / 'resoconto-copia.json', report)
    write_json(archive / 'stato/ultima-copia.json', report)
    return report
