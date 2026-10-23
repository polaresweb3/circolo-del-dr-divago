#!/usr/bin/env python3
"""Archivio locale di Dr Divago. Nessuna pubblicazione e nessun cookie del browser."""
import argparse
import json
import os
import signal
import threading
import time
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHANNEL = "https://www.youtube.com/@DrDivago"
PILOT = ["rtmt9_Mzdkw", "WzF2KJ1swVE", "bcjZdrAct5U"]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_catalog(archive):
    path = archive / "metadati" / "canale.json"
    if not path.exists():
        raise SystemExit("Manca il catalogo: esegui prima python3 divago.py catalogo")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise SystemExit("Catalogo non valido: riesegui python3 divago.py catalogo")
    return data


def entries(data):
    result = {}
    for item in data["entries"]:
        if isinstance(item, dict) and re.fullmatch(r"[A-Za-z0-9_-]{11}", item.get("id", "")):
            result.setdefault(item["id"], item)
    return list(result.values())


def export_catalog(archive):
    data = read_catalog(archive)
    audio = scan_media(archive / "audio", {".mp3"})
    video = scan_media(archive / "video", {".mp4", ".mkv", ".webm", ".mov"})
    videos = []
    for item in entries(data):
        ident = item["id"]
        videos.append({
            "id": ident, "title": item.get("title", ident),
            "url": "https://www.youtube.com/watch?v=" + ident,
            "duration": item.get("duration"),
            "audio_saved": ident in audio, "video_saved": ident in video,
            "audio_file": str(audio[ident].relative_to(ROOT)) if ident in audio and audio[ident].is_relative_to(ROOT) else None,
            "video_file": str(video[ident].relative_to(ROOT)) if ident in video and video[ident].is_relative_to(ROOT) else None,
        })
    result = {
        "channel": data.get("channel") or "Dr Divago", "channel_url": CHANNEL,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": "Scheda Video; dirette e Shorts non ancora censiti.",
        "rights": "Autorizzazione per il riutilizzo da richiedere. File multimediali solo locali.",
        "videos": videos,
    }
    write_json(ROOT / "sito" / "dist" / "data" / "catalogo.json", result)
    build_preview()
    return videos


def build_preview():
    """Aggiorna il sito a più pagine e le anteprime apribili senza server."""
    from sito_pages import build_site
    build_site(ROOT)


def scan_media(directory, extensions):
    found = {}
    if directory.exists():
        for path in directory.iterdir():
            match = re.search(r"\[([A-Za-z0-9_-]{11})\]", path.name)
            if (match and path.is_file() and not re.search(r"\]\.f\d+\.", path.name)
                    and path.suffix.lower() in extensions and path.stat().st_size):
                found[match.group(1)] = path
    return found


def catalog(args):
    target = args.archive / "metadati" / "canale.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".download.json")
    cmd = ["yt-dlp", "--ignore-config", "--flat-playlist", "--dump-single-json",
           "--socket-timeout", "20", "--retries", "2", CHANNEL + "/videos"]
    with temporary.open("w", encoding="utf-8") as handle:
        subprocess.run(cmd, stdout=handle, check=True)
    data = json.loads(temporary.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise SystemExit("Risposta di YouTube non valida: catalogo precedente conservato.")
    temporary.replace(target)
    report(args)


def run_download_command(command, log):
    limited = False
    age_restricted = False
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", bufsize=1,
                          start_new_session=True) as process:
        done = threading.Event()
        budget_errors = []
        # Il percorso del registro identifica l'archivio anche usando --archive.
        archive = Path(log.name).parent.parent
        def watch_budget():
            from archivio_tools import enforce_budget
            while not done.wait(1):
                try:
                    enforce_budget(archive, headroom=2_000_000_000)
                except (OSError, ValueError) as exc:
                    budget_errors.append(str(exc))
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    return
        watcher = threading.Thread(target=watch_budget, daemon=True)
        watcher.start()
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
                if "http error 429" in line.lower() or "http 429" in line.lower() or "too many requests" in line.lower():
                    limited = True
                if 'sign in to confirm your age' in line.lower():
                    age_restricted = True
            code = process.wait()
            if budget_errors:
                raise ValueError(budget_errors[0])
            if code and age_restricted and not limited:
                from archivio_tools import defer_age_restricted
                ident = command[-1].rsplit('=', 1)[-1]
                if re.fullmatch(r'[A-Za-z0-9_-]{11}', ident):
                    defer_age_restricted(archive, 'audio' if '--extract-audio' in command else 'video', ident)
            return code, limited
        except KeyboardInterrupt:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
        finally:
            done.set()
            watcher.join(timeout=3)


