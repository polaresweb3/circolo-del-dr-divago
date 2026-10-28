import unittest
from html.parser import HTMLParser

from sito_pages import sheet_summary, video_content, catalog_video_content


class Paragraphs(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.inside = False
        self.parts = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag == 'p':
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'p':
            self.inside = False

    def handle_data(self, text):
        if self.inside:
            self.parts.append(text)


class RefinementTest(unittest.TestCase):
    def test_expanding_long_summary_preserves_every_word_in_order(self):
        text = ('Una domanda su libri, libertà e pensiero. ' * 40).strip()
        rendered = sheet_summary(text)
        self.assertIn('<details', rendered)
        self.assertEqual(' '.join(' '.join(Paragraphs(rendered).parts).split()), text)

    def test_long_summary_without_full_stops_keeps_all_the_text(self):
        text = ' '.join('parola' + str(i) for i in range(220))
        rendered = sheet_summary(text)
        self.assertEqual(' '.join(' '.join(Paragraphs(rendered).parts).split()), text)

    def test_short_summary_does_not_need_an_extra_control(self):
        self.assertEqual(sheet_summary('Una sintesi breve.'), '<p>Una sintesi breve.</p>')

    def test_uncertainty_and_timestamp_stay_visible_outside_book_details(self):
        card = dict(video_id='abcdefghijk', title='Video', duration_seconds=60,
                    summary='Una sintesi.', passages=[dict(seconds=10, label='Passaggio')],
                    books=[dict(book_id='libro', confidence='identificazione_probabile',
                                seconds=10, evidence='Riscontro da approfondire.')])
        books = [dict(id='libro', title='Libro', author='Autore', cover=dict(edition_label='Edizione'))]
        rendered = video_content(card, books)
        self.assertLess(rendered.index('Identificazione probabile'), rendered.index('<details class="card-book-details">'))
        self.assertIn('</details><a class="text-link"', rendered)
        self.assertIn('Passaggio 0:10', rendered)
        for target in ['filmato', 'sintesi', 'libri', 'passaggi']:
            self.assertIn(f'href="#{target}"', rendered)
            self.assertIn(f'id="{target}"', rendered)

    def test_catalog_page_has_no_links_to_missing_sections(self):
        rendered = catalog_video_content(dict(id='abcdefghijk', title='Video', duration=60), [])
        self.assertIn('href="#filmato"', rendered)
        for target in ['sintesi', 'libri', 'passaggi']:
            self.assertNotIn(f'href="#{target}"', rendered)
