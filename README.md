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

GitHub Pages pubblica la cartella `docs/` del branch `main` sul [sito del Circolo](https://polaresweb3.github.io/circolo-del-dr-divago/). Un push su `main` aggiorna anche il sito pubblico. Gli aggiornamenti richiedono la conferma specifica descritta in `AGENTS.md`.

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

## Catalogo editoriale nella pagina del progetto

La citazione di Borges e la breve presentazione restano in apertura di `progetto.html`.
Il catalogo dei libri del Circolo è alimentato da `sito/dist/data/volumi.json`,
separato dai libri citati nei video. La lista vuota mantiene il primo volume del 2015
in preparazione, senza titolo, copertina o acquisto inventati.

Quando un volume è pronto, aggiungere un oggetto con `year`, `title`, `description`,
`cover` (`src`, eventualmente `alt`) e `purchase_links` (lista di `label` e `url` HTTPS).
Salvare la copertina autentica in `sito/dist/assets/volumi/` e indicarne il percorso
relativo, per esempio `assets/volumi/2015.jpg`. Il generatore richiede tutti i dati
e almeno un collegamento di acquisto per inserire il volume tra le uscite.
Non aggiungere dati di prova al catalogo pubblico.

Il volume più recente è in evidenza; gli altri seguono per anno decrescente nella
stessa pagina. Copertine e collegamenti sono mantenuti anche nelle anteprime offline
e nelle copie preparate per l'hosting. I normali comandi di generazione aggiornano
il catalogo senza aggiungere pagine o voci al menu. La pubblicazione online richiede
la conferma specifica prevista dalle istruzioni di sicurezza.

## Blog e firma pubblica — 26 ottobre 2026

Il menu mantiene la voce **Blog**. Al suo interno, **Una divagazione necessaria**
è la rubrica dedicata a una lettura o a una conversazione da riscoprire.
La Home riprende automaticamente il più recente articolo pubblicato di questa rubrica, ordinato
per `published_at`, usando gli stessi dati del Blog. Finché non ci sono articoli,
mostra la rubrica in preparazione. Il vecchio manifesto in `data/blog.json`
resta un archivio di lavoro e non viene ripubblicato nella rubrica.

Gli articoli si preparano in `sito/dist/data/articoli-blog.json`: lista di oggetti
con `id` (slug), `category` (`una-divagazione-necessaria` o `voci-del-blog`), `status` (`draft` o
`published`), `published_at` (`AAAA-MM-GG`), `title`, `excerpt`, `paragraphs`
(lista di paragrafi), eventuale `author` e `reference` (`label`, `url` HTTPS
del video o del libro scelto). Solo gli articoli pubblicati e completi entrano
nel Blog e nel richiamo in Home; i normali generatori aggiornano entrambi.
Le bozze incomplete non creano pagine. L’intenzione editoriale è mensile,
senza promettere una cadenza al pubblico e senza automazioni pianificate.

Per indicazione dell’utente, l’invito email resta **In preparazione**: nessun modulo,
raccolta di indirizzi o servizio newsletter è attivato. La firma pubblica è
**Dr Divago**. Il nome anagrafico compare soltanto nell’introduzione iniziale
della Home, marcata con `data-name-intro`. Le altre persone chiamate Sergio,
gli URL, gli identificativi e i dati delle fonti sono conservati; Python e
JavaScript uniformano i testi visibili, compresi filtri e schede.


### Voci del blog: proposta di seconda sezione

Accanto alla rubrica, Voci del blog è predisposta per articoli originali di
Dr Divago, Riccardo Persiani e altri autori interessati a contribuire su
letteratura, filosofia, storia, società e cultura. Ogni contributo pubblicato
richiede un `author` esplicito; `reference` è facoltativo per gli originali.
Gli articoli restano separati per categoria e Voci del blog non sostituisce
il richiamo alla rubrica in Home. Nessun contributo o autore ospite è inventato.
Le indicazioni di Domenico Conversa sono proposte aperte al confronto: questa
impostazione resta aperta al confronto e non costituisce un impegno alla contribuzione degli autori menzionati.

## Home: due conversazioni per cominciare — 26 ottobre 2026

La prima parte della Home contiene le due conversazioni indicate dall’utente:
**Il peso delle idee** (`HXgpLjZ7apA`), sulle ragioni del canale, e **Alcuni
precursori di George Orwell** (`vj1E4hCrITY`), con ingresso a **4:20**.
Titoli e durate provengono dal catalogo; le brevi introduzioni si basano sulle
schede già redatte da fonti automatiche. Non è dichiarato un nuovo ascolto umano.

`home_conversazioni.py` rende entrambe le scelte nella pagina statica, disponibili
anche prima del caricamento dei dati nel browser. Un solo pulsante per conversazione porta alla pagina del video,
con il minuto scelto e la scheda completa.
`sito/avvio_video.js`, incorporato nell’app, conserva `?t=260` nel parametro `start`
del player e nell’apertura da file. Il player resta attivato dalla scelta del lettore.
Archivio e progetto editoriale sono raggiungibili dal menu principale.
Il nome completo rimane soltanto nella breve introduzione iniziale della Home.
Le precedenti tre scelte nel riquadro inferiore sono sostituite da questo ingresso.


### Home semplificata

Ogni conversazione in evidenza ha una sola azione: guardare il video. Le azioni
aggiuntive per YouTube e per la scheda e il paragrafo descrittivo sotto i video
sono stati rimossi. Il secondo video conserva l’ingresso a 4:20; la scheda
rimane nella pagina del video. Archivio e progetto sono accessibili dal menu.
