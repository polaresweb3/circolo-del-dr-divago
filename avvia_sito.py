#!/usr/bin/env python3
"""Avvia l'anteprima con player YouTube su un server accessibile solo dal Mac."""
import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import re
from urllib.parse import urlsplit
import webbrowser


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, archive=None, **kwargs):
        self.archive = archive or Path(__file__).resolve().parent / "archivio"
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.send_transcript(head=False):
            return
        super().do_GET()

    def do_HEAD(self):
        if self.send_transcript(head=True):
            return
        super().do_HEAD()

    def send_transcript(self, head=False):
        path = urlsplit(self.path).path
        if not path.startswith("/trascrizioni/"):
            return False
        match = re.fullmatch(r"/trascrizioni/([A-Za-z0-9_-]{11})/([a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?)\.(txt|vtt|json)", path)
        if not match:
            self.send_error(404)
            return True
        ident, language, extension = match.groups()
        root = self.archive / "trascrizioni-autorizzate"
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"items": []}
        if not any(t["video_id"] == ident and t["language"] == language for t in manifest["items"]):
            self.send_error(404, "Trascrizione autorizzata non archiviata")
            return True
        target = (root / ident / language / ("trascrizione." + extension)).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            self.send_error(404)
            return True
        content = target.read_bytes()
        mime = {"txt": "text/plain", "vtt": "text/vtt", "json": "application/json"}[extension]
        self.send_response(200)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f'attachment; filename="{ident}.{language}.{extension}"')
        self.end_headers()
        if not head:
            self.wfile.write(content)
        return True

    def end_headers(self):
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        # I file con hash cambiano indirizzo ad ogni modifica, come nel sito pubblico.
        immutable = re.search(r'/data/indici/[a-z-]+\.[a-f0-9]{20}\.json$', urlsplit(self.path).path)
        self.send_header("Cache-Control", "public, max-age=31536000, immutable" if immutable else "no-cache")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--archive", type=Path, default=Path(__file__).resolve().parent / "archivio")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent / "sito/dist",
                        help="Cartella del sito o di una proposta grafica locale")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("La porta deve essere compresa tra 0 e 65535.")
    directory = args.directory.expanduser().resolve()
    if not (directory / "index.html").is_file():
        parser.error("La cartella scelta non contiene index.html.")
    handler = partial(PreviewHandler, directory=str(directory), archive=args.archive.expanduser().resolve())
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError:
        if args.port == 0:
            raise
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    url = "http://127.0.0.1:{}/".format(server.server_port)
    print("Circolo del Dr Divago: " + url, flush=True)
    print("Lascia aperta questa finestra mentre usi il sito. Premi Ctrl+C per chiudere.", flush=True)
    if not args.no_browser:
        opener = threading.Timer(0.3, webbrowser.open, args=(url,))
        opener.daemon = True
        opener.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAnteprima chiusa.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
