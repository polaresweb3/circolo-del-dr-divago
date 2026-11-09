#!/usr/bin/env python3
"""Rigenera la Sala di lettura e prepara docs/; non pubblica nulla."""
from pathlib import Path
import shutil
from prepara_tre_anteprime import main
from seo_pubblico import SITE_ORIGIN
from urllib.parse import urlsplit


def prepare():
    main()
    root = Path(__file__).resolve().parent
    source = root / 'pubblicazione/circolo-del-dr-divago/dist'
    destination = root / 'docs'
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    (destination / '.nojekyll').touch()
    (destination / 'CNAME').write_text(urlsplit(SITE_ORIGIN).hostname + '\n', encoding='utf-8')
    print('GitHub Pages pronto in docs/. Nessuna pubblicazione effettuata.')


if __name__ == '__main__':
    prepare()