def run_download_with_recovery(command, log):
    """Una sola riprova con metadati freschi per HTTP403, mai durante HTTP429."""
    start = log.tell()
    result = run_download_command(command, log)
    if not result[0] or result[1]:
        return result
    log.flush()
    with Path(log.name).open(encoding='utf-8') as reader:
        reader.seek(start)
        failure = reader.read().lower()
    if 'http error 403' not in failure:
        return result
    archive = Path(log.name).parent.parent
    kind = 'audio' if '--extract-audio' in command else 'video'
    ident = command[-1].rsplit('=', 1)[-1]
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', ident):
        return result
    from archivio_tools import archive_lock, enforce_budget
    state = archive / 'stato'
    record_path = state / 'riprese-403.json'
    signature = kind + ':' + ident
    def paused():
        if ((state / 'ferma-scaricamento-icloud').exists()
                or (kind == 'video' and (state / 'ferma-scaricamento-video').exists())):
            return True
        pause = state / 'pausa-download.json'
        retry = json.loads(pause.read_text()).get('retry_after') if pause.exists() else None
        return bool(retry and datetime.now(timezone.utc) < datetime.fromisoformat(retry))
    with archive_lock(archive, wait=True):
        record = json.loads(record_path.read_text()) if record_path.exists() else {}
        if record.get(signature, {}).get('attempts', 0) >= 1 or paused():
            return result
        record[signature] = {'attempts': 1, 'started_at': datetime.now(timezone.utc).isoformat(),
                             'status': 'retry_in_progress'}
        write_json(record_path, record)
    print('HTTP403 temporaneo: una riprova dopo 10 secondi, senza cookie.', flush=True)
    time.sleep(10)
    if paused():
        return result
    enforce_budget(archive, headroom=2_000_000_000)
    result = run_download_command(command, log)
    with archive_lock(archive, wait=True):
        record = json.loads(record_path.read_text())
        record[signature].update(status='download_completed' if not result[0] else 'retry_failed',
                                 finished_at=datetime.now(timezone.utc).isoformat())
        write_json(record_path, record)
    return result


def download(args):
    from archivio_tools import archive_lock
    if args.dry_run:
        download_locked(args)
        return
    with archive_lock(args.archive, name='download-' + args.command):
        download_locked(args)


