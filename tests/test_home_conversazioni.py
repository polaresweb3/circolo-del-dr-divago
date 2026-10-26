from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from home_conversazioni import home_conversations
from sito_pages import PAGES, build_site

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = [
    {'id': 'HXgpLjZ7apA', 'title': 'Il peso delle idee.', 'duration': 3356},
    {'id': 'vj1E4hCrITY', 'title': 'Alcuni precursori di George Orwell.', 'duration': 3499},
]


class HomeConversationsTests(unittest.TestCase):
    def test_selected_conversations_are_static_and_keep_the_requested_start_time(self):
        videos = deepcopy(VIDEOS)
        content = home_conversations(list(reversed(videos)))
        self.assertLess(content.index('home-video-HXgpLjZ7apA'), content.index('home-video-vj1E4hCrITY'))
        self.assertIn('video/vj1E4hCrITY.html?t=260', content)
        self.assertEqual(content.count('class="button"'), 2)
        self.assertNotIn('Apri su YouTube', content)
        self.assertNotIn('Leggi la scheda', content)
        self.assertIn('Guarda il video', content)
        self.assertIn('55:56', content)
        self.assertIn('58:19', content)
        self.assertEqual(content.count('<img '), 2)
        self.assertNotIn('<iframe', content)
        self.assertNotIn('autoplay', content)
        self.assertEqual(videos, VIDEOS)

    def test_missing_or_inconsistent_source_data_does_not_invent_a_video(self):
        with self.assertRaises(ValueError):
            home_conversations(VIDEOS[:1])
        invalid = deepcopy(VIDEOS)
        invalid[1]['duration'] = 200
        with self.assertRaises(ValueError):
            home_conversations(invalid)

    def test_titles_are_escaped(self):
        videos = deepcopy(VIDEOS)
        videos[0]['title'] = '<script>Un titolo</script>'
        content = home_conversations(videos)
        self.assertNotIn('<script>', content)
        self.assertIn('&lt;script&gt;', content)

    def test_generation_keeps_videos_first_and_preserves_timestamp_in_offline_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            templates, source = root / 'sito/templates', root / 'sito/dist'
            templates.mkdir(parents=True)
            (source / 'data').mkdir(parents=True)
            for name in ('home', 'video', 'privacy', 'crediti'):
                shutil.copyfile(ROOT / 'sito/templates' / (name + '.html'), templates / (name + '.html'))
            (source / 'styles.css').write_text('')
            (source / 'app.js').write_text('')
            for name, value in [('catalogo.json', {'videos': VIDEOS}), ('libri.json', []), ('schede.json', [])]:
                (source / 'data' / name).write_text(json.dumps(value))
            manifest = build_site(root, pages={key: PAGES[key] for key in ('home', 'video')})
            home = (source / 'index.html').read_text()
            self.assertLess(home.index('class="home-conversations"'), home.index('class="stats-band"'))
            self.assertNotIn('class="home-mission"', home)
            self.assertNotIn('Il Circolo raccoglie video e libri', home)
            self.assertEqual(home.count('Sergio Caldarella'), 1)
            self.assertNotIn('{{home_conversations}}', home)
            self.assertNotIn('id="home-videos"', home)
            offline = (root / 'sito/anteprima.html').read_text()
            self.assertIn('anteprima-scheda-vj1E4hCrITY.html?t=260', offline)
            paths = {item['path'] for item in manifest['pages']}
            self.assertIn('video/HXgpLjZ7apA.html', paths)
            self.assertIn('video/vj1E4hCrITY.html', paths)


if __name__ == '__main__':
    unittest.main()
