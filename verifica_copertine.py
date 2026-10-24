#!/usr/bin/env python3
"""Controlla che tutte le opere abbiano un’immagine locale e una fonte tracciabile."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

# Risposta JPEG regolare del servizio IBS, ma non una copertina editoriale.
PLACEHOLDER_HASHES = {
    '6181843aced612b2a2dc1aa2b7ad6a08b0d6d26e6cdf9e9f169500f1e4c228c7',
    'e7856c81f7f83bab1d324ff85020f0a6207a1ab0495810a8ab47f1256cd3a084',  # Libreria Universitaria: copertina non disponibile.
}


def verify_covers(source):
    source = Path(source).resolve()
    books = json.loads((source / 'data/libri.json').read_text())
    checked = []
    for book in books:
        cover = book.get('cover') or {}
        if not all(cover.get(key) for key in ('src', 'edition_label', 'source_page')):
            raise ValueError('Copertina o provenienza mancante: ' + book['id'])
        asset = (source / cover['src']).resolve()
        if not asset.is_relative_to(source / 'assets/copertine') or not asset.is_file():
            raise ValueError('Immagine locale non valida: ' + book['id'])
        raw = asset.read_bytes()
        fingerprint = hashlib.sha256(raw).hexdigest()
        if fingerprint in PLACEHOLDER_HASHES:
            raise ValueError('Segnaposto al posto della copertina: ' + book['id'])
        if not cover.get('asset_sha256') or fingerprint != cover['asset_sha256']:
            raise ValueError('Integrità della copertina non verificata: ' + book['id'])
        if not (cover.get('integrity_review') or {}).get('decoded'):
            raise ValueError('Decodifica della copertina da controllare: ' + book['id'])
        if asset.suffix == '.svg':
            tree = ET.fromstring(raw)
            if tree.tag != '{http://www.w3.org/2000/svg}svg':
                raise ValueError('SVG non valido: ' + book['id'])
            for element in tree.iter():
                for key, value in element.attrib.items():
                    if key.rsplit('}', 1)[-1] == 'href' and not value.startswith(('data:image/', '#')):
                        raise ValueError('Immagine SVG dipendente da una fonte esterna: ' + book['id'])
        elif not (raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'\x89PNG\r\n\x1a\n')
                  or raw.startswith((b'GIF87a', b'GIF89a'))
                  or raw.startswith(b'RIFF') and raw[8:12] == b'WEBP'):
            raise ValueError('Formato immagine non riconosciuto: ' + book['id'])
        url = urlparse(cover['source_page'])
        if url.scheme not in ('https', 'http') or not url.netloc:
            raise ValueError('Fonte della copertina non valida: ' + book['id'])
        if cover.get('container_title') and not cover.get('edition_note'):
            raise ValueError('Raccolta senza spiegazione: ' + book['id'])
        checked.append(book['id'])
    return {'works_checked': len(checked), 'missing_images': 0, 'local_assets_checked': True,
            'provenance_checked': True, 'asset_checksums_checked': True,
            'decoded_image_audit_present': True, 'known_placeholders_rejected': True}


if __name__ == '__main__':
    print(json.dumps(verify_covers(Path(__file__).resolve().parent / 'sito/dist'), indent=2))
