"""Fonti per la redazione: accessi YouTube serializzati e ASR private già presenti."""
import fcntl
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from divago import ROOT, write_json
from ricerca import fetch_for_analysis, RateLimited

WORK = ROOT / 'archivio/metadati/schede-estese-2026-10-23'


def _selected_local_source(ident, original):
    """Usa solo alternative esplicitamente selezionate, con originali e hash verificati."""
    registry = WORK / 'fonti-locali-selezionate.json'
    if not registry.is_file():
        return None
    record = json.loads(registry.read_text()).get('sources', {}).get(ident)
    if record is None:
        return None
    transcripts = ROOT / 'archivio/trascrizioni-locali'
    relative = Path(record['relative_path'])
    target = (transcripts / relative).resolve()
    allowed = (transcripts / ident / 'rielaborazioni').resolve()
    if (relative.is_absolute() or not allowed.is_relative_to(transcripts.resolve())
            or not target.is_relative_to(allowed) or target.name != 'trascrizione.json'):
        raise ValueError('Percorso della fonte alternativa non valido: ' + ident)
    original_raw = original.read_bytes()
    if hashlib.sha256(original_raw).hexdigest() != record['original_json_sha256']:
        raise ValueError('Originale della fonte alternativa modificato: ' + ident)
    raw = target.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['json_sha256']:
        raise ValueError('Integrità della fonte alternativa non valida: ' + ident)
    saved = json.loads(raw)
    if (saved.get('video_id') != ident
            or saved.get('source_type') != 'riconoscimento_vocale_locale'
            or saved.get('human_audio_review') is not False
            or record.get('human_audio_review') is not False
            or record.get('review_status') != 'selezionata_dopo_lettura_integrale_testuale'
            or saved.get('original_json_sha256') != record['original_json_sha256']
            or saved.get('source_sha256') != record['source_audio_sha256']
            or not saved.get('segments')):
        raise ValueError('Provenienza della fonte alternativa non valida: ' + ident)
    aligned = None
    if saved.get('source_variant') == 'derivazione_asr_da_audio_allineato':
        aligned = saved.get('derivation', {})
        parent_relative = Path(aligned['parent_json_relative_path'])
        parent = (transcripts / parent_relative).resolve()
        parent_base = (transcripts / aligned['parent_video_id']).resolve()
        if (parent_relative.is_absolute() or not parent_base.is_relative_to(transcripts.resolve())
                or not parent.is_relative_to(parent_base) or parent.name != 'trascrizione.json'
                or aligned['parent_video_id'] == ident
                or hashlib.sha256(parent.read_bytes()).hexdigest() != aligned['parent_json_sha256']
                or saved.get('new_asr_run') is not False):
            raise ValueError('Fonte madre dell’allineamento non valida: ' + ident)
        parent_source = json.loads(parent.read_text())
        offset = aligned['timestamp_offset_subtracted_seconds']
        if (parent_source.get('source_type') != 'riconoscimento_vocale_locale'
                or parent_source.get('human_audio_review') is not False
                or parent_source.get('video_id') != aligned['parent_video_id']
                or not isinstance(offset, (int, float)) or not 0 <= offset < float('inf')):
            raise ValueError('Provenienza dell’allineamento non valida: ' + ident)
        end = offset + saved['audio_duration_seconds']
        expected = [dict(start=round(s['start'] - offset, 6), end=round(s['end'] - offset, 6),
                         text=s['text']) for s in parent_source['segments']
                    if s['start'] >= offset and s['end'] <= end]
        if saved['segments'] != expected:
            raise ValueError('Segmenti non corrispondenti all’estratto allineato: ' + ident)
    result = {'video_id': ident, 'cues': saved['segments'], 'language': saved['language'],
            'source_type': 'riconoscimento_vocale_locale',
            'audio_duration_analyzed': saved['audio_duration_seconds'],
            'source_variant': 'rielaborazione_locale_selezionata',
            'language_forced': saved.get('language_forced', False)}
    if aligned is not None:
        result['source_alignment'] = dict(parent_video_id=aligned['parent_video_id'],
            offset_seconds=aligned['timestamp_offset_subtracted_seconds'],
            new_asr_run=False, boundary_segments_excluded=True)
    return result


