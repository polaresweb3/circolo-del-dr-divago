/* Il minuto scelto resta valido nel player e nell’apertura diretta su YouTube. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VideoStart = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  function seconds(value) {
    if (typeof value !== 'string' || !/^\d+s?$/.test(value)) return 0;
    const number = Number(value.replace(/s$/, ''));
    return Number.isSafeInteger(number) && number >= 0 ? number : 0;
  }
  function fromPage(page) {
    return seconds(new URLSearchParams(page.search || '').get('t'));
  }
  function clock(value) {
    const hours = Math.floor(value / 3600), minutes = Math.floor(value / 60) % 60;
    const end = String(value % 60).padStart(2, '0');
    return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${end}` : `${minutes}:${end}`;
  }
  return {seconds, fromPage, clock};
});

/* Firma pubblica nei testi visibili. URL, valori dei filtri e dati restano intatti. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PublicNames = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  function format(text) {
    if (typeof text !== 'string') return text;
    return text.replace(/\b(?:Sergio\s+Caldarella|Caldarella,\s*Sergio|S\.?\s+Caldarella|Caldarella)\b/gi, 'Dr Divago')
      .replace(/\b[Ss]ergio\b(?![ \t]+[A-ZÀ-ÖØ-Þ])/g, 'Dr Divago')
      .replace(/\bDr\.\s+Divago\b/gi, 'Dr Divago');
  }
  function normalizeDocument(root) {
    if (!root) return;
    const excluded = 'script, style, code, pre, textarea, [data-name-intro]';
    function textNode(text) {
      if (text.parentElement?.closest(excluded)) return;
      const revised = format(text.nodeValue);
      if (revised !== text.nodeValue) text.nodeValue = revised;
    }
    if (root.nodeType === 3) { textNode(root); return; }
    if (root.nodeType !== 1 || root.closest(excluded)) return;
    const walker = root.ownerDocument.createTreeWalker(root, 4);
    let text;
    while ((text = walker.nextNode())) textNode(text);
    for (const element of [root, ...root.querySelectorAll('[alt], [title], [aria-label]')]) {
      if (element.closest(excluded)) continue;
      for (const attr of ['alt', 'title', 'aria-label']) {
        if (!element.hasAttribute(attr)) continue;
        const original = element.getAttribute(attr), revised = format(original);
        if (original !== revised) element.setAttribute(attr, revised);
      }
    }
  }
  function observe(root) {
    if (!root) return null;
    normalizeDocument(root);
    const observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'childList') record.addedNodes.forEach(normalizeDocument);
        else normalizeDocument(record.target);
      }
    });
    observer.observe(root, {childList: true, subtree: true, characterData: true,
      attributes: true, attributeFilter: ['alt', 'title', 'aria-label']});
    return observer;
  }
  return {format, normalizeDocument, observe};
});

'use strict';
/* Filtri dell’archivio video: anno di pubblicazione e durata. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VideoFilters = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const normalize = value => String(value ?? '').toLocaleLowerCase('it').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  function yearOf(video) {
    const match = String(video.upload_date || '').match(/^(\d{4})-?(\d{2})-?(\d{2})$/);
    if (!match) return null;
    const year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
    const date = new Date(Date.UTC(year, month - 1, day));
    return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day ? year : null;
  }
  function years(videos) {
    return [...new Set(videos.map(yearOf).filter(year => year !== null))].sort((a, b) => b - a);
  }
  function matches(video, criteria = {}, details = '') {
    const year = yearOf(video), selected = criteria.year || 'all';
    const yearMatches = selected === 'all' || (selected === 'unknown' ? year === null : year === Number(selected));
    return yearMatches && (!criteria.long || (Number.isFinite(video.duration) && video.duration > 1200))
      && normalize(`${video.title || ''} ${details}`).includes(normalize(criteria.query || '').trim());
  }
  return {yearOf, years, matches};
});

'use strict';
/* Minutaggi leggibili nei testi; i dati numerici e gli URL restano invariati. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ReadableTimings = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const number = String.raw`\d+(?:[.,]\d+)?`;
  const expression = new RegExp(String.raw`(?<![\p{L}\p{N}_.,:])${number}(?:\s*(?:[–—−-]|e|a)\s*${number})*\s+(?:secondi|secondo|sec|s)(?![\p{L}\p{N}_])`, 'giu');
  function timeInWords(value) {
    const [whole] = value.split(/[.,]/); // Precisione al secondo, come i link YouTube; originale conservato.
    const total = Number(whole);
    if (!Number.isSafeInteger(total)) return value + ' secondi';
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor(total / 60) % 60;
    const seconds = total % 60;
    const parts = [];
    if (hours) parts.push(`${hours} ${hours === 1 ? 'ora' : 'ore'}`);
    if (minutes) parts.push(`${minutes} ${minutes === 1 ? 'minuto' : 'minuti'}`);
    if (seconds || !parts.length) parts.push(`${seconds} ${seconds === 1 ? 'secondo' : 'secondi'}`);
    return parts.length < 2 ? parts[0] : parts.slice(0, -1).join(', ') + ' e ' + parts.at(-1);
  }
  function format(value) {
    if (typeof value !== 'string') return value;
    return value.replace(expression, match => match.replace(/\s+(?:secondi|secondo|sec|s)$/iu, '')
      .replace(/\d+(?:[.,]\d+)?/g, timeInWords));
  }
  function normalizeDocument(root) {
    if (!root) return;
    const doc = root.ownerDocument;
    const walker = doc.createTreeWalker(root, 4); // SHOW_TEXT
    let text;
    while ((text = walker.nextNode())) {
      if (text.parentElement?.closest('script, style, code, pre, textarea')) continue;
      const readable = format(text.nodeValue);
      if (readable !== text.nodeValue) text.nodeValue = readable;
    }
    root.querySelectorAll('[title]').forEach(item => {
      if (!item.closest('script, style, code, pre, textarea')) item.title = format(item.title);
    });
  }
  return {format, timeInWords, normalizeDocument};
});

'use strict';
/* Filtri della biblioteca. Nessuna modifica ai dati editoriali. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.LibraryFilters = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const normalize = value => String(value ?? '').toLocaleLowerCase('it').normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '').replace(/[_\s]+/g, ' ').trim();
  const formats = [
    ['all', 'Tutte le opere'], ['text', 'Libri e testi'], ['film', 'Cinema'],
    ['tv', 'Serie TV'], ['art', 'Arti visive'], ['music', 'Riferimenti musicali'],
    ['video', 'Altri video'], ['unknown', 'Tipo da precisare']
  ];
  const kinds = [
    ['narrative', 'Narrativa'], ['essay', 'Saggi e studi'], ['poetry', 'Poesia'],
    ['theatre', 'Teatro'], ['letters', 'Lettere e carteggi'], ['memoir', 'Biografie, diari e memorie'],
    ['religious', 'Testi religiosi'], ['article', 'Articoli e recensioni'], ['document', 'Documenti e discorsi'],
    ['book', 'Altri libri e testi'], ['film', 'Cinema'], ['tv', 'Serie TV'], ['art', 'Arti visive'],
    ['music', 'Riferimenti musicali'], ['video', 'Altri video'], ['unknown', 'Tipo da precisare']
  ];
  // Le regole riguardano esclusivamente work_type, mai titolo o autore.
  function classify(workType) {
    const t = normalize(workType);
    if (/^(film(?:\s|$)|opera cinematografica)/.test(t)) return {format: 'film', kind: 'film'};
    if (/^(serie televisiva|serie documentaria|miniserie|episodio (?:di serie |televisivo))/.test(t)) return {format: 'tv', kind: 'tv'};
    if (/^(dipinto|disegno|mosaico|affresco|scultura|incisione|fotografia|opera grafica)/.test(t)) return {format: 'art', kind: 'art'};
    if (/^(canzone|sinfonia|opera lirica|composizione musicale|inno)/.test(t)) return {format: 'music', kind: 'music'};
    if (/^(filmato|spot televisivo)|videoregistrat/.test(t)) return {format: 'video', kind: 'video'};
    // Varianti editoriali già esplicite nei metadati: nessuna deduzione dal titolo.
    if (/^cortometraggio/.test(t)) return {format: 'film', kind: 'film'};
    if (/^serie di dipinti/.test(t)) return {format: 'art', kind: 'art'};
    if (/^(composizione strumentale|opera musicale|concerto musicale)/.test(t)) return {format: 'music', kind: 'music'};
    if (/^(registrazione video|intervento televisivo|confronto televisivo|intervento audiovisivo|sketch televisivo)/.test(t)) return {format: 'video', kind: 'video'};
    if (/^musical$/.test(t)) return {format: 'text', kind: 'theatre'};
    if (/^romance$/.test(t)) return {format: 'text', kind: 'poetry'};
    if (/^(koan|salmo biblico|passo della mishnah|enciclica|costituzioni religiose)/.test(t)) return {format: 'text', kind: 'religious'};
    if (/^(vignetta|microtesto narrativo|ciclo narrativo)/.test(t)) return {format: 'text', kind: 'narrative'};
    if (/^(conversazioni e memorie|testo autobiografico)/.test(t)) return {format: 'text', kind: 'memoir'};
    if (/^(dossier di rivista|periodico|serie di articoli|fascicolo|numero monografico|numero di giornale|editoriale|case report)/.test(t)) return {format: 'text', kind: 'article'};
    if (/^(legge |codice etico|provvedimento giudiziario|carta giuridica|carta costitutiva|testo e registrazione sonora|appello politico|opinione giudiziaria|tre appelli radiofonici|bozza di direttiva|definizione operativa|titolo di legge|ordinanza|risposta a un indirizzo)/.test(t)) return {format: 'text', kind: 'document'};
    if (/^(inchiesta|opera giuridica|commento teologico|opera storica|opera storico|monografia|opera enciclopedica|capitolo scientifico|testo di etica medica|conferenze)/.test(t)) return {format: 'text', kind: 'essay'};
    if (/^(papiro matematico|dialogo|scritti e progetto|opera collettiva|corpus di fonti|classico cinese)/.test(t)) return {format: 'text', kind: 'book'};
    let kind = 'unknown';
    if (/^(lettera|epistola(?! in versi)|epistolario|carteggio|raccolta (di lettere|epistolare))/.test(t)) kind = 'letters';
    else if (/^(autobiografia|biografia|memori|diari|testimonianza|prosa autobiografica|narrazione autobiografica)/.test(t)) kind = 'memoir';
    else if (/^(libro biblico|testo religioso|classico taoista|sutra|traduzione biblica|raccolta di hadith)/.test(t)) kind = 'religious';
    else if (/^(articolo|recensione|notizia|voce enciclopedica)/.test(t)) kind = 'article';
    else if (/^(romanzo|racconto|racconti|novella|fiaba|favola|fumetto|striscia a fumetti|prosa breve|opera narrativa|trilogia di romanzi|raccolta di (racconti|novelle|favole))/.test(t)) kind = 'narrative';
    else if (/teatr|tragedia|dramma|commedia|opera drammatica|monologo/.test(t)) kind = 'theatre';
    else if (/poesia|poema|poemetto|poetic|sonetto|\bode\b|carme|cantico|versi|serranilla|distico/.test(t)) kind = 'poetry';
    else if (/^(document|memorandum|telegramma|appunti manoscritti di riunione|atti|rapporto|testo (normativo|costituzionale|di dottrina)|manifesto|discorso|dichiarazione|risoluzione|sentenza|atto |accordo|parere|requisitoria|dispaccio|comunicato|portale|omelia|sermon|lezione nobel|orazione|intervista|colloqui|dibattito)/.test(t)) kind = 'document';
    else if (/saggio|saggi|trattato|filosof|studio|ricerca|manuale|enciclopedia|dizionario|conferenza|tesi|working paper|divulgazione|storiograf|storia |opuscolo|pamphlet/.test(t)) kind = 'essay';
    else if (/libro|raccolta|antologia|quaderni|framment|prosa|meditazione|cronaca|resoconto|manoscritto|satira|utopia|testi letterari/.test(t)) kind = 'book';
    return {format: kind === 'unknown' ? 'unknown' : 'text', kind};
  }
  // Raggruppamenti orientativi dei soli topics delle schede video.
  const themes = [
    ['philosophy', 'Filosofia ed etica', /filosof|etic|morale|giudizio|responsabil|autonomia|liberta|ragione|pensiero|bene e male|senso della vita/],
    ['politics', 'Politica e società', /politic|poter|democra|societa|social|ideolog|capital|econom|lavoro|diritt|censur|totalitar|autoritar|nazion|razzism|antisemit|guerra|israel|palestin|ucrain/],
    ['history', 'Storia e memoria', /stori|memoria|shoah|olocausto|nazis|fascis|colonial|antichita|medioev|rivoluz|archiv|testimonian/],
    ['psychology', 'Psicologia e persona', /psicolog|psich|psicoanal|inconscio|freud|fromm|emozion|paura|sofferenza|identita|conformism|solitud|disagio|morte|sogni/],
    ['education', 'Educazione e cultura', /educaz|scuola|insegn|apprend|pedagog|universit|formaz|cultura|culturale|bibliotec/],
    ['media', 'Linguaggio e media', /lingu|media|giornalis|propaganda|comunicaz|notizie|informaz|disinformaz|piattaform|television|retoric|pubblicit/],
    ['literature', 'Letteratura e poesia', /letterat|poesi|poetic|romanzo|racconto|scrittura|lettura|traduzion|narrati|libri|libro/],
    ['religion', 'Religione e spiritualità', /religio|spiritual|teolog|cristian|bibb|evangel|buddh|islam|ebraism|fede|mistica|sacro/],
    ['science', 'Scienza e tecnica', /scien|tecn|matemat|fisica|biolog|sanita|sanitar|medic|salute|vaccin|intelligenza artificiale|nuclear|ecolog|ambient|digitale/],
    ['arts', 'Arte, cinema e musica', /\barte\b|artist|estetic|cinema|\bfilm\b|musica|pittura|dipinto|fotograf|teatro/]
  ];
  const textStatuses = new Set(['verificato', 'citazione_esplicita', 'riscontro_audio_automatico', 'titolo_nella_trascrizione']);
  const probableStatuses = new Set(['identificazione_probabile', 'citazione_probabile']);
  const mainRoles = new Set(['opera_principale', 'libro discusso', 'film discusso']);
  const uniqueVideoIds = book => [...new Set((book.mentions || []).map(m => m.video_id).filter(Boolean))];
  function evidenceMatches(book, evidence) {
    if (!evidence || evidence === 'all') return true;
    if (evidence === 'probable') return probableStatuses.has(book.status);
    if (evidence === 'title') return book.status === 'titolo_nel_video';
    return evidence === 'text' && textStatuses.has(book.status);
  }
  function createIndex(books, cards = []) {
    const cardsByVideo = new Map(cards.map(card => [card.video_id, card]));
    return books.map(book => {
      const videoIds = uniqueVideoIds(book);
      const linkedCards = videoIds.map(id => cardsByVideo.get(id)).filter(Boolean);
      const topicTexts = [...new Set(linkedCards.flatMap(card => card.topics || []))];
      const themeIds = themes.filter(([, , pattern]) => topicTexts.some(topic => pattern.test(normalize(topic)))).map(([id]) => id);
      const aliases = [book.original_title, ...(book.search_aliases || []), ...(book.alternative_titles || []), ...(book.aliases || [])];
      return {
        book, ...classify(book.work_type), videoIds, topics: topicTexts, themes: themeIds,
        withCard: linkedCards.length > 0,
        main: linkedCards.some(card => (card.books || []).some(ref => ref.book_id === book.id && mainRoles.has(ref.role))),
        search: normalize([book.title, book.subtitle, book.author, ...aliases].filter(Boolean).join(' '))
      };
    });
  }
  function matches(entry, criteria = {}, omit = null) {
    const q = normalize(criteria.q).split(' ').filter(Boolean);
    return q.every(word => entry.search.includes(word))
      && (omit === 'format' || !criteria.format || criteria.format === 'all' || entry.format === criteria.format)
      && (omit === 'kind' || !criteria.kind || criteria.kind === 'all' || entry.kind === criteria.kind)
      && (omit === 'author' || !criteria.author || criteria.author === 'all' || entry.book.author === criteria.author)
      && (omit === 'theme' || !criteria.theme || criteria.theme === 'all' || entry.themes.includes(criteria.theme))
      && evidenceMatches(entry.book, criteria.evidence)
      && (!criteria.presence || criteria.presence === 'all'
        || criteria.presence === 'repeated' && entry.videoIds.length > 1
        || criteria.presence === 'with-card' && entry.withCard
        || criteria.presence === 'main' && entry.main);
  }
  const alphabetical = (a, b) => `${a.book.author} ${a.book.title}`.localeCompare(`${b.book.author} ${b.book.title}`, 'it');
  function select(index, criteria = {}) {
    return index.filter(entry => matches(entry, criteria)).sort((a, b) => {
      if (criteria.sort === 'mentions') return b.videoIds.length - a.videoIds.length || alphabetical(a, b);
      if (criteria.sort === 'title') return a.book.title.localeCompare(b.book.title, 'it') || alphabetical(a, b);
      return alphabetical(a, b);
    }).map(entry => entry.book);
  }
  function counts(index, criteria, field) {
    const result = new Map();
    for (const entry of index) {
      if (!matches(entry, criteria, field)) continue;
      const values = field === 'theme' ? entry.themes : [field === 'author' ? entry.book.author : entry[field]];
      for (const value of values) result.set(value, (result.get(value) || 0) + 1);
    }
    return result;
  }
  function randomBook(books, random = Math.random) {
    return books.length ? books[Math.min(books.length - 1, Math.max(0, Math.floor(random() * books.length)))] : null;
  }

  let mounted = null;
  function mount({books, cards, onChange, onSurprise, document: doc = document}) {
    if (mounted) return mounted;
    const index = createIndex(books, cards);
    const $ = id => doc.getElementById(id);
    const option = (value, label) => { const node = doc.createElement('option'); node.value = value; node.textContent = label; return node; };
    const formatButtons = [];
    let activeFormat = 'all';
    const read = () => ({
      q: $('book-search').value, format: activeFormat, kind: $('book-kind').value,
      author: $('book-author').value, theme: $('book-theme').value,
      evidence: $('book-filter').value, presence: $('book-presence').value, sort: $('book-sort').value
    });
    $('book-kind').replaceChildren(option('all', 'Tutti i tipi'), ...kinds.filter(([id]) => index.some(entry => entry.kind === id)).map(([id, label]) => option(id, label)));
    $('book-theme').replaceChildren(option('all', 'Tutti i temi'), ...themes.filter(([id]) => index.some(entry => entry.themes.includes(id))).map(([id, label]) => option(id, label)));
    $('book-author').replaceChildren(option('all', 'Tutti gli autori / creatori'), ...[...new Set(books.map(book => book.author))].sort((a, b) => a.localeCompare(b, 'it')).map(author => option(author, author)));
    const availableFormats = formats.filter(([id]) => id === 'all' || index.some(entry => entry.format === id));
    for (const [id, label] of availableFormats) {
      const button = doc.createElement('button');
      button.type = 'button'; button.className = 'format-chip'; button.dataset.format = id;
      button.setAttribute('aria-pressed', String(id === activeFormat));
      button.addEventListener('click', () => {
        activeFormat = id;
        $('book-kind').value = 'all'; // Il cambio formato non conserva un tipo incompatibile.
        refresh(); onChange();
      });
      button.textContent = label;
      $('book-formats').append(button); formatButtons.push([button, id, label]);
    }
    const parameters = new URLSearchParams(doc.defaultView.location.search);
    if (availableFormats.some(([id]) => id === parameters.get('formato'))) activeFormat = parameters.get('formato');
    for (const [param, id] of [['tipo', 'book-kind'], ['autore', 'book-author'], ['tema', 'book-theme'], ['presenza', 'book-presence'], ['riscontro', 'book-filter'], ['ordine', 'book-sort']]) {
      const control = $(id);
      if ([...control.options].some(opt => opt.value === parameters.get(param))) control.value = parameters.get(param);
    }
    function refresh() {
      const criteria = read();
      $('book-author-label').textContent = activeFormat === 'film' ? 'Regista / autore' : 'Autore / creatore';
      $('book-author').options[0].textContent = activeFormat === 'film' ? 'Tutti i registi / autori' : 'Tutti gli autori / creatori';
      const formatCounts = counts(index, {...criteria, kind: 'all'}, 'format');
      for (const [button, id, label] of formatButtons) {
        const count = id === 'all' ? [...formatCounts.values()].reduce((a, b) => a + b, 0) : formatCounts.get(id) || 0;
        button.textContent = `${label} · ${count.toLocaleString('it-IT')}`;
        button.setAttribute('aria-pressed', String(id === activeFormat));
        button.disabled = count === 0 && id !== activeFormat && id !== 'all';
      }
      for (const [field, id, definitions] of [['kind', 'book-kind', kinds], ['theme', 'book-theme', themes], ['author', 'book-author', null]]) {
        const totals = counts(index, criteria, field);
        for (const opt of $(id).options) {
          if (opt.value === 'all') continue;
          const label = definitions ? definitions.find(([key]) => key === opt.value)[1] : opt.value;
          const count = totals.get(opt.value) || 0;
          opt.textContent = `${label} (${count.toLocaleString('it-IT')})`;
          opt.disabled = count === 0 && opt.value !== $(id).value;
          opt.hidden = opt.disabled;
        }
      }
      const filtered = select(index, criteria);
      $('book-random').disabled = filtered.length === 0;
      const chips = [];
      function addChip(label, remove) {
        const button = doc.createElement('button');
        button.type = 'button'; button.className = 'active-filter'; button.textContent = `${label} ×`;
        button.setAttribute('aria-label', `Rimuovi filtro: ${label}`);
        button.addEventListener('click', () => { remove(); refresh(); onChange(); $('book-search').focus(); });
        chips.push(button);
      }
      if (criteria.q.trim()) addChip(`Ricerca: ${criteria.q.trim()}`, () => { $('book-search').value = ''; });
      if (activeFormat !== 'all') addChip(formats.find(([id]) => id === activeFormat)[1], () => { activeFormat = 'all'; });
      for (const id of ['book-kind', 'book-author', 'book-theme', 'book-presence', 'book-filter']) {
        if ($(id).value !== 'all') addChip($(id).selectedOptions[0].textContent.replace(/ \([\d.]+\)$/, ''), () => { $(id).value = 'all'; });
      }
      $('book-active-filters').replaceChildren(...chips);
      $('book-reset').hidden = chips.length === 0 && criteria.sort === 'author';
      const advanced = ['book-presence', 'book-filter'].filter(id => $(id).value !== 'all').length;
      $('book-advanced-label').textContent = `Altri filtri${advanced ? ` (${advanced})` : ''}`;
      // Un URL copiato mantiene i filtri senza salvare preferenze o usare storage.
      const url = new URL(doc.defaultView.location.href);
      for (const [param, value, fallback] of [['q', criteria.q.trim(), ''], ['formato', activeFormat, 'all'], ['tipo', criteria.kind, 'all'], ['autore', criteria.author, 'all'], ['tema', criteria.theme, 'all'], ['presenza', criteria.presence, 'all'], ['riscontro', criteria.evidence, 'all'], ['ordine', criteria.sort, 'author']]) {
        if (value === fallback) url.searchParams.delete(param); else url.searchParams.set(param, value);
      }
      try { doc.defaultView.history.replaceState(null, '', url); } catch (_) { /* Alcuni browser limitano history su file:. */ }
      return filtered;
    }
    for (const id of ['book-kind', 'book-author', 'book-theme', 'book-presence']) $(id).addEventListener('change', () => { refresh(); onChange(); });
    $('book-search').addEventListener('input', refresh);
    $('book-filter').addEventListener('change', refresh);
    $('book-sort').addEventListener('change', refresh);
    $('book-reset').addEventListener('click', () => {
      activeFormat = 'all'; $('book-search').value = '';
      for (const id of ['book-kind', 'book-author', 'book-theme', 'book-presence', 'book-filter']) $(id).value = 'all';
      $('book-sort').value = 'author';
      try { doc.defaultView.history.replaceState(null, '', doc.defaultView.location.pathname); } catch (_) {}
      refresh(); onChange(); $('book-search').focus();
    });
    $('book-random').addEventListener('click', () => {
      const book = randomBook(select(index, read()));
      if (book) onSurprise(book);
    });
    mounted = {index, criteria: read, refresh, select: () => select(index, read())};
    refresh();
    return mounted;
  }
  return {normalize, classify, formats, kinds, themes, uniqueVideoIds, evidenceMatches, createIndex, matches, select, counts, randomBook, mount};
});

