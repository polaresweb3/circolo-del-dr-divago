#!/usr/bin/env python3
"""Integra schede curate e citazioni senza perdere i riferimenti precedenti."""
import argparse
from copy import deepcopy
import json
from datetime import datetime, timezone
from pathlib import Path

from divago import ROOT, write_json


def integrate(cards, bibliography, additions, new_books, videos):
    cards, bibliography = deepcopy(cards), deepcopy(bibliography)
    by_book = {book['id']: book for book in bibliography}
    by_video = {video['id']: video for video in videos}
    by_card = {card['video_id']: card for card in cards}
    if len(by_book) != len(bibliography) or len(by_card) != len(cards):
        raise ValueError('Identificatori duplicati nei dati esistenti.')
    for book in new_books:
        ident = book['id']
        if ident in by_book:
            if (book['title'], book['author']) != (by_book[ident]['title'], by_book[ident]['author']):
                raise ValueError('Identità bibliografica discordante: ' + ident)
            continue
        if not book.get('title') or not book.get('author') or not book.get('references'):
            raise ValueError('Nuova opera priva di identità o fonti: ' + ident)
        book = deepcopy(book)
        book['edition_cited'] = None
        book.setdefault('mentions', [])
        bibliography.append(book)
        by_book[ident] = book
    seen = set()
    for card in additions:
        ident = card['video_id']
        if ident in seen:
            raise ValueError('Scheda ripetuta nel lotto: ' + ident)
        seen.add(ident)
        if ident not in by_video:
            raise ValueError('Video non presente nel catalogo: ' + ident)
        duration = by_video[ident]['duration']
        if card.get('duration_seconds') != duration or not card.get('title', '').strip():
            raise ValueError('Titolo o durata della scheda non corrispondenti al catalogo: ' + ident)
        if not card.get('source_type') or not card.get('language'):
            raise ValueError('Tipo di fonte o lingua mancanti: ' + ident)
        if ident in by_card:
            if by_card[ident] == card:
                continue  # Ripetere l'importazione non duplica né schede né citazioni.
            raise ValueError('Scheda già presente e diversa; revisione esplicita richiesta: ' + ident)
        minimum = 1 if duration < 180 else 3
        if not card.get('summary', '').strip() or len(card.get('topics', [])) < minimum:
            raise ValueError('Sintesi o argomenti mancanti: ' + ident)
        if card.get('human_audio_review') is not False:
            raise ValueError('Il lotto deve dichiarare la fonte automatica: ' + ident)
        coverage = card.get('source_coverage', {})
        if not coverage.get('source_sha256') or not coverage.get('segments_read'):
            raise ValueError('Provenienza della fonte mancante: ' + ident)
        if coverage.get('audio_duration_analyzed', coverage.get('last_end', 0)) < duration - 10:
            raise ValueError('La fonte non arriva alla conclusione: ' + ident)
        passages = card.get('passages', [])
        if len(passages) < minimum or passages != sorted(passages, key=lambda p: p['seconds']):
            raise ValueError('Passaggi mancanti o non ordinati: ' + ident)
        for passage in passages:
            if not 0 <= passage['seconds'] < duration or passage.get('human_audio_review') is not False:
                raise ValueError('Passaggio non valido: ' + ident)
        for mention in card.get('books', []):
            book = by_book.get(mention['book_id'])
            if book is None:
                raise ValueError('Opera da registrare prima della citazione: ' + mention['book_id'])
            if not 0 <= mention['seconds'] < duration or mention.get('verified') is not False:
                raise ValueError('Citazione non valida: ' + ident)
            if mention.get('human_audio_review') is not False:
                raise ValueError('Manca lo stato del controllo audio: ' + ident)
            confidence = mention.get('confidence', 'identificazione_probabile')
            entry = {'video_id': ident, 'seconds': mention['seconds'],
                     'title_seconds': mention.get('title_seconds', mention['seconds']),
                     'evidence': card['source_type'], 'verification': confidence,
                     'verified': False, 'human_audio_review': False,
                     'note': mention['evidence']}
            if mention.get('role'):
                entry['role'] = mention['role']
            same = [m for m in book['mentions'] if m['video_id'] == ident]
            if any(m.get('seconds') == entry['seconds'] for m in same):
                continue
            placeholder = next((m for m in same if m.get('seconds') is None
                                and m.get('evidence') == 'video_title'), None)
            if placeholder is not None:
                # Il vecchio collegamento al video resta, ora arricchito dal minutaggio.
                entry['previous_evidence'] = deepcopy(placeholder)
                placeholder.update(entry)
            else:
                book['mentions'].append(entry)
            if book.get('status') == 'titolo_nel_video':
                book['status'] = ('identificazione_probabile' if confidence == 'identificazione_probabile'
                                  else 'citazione_esplicita')
                book['source'] = 'Titolo riscontrato nella fonte automatica; dettagli e minutaggi nei riferimenti ai video. Ascolto umano da completare.'
        cards.append(deepcopy(card))
        by_card[ident] = cards[-1]
    for book in bibliography:
        for mention in book['mentions']:
            video = by_video.get(mention['video_id'])
            if video:
                mention['video_title'] = video['title']
    return cards, bibliography


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batches', type=Path, nargs='+')
    parser.add_argument('--books', type=Path, nargs='*', default=[])
    args = parser.parse_args()
    data = ROOT / 'sito/dist/data'
    cards = json.loads((data / 'schede.json').read_text())
    bibliography = json.loads((data / 'libri.json').read_text())
    additions = [c for path in args.batches for c in json.loads(path.read_text())]
    new_books = [b for path in args.books for b in json.loads(path.read_text())]
    catalog = json.loads((data / 'catalogo.json').read_text())['videos']
    updated_cards, updated_books = integrate(cards, bibliography, additions, new_books, catalog)
    # Conserva entrambi gli originali prima di cambiare i dati del sito.
    backup = ROOT / 'archivio/metadati/schede-2026-10-23/prima-aggiornamento'
    backup.mkdir(parents=True, exist_ok=True)
    for name in ('schede.json', 'libri.json'):
        target = backup / name
        if not target.exists():
            target.write_bytes((data / name).read_bytes())
    from ricerca import make_index, save_index, stamp
    archive = ROOT / 'archivio'
    index = make_index(archive)
    card_index = {card['video_id']: card for card in updated_cards}
    batch_ids = {card['video_id'] for card in additions}
    for row in index['videos']:
        card = card_index.get(row['video_id'])
        if card is None or row['video_id'] not in batch_ids:
            continue
        coverage = card['source_coverage']
        row.update(analysis_status='caption_analyzed' if card['source_type'].startswith('sottotitoli')
                   else 'audio_analyzed', source_type=card['source_type'],
                   language=card['language'], analyzed_at=card.get('updated_at', datetime.now(timezone.utc).isoformat()),
                   segments_analyzed=coverage['segments_read'], last_segment_end=coverage['last_end'],
                   source_sha256=coverage['source_sha256'], audio_review_complete=False,
                   analysis_method='editorial_full_source_reading',
                   analysis_scope='Lettura integrale della fonte automatica; sintesi originale e riferimenti bibliografici. Ascolto umano da completare.',
                   reviewed_book_ids=[book['book_id'] for book in card['books']])
    if batch_ids:
        index['last_run'] = {'status': 'editorial_batch_completed',
                             'finished_at': datetime.now(timezone.utc).isoformat(),
                             'selected': len(batch_ids)}
    write_json(data / 'libri.json', updated_books)
    write_json(data / 'schede.json', updated_cards)
    save_index(archive, index)
    pending = [row for row in index['videos'] if row['video_id'] not in card_index]
    write_json(archive / 'ricerca/coda-schede.json', {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'catalog_total': len(catalog), 'editorial_cards': len(updated_cards),
        'remaining': len(pending), 'videos': pending})
    lines = ['BIBLIOTECA DEL CIRCOLO DEL DR DIVAGO',
             f'{len(updated_books)} opere · {len(updated_cards)} schede editoriali',
             'I minutaggi sono ricavati da fonti automatiche e richiedono ascolto umano.',
             'Le edizioni delle copertine sono riferimenti bibliografici, non edizioni attribuite ai video.', '']
    for book in sorted(updated_books, key=lambda b: (b['author'], b['title'])):
        lines.extend([book['author'] + ' — ' + book['title'], book.get('source', '')])
        for mention in book['mentions']:
            second = mention.get('title_seconds')
            if second is None:
                second = mention.get('seconds')
            timing = stamp(second) if second is not None else 'minutaggio non disponibile'
            url = 'https://www.youtube.com/watch?v=' + mention['video_id']
            if second is not None:
                url += '&t=' + str(int(second))
            lines.append('  ' + mention.get('video_title', mention['video_id']) + ' · ' + timing)
            lines.append('  ' + url + ' · ' + mention.get('verification', 'da_verificare'))
        lines.extend('  Fonte: ' + ref['label'] + ' — ' + ref['url'] for ref in book.get('references', []))
        lines.append('')
    (archive / 'libri-citati.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'schede_aggiunte': len(updated_cards) - len(cards),
                      'schede_totali': len(updated_cards),
                      'opere_aggiunte': len(updated_books) - len(bibliography),
                      'opere_totali': len(updated_books),
                      'riferimenti_aggiunti': sum(len(b['mentions']) for b in updated_books)
                          - sum(len(b['mentions']) for b in bibliography)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