def _selected_visual_source(ident):
    """Osservazioni di fotogrammi: mai trascrizioni o ascolto umano impliciti."""
    registry = WORK / 'fonti-visive-selezionate.json'
    if not registry.is_file():
        return None
    record = json.loads(registry.read_text()).get('sources', {}).get(ident)
    if record is None:
        return None
    asr_registry = WORK / 'fonti-locali-selezionate.json'
    if (asr_registry.is_file() and ident in
            json.loads(asr_registry.read_text()).get('sources', {})):
        raise ValueError('Due fonti selezionate per lo stesso video: ' + ident)
    base = ROOT / 'archivio/analisi-visive' / ident
    relative = Path(record['relative_path'])
    target = (ROOT / 'archivio/analisi-visive' / relative).resolve()
    if (relative.is_absolute() or not base.resolve().is_relative_to(
            (ROOT / 'archivio/analisi-visive').resolve())
            or not target.is_relative_to(base.resolve()) or target.name != 'fonte.json'):
        raise ValueError('Percorso della fonte visiva non valido: ' + ident)
    raw = target.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['json_sha256']:
        raise ValueError('Fonte visiva modificata: ' + ident)
    saved = json.loads(raw)
    if (saved.get('video_id') != ident
            or saved.get('source_type') != 'analisi_fotogrammi_locali'
            or saved.get('human_audio_review') is not False
            or saved.get('human_visual_review') is not True
            or saved.get('partial_visual_sampling') is not True
            or saved.get('language_scope') != 'lingua_delle_osservazioni_non_del_sonoro'
            or saved.get('review_status') != 'fotogrammi_letti_con_copertura_parziale'
            or record.get('review_status') != 'selezionata_dopo_lettura_fotogrammi'
            or record.get('human_audio_review') is not False
            or not saved.get('frames') or not saved.get('observations')):
        raise ValueError('Provenienza della fonte visiva non valida: ' + ident)
    original = ROOT / 'archivio/trascrizioni-locali' / ident / 'trascrizione.json'
    original_hash = hashlib.sha256(original.read_bytes()).hexdigest() if original.is_file() else None
    if original_hash != record.get('original_asr_json_sha256'):
        raise ValueError('Fonte ASR precedente cambiata: ' + ident)
    inventory = json.loads((ROOT / 'archivio/inventario.json').read_text())
    media = next(v for v in inventory['videos'] if v['video_id'] == ident)['video']
    if (saved['source_sha256'] != media['sha256']
            or saved['source_sha256'] != record['source_video_sha256']):
        raise ValueError('Impronta del video non corrispondente: ' + ident)
    duration = saved['video_duration_seconds']
    if (not isinstance(duration, (int, float)) or not 0 < duration < float('inf')
            or abs(duration - media['probe']['duration_seconds']) > 0.1):
        raise ValueError('Durata visiva non valida: ' + ident)
    for frame in saved['frames']:
        frame_relative = Path(frame['relative_path'])
        path = (base / frame_relative).resolve()
        if (frame_relative.is_absolute() or not path.is_relative_to(base.resolve())
                or hashlib.sha256(path.read_bytes()).hexdigest() != frame['sha256']
                or not 0 <= frame['seconds'] < duration):
            raise ValueError('Fotogramma non valido o modificato: ' + ident)
    cues = []
    for observation in saved['observations']:
        indexes = observation.get('frame_indexes', [])
        if (not indexes or any(type(i) is not int or not 0 <= i < len(saved['frames']) for i in indexes)
                or not observation.get('text', '').strip()
                or not 0 <= observation['start'] <= observation['end'] < duration
                or any(not observation['start'] <= saved['frames'][i]['seconds'] <= observation['end']
                       for i in indexes)):
            raise ValueError('Osservazione priva di fotogrammi corrispondenti: ' + ident)
        cues.append({k: observation[k] for k in ('start', 'end', 'text')})
    if cues != sorted(cues, key=lambda c: c['start']):
        raise ValueError('Osservazioni non ordinate: ' + ident)
    return dict(video_id=ident, cues=cues, language=saved['language'],
                source_type='analisi_fotogrammi_locali',
                video_duration_seconds=duration,
                partial_visual_sampling=True,
                frames_reviewed=len(saved['frames']),
                frame_times_seconds=[f['seconds'] for f in saved['frames']],
                source_video_sha256=saved['source_sha256'],
                language_scope=saved['language_scope'])