'use strict';
const state = { videos: [], cards: [], filtered: [], page: 0, perPage: 9, books: [], bookPage: 0, bookPerPage: 8 };
const $ = id => document.getElementById(id);
const page = document.body.dataset.page || 'home';
const offline = document.body.dataset.preview === 'true';
const rootPath = document.body.dataset.root || '';
function siteUrl(name) {
  const routes = {home: 'index.html', video: 'video.html', biblioteca: 'biblioteca.html', blog: 'blog.html', eventi: 'eventi.html', progetto: 'progetto.html', privacy: 'privacy.html', crediti: 'crediti.html'};
  if (!(name in routes)) throw new Error('Pagina sconosciuta');
  return offline ? (name === 'home' ? 'anteprima.html' : `anteprima-${name}.html`) : rootPath + routes[name];
}
function videoPageUrl(video) {
  if (!/^[A-Za-z0-9_-]{11}$/.test(video.id)) throw new Error('ID video non valido');
  return offline ? `anteprima-scheda-${video.id}.html` : `${rootPath}video/${video.id}.html`;
}
function sheetLink(video) {
  const prepared = state.cards.some(item => item.video_id === video.id);
  const link = node('a', 'text-link sheet-link', prepared ? 'Video e approfondimento →' : 'Apri il video →');
  link.href = videoPageUrl(video);
  return link;
}
function on(id, event, handler) {
  $(id)?.addEventListener(event, handler);
}
function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = ReadableTimings.format(text);
  return item;
}
function duration(seconds) {
  if (typeof seconds !== 'number') return 'Durata n.d.';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  const rest = String(Math.floor(seconds % 60)).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}
