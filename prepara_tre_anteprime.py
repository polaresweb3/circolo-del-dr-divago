#!/usr/bin/env python3
"""Prepara la Sala di lettura come unico sito pubblico, senza deploy."""
import json
from pathlib import Path
import shutil

from crea_proposta_editoriale import create, book_cards
from prepara_versione_online import prepare, References
from verifica_copertine import verify_covers
from dati_pubblici import export_directory
from seo_pubblico import apply_public_seo

ROOT = Path(__file__).resolve().parent


def publish_salon(source, destination):
    """Usa la Sala in radice e mantiene i collegamenti /sala-lettura/."""
    shutil.copytree(source, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.DS_Store'))
    legacy = destination / 'sala-lettura'
    if source.resolve() != legacy.resolve():
        shutil.copytree(source, legacy, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.DS_Store'))
    for retired in (destination / 'originale', destination / 'assets/anteprime'):
        if retired.exists():
            shutil.rmtree(retired)
    (destination / 'versioni.html').write_text(
        '<!doctype html>\n<html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="refresh" content="0; url=index.html">'
        '<meta name="robots" content="noindex, nofollow">'
        '<title>Circolo del Dr Divago</title></head><body>'
        '<p><a href="index.html">Entra nel Circolo del Dr Divago</a></p>'
        '</body></html>\n', encoding='utf-8')


def main():
    covers = verify_covers(ROOT / 'sito/dist')
    print('Copertine locali verificate:', covers['works_checked'])
    destination = prepare()
    salon = ROOT / 'proposte/sala-lettura'
    create(proposal=salon, source=salon / 'sorgenti', label='SALA DI LETTURA',
           slug='sala-lettura', reference='Biblioteche storiche e circoli letterari',
           book_renderer=book_cards, home_page='salotto')
    source = salon / 'sito/dist'
    export_directory(source)
    publish_salon(source, destination)
    seo = apply_public_seo(destination)
    for metadata in destination.rglob('.DS_Store'):
        metadata.unlink()
    for page in destination.rglob('*.html'):
        text = page.read_text()
        for relative in References(text).paths:
            target = (page.parent / relative).resolve()
            if not target.is_relative_to(destination.resolve()) or not target.is_file():
                raise ValueError(f'Collegamento mancante: {page} → {relative}')
    files = [p for p in destination.rglob('*') if p.is_file()]
    for path in files:
        if (path.suffix not in {'.html', '.js', '.css', '.json', '.jpg', '.jpeg', '.webp', '.png', '.gif', '.svg', '.ico'}
                and path.relative_to(destination).as_posix() not in {'robots.txt', 'sitemap.xml'}):
            raise ValueError('Tipo non pubblico: ' + str(path))
        if path.suffix in {'.html', '.js', '.css', '.json', '.svg'}:
            text = path.read_text()
            if any(marker in text for marker in ['file:///', '/Users/', '/private/tmp/', '"audio_file"', '"video_file"']):
                raise ValueError('Percorso privato: ' + str(path))
    report = {'status': 'prepared_not_published', 'pages': len(list(destination.rglob('*.html'))),
              'files': len(files), 'bytes': sum(p.stat().st_size for p in files),
              'entry_point': 'index.html', 'versions': ['index.html'],
              'legacy_path': 'sala-lettura/index.html', 'removed_version': 'originale',
              'internal_links_checked': True, 'local_media_included': False,
              'full_transcripts_included': False, 'covers': covers, 'seo': seo}
    (destination.parent / 'tre-anteprime.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
