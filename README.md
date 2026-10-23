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


## Privacy e crediti — 23 ottobre 2026

Footer aggiornato con Privacy e Crediti e diritti nelle tre proposte, nelle
anteprime offline e nei pacchetti preparati. Il titolare indicato è Riccardo
Persiani. L’informativa è una bozza: mancano email pubblica e scelta dell’hosting,
con le relative informazioni su log, conservazione e trasferimenti.

Il codice non imposta cookie né usa localStorage/sessionStorage; non contiene
analytics o pixel pubblicitari. Le miniature contattano i.ytimg.com anche prima
della riproduzione. Il player youtube-nocookie.com si carica soltanto con
“Accetta e riproduci”, dopo l’avviso privacy, e si rimuove con “Disattiva player
YouTube”. La scelta resta limitata al player attivo e non è salvata per le visite
successive. Nessun banner generale aggiunto; l’hosting definitivo deve ancora
essere verificato. In apertura da file il comando apre YouTube con un avviso
specifico. La modalità nocookie non viene descritta come assenza di trattamento.

Verifica locale: 9 test sulle pagine nella cartella principale e 9 nella copia
GitHub; prova di attivazione/disattivazione in tutte e tre le proposte; 9 viste a
320 px senza scorrimento orizzontale. Le informazioni sullo storage del sito
non certificano l’assenza di cookie o memoria nei frame esterni di Google.
Resoconto: sito/verifica-privacy-2026-10-23.json nella cartella principale.
Nessuna pubblicazione eseguita.

## Ampliamento editoriale locale del 23 ottobre

L’ultima ripresa aggiunge 20 schede redatte dopo lettura integrale delle fonti automatiche: il totale preparato è di 273 schede su 869 video e 151 voci bibliografiche. Il lotto comprende 90 passaggi e 31 collegamenti opera/video. Le nuove immagini di riferimento hanno fonti registrate; racconti, saggi e libri biblici restano distinti dalle raccolte mostrate. Le opinioni controverse sono attribuite al relatore e il contributo su Nord Stream è presentato come satira. Le trascrizioni integrali e gli audio restano privati. Questi aggiornamenti sono preparati localmente, senza pubblicazione in produzione.

## Seconda ripresa editoriale locale del 23 ottobre

Aggiunte altre 18 schede, dopo lettura integrale dei segmenti disponibili: il totale è ora di **291 schede su 869 video**, con **162 voci bibliografiche**. Questo passaggio comprende 94 passaggi temporali e 17 collegamenti opera/video, su 181.7 minuti di fonti. Tutte le 162 voci hanno un’immagine locale: 159 file distinti, decodificati e controllati, con impronta registrata. Il segnaposto IBS per Schiller è stato respinto e sostituito con la copertina ufficiale Reclam. Le edizioni e le raccolte di riferimento restano dichiarate. La preparazione ora rifiuta copertine alterate, prive del controllo di decodifica o corrispondenti al segnaposto noto. Le fonti troppo frammentarie restano in coda di revisione. Audio e trascrizioni integrali sono privati; la trascrizione locale prosegue. Nessuna pubblicazione in produzione.