def read_source(ident):
    visual = _selected_visual_source(ident)
    if visual is not None:
        return visual
    local = ROOT / 'archivio/trascrizioni-locali' / ident / 'trascrizione.json'
    selected = _selected_local_source(ident, local)
    if selected is not None:
        return selected
    if local.is_file():
        saved = json.loads(local.read_text())
        return {'video_id': ident, 'cues': saved['segments'], 'language': saved['language'],
                'source_type': 'riconoscimento_vocale_locale',
                'audio_duration_analyzed': saved['audio_duration_seconds']}
    WORK.mkdir(parents=True, exist_ok=True)
    with (WORK / 'fonti.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        pause = WORK / 'pausa-sottotitoli.json'
        if pause.exists():
            record = json.loads(pause.read_text())
            if datetime.now(timezone.utc) < datetime.fromisoformat(record['retry_after']):
                raise RateLimited('Pausa globale delle richieste ai sottotitoli.')
        last = WORK / 'ultimo-accesso.json'
        if last.exists():
            delay = 3 - (time.time() - json.loads(last.read_text())['unix_time'])
            if delay > 0:
                time.sleep(delay)
        try:
            result = fetch_for_analysis(ident)
        except RateLimited:
            write_json(pause, {'video_id': ident, 'reason': 'YouTube HTTP 429',
                              'retry_after': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()})
            raise
        finally:
            write_json(last, {'video_id': ident, 'unix_time': time.time()})
    if result is None:
        return None
    cues, language, _ = result
    return {'video_id': ident, 'cues': cues, 'language': language,
            'source_type': 'sottotitoli_automatici_youtube'}


def coverage(source, duration):
    cues = source['cues']
    canonical = json.dumps(cues, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    record = {'first_start': cues[0]['start'], 'last_end': cues[-1]['end'],
              'duration_seconds': duration, 'segments_read': len(cues),
              'source_sha256': hashlib.sha256(canonical.encode()).hexdigest(),
              'source_hash_method': 'SHA-256 del JSON UTF-8 dei segmenti normalizzati, ensure_ascii=False, sort_keys=True, separatori compatti.',
              'scope': 'Lettura integrale di tutti i segmenti disponibili; fonte automatica, ascolto umano da completare.'}
    if source.get('source_type') == 'analisi_fotogrammi_locali':
        record.update(scope='Lettura integrale delle osservazioni e dei fotogrammi indicati. '
                      'Campionamento visivo parziale, non visione continua o ascolto umano del video.',
                      video_duration_seconds=source['video_duration_seconds'],
                      partial_visual_sampling=True, frames_reviewed=source['frames_reviewed'],
                      frame_times_seconds=source['frame_times_seconds'],
                      source_video_sha256=source['source_video_sha256'],
                      language_scope=source['language_scope'])
    elif source.get('audio_duration_analyzed') is not None:
        record['audio_duration_analyzed'] = source['audio_duration_analyzed']
        record['scope'] += ' Il riconoscimento locale ha elaborato l’intero audio, incluse le parti senza parlato rilevato.'
    if source.get('source_alignment'):
        record['source_alignment'] = source['source_alignment']
        record['scope'] = ('Lettura integrale dei segmenti automatici derivati dall’audio più lungo, '
                           'con corrispondenza fisica documentata dell’estratto. Tempi traslati; '
                           'segmenti che attraversano i confini esclusi senza completare parole. '
                           'Nessuna nuova esecuzione ASR o revisione umana del sonoro.')
    return record


def make_card(ident, summary, topics, passages, books=None, notes=None):
    """Compone lo schema dopo la lettura della fonte e la stesura dei testi."""
    video = next(v for v in json.loads((ROOT / 'sito/dist/data/catalogo.json').read_text())['videos']
                 if v['id'] == ident)
    source = read_source(ident)
    if not source:
        raise ValueError('Fonte non disponibile: ' + ident)
    verification = ('riscontro_audio_automatico' if source['source_type'] == 'riconoscimento_vocale_locale'
                    else 'riscontro_testuale')
    return {'video_id': ident, 'title': video['title'], 'duration_seconds': video['duration'],
            'updated_at': datetime.now(timezone.utc).isoformat(), 'human_audio_review': False,
            'source_type': source['source_type'], 'language': source['language'],
            'editorial_status': ('scheda_descrittiva_da_fotogrammi'
                                 if source['source_type'] == 'analisi_fotogrammi_locali'
                                 else 'scheda_redatta_da_fonte_automatica'), 'summary': summary,
            'topics': topics,
            'passages': [dict(seconds=s, label=label, description=description,
                              source_type=source['source_type'], verification=verification,
                              human_audio_review=False) for s, label, description in passages],
            'books': books or [], 'source_coverage': coverage(source, video['duration']),
            'analysis_notes': notes or [
                'Fotogrammi indicati esaminati; campionamento parziale, sonoro non ascoltato.'
                if source['source_type'] == 'analisi_fotogrammi_locali'
                else 'Fonte automatica letta integralmente; ascolto umano da completare.']}