function youtube(id, seconds = null) {
  if (!/^[A-Za-z0-9_-]{11}$/.test(id)) throw new Error('ID video non valido');
  const url = new URL('https://www.youtube.com/watch');
  url.searchParams.set('v', id);
  if (Number.isFinite(seconds) && seconds >= 0) url.searchParams.set('t', Math.floor(seconds));
  return url.href;
}
function sourceLink(id, label, seconds) {
  const link = node('a', 'text-link', label);
  link.href = youtube(id, seconds);
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  return link;
}
function showDialog(content) {
  $('dialog-content').replaceChildren(...content);
  if (!$('detail').open) $('detail').showModal();
  else $('close-dialog').focus();
  document.body.style.overflow = 'hidden';
}
function canEmbedYouTube(page = window.location) {
  return ['http:', 'https:'].includes(page.protocol) && Boolean(page.origin) && page.origin !== 'null';
}
function youtubeEmbedUrl(id, page = window.location, start = VideoStart.fromPage(page)) {
  youtube(id);
  if (!canEmbedYouTube(page)) throw new Error('Il player richiede un’origine web valida.');
  const url = new URL(`https://www.youtube-nocookie.com/embed/${id}`);
  url.searchParams.set('autoplay', '1');
  url.searchParams.set('playsinline', '1');
  url.searchParams.set('origin', page.origin);
  if (start > 0) url.searchParams.set('start', String(start));
  return url.href;
}
function playInlineVideo(button) {
  const id = button.dataset.playVideo;
  const start = VideoStart.fromPage(window.location);
  if (!canEmbedYouTube()) {
    window.open(youtube(id, start || null), '_blank', 'noopener,noreferrer');
    return;
  }
  const frame = node('iframe', 'video-frame');
  frame.title = document.querySelector('h1').textContent;
  frame.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture';
  frame.referrerPolicy = 'strict-origin-when-cross-origin';
  frame.allowFullscreen = true;
  frame.src = youtubeEmbedUrl(id, window.location, start);
  const container = button.closest('.video-consent');
  const disable = container.querySelector('.player-disable');
  button.replaceWith(frame);
  disable.hidden = false;
  disable.onclick = () => {
    frame.replaceWith(button);
    disable.hidden = true;
    disable.onclick = null;
    button.focus();
  };
  frame.focus();
}
function videoCard(video) {
  const card = node('article', 'video-card');
  const image = node('a', 'thumbnail-button');
  image.href = videoPageUrl(video);
  image.setAttribute('aria-label', 'Apri il video: ' + video.title);
  const img = node('img');
  img.src = `https://i.ytimg.com/vi/${video.id}/hqdefault.jpg`;
  img.alt = ''; img.loading = 'lazy'; img.width = 480; img.height = 270;
  image.append(img, node('span', 'play-icon', '▶'), node('span', 'duration', duration(video.duration)));
  const heading = node('h3');
  const title = node('a', 'title-button', video.title);
  title.href = videoPageUrl(video);
  heading.append(title);
  card.append(image, heading, sheetLink(video));
  return card;
}
function renderVideos() {
  const total = state.filtered.length;
  const pages = Math.max(1, Math.ceil(total / state.perPage));
  state.page = Math.min(state.page, pages - 1);
  const start = state.page * state.perPage;
  const cards = state.filtered.slice(start, start + state.perPage).map(videoCard);
  $('videos').replaceChildren(...(cards.length ? cards : [node('p', 'empty', 'Nessun video trovato. Prova un altro titolo o cambia il filtro.')]));
  $('results').textContent = `${total.toLocaleString('it-IT')} ${total === 1 ? 'contributo' : 'contributi'}${total ? ` · ${start + 1}–${Math.min(start + state.perPage, total)}` : ''}`;
  $('page-label').textContent = `Pagina ${state.page + 1} di ${pages}`;
  $('previous').disabled = state.page === 0;
  $('next').disabled = state.page >= pages - 1;
}
function populateVideoYears() {
  const select = $('video-year');
  if (!select) return;
  const options = [['all', 'Tutti gli anni'], ...VideoFilters.years(state.videos).map(year => [String(year), String(year)])];
  const missingYears = state.videos.filter(video => VideoFilters.yearOf(video) === null).length;
  if (missingYears) options.push(['unknown', `Anno da recuperare (${missingYears})`]);
  select.replaceChildren(...options.map(([value, label]) => { const option = node('option', '', label); option.value = value; return option; }));
}
function filterVideos() {
  const query = $('search').value.trim();
  const year = $('video-year')?.value || 'all';
  const long = $('filter').value === 'long';
  state.perPage = 9;
  const details = new Map(state.cards.map(card => [card.video_id, [card.title, ...card.topics, ...card.books.map(book => `${book.title} ${book.author}`)].join(' ')]));
  state.filtered = state.videos.filter(video => VideoFilters.matches(video, {query, year, long}, details.get(video.id) || ''));
  state.page = 0;
  renderVideos();
}
function coverAlt(book) {
  return book.cover.alt || `${book.cover.image_label || 'Copertina'} di ${book.cover.display_title || book.title}, ${book.author}`;
}
function compactCoverCaption(book) {
  const cover = book.cover || {};
  const label = String(cover.caption || cover.edition_label || '').replace(/\s+/g, ' ').trim();
  if (label && label.length <= 56) return label;
  if (cover.container_title) return 'Volume di riferimento';
  const imageLabel = String(cover.image_label || '').replace(/\s+/g, ' ').trim();
  if (imageLabel && imageLabel.length <= 36) return imageLabel;
  return LibraryFilters.classify(book.work_type).format === 'text'
    ? 'Edizione di riferimento' : 'Immagine di riferimento';
}
function showBookCover(book) {
  const heading = node('h2', 'dialog-title', book.title);
  heading.id = 'dialog-title';
  const image = node('img', 'book-cover-large');
  image.src = book.cover.src;
  image.alt = coverAlt(book);
  const caption = node('p', 'dialog-description', `${book.author} · ${book.cover.edition_label}`);
  const link = node('a', 'text-link', 'Fonte della copertina ↗');
  link.href = book.cover.source_page;
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  const collection = book.cover.container_title ? [node('p', 'dialog-description', `Volume di riferimento: ${book.cover.container_title}`)] : [];
  const editionNote = book.cover.edition_note ? [node('p', 'dialog-description', book.cover.edition_note)] : [];
  showDialog([heading, image, caption, ...collection, ...editionNote, link]);
}
function renderBooks(books) {
  const pages = Math.max(1, Math.ceil(books.length / state.bookPerPage));
  state.bookPage = Math.min(state.bookPage, pages - 1);
  const start = state.bookPage * state.bookPerPage;
  $('book-results').textContent = `${books.length} ${books.length === 1 ? 'opera' : 'opere'}${books.length ? ` · ${start + 1}–${Math.min(start + state.bookPerPage, books.length)}` : ''}`;
  $('book-page').textContent = `Pagina ${state.bookPage + 1} di ${pages}`;
  $('book-previous').disabled = state.bookPage === 0;
  $('book-next').disabled = state.bookPage >= pages - 1;
  const rows = books.slice(start, start + state.bookPerPage).map(book => {
    const row = node('article', 'book-row');
    row.id = 'book-' + book.id;
    const cover = node('figure', 'book-cover');
    if (book.cover && book.cover.src) {
      const button = node('button', 'book-cover-button');
      button.setAttribute('aria-label', `Apri copertina e dettagli: ${coverAlt(book)}`);
      button.setAttribute('aria-haspopup', 'dialog');
      button.title = 'Apri copertina, edizione e fonte';
      const image = node('img');
      image.src = book.cover.src;
      image.alt = coverAlt(book);
      image.loading = 'lazy'; image.width = 84; image.height = 126;
      image.addEventListener('error', () => {
        button.replaceWith(node('span', 'cover-missing', 'Copertina non disponibile'));
      }, {once: true});
      button.append(image);
      button.addEventListener('click', () => showBookCover(book));
      cover.append(button, node('figcaption', '', compactCoverCaption(book)));
    } else {
      const workLabel = {saggio: 'Saggio', poesia: 'Poesia'}[book.work_type];
      cover.append(node('span', 'cover-missing', workLabel || 'Copertina non disponibile'));
    }
    const text = node('div', 'book-copy');
    const title = node('h3', '', book.title);
    const labels = {verificato: 'VERIFICATO', citazione_esplicita: 'RISCONTRO NEL TESTO AUTOMATICO', riscontro_audio_automatico: 'RISCONTRO VOCALE AUTOMATICO', titolo_nella_trascrizione: 'TITOLO NELLA TRASCRIZIONE', titolo_nel_video: 'NEL TITOLO DEL VIDEO', identificazione_probabile: 'IDENTIFICAZIONE PROBABILE', da_riascoltare: 'DA RIASCOLTARE'};
    title.append(node('span', 'book-state', labels[book.status] || 'DA VERIFICARE'));
    text.append(title);
    if (book.subtitle) text.append(node('p', 'book-subtitle', book.subtitle));
    text.append(node('p', 'book-author', book.author));
    if (book.work_type === 'saggio') text.append(node('p', 'book-work-type', 'Saggio · testo distinto dalle raccolte'));
    if (book.work_type === 'poesia') text.append(node('p', 'book-work-type', 'Poesia · testo distinto dalle raccolte'));
    if (book.work_type === 'articolo') text.append(node('p', 'book-work-type', 'Articolo · testo distinto dal periodico'));
    const videoCount = new Set(book.mentions.map(mention => mention.video_id)).size;
    text.append(node('p', 'book-mentions-count', videoCount === 1 ? '1 video collegato' : `${videoCount} video collegati`));
    if (book.source) {
      const notes = node('details', 'book-details');
      notes.append(node('summary', '', 'Note sul riferimento'), node('p', 'book-source', book.source));
      text.append(notes);
    }
    row.append(cover, text);
    const links = node('div', 'book-links');
    const videoLinks = node('div', 'book-link-group');
    if (book.mentions.length) videoLinks.append(node('h4', 'book-links-heading', 'Video e passaggi'));
    for (const mention of book.mentions) {
      const reference = node('div', 'book-mention');
      const moment = mention.title_seconds ?? mention.seconds;
      const qualifier = mention.verification === 'identificazione_probabile' ? ' · probabile' : '';
      const link = sourceLink(mention.video_id, '', moment);
      link.className = 'book-youtube-link';
      const play = node('span', 'book-link-icon', '▶');
      play.setAttribute('aria-hidden', 'true');
      link.append(play, node('span', '', Number.isFinite(moment) ? `YouTube · ${duration(moment)}${qualifier} ↗` : `Guarda su YouTube${qualifier} ↗`));
      link.setAttribute('aria-label', `Guarda su YouTube: ${mention.video_title || book.title}${Number.isFinite(moment) ? `, passaggio ${duration(moment)}` : ''}${qualifier} (nuova scheda)`);
      if (mention.note) link.title = ReadableTimings.format(mention.note);
      const context = node('a', 'text-link book-video-title', mention.video_title || 'Video e scheda →');
      context.href = videoPageUrl({id: mention.video_id});
      reference.append(context, link);
      videoLinks.append(reference);
    }
    if (book.mentions.length) links.append(videoLinks);
    const sourceLinks = node('div', 'book-link-group book-bibliographic-sources');
    for (const reference of book.references || []) {
      const url = new URL(reference.url);
      if (url.protocol !== 'https:') continue;
      const link = node('a', 'bibliographic-link', `${reference.label} ↗`);
      link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      sourceLinks.append(link);
    }
    if (sourceLinks.childElementCount) {
      sourceLinks.prepend(node('h4', 'book-links-heading', 'Editore e fonti'));
      links.append(sourceLinks);
    }
    row.append(links);
    return row;
  });
  $('books').replaceChildren(...(rows.length ? rows : [node('p', 'empty', 'Nessuna opera corrisponde ai filtri. Rimuovi un filtro o usa “Azzera filtri”.')]));
}
function normalizeSearch(text) {
  return text.toLocaleLowerCase('it').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}
