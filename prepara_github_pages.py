#!/usr/bin/env python3
"""Rigenera le tre proposte e prepara docs/; non pubblica nulla."""
from pathlib import Path
import shutil
from prepara_tre_anteprime import main


def prepare():
    main()
    root = Path(__file__).resolve().parent
    source = root / 'pubblicazione/circolo-del-dr-divago/dist'
    destination = root / 'docs'
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    (destination / '.nojekyll').touch()
    print('GitHub Pages pronto in docs/. Nessuna pubblicazione effettuata.')


if __name__ == '__main__':
    prepare()
