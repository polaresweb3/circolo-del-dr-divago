"""Esporta i dati destinati ai lettori senza i registri della lavorazione.

I dataset sorgente restano completi; questo modulo restituisce nuove strutture.
"""
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit

BOOK_FIELDS = {"verification_sources"} | set('''id title author status source references bibliographic_verified edition_cited mentions cover work_type subtitle original_title alternative_titles search_aliases aliases alternate_titles alternative_author_names title_aliases publication_year year original_publication_year original_publication_date publication_date publisher isbn isbn_10 edition_isbn edition_year original_language language translator edition_translator contributors editors editor pages journal volume issue doi preprint_doi pmid pmcid document_date document_identifier container_title contained_in reference_location series collection number season episode recipient composition_year composition_date first_publication_year first_publication_date first_edition_title_page_year original_title_variant official_title official_identifier official_publication publication_place work_type_note year_note publication_year_note date_note edition_caveat quotation_caveat attribution_note title_note publication_history_note independent_title_unverified title_is_incipit title_author_verified attribution_verified human_audio_review verified spoken_title_translation spoken_title_is_verified_published_translation'''.split())
COVER_FIELDS = set('''src alt image_label display_title caption edition_label edition_note image_url source_page source_document_url edition_confirmed_in_video isbn ismn ean doi image_type container_title container_author container_editor container_year container_pages contained_work_pages represents_collection represents_frontispiece is_frontispiece source_pdf_page pdf_page source_document_page source_page_number source_printed_page printed_page plate_number credit_line image_credit credit copyright_credit license license_url license_note rights_note rights image_author photographer photograph_year copyright changes archive_inventory archive_identifier provenance_record_title provenance_record_author provenance_link_note'''.split())
MENTION_FIELDS = set('''video_id seconds title_seconds video_title note role verification verified human_audio_review'''.split())
CARD_FIELDS = {"verification_sources"} | set('''video_id title summary topics passages books duration_seconds language participants references contextual_verification_sources source_type verified human_audio_review human_visual_review partial_visual_sampling'''.split())
PASSAGE_FIELDS = set('''seconds label description verification verified human_audio_review'''.split())
CARD_BOOK_FIELDS = {"verification_sources"} | set('''book_id title author seconds title_seconds author_seconds end_seconds evidence confidence role status verification verified human_audio_review human_visual_review references additional_references additional_reference_seconds original_title spoken_title title_spoken_in_translation'''.split())


def select(value, fields):
    return {key: deepcopy(item) for key, item in value.items() if key in fields}


def source_urls(value):
    """Estrae i collegamenti dalle note, senza esportarne il testo operativo."""
    if isinstance(value, dict):
        return set().union(*(source_urls(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(source_urls(item) for item in value)) if value else set()
    if not isinstance(value, str):
        return set()
    if value.startswith(('https://', 'http://')) and not re.search(r'\s', value):
        return {value}
    urls = set()
    for url in re.findall(r'https?://[^\s<>"\u00ab\u00bb]+', value):
        url = url.rstrip('.,;:!?\u201d\u2019')
        while url.endswith(')') and url.count(')') > url.count('('):
            url = url[:-1]
        urls.add(url)
    return urls


def preserve_sources(source, exported):
    # Le note di analisi possono contenere anche fonti utili: conserviamo i soli link.
    missing = source_urls(source) - source_urls(exported)
    if missing:
        existing = exported.get('verification_sources', [])
        exported['verification_sources'] = existing + [
            {'label': urlsplit(url).netloc.removeprefix('www.'), 'url': url}
            for url in sorted(missing)
        ]
    return exported


def public_dataset(name, value):
    """Filtra soltanto i dataset editoriali; gli altri mantengono lo schema."""
    if name == 'libri.json':
        result = []
        for source in value:
            book = select(source, BOOK_FIELDS)
            book['cover'] = select(source.get('cover') or {}, COVER_FIELDS)
            book['mentions'] = [select(item, MENTION_FIELDS) for item in source['mentions']]
            result.append(preserve_sources(source, book))
        return result
    if name == 'schede.json':
        result = []
        for source in value:
            card = select(source, CARD_FIELDS)
            card['passages'] = [select(item, PASSAGE_FIELDS) for item in source['passages']]
            card['books'] = [select(item, CARD_BOOK_FIELDS) for item in source['books']]
            result.append(preserve_sources(source, card))
        return result
    return deepcopy(value)


def export_directory(directory):
    for name in ('libri.json', 'schede.json'):
        path = directory / 'data' / name
        value = json.loads(path.read_text(encoding='utf-8'))
        path.write_text(json.dumps(public_dataset(name, value), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