let libraryExplorer;
function filterBooks(reset = true, focusId = null) {
  if (!libraryExplorer) return;
  const filtered = libraryExplorer.select();
  if (reset) state.bookPage = 0;
  if (focusId) {
    const index = filtered.findIndex(book => 'book-' + book.id === focusId);
    if (index >= 0) state.bookPage = Math.floor(index / state.bookPerPage);
  }
  renderBooks(filtered);
  const themeId = libraryExplorer.criteria().theme;
  for (const entry of libraryExplorer.index) {
    const row = $('book-' + entry.book.id);
    if (!row) continue;
    if (!row.querySelector('.book-work-type')) {
      const kind = LibraryFilters.kinds.find(([id]) => id === entry.kind)?.[1];
      if (kind) row.children[1].insertBefore(node('p', 'book-work-type', kind), row.children[1].querySelector('.book-mentions-count'));
    }
  }
  if (themeId !== 'all') {
    const pattern = LibraryFilters.themes.find(([id]) => id === themeId)?.[2];
    for (const entry of libraryExplorer.index) {
      const row = $('book-' + entry.book.id);
      if (!row || !pattern) continue;
      const context = node('p', 'book-context-themes', 'Nel video:');
      const relevant = entry.topics.filter(topic => pattern.test(LibraryFilters.normalize(topic)));
      context.append(node('span', '', relevant.join(' · ')));
      row.children[1].append(context);
    }
  }
  if (focusId) $(focusId)?.scrollIntoView({block: 'start'});
}
on('search', 'input', filterVideos);
on('filter', 'change', filterVideos);
on('video-year', 'change', filterVideos);
on('book-search', 'input', () => filterBooks());
on('book-filter', 'change', () => filterBooks());
on('book-sort', 'change', () => filterBooks());
for (const [id, delta] of [['book-previous', -1], ['book-next', 1]]) {
  on(id, 'click', () => { state.bookPage += delta; filterBooks(false); $('book-results').scrollIntoView({block: 'start'}); });
}
for (const [id, delta] of [['previous', -1], ['next', 1]]) {
  on(id, 'click', () => { state.page += delta; renderVideos(); $('results').scrollIntoView({block: 'start'}); });
}
on('close-dialog', 'click', () => $('detail').close());
on('detail', 'click', e => { if (e.target === $('detail')) { const r = $('detail').getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) $('detail').close(); } });
on('detail', 'close', () => { $('dialog-content').replaceChildren(); document.body.style.overflow = ''; });
async function loadData(path) {
  const embedded = document.getElementById('embedded-data');
  if (embedded) {
    const data = JSON.parse(embedded.textContent);
    if (!(path in data)) throw new Error(`Dati mancanti: ${path}`);
    return data[path];
  }
  const response = await fetch(rootPath + path, {cache: 'no-cache'});
  if (!response.ok) throw new Error(`Impossibile caricare ${path}`);
  return response.json();
}
function renderHome() {
  $('total-count').textContent = state.videos.length.toLocaleString('it-IT');
  $('hours-count').textContent = Math.round(state.videos.reduce((sum, video) => sum + (video.duration || 0), 0) / 3600).toLocaleString('it-IT');
  $('library-count').textContent = state.books.length.toLocaleString('it-IT');
  const starterIds = ['Qr7vi4Mgd_0', 'rtmt9_Mzdkw', 'WzF2KJ1swVE'];
  const starters = starterIds.map(id => state.videos.find(video => video.id === id)).filter(Boolean);
  $('home-videos')?.replaceChildren(...(starters.length ? starters : state.videos.slice(0, 3)).map(videoCard));
  const featured = (document.body.dataset.featuredBooks || '').split(',').map(id => state.books.find(book => book.id === id)).filter(Boolean);
  $('home-books').replaceChildren(...featured.map(book => {
    const link = node('a', 'home-book');
    link.href = `${siteUrl('biblioteca')}#book-${encodeURIComponent(book.id)}`;
    const visual = node('div', 'home-book-image');
    if (book.cover?.src) {
      const image = node('img'); image.src = book.cover.src; image.alt = coverAlt(book);
      image.loading = 'lazy'; image.width = 100; image.height = 150; visual.append(image);
    }
    const copy = node('div');
    copy.append(node('p', 'eyebrow', 'DALLA BIBLIOTECA'), node('h3', '', book.title), node('p', '', book.author), node('span', 'text-link', 'Scopri il riferimento ↗'));
    link.append(visual, copy); return link;
  }));
}
async function start() {
  PublicNames.observe(document.querySelector('main'));
  PublicNames.observe(document.getElementById('detail'));
  ReadableTimings.normalizeDocument(document.querySelector('main'));
  if (page === 'home') {
    const legacy = {archivio: 'video', biblioteca: 'biblioteca', ricerca: 'video', blog: 'blog', progetto: 'progetto'};
    const fragment = window.location.hash.slice(1);
    const target = Object.prototype.hasOwnProperty.call(legacy, fragment) ? legacy[fragment] : null;
    if (target) { window.location.replace(siteUrl(target)); return; }
  }
  const datasets = {home: ['catalogo.json', 'libri.json', 'schede.json'], video: ['catalogo.json', 'schede.json'], biblioteca: ['libri.json', 'schede.json'],
    progetto: [], eventi: [], scheda: []}[page] || [];
  const loaded = await Promise.allSettled(datasets.map(name => loadData('data/' + name)));
  const data = {};
  loaded.forEach((result, index) => { if (result.status === 'fulfilled') data[datasets[index]] = result.value; });
  state.videos = data['catalogo.json']?.videos || [];
  state.books = data['libri.json'] || [];
  state.cards = data['schede.json'] || [];
  if (page === 'home') renderHome();
  if (page === 'video') {
    if (data['catalogo.json']) {
      $('search').value = new URLSearchParams(window.location.search).get('q') || '';
      populateVideoYears();
      const params = new URLSearchParams(window.location.search);
      const year = params.get('anno');
      if (year && [...$('video-year').options].some(option => option.value === year)) $('video-year').value = year;
      if (params.get('durata') === 'long') $('filter').value = 'long';
      filterVideos();
    } else $('results').textContent = 'Catalogo momentaneamente non disponibile. Ricarica la pagina.';
  }
  if (page === 'biblioteca') {
    if (!data['libri.json'] || !data['schede.json']) throw new Error('Dati della biblioteca non disponibili');
    $('book-count').textContent = `${state.books.length.toLocaleString('it-IT')} OPERE`;
    $('book-search').value = new URLSearchParams(window.location.search).get('q') || '';
    libraryExplorer = LibraryFilters.mount({
      books: state.books, cards: state.cards,
      onChange: () => filterBooks(),
      onSurprise: book => {
        const url = new URL(window.location.href);
        url.hash = 'book-' + book.id;
        try { window.history.replaceState(null, '', url); } catch (_) {}
        filterBooks(true, 'book-' + book.id);
        const row = $('book-' + book.id);
        row?.setAttribute('tabindex', '-1'); row?.focus({preventScroll: true});
        $('book-results').textContent += ` · Opera a sorpresa: ${book.title}`;
      }
    });
    filterBooks(true, window.location.hash.slice(1));
  }
  if (page === 'scheda') {
    document.querySelectorAll('[data-play-video]').forEach(button => {
      const start = VideoStart.fromPage(window.location);
      if (start > 0 && canEmbedYouTube()) {
        button.querySelector('.sheet-play-label').textContent = '▶ Accetta e riproduci da ' + VideoStart.clock(start);
        button.setAttribute('aria-label', 'Accetta e riproduci da ' + VideoStart.clock(start) + ': ' + document.querySelector('h1').textContent);
      }
      if (!canEmbedYouTube()) {
        button.querySelector('.sheet-play-label').textContent = 'Apri su YouTube' + (start ? ' da ' + VideoStart.clock(start) : '') + ' ↗';
        button.setAttribute('aria-label', 'Apri su YouTube' + (start ? ' da ' + VideoStart.clock(start) : '') + ': ' + document.querySelector('h1').textContent);
        const notice = document.getElementById('player-privacy');
        notice.textContent = 'Questa anteprima apre il video sul sito di YouTube, dove si applica l’informativa del servizio. ';
        const link = node('a', '', 'Privacy');
        link.href = siteUrl('privacy');
        notice.append(link);
      }
      button.addEventListener('click', () => playInlineVideo(button));
    });
  }
}
start().catch(() => {
  const message = node('p', 'wrap load-error', 'Impossibile caricare tutti i contenuti. Ricarica la pagina.');
  message.setAttribute('role', 'alert'); $('contenuto').append(message);
});
