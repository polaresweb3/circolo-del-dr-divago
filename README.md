# Circolo del Dr Divago

Sito statico del progetto culturale dedicato ai contributi del canale [Dr Divago](https://www.youtube.com/@DrDivago), con catalogo video, biblioteca dei libri citati e schede editoriali originali.

Il repository contiene i sorgenti Python, i modelli HTML, CSS e JavaScript, i dati destinati alla consultazione pubblica e le tre proposte grafiche. Audio, video scaricati, trascrizioni integrali e archivio privato restano fuori da GitHub. I video si consultano tramite YouTube. Le fonti automatiche e i minutaggi richiedono revisione; le copertine indicano edizioni di riferimento, senza attribuirle automaticamente ai video.

## Consultazione locale

```sh
python3 -m http.server 8765 --directory docs --bind 127.0.0.1
```

Aprire http://127.0.0.1:8765/. La pagina iniziale permette di scegliere tra Originale, Editoriale e Sala di lettura.

## Modifiche e generazione

Richiede Python 3.9 o successivo su macOS o Linux. La generazione del sito usa la libreria standard e non richiede download o servizi esterni.

- Modelli delle pagine: `sito/templates/`.
- Stile e interazioni: `sito/dist/styles.css`, `sito/dist/app.js`.
- Dati pubblici: `sito/dist/data/`.
- Varianti grafiche: `proposte/editoriale/sorgenti/` e `proposte/sala-lettura/sorgenti/`.

```sh
python3 -B prepara_github_pages.py
```

Il comando rigenera le pagine, controlla collegamenti e riferimenti ai file privati, e aggiorna `docs/`. Non pubblica il sito. Gli strumenti di archiviazione e trascrizione sono conservati come codice: richiedono l’archivio locale e le rispettive dipendenze, tra cui yt-dlp, ffmpeg e faster-whisper.

## GitHub Pages

La cartella `docs/` è pronta per essere selezionata come sorgente GitHub Pages dal branch `main`. Non sono presenti workflow di deploy automatico. L’attivazione di Pages e gli aggiornamenti successivi del sito online richiedono la conferma specifica descritta in `AGENTS.md`.

## Attribuzioni

Questo progetto non implica un’affiliazione ufficiale con il titolare del canale. Metadati, collegamenti e copertine mantengono le attribuzioni presenti nei dati; non viene concessa una licenza sui contenuti di terzi.
