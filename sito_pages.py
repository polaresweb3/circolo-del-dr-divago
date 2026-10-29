"""Genera le pagine del sito e le corrispondenti anteprime offline collegate."""
import base64
import fcntl
import hashlib
from copy import deepcopy
from dati_pubblici import public_dataset
import html
import json
import mimetypes
import posixpath
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from nomi_pubblici import public_html
from blog_editoriale import published_articles, blog_index, home_latest, blog_article
from home_conversazioni import home_conversations
from home_proposte import render_home
from indici_lettura import write_reading_indexes

PAGES = {
    "home": ("index.html", "Home", "Le idee del passato per comprendere il presente e immaginare il futuro", ["catalogo.json", "libri.json", "schede.json"]),
    "video": ("video.html", "Video", "L’archivio delle divagazioni", ["catalogo.json", "schede.json"]),
    "biblioteca": ("biblioteca.html", "Biblioteca", "La biblioteca citata", ["libri.json", "schede.json"]),
    "blog": ("blog.html", "Blog", "Il blog del Circolo", []),
    "eventi": ("eventi.html", "Eventi", "Gli incontri del Circolo", []),
    "progetto": ("progetto.html", "Progetto Editoriale", "Progetto Editoriale", []),
}
FEATURED_BOOKS = ["libri-della-mia-vita-salamov", "minima-moralia-adorno", "nel-ventre-della-balena-orwell"]
# Sezioni conservate nei sorgenti, temporaneamente escluse dalla navigazione.
HIDDEN_PAGES = {"blog"}
LEGAL_PAGES = {
    "privacy": ("privacy.html", "Privacy", "Privacy", []),
    "crediti": ("crediti.html", "Crediti e diritti", "Crediti e diritti", []),
}


def preview_name(page):
    return "anteprima.html" if page == "home" else f"anteprima-{page}.html"


def document(title, current, main, prefix="", featured=(), pages=None):
    pages = pages or PAGES
    labels = pages | LEGAL_PAGES
    nav = "".join(
        f'<a href="{prefix}{filename}"' + (' aria-current="page"' if key == current else "")
        + (' class="nav-featured"' if key == "completate" else "")
        + f'>{html.escape(label)}</a>'
        for key, (filename, label, _, _) in pages.items() if key not in HIDDEN_PAGES)
    breadcrumb = "" if current == "home" else (
        f'<div class="breadcrumb wrap" aria-label="Percorso"><a href="{prefix}index.html">Home</a>'
        f'<span aria-hidden="true">/</span><span>{html.escape(labels[current][1])}</span></div>')
    return public_html(f'''<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <meta name="description" content="{html.escape(title, quote=True)} — Circolo del Dr Divago: libri e storia delle idee per comprendere il presente e pensare insieme.">
  <meta name="color-scheme" content="light">
  <title>{html.escape(title)} — Circolo del Dr Divago</title>
  <link rel="stylesheet" href="{prefix}styles.css">
  <link rel="stylesheet" href="{prefix}refinement.css">
  <script src="{prefix}app.js" defer></script>
</head>
<body id="inizio" data-page="{current}" data-root="{prefix}" data-featured-books="{html.escape(','.join(featured), quote=True)}">
  <a class="skip" href="#contenuto">Vai al contenuto</a>
  <header class="header wrap">
    <a class="wordmark" href="{prefix}index.html" aria-label="Circolo del Dr Divago, Home">Circolo del <em>Dr Divago</em><span>LE IDEE DEL PASSATO PER COMPRENDERE IL PRESENTE E IMMAGINARE IL FUTURO</span></a>
    <button type="button" class="nav-toggle" aria-expanded="false" aria-controls="site-navigation" hidden>Menu <span aria-hidden="true">☰</span></button>
    <nav id="site-navigation" aria-label="Navigazione principale">{nav}</nav>
  </header>
  {breadcrumb}
  <main id="contenuto">{main}</main>
  <footer class="wrap footer"><a class="footer-wordmark" href="{prefix}index.html">Circolo del <em>Dr Divago</em></a><span>LIBRI, IDEE, CONVERSAZIONI.</span><div class="footer-links"><a href="{prefix}privacy.html">Privacy</a><a href="{prefix}crediti.html">Crediti e diritti</a><a href="https://www.youtube.com/@DrDivago" target="_blank" rel="noopener noreferrer">Il canale ↗</a><a href="#inizio">Torna su ↑</a></div></footer>
  <dialog id="detail" aria-labelledby="dialog-title"><div class="dialog-top"><span>CIRCOLO DEL DR DIVAGO</span><button id="close-dialog" aria-label="Chiudi finestra">✕</button></div><div id="dialog-content"></div></dialog>
</body>
</html>
''')


