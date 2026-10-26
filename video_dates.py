"""Mantiene le date di pubblicazione già riscontrate, senza accessi alla rete o ai media."""
import json
from datetime import datetime
from pathlib import Path


def normalize_publication_date(value):
    if not isinstance(value, str):
        return None
    for pattern in ('%Y-%m-%d', '%Y%m%d'):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def publication_dates(archive, public_catalog):
    dates = {}
    public_catalog = Path(public_catalog)
    if public_catalog.exists():
        for video in json.loads(public_catalog.read_text()).get('videos', []):
            date = normalize_publication_date(video.get('upload_date'))
            if date:
                dates[video['id']] = date
    cache = Path(archive) / 'metadati/date-pubblicazione-video.json'
    if cache.exists():
        for ident, record in json.loads(cache.read_text()).get('dates', {}).items():
            date = normalize_publication_date(record.get('upload_date'))
            if date:
                dates[ident] = date
    return dates
