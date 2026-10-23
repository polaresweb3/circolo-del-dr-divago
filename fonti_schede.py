"""Fonti per la redazione: accessi YouTube serializzati e ASR private già presenti."""
import fcntl
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone

from divago import ROOT, write_json
from ricerca import fetch_for_analysis, RateLimited

WORK = ROOT / 'archivio/metadati/schede-estese-2026-10-23'


def read_source(ident):
    local = ROOT / 'archivio/trascrizioni-locali' / ident / 'trascrizione.json'
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
    if source.get('audio_duration_analyzed') is not None:
        record['audio_duration_analyzed'] = source['audio_duration_analyzed']
        record['scope'] += ' Il riconoscimento locale ha elaborato l’intero audio, incluse le parti senza parlato rilevato.'
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
            'editorial_status': 'scheda_redatta_da_fonte_automatica', 'summary': summary,
            'topics': topics,
            'passages': [dict(seconds=s, label=label, description=description,
                              source_type=source['source_type'], verification=verification,
                              human_audio_review=False) for s, label, description in passages],
            'books': books or [], 'source_coverage': coverage(source, video['duration']),
            'analysis_notes': notes or ['Fonte automatica letta integralmente; ascolto umano da completare.']}
