#!/usr/bin/env python3
"""Prepara le tre proposte pubblicabili sotto lo stesso sito, senza deploy."""
import json
from pathlib import Path
import shutil

from crea_proposta_editoriale import create, book_cards
from prepara_versione_online import prepare, References
from verifica_copertine import verify_covers
from dati_pubblici import export_directory

ROOT = Path(__file__).resolve().parent


def main():
    covers = verify_covers(ROOT / 'sito/dist')
    print('Copertine locali verificate:', covers['works_checked'])
    destination = prepare()
    # Mantiene funzionanti anche i collegamenti alle pagine del sito precedente.
    originals = [p for p in destination.iterdir() if p.name != '.DS_Store']
    original = destination / 'originale'
    original.mkdir()
    for path in originals:
        if path.is_dir():
            shutil.copytree(path, original / path.name, ignore=shutil.ignore_patterns('.DS_Store'))
        else:
            shutil.copyfile(path, original / path.name)
    salon = ROOT / 'proposte/sala-lettura'
    create(proposal=salon, source=salon / 'sorgenti', label='SALA DI LETTURA',
           slug='sala-lettura', reference='Biblioteche storiche e circoli letterari',
           book_renderer=book_cards, home_page='salotto')
    for slug in ['sala-lettura']:
        shutil.copytree(ROOT / 'proposte' / slug / 'sito/dist', destination / slug,
                        ignore=shutil.ignore_patterns('.DS_Store'))
    export_directory(destination / 'sala-lettura')
    shutil.copyfile(ROOT / 'sito/confronto-versioni.html', destination / 'versioni.html')
    shutil.copyfile(ROOT / 'sito/confronto-versioni.html', destination / 'index.html')
    images = destination / 'assets/anteprime'
    images.mkdir(exist_ok=True)
    for slug in ['originale', 'sala-lettura']:
        shutil.copyfile(ROOT / 'sito/anteprime-stili' / (slug + '.jpg'), images / (slug + '.jpg'))
    for metadata in destination.rglob('.DS_Store'):
        metadata.unlink()
    for page in destination.rglob('*.html'):
        text = page.read_text()
        if '<meta name="robots"' not in text:
            text = text.replace('</head>', '<meta name="robots" content="noindex, nofollow">\n</head>')
            page.write_text(text)
        for relative in References(text).paths:
            target = (page.parent / relative).resolve()
            if not target.is_relative_to(destination.resolve()) or not target.is_file():
                raise ValueError(f'Collegamento mancante: {page} → {relative}')
    files = [p for p in destination.rglob('*') if p.is_file()]
    for path in files:
        if path.suffix not in {'.html', '.js', '.css', '.json', '.jpg', '.jpeg', '.webp', '.png', '.gif', '.svg'}:
            raise ValueError('Tipo non pubblico: ' + str(path))
        if path.suffix in {'.html', '.js', '.css', '.json', '.svg'}:
            text = path.read_text()
            if any(marker in text for marker in ['file:///', '/Users/', '/private/tmp/', '"audio_file"', '"video_file"']):
                raise ValueError('Percorso privato: ' + str(path))
    report = {'status': 'prepared_not_published', 'pages': len(list(destination.rglob('*.html'))),
              'files': len(files), 'bytes': sum(p.stat().st_size for p in files),
              'comparison': 'index.html', 'versions': ['originale/index.html', 'sala-lettura/index.html'],
              'internal_links_checked': True, 'local_media_included': False,
              'full_transcripts_included': False, 'covers': covers}
    (destination.parent / 'tre-anteprime.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