def editorial_catalog(volumes, source):
    """Un catalogo nella pagina del progetto; nessun volume fittizio tra le uscite."""
    if not isinstance(volumes, list):
        raise ValueError("Il catalogo editoriale deve essere una lista di volumi.")
    heading = ('<section class="project-catalog" aria-labelledby="editorial-catalog-title">'
               '<header class="project-catalog-heading"><p class="eyebrow">LA COLLANA</p>'
               '<h2 id="editorial-catalog-title">Le conversazioni, anno dopo anno.</h2></header>')
    if not volumes:
        return (heading + '<article class="project-volume project-volume-featured project-volume-pending" '
                'aria-labelledby="project-first-year"><div class="project-cover-placeholder" aria-hidden="true">'
                '<span>PRIMO VOLUME</span><strong>2015</strong><span>IN PREPARAZIONE</span></div>'
                '<div class="project-volume-copy"><p class="eyebrow">LE CONVERSAZIONI DEL 2015</p>'
                '<h3 id="project-first-year">Si comincia dal 2015.</h3>'
                '<p class="project-volume-description">Il primo passo sarà realizzare il volume dedicato al 2015, '
                'per poi proseguire progressivamente con gli anni successivi.</p>'
                '<p class="project-volume-description">Un modo per conservare le idee, ritrovare le parole '
                'e continuare a leggere ciò che abbiamo ascoltato.</p>'
                '<p class="project-status">Il progetto è in preparazione</p></div></article></section>')
    source = Path(source).resolve()
    years = set()
    for volume in volumes:
        if not isinstance(volume, dict):
            raise ValueError("Scheda del volume non valida.")
        year = volume.get('year')
        if type(year) is not int or not 2015 <= year <= 9999 or year in years:
            raise ValueError("Anno del volume non valido o duplicato.")
        years.add(year)
        for field in ('title', 'description'):
            if not isinstance(volume.get(field), str) or not volume[field].strip():
                raise ValueError("Titolo e descrizione del volume sono obbligatori.")
        cover = volume.get('cover') or {}
        src = cover.get('src') if isinstance(cover, dict) else None
        if not isinstance(src, str) or not src.startswith('assets/volumi/'):
            raise ValueError("La copertina del volume deve essere un'immagine locale in assets/volumi/.")
        asset = (source / src).resolve()
        if not asset.is_relative_to(source) or not asset.is_relative_to((source / 'assets/volumi').resolve()) or not asset.is_file() or asset.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.svg'}:
            raise ValueError("Copertina del volume mancante o non valida.")
        purchases = volume.get('purchase_links')
        if not isinstance(purchases, list) or not purchases:
            raise ValueError("Ogni volume disponibile deve avere le informazioni per l'acquisto.")
        for purchase in purchases:
            if not isinstance(purchase, dict) or not isinstance(purchase.get('url'), str):
                raise ValueError("Collegamento di acquisto non valido.")
            url = urlsplit(purchase['url'])
            if url.scheme != 'https' or not url.netloc or not isinstance(purchase.get('label'), str) or not purchase['label'].strip():
                raise ValueError("L'acquisto richiede un indirizzo HTTPS e un'etichetta.")
    rows = []
    esc = html.escape
    for index, volume in enumerate(sorted(volumes, key=lambda item: item['year'], reverse=True)):
        year = volume['year']
        cover = volume['cover']
        title = esc(volume['title'])
        alt = cover.get('alt') or ('Copertina di ' + volume['title'])
        actions = ''.join('<a class="button" href="' + esc(link['url'], quote=True) + '" target="_blank" '
                          'rel="noopener noreferrer">' + esc(link['label']) + ' <span aria-hidden="true">↗</span></a>'
                          for link in volume['purchase_links'])
        featured = ' project-volume-featured' if index == 0 else ''
        rows.append(f'<article class="project-volume{featured}" aria-labelledby="volume-title-{year}">'
                    f'<div class="project-volume-cover"><img src="{esc(cover["src"], quote=True)}" '
                    f'alt="{esc(alt, quote=True)}" width="400" height="600" '
                    f'loading="{"eager" if index == 0 else "lazy"}" decoding="async"></div>'
                    f'<div class="project-volume-copy"><p class="eyebrow">CONVERSAZIONI DEL {year}</p>'
                    f'<h3 id="volume-title-{year}">{title}</h3><p class="project-volume-author">Dr Divago</p>'
                    f'<p class="project-volume-description">{esc(volume["description"])}</p>'
                    f'<div class="project-volume-actions">{actions}</div></div></article>')
    return heading + '<div class="project-volumes">' + ''.join(rows) + '</div></section>'


