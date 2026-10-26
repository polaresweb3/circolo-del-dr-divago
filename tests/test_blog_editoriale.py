from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from blog_editoriale import RUBRIC, VOICES, published_articles, home_latest, blog_index, blog_article
from nomi_pubblici import public_html, public_name
from sito_pages import PAGES, build_site

ROOT = Path(__file__).resolve().parents[1]


def article(ident='prima-lettura', when='2026-10-01'):
    return {'id': ident, 'category': RUBRIC, 'status': 'published', 'published_at': when,
            'title': 'Titolo di ' + ident, 'excerpt': 'Un invito alla lettura con Sergio Caldarella.',
            'paragraphs': ['Una conversazione di Sergio Caldarella da riscoprire.'],
            'reference': {'label': 'Guarda la conversazione', 'url': 'https://www.youtube.com/watch?v=Qr7vi4Mgd_0'}}


def voice():
    result = article('riflessione-originale', '2026-10-27')
    result.update(category=VOICES, author='Riccardo Persiani')
    result.pop('reference')
    return result


class BlogTests(unittest.TestCase):
    def test_home_selects_newest_published_article_independently_of_source_order(self):
        older, newer = article(), article('ultima-lettura', '2026-10-26')
        draft = {'status': 'draft', 'id': 'bozza-incompleta', 'category': RUBRIC}
        source = [older, draft, newer]
        original = deepcopy(source)
        posts = published_articles(source)
        teaser = home_latest(posts)
        self.assertIn('articoli/ultima-lettura.html', teaser)
        self.assertNotIn('articoli/prima-lettura.html', teaser)
        self.assertNotIn('bozza-incompleta', teaser)
        self.assertEqual(source, original)

    def test_empty_rubric_has_no_fictitious_article_or_dead_article_link(self):
        teaser = home_latest([])
        self.assertIn('Il primo articolo è in preparazione.', teaser)
        self.assertIn('blog.html#una-divagazione-necessaria', teaser)
        self.assertNotIn('articoli/', teaser)

    def test_newer_original_article_does_not_displace_rubric_on_home(self):
        posts = published_articles([article(), voice()])
        self.assertIn('articoli/prima-lettura.html', home_latest(posts))
        self.assertNotIn('riflessione-originale', home_latest(posts))
        self.assertNotIn('riflessione-originale', blog_index(posts))
        voices = blog_index(posts, category=VOICES)
        self.assertIn('riflessione-originale', voices)
        self.assertIn('Riccardo Persiani', voices)
        self.assertNotIn('prima-lettura', voices)

    def test_original_contributions_require_author_and_can_stand_without_external_reference(self):
        original = voice()
        self.assertEqual(published_articles([original]), [original])
        page = blog_article(original)
        self.assertIn('../blog.html#voci-del-blog', page)
        self.assertIn('Riccardo Persiani', page)
        self.assertNotIn('Guarda la conversazione', page)
        original.pop('author')
        with self.assertRaises(ValueError):
            published_articles([original])

    def test_published_article_needs_real_content_date_and_reference(self):
        for field in ('published_at', 'excerpt', 'paragraphs', 'reference'):
            value = article()
            value.pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                published_articles([value])
        value = article()
        value['reference']['url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError):
            published_articles([value])
        with self.assertRaises(ValueError):
            published_articles([article(), article()])

    def test_home_blog_and_article_pages_share_publication_and_offline_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            templates, dist = root / 'sito/templates', root / 'sito/dist'
            templates.mkdir(parents=True)
            (dist / 'data').mkdir(parents=True)
            (templates / 'home.html').write_text('<h1>Home</h1><p data-name-intro>Sergio Caldarella, Dr Divago.</p>{{latest_divagation}}')
            (templates / 'blog.html').write_text((ROOT / 'sito/templates/blog.html').read_text())
            for name in ('privacy', 'crediti'):
                (templates / (name + '.html')).write_text('<h1>' + name + '</h1>')
            (dist / 'styles.css').write_text('')
            (dist / 'app.js').write_text('')
            posts = [article(), {'status': 'draft', 'id': 'bozza-incompleta'}, article('ultima-lettura', '2026-10-26'), voice()]
            (dist / 'data/articoli-blog.json').write_text(json.dumps(posts))
            manifest = build_site(root, pages={key: PAGES[key] for key in ('home', 'blog')})
            paths = {item['path'] for item in manifest['pages']}
            self.assertIn('articoli/ultima-lettura.html', paths)
            self.assertIn('articoli/riflessione-originale.html', paths)
            self.assertNotIn('articoli/bozza-incompleta.html', paths)
            home = (dist / 'index.html').read_text()
            self.assertEqual(home.count('Sergio Caldarella'), 1)
            self.assertIn('articoli/ultima-lettura.html', home)
            self.assertNotIn('articoli/prima-lettura.html', home)
            self.assertNotIn('riflessione-originale', home)
            blog = (dist / 'blog.html').read_text()
            self.assertIn('articoli/prima-lettura.html', blog)
            self.assertIn('articoli/ultima-lettura.html', blog)
            self.assertNotIn('Sergio Caldarella', blog)
            self.assertIn('id="voci-del-blog"', blog)
            self.assertIn('articoli/riflessione-originale.html', blog)
            offline = (root / 'sito/anteprima.html').read_text()
            self.assertIn('anteprima-articolo-ultima-lettura.html', offline)
            body = (dist / 'articoli/ultima-lettura.html').read_text()
            self.assertIn('https://www.youtube.com/watch?v=Qr7vi4Mgd_0', body)
            self.assertNotIn('Sergio Caldarella', body)
            original = (root / 'sito/anteprima-articolo-riflessione-originale.html').read_text()
            self.assertIn('anteprima-blog.html#voci-del-blog', original)
            self.assertNotIn('{{voices_articles}}', blog)

    def test_email_invitation_is_in_preparation_without_signup_form(self):
        template = (ROOT / 'sito/templates/blog.html').read_text()
        self.assertIn('Ricevi la prossima divagazione', template)
        self.assertIn('In preparazione', template)
        self.assertNotIn('<form', template)
        self.assertNotIn('<input', template)
        self.assertNotIn('mensile', template)


class PublicNameTests(unittest.TestCase):
    def test_alias_does_not_rename_other_people(self):
        self.assertEqual(public_name('Sergio Caldarella, Caldarella e Sergio discutono.'), 'Dr Divago, Dr Divago e Dr Divago discutono.')
        for name in ('Sergio Mattarella', 'Sergio Landucci', 'Sergio Harari', 'Sergio Campailla', 'Sergio Claudio Perroni'):
            self.assertEqual(public_name(name), name)

    def test_html_keeps_home_introduction_urls_ids_svg_and_source_data(self):
        source = ('<p data-name-intro>Sergio Caldarella, Dr Divago.</p><p>Sergio Caldarella</p>'
                  '<a id="libro-caldarella" href="https://example.com/sergio-caldarella" title="Sergio Caldarella">Caldarella</a>'
                  '<svg viewBox="0 0 10 10"><linearGradient id="x"></linearGradient></svg>'
                  '<script>{"author":"Sergio Caldarella"}</script>')
        result = public_html(source)
        self.assertIn('<p data-name-intro>Sergio Caldarella, Dr Divago.</p>', result)
        self.assertIn('href="https://example.com/sergio-caldarella"', result)
        self.assertIn('id="libro-caldarella"', result)
        self.assertIn('title="Dr Divago">Dr Divago</a>', result)
        self.assertIn('<linearGradient id="x"></linearGradient>', result)
        self.assertIn('<script>{"author":"Sergio Caldarella"}</script>', result)


if __name__ == '__main__':
    unittest.main()
