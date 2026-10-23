"""La build deve fermarsi se un asset verificato viene corrotto o sostituito."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from verifica_copertine import verify_covers

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC')

class CoverIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        (self.root / 'assets/copertine').mkdir(parents=True)
        self.asset = self.root / 'assets/copertine/test.png'
        self.asset.write_bytes(PNG)
        self.cover = dict(src='assets/copertine/test.png', edition_label='Edizione di riferimento',
                          source_page='https://example.org/catalogo',
                          asset_sha256=hashlib.sha256(PNG).hexdigest(),
                          integrity_review={'decoded': True})
        self.save()

    def save(self):
        (self.root / 'data/libri.json').write_text(json.dumps([{'id': 'test', 'cover': self.cover}]))

    def test_verified_asset_passes(self):
        self.assertEqual(verify_covers(self.root)['works_checked'], 1)

    def test_truncated_image_with_valid_signature_is_rejected(self):
        self.asset.write_bytes(PNG[:20])
        with self.assertRaisesRegex(ValueError, 'Integrità'):
            verify_covers(self.root)

    def test_missing_file_is_rejected(self):
        self.asset.unlink()
        with self.assertRaisesRegex(ValueError, 'Immagine locale'):
            verify_covers(self.root)

    def test_unreviewed_download_is_rejected(self):
        self.cover.pop('integrity_review')
        self.save()
        with self.assertRaisesRegex(ValueError, 'Decodifica'):
            verify_covers(self.root)

    def test_known_placeholder_is_rejected_even_with_matching_checksum(self):
        with patch('verifica_copertine.PLACEHOLDER_HASHES', {hashlib.sha256(PNG).hexdigest()}):
            with self.assertRaisesRegex(ValueError, 'Segnaposto'):
                verify_covers(self.root)

    def test_external_svg_dependency_is_rejected(self):
        raw = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.org/cover.jpg"/></svg>'
        svg = self.asset.with_suffix('.svg')
        svg.write_bytes(raw)
        self.cover.update(src='assets/copertine/test.svg', asset_sha256=hashlib.sha256(raw).hexdigest())
        self.save()
        with self.assertRaisesRegex(ValueError, 'fonte esterna'):
            verify_covers(self.root)
