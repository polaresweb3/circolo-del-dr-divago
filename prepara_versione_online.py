#!/usr/bin/env python3
"""Prepara e controlla una copia statica per l’hosting; non pubblica nulla."""
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit
import zipfile

from sito_pages import build_site
from dati_pubblici import public_dataset

ROOT = Path(__file__).resolve().parent


class References(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.paths = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('href', 'src'):
            value = attrs.get(key)
            if value:
                parts = urlsplit(value)
                if parts.path and not parts.scheme and not parts.netloc:
                    self.paths.append(parts.path)


def prepare():
    manifest = build_site(ROOT)
    source = ROOT / 'sito/dist'
    project = ROOT / 'pubblicazione/circolo-del-dr-divago'
    destination = project / 'dist'
    # La cartella è riservata a questo generatore: non contiene l’archivio di lavoro.
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    files = [item['path'] for item in manifest['pages']]
    files += ['styles.css', 'refinement.css', 'app.js']
    files += [path.relative_to(source).as_posix() for path in (source / 'data/indici').glob('*.json')]
    datasets = ['catalogo.json', 'libri.json', 'schede.json']
    if (source / 'data/articoli-blog.json').exists():
        datasets.append('articoli-blog.json')
    volumes_path = source / 'data/volumi.json'
    if volumes_path.exists():
        datasets.append('volumi.json')
        volumes = json.loads(volumes_path.read_text(encoding='utf-8'))
        files += [volume['cover']['src'] for volume in volumes]
    bibliography = json.loads((source / 'data/libri.json').read_text(encoding='utf-8'))
    files += sorted({book['cover']['src'] for book in bibliography if book.get('cover')})
    for name in files:
        original = (source / name).resolve()
        if not original.is_relative_to(source.resolve()) or not original.is_file():
            raise ValueError('File pubblico non valido: ' + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == '.html':
            target.write_text(original.read_text(encoding='utf-8').replace(
                '>ANTEPRIMA LOCALE<', '>ANTEPRIMA DEL PROGETTO<'), encoding='utf-8')
        else:
            shutil.copyfile(original, target)
    for name in datasets:
        value = public_dataset(name, json.loads((source / 'data' / name).read_text(encoding='utf-8')))
        if name == 'catalogo.json':
            for video in value['videos']:
                video.pop('audio_file', None)
                video.pop('video_file', None)
        if name == 'ricerca.json':
            value['counts']['transcripts_saved'] = 0
            for video in value['videos']:
                video['transcripts'] = []
        target = destination / 'data' / name
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for page in destination.rglob('*.html'):
        text = page.read_text(encoding='utf-8')
        for name in References(text).paths:
            target = (page.parent / name).resolve()
            if not target.is_relative_to(destination.resolve()) or not target.is_file():
                raise ValueError(f'Collegamento locale non incluso: {page.name} → {name}')
    packaged = sorted(p for p in destination.rglob('*') if p.is_file())
    for path in packaged:
        if path.suffix not in {'.html', '.js', '.css', '.json', '.jpg', '.jpeg', '.webp', '.png', '.gif', '.svg'}:
            raise ValueError('Tipo di file inatteso per il sito pubblico: ' + path.name)
        if path.suffix in {'.html', '.js', '.css', '.json', '.svg'}:
            text = path.read_text(encoding='utf-8')
            if any(marker in text for marker in ('file:///', '/Users/', '/private/tmp/', '"audio_file"', '"video_file"')):
                raise ValueError('Riferimento locale inatteso: ' + path.name)
    output = ROOT / 'condivisione/Circolo-del-Dr-Divago-online.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in packaged:
            archive.write(path, path.relative_to(destination).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert 'index.html' in archive.namelist()
    report = {
        'status': 'prepared_not_published', 'pages': len(manifest['pages']),
        'files': len(packaged), 'bytes': sum(p.stat().st_size for p in packaged),
        'local_media_included': False, 'full_transcripts_included': False,
        'internal_links_checked': True,
        'hosting_directory': str(destination.relative_to(ROOT)),
        'zip': str(output.relative_to(ROOT)),
    }
    (project / 'preparazione.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return destination


if __name__ == '__main__':
    prepare()
