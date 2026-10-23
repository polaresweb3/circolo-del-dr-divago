#!/usr/bin/env python3
"""Prepara una copia portatile del sito per una revisione privata, senza media."""
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit
import zipfile

from sito_pages import build_site

ROOT = Path(__file__).resolve().parent


GUIDA = """CIRCOLO DEL DR DIVAGO
Anteprima del progetto — {date}

COME APRIRE IL SITO
1. Estrai lo ZIP in una cartella sul tuo computer.
2. Apri APRI-IL-SITO.html con il tuo browser abituale.
   Se non si apre automaticamente, apri anteprima.html.
3. Tieni tutti i file HTML nella stessa cartella: i menu collegano le pagine.

Non servono installazioni o un account. Usa un computer per la visita completa.
L'anteprima interna di un servizio di posta o di un'app per file potrebbe non
eseguire il sito: salva ed estrai prima il pacchetto, poi aprilo nel browser.

COSA PUOI VEDERE
Home, Video, Biblioteca e Il progetto.
Ogni video si apre nella propria pagina. I contributi già curati contengono
sintesi originali, argomenti, libri e collegamenti ai passaggi.
Per gli altri video è indicato lo stato del lavoro, con i riferimenti disponibili.
Ricerca, testi e copertine disponibili sono incorporati nei file HTML.
Internet serve per le miniature dei video e per aprire YouTube o le fonti.
In questa copia i video si aprono su YouTube.

CONTENUTO DEL PACCHETTO
Questa è una dimostrazione del sito, non una pubblicazione online.
Non contiene gli MP3, i video scaricati, le trascrizioni integrali,
l'archivio di lavoro o i percorsi dei file multimediali sul Mac di Riccardo.
I conteggi degli audio e video conservati si riferiscono al progetto originale.
I riferimenti probabili e gli ascolti ancora da completare sono segnalati.

PER LA REVISIONE
Per segnalare un'osservazione, indica pagina, titolo del video o del libro
e il punto da modificare. Il sito non invia commenti e non sincronizza modifiche.
"""

START = """<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url=anteprima.html">
<title>Circolo del Dr Divago — Apri l’anteprima</title></head>
<body><h1>Circolo del Dr Divago</h1>
<p><a href="anteprima.html">Apri l’anteprima del sito</a></p></body></html>
"""


class Links(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.local = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("href", "src"):
            value = attrs.get(key)
            if not value:
                continue
            parts = urlsplit(value)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            self.local.append(parts.path)


def portable_html(source):
    """Mantiene i dati per la consultazione, eliminando i riferimenti ai media locali."""
    def clean(match):
        data = json.loads(match[1])
        for video in data.get("data/catalogo.json", {}).get("videos", []):
            video.pop("audio_file", None)
            video.pop("video_file", None)
        # I download dell'archivio privato non fanno parte della copia da inviare.
        research = data.get("data/ricerca.json")
        if research:
            research["counts"]["transcripts_saved"] = 0
            for video in research["videos"]:
                video["transcripts"] = []
        encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
        return '<script id="embedded-data" type="application/json">' + encoded + '</script>'
    source = re.sub(r'<script id="embedded-data" type="application/json">(.*?)</script>',
                    clean, source, flags=re.S)
    return source.replace('>ANTEPRIMA LOCALE<', '>ANTEPRIMA DEL PROGETTO<')


def create_package():
    manifest = build_site(ROOT)
    files = {item["preview"]: portable_html((ROOT / "sito" / item["preview"]).read_text(encoding="utf-8"))
             for item in manifest["pages"]}
    files["APRI-IL-SITO.html"] = START
    files["LEGGIMI.txt"] = GUIDA.format(date=date.today().strftime("%d/%m/%Y"))
    for name, source in files.items():
        if not name.endswith(".html"):
            continue
        if "file:///" in source or "/Users/" in source or "/private/tmp/" in source:
            raise ValueError("Percorso locale inatteso nella copia da condividere: " + name)
        for target in Links(source).local:
            if PurePosixPath(target).name != target or target not in files:
                raise ValueError(f"Collegamento locale non incluso: {name} → {target}")
    output = ROOT / "condivisione"
    output.mkdir(exist_ok=True)
    path = output / ("Circolo-del-Dr-Divago-anteprima-" + date.today().isoformat() + ".zip")
    folder = "Circolo-del-Dr-Divago/"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in files.items():
            archive.writestr(folder + name, source.encode("utf-8"))
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archivio ZIP non integro.")
        assert len(archive.namelist()) == len(files)
    print(f"Creato: {path}")
    print(f"Dimensione: {path.stat().st_size / 1_000_000:.1f} MB")
    print(f"Contenuto: {len(manifest['pages'])} pagine, file di apertura e guida. Nessun media incluso.")
    return path


if __name__ == "__main__":
    create_package()
