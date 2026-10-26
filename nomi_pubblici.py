"""La firma pubblica del relatore, senza modificare identificativi e fonti."""
from html import escape, unescape
from html.parser import HTMLParser
import re


def public_name(text):
    text = re.sub(r'\b(?:Sergio\s+Caldarella|Caldarella,\s*Sergio|S\.?\s+Caldarella|Caldarella)\b', 'Dr Divago', text, flags=re.I)
    text = re.sub(r'\b[Ss]ergio\b(?![ \t]+[A-ZÀ-ÖØ-Þ])', 'Dr Divago', text)
    return re.sub(r'\bDr\.\s+Divago\b', 'Dr Divago', text, flags=re.I)


def public_html(source):
    """Corregge testo e attributi leggibili; conserva markup, URL e introduzione."""
    class Names(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.lines = [0]
            self.lines.extend(match.end() for match in re.finditer('\n', source))
            self.stack = []
            self.changes = []

        def position(self):
            line, column = self.getpos()
            return self.lines[line - 1] + column

        def start(self, tag, attrs, closed=False):
            raw = self.get_starttag_text()
            def attribute(match):
                name, quote, value = match.groups()
                original = unescape(value)
                revised = public_name(original)
                return match[0] if original == revised else name + '=' + quote + escape(revised, quote=True) + quote
            revised = re.sub(r'\b(alt|title|aria-label)=(\"|\')(.*?)\2', attribute, raw, flags=re.S | re.I)
            if revised != raw:
                self.changes.append((self.position(), self.position() + len(raw), revised))
            skip = (self.stack and self.stack[-1][1]) or tag in {'script', 'style', 'code', 'pre', 'textarea'} or 'data-name-intro' in dict(attrs)
            if not closed and tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
                self.stack.append((tag, skip))

        def handle_starttag(self, tag, attrs):
            self.start(tag, attrs)

        def handle_startendtag(self, tag, attrs):
            self.start(tag, attrs, closed=True)

        def handle_endtag(self, tag):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    del self.stack[index:]
                    break

        def handle_data(self, text):
            if self.stack and self.stack[-1][1]:
                return
            revised = public_name(text)
            if revised != text:
                self.changes.append((self.position(), self.position() + len(text), revised))

    parser = Names()
    parser.feed(source)
    for start, end, text in reversed(parser.changes):
        source = source[:start] + text + source[end:]
    return source
