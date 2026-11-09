import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from seo_pubblico import apply_public_seo, canonical_url, metadata


HTML = '''<!doctype html><html><head><title>Libri &amp; idee</title>
<meta name="description" content="Una lettura &amp; una conversazione.">
<meta name="robots" content="noindex, nofollow"></head>
<body><h1>Libri &amp; idee</h1><script>{"author":"Sergio Caldarella"}</script></body></html>'''


class PublicSEOTests(unittest.TestCase):
    def test_metadata_escapes_text_and_preserves_body(self):
        result = metadata(HTML, 'video/HXgpLjZ7apA.html')
        self.assertEqual(result.split('<body>', 1)[1], HTML.split('<body>', 1)[1])
        self.assertIn('property="og:title" content="Libri &amp; idee"', result)
        self.assertIn('name="robots" content="index, follow, max-image-preview:large"', result)
        self.assertNotIn('noindex', result)
        self.assertIn('https://circolodivago.it/video/HXgpLjZ7apA.html', result)

    def test_repeated_generation_has_one_canonical_and_no_duplicate_metadata(self):
        once = metadata(HTML, 'index.html')
        self.assertEqual(metadata(once, 'index.html'), once)
        self.assertEqual(once.count('rel="canonical"'), 1)
        self.assertEqual(once.count('property="og:image"'), 1)
        self.assertIn('<title>Circolo del Dr Divago</title>', once)
        self.assertIn('property="og:title" content="Circolo del Dr Divago"', once)
        library = metadata(HTML, 'sala-lettura/biblioteca.html', indexable=False)
        self.assertIn('<title>Biblioteca — Circolo del Dr Divago</title>', library)

    def test_sitemap_excludes_retired_paths_and_unpublished_blog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['index.html', 'biblioteca.html', 'video/abcdefghijk.html',
                         'sala-lettura/index.html', 'originale/index.html', 'blog.html', 'versioni.html']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(HTML)
            # Una rigenerazione produce anche pagine ausiliarie prive di robots.
            (root / 'blog.html').write_text(HTML.replace('<meta name="robots" content="noindex, nofollow">', ''))
            image = root / 'source.png'
            image.write_bytes(b'original image bytes')
            library = root / 'data/libri.json'
            library.parent.mkdir()
            library.write_text('[{"author":"Sergio Caldarella","id":"libro"}]')
            before = library.read_bytes()
            result = apply_public_seo(root, image_source=image)
            ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = [node.text for node in ET.parse(root / 'sitemap.xml').findall('s:url/s:loc', ns)]
            self.assertEqual(urls, ['https://circolodivago.it/', 'https://circolodivago.it/biblioteca.html',
                                    'https://circolodivago.it/video/abcdefghijk.html'])
            self.assertEqual(result['canonical_pages'], 3)
            self.assertIn('noindex, follow', (root / 'sala-lettura/index.html').read_text())
            self.assertIn('noindex, nofollow', (root / 'blog.html').read_text())
            self.assertEqual((root / 'originale/index.html').read_text().split('<body>', 1)[1],
                             HTML.split('<body>', 1)[1])
            self.assertIn('href="../favicon.ico?v=', (root / 'video/abcdefghijk.html').read_text())
            self.assertIn('href="../favicon.ico?v=', (root / 'sala-lettura/index.html').read_text())
            self.assertEqual((root / 'favicon.ico').read_bytes(),
                             (Path(__file__).resolve().parents[1] / 'assets/icons/favicon.ico').read_bytes())
            self.assertEqual(library.read_bytes(), before)
            self.assertEqual((root / 'assets/social/circolo-divago.png').read_bytes(), image.read_bytes())
            self.assertIn('Sitemap: https://circolodivago.it/sitemap.xml', (root / 'robots.txt').read_text())

    def test_does_not_create_old_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'index.html').write_text(HTML)
            image = root / 'source.png'
            image.write_bytes(b'image')
            apply_public_seo(root, image_source=image)
            self.assertFalse((root / 'originale').exists())
            self.assertFalse((root / 'sala-lettura').exists())

    def test_canonical_addresses_use_only_https_main_origin(self):
        self.assertEqual(canonical_url('sala-lettura/index.html'), 'https://circolodivago.it/')
        self.assertEqual(canonical_url('sala-lettura/video/abcdefghijk.html'),
                         'https://circolodivago.it/video/abcdefghijk.html')
        for origin in ['http://circolodivago.it', 'https://circolodivago.it/originale',
                       'https://user:password@circolodivago.it']:
            with self.assertRaises(ValueError):
                canonical_url('index.html', origin)

    def test_github_pages_rebuild_keeps_custom_domain(self):
        import prepara_github_pages
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'pubblicazione/circolo-del-dr-divago/dist'
            source.mkdir(parents=True)
            (source / 'index.html').write_text(HTML)
            (source / 'robots.txt').write_text('User-agent: *\nAllow: /\n')
            with patch.object(prepara_github_pages, '__file__', str(root / 'prepara_github_pages.py')), \
                    patch.object(prepara_github_pages, 'main'):
                for _ in range(2):
                    prepara_github_pages.prepare()
                    self.assertEqual((root / 'docs/CNAME').read_text(), 'circolodivago.it\n')
                    self.assertTrue((root / 'docs/.nojekyll').is_file())
                    self.assertEqual((root / 'docs/robots.txt').read_text(), 'User-agent: *\nAllow: /\n')


if __name__ == '__main__':
    unittest.main()
