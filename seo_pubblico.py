"""Metadati e sitemap del sito pubblico, senza cambiare i contenuti editoriali."""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import posixpath
import re
import shutil
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET

SITE_ORIGIN = 'https://circolodivago.it'
SITE_NAME = 'Circolo del Dr Divago'
SHARE_IMAGE = 'assets/social/circolo-divago.png'
SHARE_ALT = 'Circolo del Dr Divago — Libri, idee, conversazioni.'
MAIN_PAGES = {'index.html', 'video.html', 'biblioteca.html', 'eventi.html',
              'progetto.html', 'privacy.html', 'crediti.html'}
PAGE_TITLES = {'index.html': SITE_NAME, 'video.html': 'Video',
               'biblioteca.html': 'Biblioteca', 'eventi.html': 'Eventi',
               'progetto.html': 'Progetto editoriale', 'privacy.html': 'Privacy',
               'crediti.html': 'Crediti', 'blog.html': 'Blog'}
ICON_FILES = {'favicon.ico': ('icon', 'image/x-icon', None),
              'favicon-32x32.png': ('icon', 'image/png', '32x32'),
              'apple-touch-icon.png': ('apple-touch-icon', None, '180x180')}
META_TAG = re.compile(r'<meta\b[^>]*>', re.I)
LINK_TAG = re.compile(r'<link\b[^>]*>', re.I)


class Head(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.in_title = False
        self.description = ''
        self.attrs = {}
        self.feed(re.split(r'</head\s*>', source, maxsplit=1, flags=re.I)[0])

    def handle_starttag(self, tag, attrs):
        self.attrs = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'meta' and self.attrs.get('name', '').lower() == 'description':
            self.description = self.attrs.get('content', '')

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)


def normalized_origin(origin):
    parts = urlsplit(origin)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.path not in ('', '/') or parts.query or parts.fragment):
        raise ValueError('Il sito pubblico richiede una origine HTTPS senza percorsi.')
    return origin.rstrip('/')


def canonical_url(path, origin=SITE_ORIGIN):
    origin = normalized_origin(origin)
    relative = Path(path).as_posix()
    if relative.startswith('sala-lettura/'):
        relative = relative.removeprefix('sala-lettura/')
    if relative.startswith('/') or '..' in Path(relative).parts:
        raise ValueError('Percorso pubblico non valido.')
    return origin + '/' + ('' if relative == 'index.html' else quote(relative, safe='/-._~'))


def metadata(source, path, *, origin=SITE_ORIGIN, indexable=True):
    if not re.search(r'</head\s*>', source, re.I):
        raise ValueError('Intestazione HTML mancante: ' + str(path))
    relative = Path(path).as_posix().removeprefix('sala-lettura/')
    if relative in PAGE_TITLES:
        title = PAGE_TITLES[relative]
        title += '' if relative == 'index.html' else ' — ' + SITE_NAME
        source = re.sub(r'<title\b[^>]*>.*?</title>', '<title>' + escape(title) + '</title>',
                        source, count=1, flags=re.I | re.S)
    head = Head(source)
    title = ''.join(head.title_parts).strip() or SITE_NAME
    description = head.description or 'Libri, idee e conversazioni del Circolo del Dr Divago.'

    def clean_meta(match):
        attrs = Head(match[0]).attrs
        name = attrs.get('name', '').lower()
        prop = attrs.get('property', '').lower()
        return '' if name == 'robots' or name.startswith('twitter:') or prop.startswith('og:') else match[0]

    def clean_link(match):
        attrs = Head(match[0]).attrs
        return '' if 'canonical' in attrs.get('rel', '').lower().split() else match[0]

    source = META_TAG.sub(clean_meta, source)
    source = LINK_TAG.sub(clean_link, source)
    url = canonical_url(path, origin)
    image = normalized_origin(origin) + '/' + SHARE_IMAGE
    tags = [f'<link rel="canonical" href="{escape(url, quote=True)}">']
    values = [('name', 'robots', 'index, follow, max-image-preview:large' if indexable else 'noindex, follow'),
              ('property', 'og:type', 'website'), ('property', 'og:site_name', SITE_NAME),
              ('property', 'og:locale', 'it_IT'), ('property', 'og:title', title),
              ('property', 'og:description', description), ('property', 'og:url', url),
              ('property', 'og:image', image), ('property', 'og:image:type', 'image/png'),
              ('property', 'og:image:width', '1200'), ('property', 'og:image:height', '630'),
              ('property', 'og:image:alt', SHARE_ALT), ('name', 'twitter:card', 'summary_large_image'),
              ('name', 'twitter:title', title), ('name', 'twitter:description', description),
              ('name', 'twitter:image', image), ('name', 'twitter:image:alt', SHARE_ALT)]
    tags += [f'<meta {attr}="{name}" content="{escape(value, quote=True)}">'
             for attr, name, value in values]
    # Elimina solo righe vuote dell'head lasciate dalla precedente applicazione.
    before, after = re.split(r'</head\s*>', source, maxsplit=1, flags=re.I)
    before = re.sub(r'\n[ \t]*(?=\n)', '', before).rstrip()
    return before + '\n  ' + '\n  '.join(tags) + '\n</head>' + after


