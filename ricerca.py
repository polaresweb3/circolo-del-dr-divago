#!/usr/bin/env python3
"""Indice di ricerca riprendibile e archivio privato di trascrizioni autorizzate.

I sottotitoli recuperati dal canale sono analizzati in memoria: si conservano
solo riferimenti bibliografici e stato del lavoro. L'importazione integrale è
riservata a file forniti o concessi in licenza dal titolare.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from divago import ROOT, entries, read_catalog, write_json

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
TIMING = re.compile(r"((?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3})")


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(text):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()).strip()


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def seconds(value):
    parts = value.replace(",", ".").split(":")
    return sum(float(n) * 60 ** i for i, n in enumerate(reversed(parts)))


def stamp(value):
    millis = round(value * 1000)
    hours, rest = divmod(millis, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def parse_captions(text, deduplicate=True):
    """Legge VTT/SRT e rimuove tag e ripetizioni dei sottotitoli scorrevoli."""
    cues = []
    previous = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").lstrip("\ufeff")):
        lines = block.splitlines()
        if not lines or lines[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        match = next(((i, TIMING.search(line)) for i, line in enumerate(lines) if TIMING.search(line)), None)
        if match is None:
            continue
        index, timing = match
        raw = html.unescape(re.sub(r"<[^>]+>", "", " ".join(lines[index + 1:]))).strip()
        words = raw.split()
        overlap = 0
        for size in range(min(len(previous), len(words)) if deduplicate else 0, 0, -1):
            if previous[-size:] == words[:size]:
                overlap = size
                break
        fresh = words[overlap:]
        previous = words
        start, end = seconds(timing[1]), seconds(timing[2])
        if end < start:
            raise ValueError("Intervallo temporale non valido nei sottotitoli.")
        if fresh:
            cues.append({"start": start, "end": end, "text": " ".join(fresh)})
    if not cues:
        raise ValueError("Nessun segmento temporizzato VTT/SRT valido.")
    return cues


def validate_cues(cues):
    if not isinstance(cues, list) or not cues:
        raise ValueError("La trascrizione deve contenere segmenti temporizzati.")
    output = []
    for cue in cues:
        start, end, text = cue.get("start"), cue.get("end"), cue.get("text")
        if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not (0 <= start <= end < 1e8) or not isinstance(text, str) or not text.strip()):
            raise ValueError("Segmento non valido: servono start, end e text.")
        if output and start < output[-1]["start"]:
            raise ValueError("Segmenti fuori ordine temporale.")
        output.append({"start": float(start), "end": float(end), "text": " ".join(text.split())})
    return output


def books():
    return read_json(ROOT / "sito/dist/data/libri.json", [])


def book_matches(cues, bibliography):
    # La corrispondenza è solo una proposta: non si modifica la biblioteca verificata.
    words, timed_words = [], []
    for cue in cues:
        tokens = normalize(cue["text"]).split()
        words.extend(tokens)
        timed_words.extend([cue["start"]] * len(tokens))
    joined = " " + " ".join(words) + " "
    matches = []
    for book in bibliography:
        aliases = {book["title"], book.get("original_title", ""), *book.get("search_aliases", [])}
        for alias in sorted(aliases, key=len, reverse=True):
            title = normalize(alias)
            if not title:
                continue
            hit = joined.find(" " + title + " ")
            if hit < 0:
                continue
            # I titoli brevi e omonimi richiedono anche il cognome nelle vicinanze.
            namesake = sum(normalize(b["title"]) == title for b in bibliography) > 1
            neighborhood = joined[max(0, hit - 350):hit + len(title) + 350]
            surname = normalize(book["author"]).split()[-1]
            if (len(title.split()) < 3 or namesake) and surname not in neighborhood:
                continue
            token_index = len(joined[:hit].split())
            matches.append({"book_id": book["id"], "seconds": timed_words[token_index],
                            "evidence": "corrispondenza_automatica_da_rivedere", "verified": False})
            break
    return matches


def index_path(archive):
    return archive / "ricerca/indice.json"


def authorized_manifest(archive):
    return read_json(archive / "trascrizioni-autorizzate/manifest.json", {"schema_version": 1, "items": []})


def make_index(archive):
    old = read_json(index_path(archive), {})
    old_rows = {row["video_id"]: row for row in old.get("videos", [])}
    previous = read_json(archive / "metadati/analisi-riferimenti.json", {})
    reviewed = {row["video_id"]: row for row in previous.get("videos_analyzed", [])}
    rows = []
    bibliography = books()
    for item in entries(read_catalog(archive)):
        ident = item["id"]
        row = old_rows.get(ident, {"video_id": ident, "analysis_status": "pending", "attempts": 0})
        row.update({"title": item.get("title", ident), "duration": item.get("duration"),
                    "url": f"https://www.youtube.com/watch?v={ident}", "title_indexed": True})
        row["title_book_ids"] = sorted({book["id"] for book in bibliography for mention in book.get("mentions", [])
                                       if mention["video_id"] == ident and mention.get("evidence") == "video_title"})
        if ident in reviewed and row["analysis_status"] == "pending":
            source = reviewed[ident]
            row.update({"analysis_status": "reviewed_pilot", "source_type": source["source_type"],
                        "language": source.get("language"), "reviewed_book_ids": source.get("book_ids", []),
                        "audio_review_complete": False})
        rows.append(row)
    return {"schema_version": 1, "updated_at": now(), "coverage": "Scheda Video; dirette e Shorts non ancora censiti.",
            "copyright": "Indice di ricerca; le trascrizioni integrali sono importate solo da file forniti o autorizzati.",
            "last_run": old.get("last_run"), "retry_after": old.get("retry_after"), "videos": rows}


def save_index(archive, index):
    index["updated_at"] = now()
    write_json(index_path(archive), index)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["video_id", "title", "duration_seconds", "analysis_status", "source_type", "language", "book_ids", "url"])
    bibliography = books()
    for row in index["videos"]:
        ids = {book["id"] for book in bibliography for m in book.get("mentions", []) if m["video_id"] == row["video_id"]}
        values = [row["video_id"], row["title"], row.get("duration"), row["analysis_status"], row.get("source_type", ""),
                  row.get("language", ""), ";".join(sorted(ids)), row["url"]]
        writer.writerow(["'" + str(v) if str(v).startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in values])
    (archive / "ricerca/indice.csv").write_text(output.getvalue(), encoding="utf-8-sig")
    publish_research_metadata(archive, index)


def publish_research_metadata(archive, index):
    bibliography = books()
    saved = authorized_manifest(archive)["items"]
    counts = {}
    rows = []
    for source in index["videos"]:
        status = source["analysis_status"]
        counts[status] = counts.get(status, 0) + 1
        row = {key: source.get(key) for key in ("video_id", "title", "analysis_status", "language", "source_type", "analyzed_at")}
        row["book_ids"] = sorted({b["id"] for b in bibliography for m in b.get("mentions", []) if m["video_id"] == source["video_id"]})
        row["transcripts"] = [{"language": t["language"], "formats": ["txt", "vtt", "json"],
                                "segments": t["segments"], "sha256": t["sha256"], "local_only": True}
                               for t in saved if t["video_id"] == source["video_id"]]
        rows.append(row)
    result = {"schema_version": 1, "updated_at": index["updated_at"], "coverage": index["coverage"],
              "counts": {"total": len(rows), "title_indexed": len(rows), **counts,
                         "content_analyzed": sum(counts.get(s, 0) for s in ("reviewed_pilot", "caption_analyzed", "audio_analyzed", "authorized_import")),
                         "books": len(bibliography), "transcripts_saved": len(saved)},
              "last_run": index.get("last_run"), "retry_after": index.get("retry_after"), "videos": rows}
    write_json(ROOT / "sito/dist/data/ricerca.json", result)


def analyze_cues(archive, index, ident, cues, language, source_type):
    row = next((r for r in index["videos"] if r["video_id"] == ident), None)
    if row is None:
        raise ValueError("ID assente dal catalogo.")
    cues = validate_cues(cues)
    row.update({"analysis_status": "caption_analyzed", "source_type": source_type, "language": language,
                "analyzed_at": now(), "segments_analyzed": len(cues), "last_segment_end": cues[-1]["end"],
                "automatic_book_candidates": book_matches(cues, books()), "audio_review_complete": False,
                "analysis_method": "automatic_known_titles",
                "analysis_scope": "Ricerca automatica di opere già in biblioteca; nuovi titoli e citazioni richiedono revisione."})
    row.pop("error", None)
    save_index(archive, index)


def set_rate_limit(archive, index, ident):
    index["retry_after"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    index["last_run"] = {"finished_at": now(), "status": "rate_limited", "video_id": ident,
                         "note": "YouTube HTTP 429: richieste fermate. Riprendere dopo la scadenza; nessun tentativo di aggiramento."}
    save_index(archive, index)


class RateLimited(Exception):
    pass


def fetch_for_analysis(ident):
    command = ["yt-dlp", "--ignore-config", "--no-playlist", "--skip-download", "--dump-single-json",
               "--socket-timeout", "20", "--retries", "0", "--no-warnings", f"https://www.youtube.com/watch?v={ident}"]
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if "429" in result.stderr:
        raise RateLimited()
    if result.returncode:
        raise RuntimeError("Estrazione metadati non disponibile; nessun sottotitolo inventato.")
    info = json.loads(result.stdout)
    chosen = None
    preferred = list(dict.fromkeys(filter(None, [info.get("language"), "it", "en"])))
    for kind in ("subtitles", "automatic_captions"):
        tracks = info.get(kind) or {}
        for language in preferred + [key for key in tracks if key.endswith("-orig")]:
            available = [track for track in tracks.get(language, []) if track.get("ext") == "vtt"]
            if available:
                chosen = (language, available[0]["url"], kind)
                break
        if chosen:
            break
    if not chosen:
        return None
    language, url, kind = chosen
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read(15_000_001)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RateLimited() from exc
        raise
    if len(content) > 15_000_000:
        raise ValueError("Sottotitoli oltre il limite di analisi di 15 MB.")
    # Nessun file integrale viene scritto: i testi rimangono solo in memoria.
    return parse_captions(content.decode("utf-8-sig")), language, kind


def run_analysis(archive, selection=None, limit=None):
    index = make_index(archive)
    save_index(archive, index)
    retry = index.get("retry_after")
    if retry and datetime.now(timezone.utc) < datetime.fromisoformat(retry):
        print("YouTube ha limitato le richieste. Riprova dopo " + retry + ". Indice conservato.")
        return index
    known = {r["video_id"] for r in index["videos"]}
    if selection and set(selection) - known:
        raise ValueError("ID assenti dal catalogo.")
    pending = [r for r in index["videos"] if (not selection or r["video_id"] in selection)
               and r["analysis_status"] in ("pending", "error", "rate_limited")]
    pending.sort(key=lambda r: (not bool(r["title_book_ids"]), r.get("attempts", 0)))
    if limit is not None:
        pending = pending[:limit]
    index["retry_after"] = None
    index["last_run"] = {"started_at": now(), "status": "running", "selected": len(pending)}
    save_index(archive, index)
    for number, row in enumerate(pending, 1):
        ident = row["video_id"]
        print(f"[{number}/{len(pending)}] Analisi temporanea {ident}", flush=True)
        row["attempts"] = row.get("attempts", 0) + 1
        row["last_attempt_at"] = now()
        try:
            result = fetch_for_analysis(ident)
            if result is None:
                row["analysis_status"] = "no_captions"
            else:
                cues, language, kind = result
                analyze_cues(archive, index, ident, cues, language, kind)
        except RateLimited:
            row["analysis_status"] = "rate_limited"
            set_rate_limit(archive, index, ident)
            print("HTTP 429: fermato. La coda può essere ripresa senza rifare i video analizzati.")
            return index
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            row["analysis_status"] = "error"
            row["error"] = type(exc).__name__
        save_index(archive, index)
        if number < len(pending):
            time.sleep(3)
    index["last_run"].update({"finished_at": now(), "status": "completed_selection"})
    save_index(archive, index)
    return index


def transcript_bundle(ident, language, title, cues, rights_note, source_name):
    if not VIDEO_ID.fullmatch(ident) or not LANGUAGE.fullmatch(language):
        raise ValueError("ID video o codice lingua non valido.")
    cues = validate_cues(cues)
    data = {"schema_version": 1, "video_id": ident, "language": language, "title": title,
            "url": f"https://www.youtube.com/watch?v={ident}", "imported_at": now(),
            "rights_note": rights_note, "source_file": source_name, "review_status": "da_rivedere", "segments": cues}
    header = f"{title}\n{data['url']}\nLingua: {language}\nFonte: {source_name}\nStato: da rivedere\n\n"
    text = header + "\n".join(f"[{stamp(c['start'])}] {c['text']}" for c in cues) + "\n"
    vtt = "WEBVTT\n\n" + "\n\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i, c in enumerate(cues, 1)) + "\n"
    return {"json": (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            "txt": text.encode("utf-8"), "vtt": vtt.encode("utf-8")}


def import_transcript(archive, path, ident, language, rights_note):
    if not rights_note.strip():
        raise ValueError("Annotare la provenienza e l'autorizzazione del file.")
    catalog = {r["id"]: r for r in entries(read_catalog(archive))}
    if ident not in catalog:
        raise ValueError("ID assente dal catalogo.")
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".json":
        source = json.loads(raw)
        if source.get("video_id", ident) != ident or source.get("language", language) != language:
            raise ValueError("ID o lingua del file JSON non corrispondenti alla destinazione.")
        cues = validate_cues(source.get("segments"))
    elif path.suffix.lower() in (".vtt", ".srt"):
        # L'importazione conserva tutte le parole del file fornito. La rimozione
        # delle ripetizioni scorrevoli è riservata alla ricerca automatica.
        cues = parse_captions(raw, deduplicate=False)
    else:
        raise ValueError("Importare VTT, SRT o JSON con segmenti temporizzati.")
    bundle = transcript_bundle(ident, language, catalog[ident].get("title", ident), cues, rights_note, path.name)
    target = archive / "trascrizioni-autorizzate" / ident / language
    manifest = authorized_manifest(archive)
    if target.exists():
        raise ValueError("Una trascrizione è già archiviata per questo video e questa lingua; nessuna sovrascrittura.")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Si prepara l'intero gruppo prima di rendere visibile la cartella finale.
    with tempfile.TemporaryDirectory(prefix=".import-", dir=target.parent) as staging:
        staged = Path(staging) / "bundle"
        staged.mkdir()
        for ext, content in bundle.items():
            (staged / ("trascrizione." + ext)).write_bytes(content)
        staged.rename(target)
    metadata = {"video_id": ident, "language": language, "imported_at": now(), "segments": len(cues),
                "sha256": hashlib.sha256(bundle["json"]).hexdigest(), "rights_note": rights_note,
                "formats": {ext: str((target / ("trascrizione." + ext)).relative_to(archive)) for ext in bundle}}
    manifest["items"] = [t for t in manifest["items"] if (t["video_id"], t["language"]) != (ident, language)] + [metadata]
    write_json(archive / "trascrizioni-autorizzate/manifest.json", manifest)
    index = make_index(archive)
    analyze_cues(archive, index, ident, cues, language, "file_fornito_o_autorizzato")
    next(r for r in index["videos"] if r["video_id"] == ident)["analysis_status"] = "authorized_import"
    save_index(archive, index)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "archivio")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("indicizza", help="Aggiorna indice JSON/CSV di tutti i video, senza richieste di rete")
    sub.add_parser("candidati", help="Esporta le corrispondenze automatiche da controllare prima di aggiungerle alla biblioteca")
    analyze = sub.add_parser("analizza", help="Analizza sottotitoli temporanei; conserva solo riferimenti e stato")
    group = analyze.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--ids", nargs="+")
    analyze.add_argument("--limit", type=int)
    ingest = sub.add_parser("importa", help="Archivia una trascrizione fornita o autorizzata dal titolare")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--video-id", required=True)
    ingest.add_argument("--language", required=True)
    ingest.add_argument("--rights-note", required=True, help="Provenienza e riferimento al permesso/licenza")
    args = parser.parse_args()
    archive = args.archive.expanduser().resolve()
    try:
        if args.command == "indicizza":
            index = make_index(archive)
            save_index(archive, index)
            print(f"Indicizzati {len(index['videos'])} video. Testi integrali esclusi dall'indice pubblico.")
        elif args.command == "candidati":
            index = make_index(archive)
            candidates = [{"video_id": row["video_id"], "video_title": row["title"], **candidate}
                          for row in index["videos"] for candidate in row.get("automatic_book_candidates", [])]
            write_json(archive / "ricerca/candidati-da-verificare.json", {"updated_at": now(), "candidates": candidates,
                       "note": "Corrispondenze di titoli già noti: non sono verifiche della citazione, né una ricerca esaustiva di opere nuove."})
            print(f"Esportate {len(candidates)} proposte da verificare.")
        elif args.command == "analizza":
            if args.limit is not None and args.limit < 1:
                parser.error("--limit deve essere positivo")
            run_analysis(archive, args.ids, args.limit)
        else:
            result = import_transcript(archive, args.file.expanduser(), args.video_id, args.language, args.rights_note)
            print(json.dumps({"video_id": result["video_id"], "language": result["language"], "segments": result["segments"],
                              "formats": list(result["formats"])}, ensure_ascii=False, indent=2))
        from divago import build_preview
        build_preview()
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit("Operazione non completata: " + str(exc)) from exc


if __name__ == "__main__":
    main()
