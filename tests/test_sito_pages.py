"""Verifica collegamenti reali e isolamento delle pagine generate, anche offline."""
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import unittest
from urllib.parse import urlsplit

from sito_pages import PAGES, LEGAL_PAGES, offline_links

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = []
        self.links = []
        self.nav = []
        self.body = {}
        self.headings = 0
        self.in_nav = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'body':
            self.body = attrs
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'h1':
            self.headings += 1
        if tag == 'nav' and attrs.get('aria-label') == 'Navigazione principale':
            self.in_nav = True
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
            if self.in_nav:
                self.nav.append(attrs)

    def handle_endtag(self, tag):
        if tag == 'nav':
            self.in_nav = False


class MultipageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'sito/dist/data/pagine.json').read_text())['pages']

    def test_unique_page_structure_and_active_navigation(self):
        for item in self.manifest:
            with self.subTest(page=item['path']):
                page = Page((ROOT / 'sito/dist' / item['path']).read_text())
                self.assertEqual(page.headings, 1)
                self.assertEqual(len(page.ids), len(set(page.ids)))
                self.assertEqual(len(page.nav), len(PAGES))
                selected = [link for link in page.nav if link.get('aria-current') == 'page']
                self.assertEqual(len(selected), 0 if item['page'] in LEGAL_PAGES else 1)
                if item['page'] in LEGAL_PAGES:
                    continue
                expected = {'articolo': 'blog', 'scheda': 'video'}.get(item['page'], item['page'])
                self.assertTrue(selected[0]['href'].endswith(PAGES[expected][0]))

    def test_all_static_internal_links_resolve(self):
        for item in self.manifest:
            for base, name in [(ROOT / 'sito/dist', item['path']), (ROOT / 'sito', item['preview'])]:
                path = base / name
                page = Page(path.read_text())
                for href in page.links:
                    parts = urlsplit(href)
                    if parts.scheme or parts.netloc or not parts.path:
                        continue
                    with self.subTest(page=name, href=href):
                        target = (path.parent / parts.path).resolve()
                        self.assertTrue(target.is_relative_to(base.resolve()))
                        self.assertTrue(target.is_file())

    def test_sections_have_dedicated_pages(self):
        home = Page((ROOT / 'sito/dist/index.html').read_text())
        self.assertNotIn('videos', home.ids)
        self.assertNotIn('books', home.ids)
        self.assertNotIn('research-list', home.ids)
        self.assertNotIn('posts', home.ids)
        for file, marker in [('video.html', 'videos'), ('biblioteca.html', 'books')]:
            self.assertIn(marker, Page((ROOT / 'sito/dist' / file).read_text()).ids)

    def test_every_catalog_video_has_a_real_page_and_hidden_sections_are_withdrawn(self):
        videos = json.loads((ROOT / 'sito/dist/data/catalogo.json').read_text())['videos']
        expected = {'video/' + video['id'] + '.html' for video in videos}
        actual = {item['path'] for item in self.manifest if item['page'] == 'scheda'}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 869)
        for name in ['schede-completate.html', 'trascrizioni.html', 'casa-editrice.html', 'blog.html']:
            self.assertFalse((ROOT / 'sito/dist' / name).exists())
        for item in self.manifest:
            text = (ROOT / 'sito/dist' / item['path']).read_text()
            self.assertNotIn('{{', text)
            for retired in ['schede-completate.html', 'trascrizioni.html', 'casa-editrice.html', 'blog.html']:
                self.assertNotIn(retired, text)

    def test_uncurated_video_does_not_claim_an_existing_editorial_summary(self):
        cards = {c['video_id'] for c in json.loads((ROOT / 'sito/dist/data/schede.json').read_text())}
        videos = json.loads((ROOT / 'sito/dist/data/catalogo.json').read_text())['videos']
        uncurated = next(video for video in videos if video['id'] not in cards)
        text = (ROOT / 'sito/dist/video' / (uncurated['id'] + '.html')).read_text()
        self.assertIn('Approfondimento in preparazione.', text)
        self.assertIn('data-play-video="' + uncurated['id'] + '"', text)
        self.assertNotIn('id="sintesi"', text)

    def test_offline_navigation_stays_in_preview_files(self):
        for item in self.manifest:
            page = Page((ROOT / 'sito' / item['preview']).read_text())
            self.assertEqual(page.body.get('data-preview'), 'true')
            for link in page.nav:
                self.assertTrue(link['href'].startswith('anteprima'))
            for href in page.links:
                parts = urlsplit(href)
                if not parts.scheme and parts.path.endswith('.html'):
                    self.assertTrue(parts.path.startswith('anteprima'))

    def test_article_relative_links_preserve_queries_and_fragments(self):
        html = '<a href="../biblioteca.html?q=Freud&amp;ordine=titolo#book-freud">Libro</a><a href="https://example.com/a">Fonte</a>'
        converted = offline_links(html, 'articoli/nota.html', {'biblioteca.html': 'anteprima-biblioteca.html'})
        self.assertIn('href="anteprima-biblioteca.html?q=Freud&amp;ordine=titolo#book-freud"', converted)
        self.assertIn('href="https://example.com/a"', converted)

    def test_editorial_cards_have_valid_sources_and_book_links(self):
        data = ROOT / 'sito/dist/data'
        cards = json.loads((data / 'schede.json').read_text())
        videos = {v['id']: v for v in json.loads((data / 'catalogo.json').read_text())['videos']}
        books = {b['id']: b for b in json.loads((data / 'libri.json').read_text())}
        self.assertGreaterEqual(len(cards), 10)
        self.assertEqual(len({c['video_id'] for c in cards}), len(cards))
        for card in cards:
            ident = card['video_id']
            duration = videos[ident]['duration']
            with self.subTest(video=ident):
                self.assertFalse(card['human_audio_review'])
                self.assertTrue(card['summary'].strip())
                minimum = 1 if duration < 180 else 3
                self.assertGreaterEqual(len(card['topics']), minimum)
                self.assertGreaterEqual(len(card['passages']), minimum)
                coverage = card['source_coverage']
                self.assertGreaterEqual(coverage.get('audio_duration_analyzed', coverage['last_end']), duration - 10)
                self.assertEqual(card['passages'], sorted(card['passages'], key=lambda p: p['seconds']))
                for passage in card['passages']:
                    self.assertTrue(0 <= passage['seconds'] < duration)
                    self.assertFalse(passage['human_audio_review'])
                for mention in card['books']:
                    self.assertTrue(0 <= mention['seconds'] < duration)
                    self.assertFalse(mention['verified'])
                    book = books[mention['book_id']]
                    self.assertTrue(any(m['video_id'] == ident and m.get('seconds') == mention['seconds'] for m in book['mentions']))
                    self.assertIsNone(book['edition_cited'])
                page = Page((ROOT / 'sito/dist/video' / (ident + '.html')).read_text())
                self.assertIn('passaggi', page.ids)
                self.assertIn('libri', page.ids)

    def test_probable_passages_are_not_confirmed_by_another_occurrence(self):
        books = {b['id']: b for b in json.loads((ROOT / 'sito/dist/data/libri.json').read_text())}
        fromm = books['fuga-dalla-liberta-fromm']
        mentions = {m['video_id']: m for m in fromm['mentions']}
        self.assertEqual(mentions['rtmt9_Mzdkw']['verification'], 'identificazione_probabile')
        self.assertEqual(mentions['1BOOpIWLGjU']['verification'], 'riscontro_testuale')
        self.assertFalse(mentions['1BOOpIWLGjU']['verified'])


if __name__ == '__main__':
    unittest.main()