def favicon_links(source, path, versions):
    """Usa percorsi relativi anche nelle pagine dei video e nelle copie esistenti."""
    before, after = re.split(r'</head\s*>', source, maxsplit=1, flags=re.I)
    def clean(match):
        rel = Head(match[0]).attrs.get('rel', '').lower().split()
        return '' if 'icon' in rel or 'apple-touch-icon' in rel else match[0]
    before = LINK_TAG.sub(clean, before)
    tags = []
    for name, (rel, mime, size) in ICON_FILES.items():
        href = posixpath.relpath(name, posixpath.dirname(Path(path).as_posix()) or '.')
        tag = f'<link rel="{rel}" href="{href}?v={versions[name]}"'
        if mime:
            tag += f' type="{mime}"'
        if size:
            tag += f' sizes="{size}"'
        tags.append(tag + '>')
    before = re.sub(r'\n[ \t]*(?=\n)', '', before).rstrip()
    return before + '\n  ' + '\n  '.join(tags) + '\n</head>' + after


def apply_public_seo(destination, *, origin=SITE_ORIGIN, image_source=None, icon_source=None):
    destination = Path(destination)
    origin = normalized_origin(origin)
    image_source = (Path(image_source) if image_source is not None else
                    Path(__file__).resolve().parent / SHARE_IMAGE)
    if not image_source.is_file():
        raise ValueError('Immagine di condivisione mancante.')
    image_target = destination / SHARE_IMAGE
    image_target.parent.mkdir(parents=True, exist_ok=True)
    if image_source.resolve() != image_target.resolve():
        shutil.copyfile(image_source, image_target)
    icon_source = Path(icon_source) if icon_source else Path(__file__).resolve().parent / 'assets/icons'
    versions = {}
    for name in ICON_FILES:
        data = (icon_source / name).read_bytes()
        (destination / name).write_bytes(data)
        versions[name] = hashlib.sha256(data).hexdigest()[:12]
    pages = sorted(p for p in destination.glob('*.html') if p.name in MAIN_PAGES)
    pages += sorted((destination / 'video').glob('*.html'))
    articles = sorted((destination / 'articoli').glob('*.html'))
    pages += articles
    if articles and (destination / 'blog.html').is_file():
        pages.append(destination / 'blog.html')
    urls = []
    for page in pages:
        relative = page.relative_to(destination).as_posix()
        page.write_text(metadata(page.read_text(encoding='utf-8'), relative, origin=origin), encoding='utf-8')
        urls.append(canonical_url(relative, origin))
        # Le copie esistenti restano escluse dall'indice e non generano nuovi URL.
        duplicate = destination / 'sala-lettura' / relative
        if duplicate.is_file():
            duplicate.write_text(metadata(duplicate.read_text(encoding='utf-8'),
                                          'sala-lettura/' + relative, origin=origin,
                                          indexable=False), encoding='utf-8')
    # Anche dopo una generazione da zero, le pagine ausiliarie non selezionate
    # (per esempio il Blog vuoto) conservano l'esclusione dai motori di ricerca.
    for page in destination.rglob('*.html'):
        source = page.read_text(encoding='utf-8')
        head_source = re.split(r'</head\s*>', source, maxsplit=1, flags=re.I)[0]
        has_robots = any(Head(tag[0]).attrs.get('name', '').lower() == 'robots'
                         for tag in META_TAG.finditer(head_source))
        if not has_robots:
            revised = re.sub(r'</head\s*>', '<meta name="robots" content="noindex, nofollow">\n</head>',
                             source, count=1, flags=re.I)
            source = revised
        page.write_text(favicon_links(source, page.relative_to(destination), versions), encoding='utf-8')
    namespace = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    ET.register_namespace('', namespace)
    sitemap = ET.Element(f'{{{namespace}}}urlset')
    for url in sorted(set(urls)):
        row = ET.SubElement(sitemap, f'{{{namespace}}}url')
        ET.SubElement(row, f'{{{namespace}}}loc').text = url
    ET.indent(sitemap, space='  ')
    (destination / 'sitemap.xml').write_bytes(ET.tostring(sitemap, encoding='utf-8', xml_declaration=True) + b'\n')
    (destination / 'robots.txt').write_text('User-agent: *\nAllow: /\n\nSitemap: ' + origin + '/sitemap.xml\n', encoding='utf-8')
    return {'canonical_pages': len(set(urls)), 'origin': origin, 'sitemap': 'sitemap.xml',
            'share_image': SHARE_IMAGE}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(apply_public_seo(args.destination), ensure_ascii=False))