def article_content(post):
    title = html.escape(post["title"])
    paragraphs = "".join(f'<p>{html.escape(p)}</p>' for p in post["paragraphs"])
    return ('<article class="section wrap article-page"><a class="text-link" href="../blog.html">← Tutte le note</a>'
            f'<header class="article-heading"><p class="eyebrow">{html.escape(post["category"])}</p>'
            f'<h1>{title}</h1><p class="article-byline">{html.escape(post["author"])}'
            f' · {html.escape(post["status"])}</p></header><div class="article-body">{paragraphs}</div>'
            '<footer class="article-end"><a class="text-link" href="../blog.html">Torna al blog ↗</a>'
            '<a class="text-link" href="../progetto.html">Scopri il progetto ↗</a></footer></article>')


def timestamp(value):
    if value is None:
        return "Durata non disponibile"
    value = int(value)
    hours, rest = divmod(value, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{secs:02}" if hours else f"{minutes}:{secs:02}"


def completed_cards(cards, bibliography):
    """Raccoglie soltanto le schede redatte, consultabili anche senza JavaScript."""
    books = {book["id"]: book for book in bibliography}
    output = []
    for card in cards:
        ident = card["video_id"]
        related = [books[m["book_id"]] for m in card["books"]]
        search = " ".join([card["title"], *card["topics"], *[b["title"] + " " + b["author"] for b in related]])
        title = html.escape(card["title"])
        target = f"video/{ident}.html"
        excerpt = re.split(r'(?<=\.)\s+', card["summary"], maxsplit=1)[0]
        topics = "".join(f'<li>{html.escape(topic)}</li>' for topic in card["topics"][:3])
        book_count = "1 opera collegata" if len(related) == 1 else f"{len(related)} opere collegate"
        output.append(
            f'<article class="completed-card" data-completed-card data-search="{html.escape(search, quote=True)}">'
            f'<a class="completed-card-image" href="{target}" aria-label="Leggi la scheda: {html.escape(card["title"], quote=True)}">'
            f'<img src="https://i.ytimg.com/vi/{ident}/hqdefault.jpg" alt="" width="480" height="270" loading="lazy">'
            f'<span class="duration">{timestamp(card["duration_seconds"])}</span></a>'
            '<div class="completed-card-copy"><p class="eyebrow">SCHEDA EDITORIALE PRONTA</p>'
            f'<h2><a href="{target}">{title}</a></h2><p class="completed-excerpt">{html.escape(excerpt)}</p>'
            f'<ul class="topic-tags" aria-label="Argomenti">{topics}</ul>'
            f'<p class="completed-card-meta">{book_count} · {len(card["passages"])} passaggi tematici</p>'
            f'<a class="text-link" href="{target}">Leggi la scheda →</a></div></article>')
    return "".join(output)


def sheet_index(*, summary=False, books=False, passages=False):
    links = [('filmato', 'Video')]
    if summary:
        links.append(('sintesi', 'Sintesi'))
    if books:
        links.append(('libri', 'Libri'))
    if passages:
        links.append(('passaggi', 'Passaggi'))
    return ('<nav class="sheet-index" aria-label="In questa scheda">'
            + ''.join(f'<a href="#{ident}">{label}</a>' for ident, label in links) + '</nav>')


def sheet_summary(text):
    """Conserva la sintesi integrale e apre la lettura con un breve estratto."""
    if len(text.split()) <= 150:
        return f'<p>{html.escape(text)}</p>'
    boundaries = [match.end() for match in re.finditer(r'(?<=[.!?])\s+', text)
                  if 45 <= len(text[:match.start()].split()) <= 90]
    if boundaries:
        split = min(boundaries, key=lambda position: abs(len(text[:position].split()) - 65))
    else:
        split = list(re.finditer(r'\S+', text))[75].start()
    return (f'<p>{html.escape(text[:split].rstrip())}</p>'
            '<details class="sheet-summary-more"><summary>'
            '<span class="when-closed">Leggi la sintesi completa</span>'
            '<span class="when-open">Riduci la sintesi</span></summary>'
            f'<p>{html.escape(text[split:].lstrip())}</p></details>')


def book_reference_notes(content):
    return ('<details class="card-book-details"><summary>Note sul riferimento</summary>'
            + content + '</details>') if content else ''


def video_content(card, bibliography):
    """Schede editoriali leggibili anche senza JavaScript o file sorgente integrale."""
    esc = html.escape
    ident = card["video_id"]
    visual = card.get('source_type') in ('analisi_fotogrammi_locali', 'analisi_fotogrammi_browser')
    summary_heading = 'Il contenuto del filmato' if visual else 'Il filo del discorso'
    books_heading = 'Opere e riferimenti' if visual else 'I libri nel discorso'
    source_note = ('La descrizione riguarda alcune immagini del filmato. Il sonoro non è verificato; '
                   'le didascalie visibili non attestano le parole pronunciate.' if visual else '')
    source_note_html = f'<p class="source-note">{source_note}</p>' if source_note else ''
    def watch(seconds=None):
        return "https://www.youtube.com/watch?v=" + ident + ("&t=" + str(int(seconds)) if seconds is not None else "")
    passages = "".join(
        f'<li><a href="{esc(watch(p["seconds"]), quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'<span class="passage-time">{timestamp(p["seconds"])}</span><span><strong>{esc(p["label"])}</strong>'
        f'<span>{esc(p.get("description", ""))}</span></span><span aria-hidden="true">↗</span></a></li>'
        for p in card["passages"])
    books = []
    for mention in card["books"]:
        book = next(b for b in bibliography if b["id"] == mention["book_id"])
        cover = book.get("cover") or {}
        image = (f'<img src="../{esc(cover["src"], quote=True)}" alt="{esc(cover.get("alt") or (cover.get("image_label", "Copertina") + " di " + (cover.get("display_title") or book["title"])), quote=True)}" '
                 'width="72" height="108" loading="lazy">') if cover.get("src") else '<span class="card-book-no-cover" aria-hidden="true">↗</span>'
        edition = (f'<p class="card-book-edition">{esc(cover.get("image_label", "Copertina"))}: {esc(cover["edition_label"])}</p>') if cover.get('edition_label') else ''
        if cover.get('edition_note'):
            edition += f'<p class="card-book-edition">{esc(cover["edition_note"])}</p>'
        status = mention.get("confidence", "riscontro_testuale")
        label = {"identificazione_probabile": "Identificazione probabile", "riferimento_descrizione": "Nella descrizione del video"}.get(status, "")
        status_note = f'<p class="card-book-status">{esc(label)}</p>' if label else ""
        moment = mention.get("title_seconds") or mention.get("seconds")
        evidence = f'<p>{esc(mention["evidence"])}</p>' if mention.get('evidence') else ''
        notes = book_reference_notes(edition + evidence)
        books.append(f'<article class="card-book">{image}<div><h3><a href="../biblioteca.html#book-{esc(book["id"])}">'
                     f'{esc(book["title"])}</a></h3><p class="card-book-author">{esc(book["author"])}</p>'
                     f'{status_note}{notes}'
                     f'<a class="text-link" href="{esc(watch(moment), quote=True)}" target="_blank" rel="noopener noreferrer">'
                     f'Passaggio {timestamp(moment)} ↗</a> · <a class="text-link" href="../biblioteca.html#book-{esc(book["id"])}">Fonti e libro ↗</a></div></article>')
    sources = public_dataset('schede.json', [card])[0]
    references = []
    seen_urls = set()
    for reference in (sources.get('references', []) + sources.get('contextual_verification_sources', [])
                      + sources.get('verification_sources', [])):
        if reference['url'] not in seen_urls:
            seen_urls.add(reference['url'])
            references.append(reference)
    source_links = ''.join(
        f'<li><a href="{esc(ref["url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'{esc(ref["label"])} ↗</a></li>' for ref in references)
    references_html = (f'<details class="source-note"><summary>Fonti e approfondimenti ({len(references)})</summary>'
                       f'<ul>{source_links}</ul></details>') if references else ''
    return (f'<article class="section wrap video-sheet"><a class="text-link" href="../video.html">← Tutti i video</a>'
            f'<header class="sheet-heading"><p class="eyebrow">{timestamp(card["duration_seconds"])} · {len(books)} {"OPERA" if len(books) == 1 else "OPERE"}</p>'
            f'<h1>{esc(card["title"])}</h1></header>'
            f'{sheet_index(summary=True, books=bool(books), passages=bool(card["passages"]))}'
            f'<div class="sheet-layout"><div>{video_player(ident, card["title"])}<section class="sheet-summary" aria-labelledby="sintesi"><h2 id="sintesi">{summary_heading}</h2>'
            f'{sheet_summary(card["summary"])}<div class="sheet-actions">'
            f'<a class="text-link" href="{esc(watch(), quote=True)}" target="_blank" rel="noopener noreferrer">Apri su YouTube ↗</a>'
            '<a class="text-link" href="#passaggi">Vai ai passaggi ↓</a></div></section>'
            f'<section class="sheet-books" aria-labelledby="libri"><h2 id="libri">{books_heading}</h2>{"".join(books)}</section></div>'
            f'<aside class="sheet-passages" aria-labelledby="passaggi"><h2 id="passaggi">Passaggi</h2>'
            f'<ol>{passages}</ol></aside></div>'
            f'{source_note_html}{references_html}</article>')


def video_player(ident, title):
    return ('<div class="video-consent" id="filmato">'
            f'<div class="sheet-player"><button class="sheet-play" data-play-video="{html.escape(ident)}" '
            f'aria-label="Accetta e riproduci: {html.escape(title, quote=True)}">'
            f'<img src="https://i.ytimg.com/vi/{html.escape(ident)}/hqdefault.jpg" alt="" width="480" height="270" decoding="async">'
            '<span class="sheet-play-label"><span aria-hidden="true">▶</span> Accetta e riproduci</span></button></div>'
            '<button type="button" class="text-link player-disable" hidden>Disattiva player YouTube</button></div>')


def catalog_video_content(video, bibliography):
    """Pagina del contributo; distingue i riferimenti disponibili dalle analisi ancora da fare."""
    esc = html.escape
    ident = video['id']
    related = [book for book in bibliography if any(m['video_id'] == ident for m in book['mentions'])]
    book_rows = []
    for book in related:
        cover = book.get('cover') or {}
        image = (f'<img src="../{esc(cover["src"], quote=True)}" alt="{esc(cover.get("alt") or (cover.get("image_label", "Copertina") + " di " + (cover.get("display_title") or book["title"])), quote=True)}" width="72" height="108" loading="lazy">') if cover.get('src') else ''
        edition = f'<p class="card-book-edition">{esc(cover.get("image_label", "Copertina"))}: {esc(cover["edition_label"])}</p>' if cover.get('edition_label') else ''
        if cover.get('edition_note'):
            edition += f'<p class="card-book-edition">{esc(cover["edition_note"])}</p>'
        mentions = [m for m in book['mentions'] if m['video_id'] == ident]
        links = []
        for mention in mentions:
            moment = mention.get('title_seconds') if mention.get('title_seconds') is not None else mention.get('seconds')
            if moment is not None:
                links.append(f'<a class="text-link" href="https://www.youtube.com/watch?v={ident}&amp;t={int(moment)}" target="_blank" rel="noopener noreferrer">Passaggio {timestamp(moment)} ↗</a>')
            else:
                links.append('<p class="card-book-status">Riferimento nel titolo del video; contenuto da verificare.</p>')
        book_rows.append(f'<article class="card-book">{image}<div><h3><a href="../biblioteca.html#book-{esc(book["id"])}">{esc(book["title"])}</a></h3>'
                         f'<p class="card-book-author">{esc(book["author"])}</p>{book_reference_notes(edition)}{"".join(links)}'
                         f'<a class="text-link" href="../biblioteca.html#book-{esc(book["id"])}">Fonti e libro →</a></div></article>')
    references = ('<section class="sheet-books" aria-labelledby="libri"><h2 id="libri">Riferimenti già collegati</h2>'
                  + ''.join(book_rows) + '</section>') if related else ''
    return (f'<article class="section wrap video-sheet"><a class="text-link" href="../video.html">← Tutti i video</a>'
            f'<header class="sheet-heading"><p class="eyebrow">DALL’ARCHIVIO DEL CANALE · {timestamp(video.get("duration"))}</p><h1>{esc(video["title"])}</h1></header>'
            f'{sheet_index(books=bool(related))}'
            f'<div class="sheet-layout"><div>{video_player(ident, video["title"])}'
            f'<p class="sheet-original"><a class="text-link" href="https://www.youtube.com/watch?v={ident}" target="_blank" rel="noopener noreferrer">Apri il video su YouTube ↗</a></p>{references}</div>'
            '<aside class="sheet-work-state"><p class="source-note">Approfondimento in preparazione.</p></aside></div></article>')


def embed_cover(source, cover):
    if not cover or not cover.get("src"):
        return
    asset = (source / cover["src"]).resolve()
    if not asset.is_relative_to(source.resolve()) or not asset.is_file():
        raise ValueError("Copertina locale non valida: " + cover["src"])
    mime = mimetypes.guess_type(asset.name)[0] or "image/jpeg"
    cover["src"] = "data:" + mime + ";base64," + base64.b64encode(asset.read_bytes()).decode("ascii")


def offline_links(page, filename, mapping):
    def replace(match):
        parts = urlsplit(html.unescape(match[1]))
        if parts.scheme or parts.netloc or not parts.path:
            return match[0]
        target = posixpath.normpath(posixpath.join(posixpath.dirname(filename), parts.path))
        if target not in mapping:
            return match[0]
        url = urlunsplit(("", "", mapping[target], parts.query, parts.fragment))
        return 'href="' + html.escape(url, quote=True) + '"'
    return re.sub(r'href="([^"]+)"', replace, page)


def build_site(root, pages=None, *, home_template=None):
    root = Path(root)
    if not (root / 'sito/templates').exists():
        return
    # Anche il processo di archiviazione aggiorna i dati: serializziamo le generazioni.
    with (root / 'sito/.build.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _build_site(root, pages, home_template=home_template)


def _build_site(root, pages=None, *, home_template=None):
    pages = pages or PAGES
    source = root / "sito/dist"
    templates = root / "sito/templates"
    if not templates.exists():
        return
    previous = json.loads((source / 'data/pagine.json').read_text()) if (source / 'data/pagine.json').exists() else {'pages': []}
    data = {name: json.loads((source / "data" / name).read_text(encoding="utf-8"))
            for name in ("catalogo.json", "libri.json", "blog.json", "ricerca.json", "schede.json", "volumi.json", "articoli-blog.json")
            if (source / "data" / name).exists()}
    bibliography = data.get("libri.json", [])
    ids = [book["id"] for book in bibliography]
    featured = [ident for ident in FEATURED_BOOKS if ident in ids]
    featured += [ident for ident in ids if ident not in featured]
    featured = featured[:3]
    all_pages = pages | LEGAL_PAGES
    mapping = {filename: preview_name(key) for key, (filename, _, _, _) in all_pages.items()}
    documents = []
    cards = data.get("schede.json", [])
    reading = write_reading_indexes(source, data.get('catalogo.json', {}), bibliography, cards)
    posts = published_articles(data.get("articoli-blog.json", []))
    for key, (filename, _, title, datasets) in all_pages.items():
        template = templates / (key + ".html")
        proposal_source = root / 'sorgenti/home.html'
        if key == 'home' and (home_template is not None or proposal_source.is_file()):
            main = home_template if home_template is not None else render_home(
                proposal_source, bibliography, data.get('catalogo.json', {}), cards)
            # La copia compilata viene sempre riallineata alla sorgente della proposta.
            if not template.exists() or template.read_text(encoding='utf-8') != main:
                template.write_text(main, encoding='utf-8')
        else:
            main = template.read_text(encoding="utf-8")
        main = main.replace("{{completed_count}}", str(len(cards)))
        main = main.replace("{{books_count}}", f"{len(bibliography):,}".replace(",", "."))
        main = main.replace("{{videos_count}}", str(len(data.get("catalogo.json", {}).get("videos", []))))
        main = main.replace("{{hours_count}}", str(round(sum(video.get("duration") or 0 for video in data.get("catalogo.json", {}).get("videos", [])) / 3600)))
        if "{{home_conversations}}" in main:
            main = main.replace("{{home_conversations}}", home_conversations(data.get("catalogo.json", {}).get("videos", [])))
        main = main.replace("{{latest_divagation}}", home_latest(posts))
        main = main.replace("{{divagation_articles}}", blog_index(posts))
        main = main.replace("{{voices_articles}}", blog_index(posts, category="voci-del-blog"))
        if key == "progetto":
            main = main.replace("{{editorial_catalog}}", editorial_catalog(data.get("volumi.json", []), source))
        if key == "completate":
            main = main.replace("{{completed_grid}}", completed_cards(cards, bibliography))
            main = main.replace("{{completed_books}}", str(len({m["book_id"] for c in cards for m in c["books"]})))
            main = main.replace("{{completed_passages}}", str(sum(len(c["passages"]) for c in cards)))
        page = document(title, key, main, featured=featured, pages=pages)
        documents.append((key, filename, page, datasets))
    seen = set()
    for post in (posts if 'blog' in pages else []):
        ident = post["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ident) or ident in seen:
            raise ValueError("Identificativo articolo non valido o duplicato.")
        seen.add(ident)
        filename = f"articoli/{ident}.html"
        mapping[filename] = f"anteprima-articolo-{ident}.html"
        page = document(post["title"], "blog", blog_article(post), prefix="../", pages=pages)
        page = page.replace('data-page="blog"', 'data-page="articolo"')
        documents.append(("articolo", filename, page, []))
    card_lookup = {card['video_id']: card for card in cards}
    seen_cards = set()
    for video in data.get('catalogo.json', {}).get('videos', []):
        ident = video['id']
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", ident) or ident in seen_cards:
            raise ValueError("Identificativo scheda non valido o duplicato.")
        seen_cards.add(ident)
        filename = f"video/{ident}.html"
        mapping[filename] = f"anteprima-scheda-{ident}.html"
        card = card_lookup.get(ident)
        content = video_content(card, bibliography) if card else catalog_video_content(video, bibliography)
        page = document(video['title'], 'video', content, prefix='../', pages=pages)
        page = page.replace('data-page="video"', 'data-page="scheda"')
        documents.append(("scheda", filename, page, []))
    style = (source / "styles.css").read_text(encoding="utf-8")
    refinement = (source / 'refinement.css').read_text(encoding='utf-8') if (source / 'refinement.css').exists() else ''
    style_version = hashlib.sha256(style.encode("utf-8")).hexdigest()[:12]
    script = (source / "app.js").read_text(encoding="utf-8")
    script_version = hashlib.sha256(script.encode("utf-8")).hexdigest()[:12]
    refinement_version = hashlib.sha256(refinement.encode('utf-8')).hexdigest()[:12]
    for key, filename, page, datasets in documents:
        prefix = "../" if key in ("articolo", "scheda") else ""
        page = page.replace('<body ', '<body data-index-manifest="' + reading['manifest'] + '" ', 1)
        stylesheet = f'<link rel="stylesheet" href="{prefix}styles.css?v={style_version}">'
        page = page.replace(f'<link rel="stylesheet" href="{prefix}styles.css">', stylesheet)
        page = page.replace(f'href="{prefix}refinement.css"', f'href="{prefix}refinement.css?v={refinement_version}"')
        script_tag = f'<script src="{prefix}app.js?v={script_version}" defer></script>'
        page = page.replace(f'<script src="{prefix}app.js" defer></script>', script_tag)
        target = source / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding="utf-8")
        embedded = {"data/" + name: public_dataset(name, data[name]) for name in datasets if name in data}
        for book in embedded.get("data/libri.json", []):
            if key == "biblioteca" or (key == "home" and book["id"] in featured):
                embed_cover(source, book.get("cover"))
        safe_json = json.dumps(embedded, ensure_ascii=False).replace("<", "\\u003c")
        page = page.replace(stylesheet, "<style>" + style + '\n' + refinement + "</style>")
        page = page.replace(f'<link rel="stylesheet" href="{prefix}refinement.css?v={refinement_version}">', '')
        page = page.replace(script_tag, "")
        page = page.replace('<body ', '<body data-preview="true" ', 1)
        page = offline_links(page, filename, mapping)
        if key == "progetto":
            for volume in data.get("volumi.json", []):
                cover = deepcopy(volume["cover"])
                embed_cover(source, cover)
                page = page.replace('src="' + volume["cover"]["src"] + '"', 'src="' + cover["src"] + '"')
        if key in {"scheda", "home"}:
            # Anche le copertine statiche della Home restano autonome offline.
            image_paths = set(re.findall(r'<img[^>]*\bsrc="([^"]+)"', page))
            for book in bibliography:
                original_cover = book.get("cover") or {}
                if original_cover.get("src") and prefix + original_cover["src"] in image_paths:
                    cover = deepcopy(original_cover)
                    embed_cover(source, cover)
                    page = page.replace('src="' + prefix + original_cover["src"] + '"', 'src="' + cover["src"] + '"')
        page = page.replace("</body>", '<script id="embedded-data" type="application/json">' + safe_json
                            + "</script><script>" + script + "</script></body>")
        (root / "sito" / mapping[filename]).write_text(page, encoding="utf-8")
    manifest = {"pages": [{"page": key, "path": filename, "preview": mapping[filename]}
                          for key, filename, _, _ in documents]}
    active = {item['path'] for item in manifest['pages']}
    for item in previous['pages']:
        if item['path'] not in active:
            for base, name in ((source, item['path']), (root / 'sito', item['preview'])):
                obsolete = (base / name).resolve()
                if obsolete.is_relative_to(base.resolve()):
                    obsolete.unlink(missing_ok=True)
    (source / "data/pagine.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = build_site(Path(__file__).resolve().parent)
    print(f"Generate {len(result['pages'])} pagine e anteprime offline.")
