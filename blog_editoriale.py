"""Rubrica del Blog e ultimo articolo in homepage, generati dagli stessi dati."""
from datetime import date
from html import escape
import re
from urllib.parse import urlsplit

RUBRIC = 'una-divagazione-necessaria'
RUBRIC_TITLE = 'Una divagazione necessaria'
VOICES = 'voci-del-blog'
CATEGORIES = {RUBRIC: RUBRIC_TITLE, VOICES: 'Voci del blog'}
MONTHS = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
          'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')


def published_articles(articles):
    if not isinstance(articles, list):
        raise ValueError('Gli articoli del Blog devono essere una lista.')
    published = []
    seen = set()
    for article in articles:
        if not isinstance(article, dict):
            raise ValueError('Articolo del Blog non valido.')
        status = article.get('status', 'draft')
        if status == 'draft':
            continue
        if status != 'published':
            raise ValueError('Stato dell’articolo non valido: usare draft o published.')
        ident = article.get('id', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', ident) or ident in seen:
            raise ValueError('Identificativo dell’articolo non valido o duplicato.')
        seen.add(ident)
        category = article.get('category')
        if category not in CATEGORIES:
            raise ValueError('Categoria del Blog non riconosciuta.')
        author = article.get('author')
        if (category == VOICES or author is not None) and (not isinstance(author, str) or not author.strip()):
            raise ValueError('Gli articoli originali richiedono la firma dell’autore.')
        for field in ('title', 'excerpt', 'published_at'):
            if not isinstance(article.get(field), str) or not article[field].strip():
                raise ValueError('Titolo, sintesi e data sono obbligatori per un articolo pubblicato.')
        try:
            date.fromisoformat(article['published_at'])
        except ValueError as error:
            raise ValueError('Data dell’articolo non valida: usare AAAA-MM-GG.') from error
        paragraphs = article.get('paragraphs')
        if not isinstance(paragraphs, list) or not paragraphs or any(not isinstance(p, str) or not p.strip() for p in paragraphs):
            raise ValueError('Un articolo pubblicato deve avere un testo completo.')
        reference = article.get('reference')
        if category == RUBRIC or reference is not None:
            if not isinstance(reference, dict) or not isinstance(reference.get('url'), str) or not isinstance(reference.get('label'), str) or not reference['label'].strip():
                raise ValueError('Indicare il video o il libro scelto, con etichetta e collegamento.')
            url = urlsplit(reference['url'])
            if url.scheme != 'https' or not url.netloc:
                raise ValueError('Il collegamento al video o al libro deve usare HTTPS.')
        published.append(article)
    return sorted(published, key=lambda item: (item['published_at'], item['id']), reverse=True)


def article_date(article):
    value = date.fromisoformat(article['published_at'])
    return f'<time datetime="{value.isoformat()}">{value.day} {MONTHS[value.month - 1]} {value.year}</time>'


def blog_index(articles, category=RUBRIC):
    articles = [article for article in articles if article['category'] == category]
    if not articles:
        message = 'La prima divagazione è in preparazione.' if category == RUBRIC else 'Uno spazio in preparazione, aperto a nuove voci.'
        return '<p class="blog-empty">' + message + '</p>'
    return ''.join('<article class="blog-card"><p class="blog-meta">' + article_date(article) + '</p>'
                   '<div><h3><a href="articoli/' + article['id'] + '.html">' + escape(article['title']) + '</a></h3>'
                   '<p class="blog-byline">' + escape(article.get('author') or 'Redazione del Circolo') + '</p>'
                   '<p>' + escape(article['excerpt']) + '</p></div><a class="text-link" href="articoli/'
                   + article['id'] + '.html">Leggi l’articolo →</a></article>' for article in articles)


def home_latest(articles):
    articles = [article for article in articles if article['category'] == RUBRIC]
    start = ('<section class="section wrap home-blog" aria-labelledby="home-blog-title">'
             '<div class="home-blog-intro"><p class="eyebrow">DAL BLOG · UNA DIVAGAZIONE NECESSARIA</p>'
             '<h2 id="home-blog-title">Un’idea da <em>portare con te.</em></h2>'
             '<p>Un libro, una conversazione, un altro modo di guardare la vita.</p>'
             '<a class="text-link" href="blog.html#una-divagazione-necessaria">Scopri la rubrica →</a></div>')
    if not articles:
        return start + ('<div class="home-blog-latest"><p class="eyebrow">LA PROSSIMA DIVAGAZIONE</p>'
                        '<h3>Il primo articolo è in preparazione.</h3>'
                        '<p>Una lettura consigliata da Dr Divago oppure una sua conversazione da riscoprire.</p>'
                        '</div></section>')
    article = articles[0]
    return start + ('<article class="home-blog-latest"><p class="eyebrow">L’ULTIMO ARTICOLO</p>'
                    '<p class="blog-meta">' + article_date(article) + '</p><h3><a href="articoli/'
                    + article['id'] + '.html">' + escape(article['title']) + '</a></h3><p>'
                    + escape(article['excerpt']) + '</p><a class="text-link" href="articoli/'
                    + article['id'] + '.html">Leggi l’articolo →</a></article></section>')


def blog_article(article):
    reference = article.get('reference')
    category = article['category']
    category_title = CATEGORIES[category]
    reference_link = ('<p><a class="button" href="' + escape(reference['url'], quote=True)
                      + '" target="_blank" rel="noopener noreferrer">' + escape(reference['label'])
                      + ' <span aria-hidden="true">↗</span></a></p>') if reference else ''
    return ('<article class="section wrap article-page"><a class="text-link" href="../blog.html#'
            + category + '">← ' + category_title + '</a><header class="article-heading">'
            '<p class="eyebrow">' + category_title.upper() + '</p><h1>' + escape(article['title'])
            + '</h1><p class="article-byline">' + article_date(article) + ' · '
            + escape(article.get('author') or 'Redazione del Circolo') + '</p></header>'
            '<div class="article-body">' + ''.join('<p>' + escape(p) + '</p>' for p in article['paragraphs'])
            + '</div>' + reference_link +
            '<footer class="article-end"><a class="text-link" href="../blog.html">Torna al Blog →</a></footer></article>')