def download_locked(args):
    catalogued = entries(read_catalog(args.archive))
    known = {item["id"]: item for item in catalogued}
    selection = list(known) if args.all else (args.ids or PILOT)
    selection = list(dict.fromkeys(selection))
    invalid = set(selection) - set(known)
    if invalid:
        raise SystemExit("ID assenti dal catalogo: " + ", ".join(sorted(invalid)))
    mode = args.command
    folder = args.archive / mode
    present = scan_media(folder, {".mp3"} if mode == "audio" else {".mp4", ".mkv", ".webm", ".mov"})
    skipped = sum(ident in present for ident in selection)
    selection = [ident for ident in selection if ident not in present]
    if args.limit is not None:
        selection = selection[:args.limit]
    if args.dry_run:
        print(json.dumps({"simulation": True, "kind": mode, "already_present": skipped,
                          "new_downloads": len(selection), "video_ids": selection,
                          "archive": str(args.archive)}, ensure_ascii=False, indent=2))
        return
    pause = args.archive / "stato/pausa-download.json"
    if pause.exists():
        retry = json.loads(pause.read_text(encoding="utf-8")).get("retry_after")
        if retry and datetime.now(timezone.utc) < datetime.fromisoformat(retry):
            raise ValueError("YouTube ha limitato le richieste: riprendere dopo " + retry)
    folder.mkdir(parents=True, exist_ok=True)
    state = args.archive / "stato"
    state.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp", "--ignore-config", "--no-playlist", "--continue", "--no-overwrites",
        "--socket-timeout", "30", "--retries", "3", "--fragment-retries", "3",
        "--abort-on-unavailable-fragments", "--sleep-requests", "0.75",
        "--sleep-interval", "2", "--max-sleep-interval", "4",
        "--write-info-json", "--write-description", "--no-progress", "--newline",
        "--download-archive", str(state / (mode + ".txt")),
        "--output", str(folder / "%(title).120B [%(id)s].%(ext)s"),
    ]
    if mode == "audio":
        command += ["--format", "bestaudio", "--extract-audio", "--audio-format", "mp3",
                    "--audio-quality", "160K", "--embed-metadata"]
    elif mode == "video":
        command += ["--format", "bv*[height<=1080]+ba/b[height<=1080]",
                    "--merge-output-format", "mkv"]
    failures = []
    attempted = []
    stopped = None
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_path = args.archive / "logs" / (run_id + "-" + mode + ".log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    registered = set()
    registry = state / (mode + ".txt")
    if registry.exists():
        registered = {line.split()[-1] for line in registry.read_text().splitlines() if line.strip()}
    print("Già presenti:", skipped, "· Nuovi nel lotto:", len(selection), flush=True)
    try:
        with log_path.open("w", encoding="utf-8") as log:
            for index, ident in enumerate(selection, 1):
                if mode == 'video' and (state / 'ferma-scaricamento-video').exists():
                    stopped = 'Video in pausa su richiesta dell’utente; gli audio possono continuare.'
                    break
                if pause.exists():
                    retry = json.loads(pause.read_text()).get('retry_after')
                    if retry and datetime.now(timezone.utc) < datetime.fromisoformat(retry):
                        stopped = 'Pausa HTTP 429 condivisa: nessuna ulteriore richiesta prima di ' + retry
                        break
                print("\n[{}/{}] {} · {}".format(index, len(selection), mode, ident), flush=True)
                if ident in registered:
                    print("ID nel registro ma file locale assente: controllare l’eventuale copia cloud/disco prima di riscaricare.")
                    failures.append(ident)
                    continue
                seconds = known[ident].get("duration") or 1800
                needed = seconds * (80000 if mode == "audio" else 2000000) + 5_000_000_000
                if shutil.disk_usage(args.archive).free < needed:
                    stopped = "Spazio insufficiente per completare il prossimo file e la conversione."
                    break
                attempted.append(ident)
                from archivio_tools import archive_lock
                marker = state / ('attivo-' + mode + '.json')
                with archive_lock(args.archive, wait=True):
                    from archivio_tools import enforce_budget
                    enforce_budget(args.archive, additional=seconds * (100000 if mode == 'audio' else 4000000), headroom=2_000_000_000)
                    write_json(marker, {'pid': os.getpid(), 'video_id': ident})
                try:
                    code, limited = run_download_with_recovery(command + ["https://www.youtube.com/watch?v=" + ident], log)
                finally:
                    with archive_lock(args.archive, wait=True):
                        marker.unlink(missing_ok=True)
                if code:
                    failures.append(ident)
                if limited:
                    retry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                    write_json(pause, {"reason": "YouTube HTTP 429", "retry_after": retry, "video_id": ident})
                    stopped = "YouTube HTTP 429: lotto interrotto; nessuna ulteriore richiesta."
                    break
    except KeyboardInterrupt:
        print("\nInterrotto: file parziali e registri sono conservati per riprendere.")
        raise SystemExit(130)
    from archivio_tools import archive_lock, inventory
    with archive_lock(args.archive, wait=True):
        checked = inventory(args.archive)
        for row in checked['videos']:
            if row['video_id'] in attempted and row[mode]['status'] != 'verified' and row['video_id'] not in failures:
                failures.append(row['video_id'])
        result = {"finished_at": datetime.now(timezone.utc).isoformat(),
               "kind": mode, "requested_ids": selection, "attempted_ids": attempted, "failures": failures, "stopped": stopped,
               "log": str(log_path.relative_to(args.archive))}
        write_json(state / ('ultimo-download-' + mode + '.json'), result)
        if mode == 'audio':
            write_json(state / 'ultimo-download.json', result)
        report(args)
    if stopped:
        raise SystemExit(stopped)
    if failures:
        print("Non completati: " + ", ".join(failures), file=sys.stderr)
        print("Riesegui lo stesso comando per riprendere.", file=sys.stderr)
        raise SystemExit(1)


def report(args):
    items = export_catalog(args.archive)
    seconds = sum(item.get("duration") or 0 for item in items)
    size_audio = sum(p.stat().st_size for p in scan_media(args.archive / "audio", {".mp3"}).values())
    size_video = sum(p.stat().st_size for p in scan_media(args.archive / "video", {".mkv", ".mp4", ".webm", ".mov"}).values())
    transcripts = scan_media(args.archive / "trascrizioni", {".vtt"})
    research = args.archive / "ricerca/indice.json"
    research_data = json.loads(research.read_text(encoding="utf-8")) if research.exists() else {}
    authorized = args.archive / "trascrizioni-autorizzate/manifest.json"
    authorized_data = json.loads(authorized.read_text(encoding="utf-8")) if authorized.exists() else {}
    print(json.dumps({
        "video_catalogati": len(items), "ore_note": round(seconds / 3600, 2),
        "audio_salvati": sum(item["audio_saved"] for item in items),
        "video_salvati": sum(item["video_saved"] for item in items),
        "trascrizioni_salvate": len(transcripts),
        "trascrizioni_autorizzate_importate": len(authorized_data.get("items", [])),
        "video_con_analisi_del_contenuto": sum(row.get("analysis_status") in {"reviewed_pilot", "caption_analyzed", "authorized_import"}
                                              for row in research_data.get("videos", [])),
        "audio_MB": round(size_audio / 1_000_000, 1), "video_MB": round(size_video / 1_000_000, 1),
        "stima_audio_totale_GB_160kbps": round(seconds * 160_000 / 8 / 1_000_000_000, 1),
        "copertura": "Scheda Video, escluse dirette e Shorts",
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["catalogo", "audio", "video", "trascrizioni", "stato"])
    parser.add_argument("--archive", type=Path, default=ROOT / "archivio", help="Cartella dati, anche su disco esterno")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Intera scheda Video censita; predefinito: 3 contributi di prova")
    group.add_argument("--ids", nargs="+", action="extend", help="ID YouTube presenti nel catalogo; ripetibile come --ids=ID")
    parser.add_argument("--limit", type=int, help="Limita i nuovi file da scaricare o i video da analizzare")
    parser.add_argument("--dry-run", action="store_true", help="Mostra il lotto audio/video senza richieste a YouTube")
    args = parser.parse_args()
    args.archive = args.archive.expanduser().resolve()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit deve essere positivo")
    if args.dry_run and args.command not in {"audio", "video"}:
        parser.error("--dry-run è disponibile per audio e video")
    if args.command != "stato" and not args.dry_run:
        required = ["yt-dlp"] + (["ffmpeg"] if args.command in {"audio", "video"} else [])
        for binary in required:
            if not shutil.which(binary):
                raise SystemExit("Strumento mancante: " + binary)
    try:
        if args.command == "catalogo":
            catalog(args)
        elif args.command == "stato":
            report(args)
        elif args.command == "trascrizioni":
            from ricerca import run_analysis
            if args.limit is not None and args.limit < 1:
                parser.error("--limit deve essere positivo")
            run_analysis(args.archive, None if args.all else (args.ids or PILOT), args.limit)
            report(args)
        else:
            download(args)
    except (subprocess.CalledProcessError, OSError, ValueError) as exc:
        raise SystemExit("Operazione non completata: " + str(exc)) from exc


if __name__ == "__main__":
    main()
