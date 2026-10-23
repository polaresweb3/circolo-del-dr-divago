'use strict';
const state = { videos: [], cards: [], filtered: [], page: 0, perPage: 9, books: [], bookPage: 0, bookPerPage: 8 };
const $ = id => document.getElementById(id);
const page = document.body.dataset.page || 'home';
const offline = document.body.dataset.preview === 'true';
const rootPath = document.body.dataset.root || '';
function siteUrl(name) {
  const routes = {home: 'index.html', video: 'video.html', biblioteca: 'biblioteca.html', eventi: 'eventi.html', progetto: 'progetto.html'};
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
  if (text !== undefined) item.textContent = text;
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
function youtubeEmbedUrl(id, page = window.location) {
  youtube(id);
  if (!canEmbedYouTube(page)) throw new Error('Il player richiede un’origine web valida.');
  const url = new URL(`https://www.youtube-nocookie.com/embed/${id}`);
  url.searchParams.set('autoplay', '1');
  url.searchParams.set('playsinline', '1');
  url.searchParams.set('origin', page.origin);
  return url.href;
}
function playInlineVideo(button) {
  const id = button.dataset.playVideo;
  if (!canEmbedYouTube()) {
    window.open(youtube(id), '_blank', 'noopener,noreferrer');
    return;
  }
  const frame = node('iframe', 'video-frame');
  frame.title = document.querySelector('h1').textContent;
  frame.allow = 'accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture';
  frame.referrerPolicy = 'strict-origin-when-cross-origin';
  frame.allowFullscreen = true;
  frame.src = youtubeEmbedUrl(id);
  button.replaceWith(frame);
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
function filterVideos() {
  const normalize = s => s.toLocaleLowerCase('it').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const query = normalize($('search').value.trim());
  const selected = $('filter').value;
  state.perPage = selected === 'sheets' ? 12 : 9;
  const details = new Map(state.cards.map(card => [card.video_id, [card.title, ...card.topics, ...card.books.map(book => `${book.title} ${book.author}`)].join(' ')]));
  state.filtered = state.videos.filter(video => normalize(`${video.title} ${details.get(video.id) || ''}`).includes(query) &&
    (selected !== 'long' || video.duration > 1200) &&
    (selected !== 'saved' || video.audio_saved) &&
    (selected !== 'sheets' || state.cards.some(card => card.video_id === video.id)));
  state.page = 0;
  renderVideos();
}
function showBookCover(book) {
  const heading = node('h2', 'dialog-title', book.title);
  heading.id = 'dialog-title';
  const image = node('img', 'book-cover-large');
  image.src = book.cover.src;
  image.alt = `Copertina di ${book.cover.display_title || book.title}, ${book.author}`;
  const caption = node('p', 'dialog-description', `${book.author} · ${book.cover.edition_label}`);
  const link = node('a', 'text-link', 'Fonte della copertina ↗');
  link.href = book.cover.source_page;
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  const editionNote = book.cover.edition_note ? [node('p', 'dialog-description', book.cover.edition_note)] : [];
  showDialog([heading, image, caption, ...editionNote, link]);
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
      button.setAttribute('aria-label', `Ingrandisci la copertina di ${book.title}, ${book.author}`);
      const image = node('img');
      image.src = book.cover.src;
      image.alt = `Copertina di ${book.cover.display_title || book.title}, ${book.author}`;
      image.loading = 'lazy'; image.width = 84; image.height = 126;
      image.addEventListener('error', () => {
        button.replaceWith(node('span', 'cover-missing', 'Copertina non disponibile'));
      }, {once: true});
      button.append(image);
      button.addEventListener('click', () => showBookCover(book));
      cover.append(button, node('figcaption', '', book.cover.edition_label));
    } else {
      const workLabel = {saggio: 'Saggio', poesia: 'Poesia'}[book.work_type];
      cover.append(node('span', 'cover-missing', workLabel || 'Copertina non disponibile'));
    }
    const text = node('div');
    const title = node('h3', '', book.title);
    const labels = {verificato: 'VERIFICATO', citazione_esplicita: 'TITOLO NEL TESTO AUTOMATICO', riscontro_audio_automatico: 'RISCONTRO VOCALE AUTOMATICO', titolo_nella_trascrizione: 'TITOLO NELLA TRASCRIZIONE', titolo_nel_video: 'NEL TITOLO DEL VIDEO', identificazione_probabile: 'IDENTIFICAZIONE PROBABILE', da_riascoltare: 'DA RIASCOLTARE'};
    title.append(node('span', 'book-state', labels[book.status] || 'DA VERIFICARE'));
    text.append(title);
    if (book.subtitle) text.append(node('p', 'book-subtitle', book.subtitle));
    text.append(node('p', 'book-author', book.author), node('p', 'book-source', book.source));
    if (book.work_type === 'saggio') text.append(node('p', 'book-work-type', 'Saggio · testo distinto dalle raccolte'));
    if (book.work_type === 'poesia') text.append(node('p', 'book-work-type', 'Poesia · testo distinto dalle raccolte'));
    const videoCount = new Set(book.mentions.map(mention => mention.video_id)).size;
    text.append(node('p', 'book-mentions-count', videoCount === 1 ? '1 video collegato' : `${videoCount} video collegati`));
    row.append(cover, text);
    const links = node('div', 'book-links');
    for (const mention of book.mentions) {
      const reference = node('div', 'book-mention');
      const moment = mention.title_seconds ?? mention.seconds;
      const qualifier = mention.verification === 'identificazione_probabile' ? ' · probabile' : '';
      const link = sourceLink(mention.video_id, Number.isFinite(moment) ? `Passaggio ${duration(moment)}${qualifier} ↗` : 'Vedi il video di origine ↗', moment);
      if (mention.note) link.title = mention.note;
      const context = node('a', 'text-link book-video-title', mention.video_title || 'Video e scheda →');
      context.href = videoPageUrl({id: mention.video_id});
      reference.append(context, link);
      links.append(reference);
    }
    for (const reference of book.references || []) {
      const url = new URL(reference.url);
      if (url.protocol !== 'https:') continue;
      const link = node('a', 'text-link bibliographic-link', `${reference.label} ↗`);
      link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
      links.append(link);
    }
    row.append(links);
    return row;
  });
  $('books').replaceChildren(...(rows.length ? rows : [node('p', 'empty', 'Nessuna opera corrisponde alla ricerca. Prova un altro titolo, autore o tipo di riscontro.')]));
}
function normalizeSearch(text) {
  return text.toLocaleLowerCase('it').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}
function filterBooks(reset = true, focusId = null) {
  const query = normalizeSearch($('book-search').value.trim());
  const selected = $('book-filter').value;
  const filtered = state.books.filter(book => normalizeSearch(`${book.title} ${book.subtitle || ''} ${book.author}`).includes(query)
    && (selected !== 'text' || book.status !== 'titolo_nel_video')
    && (selected !== 'title' || book.status === 'titolo_nel_video')
    && (selected !== 'probable' || book.status === 'identificazione_probabile'));
  const sort = $('book-sort').value;
  filtered.sort((a, b) => (sort === 'title' ? a.title : `${a.author} ${a.title}`).localeCompare(sort === 'title' ? b.title : `${b.author} ${b.title}`, 'it'));
  if (reset) state.bookPage = 0;
  if (focusId) {
    const index = filtered.findIndex(book => 'book-' + book.id === focusId);
    if (index >= 0) state.bookPage = Math.floor(index / state.bookPerPage);
  }
  renderBooks(filtered);
  if (focusId) $(focusId)?.scrollIntoView({block: 'start'});
}
on('search', 'input', filterVideos);
on('filter', 'change', filterVideos);
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
  const response = await fetch(rootPath + path);
  if (!response.ok) throw new Error(`Impossibile caricare ${path}`);
  return response.json();
}
function renderHome() {
  $('total-count').textContent = state.videos.length.toLocaleString('it-IT');
  $('hours-count').textContent = Math.round(state.videos.reduce((sum, video) => sum + (video.duration || 0), 0) / 3600).toLocaleString('it-IT');
  $('curated-count').textContent = state.cards.length;
  const starterIds = ['Qr7vi4Mgd_0', 'rtmt9_Mzdkw', 'WzF2KJ1swVE'];
  const starters = starterIds.map(id => state.videos.find(video => video.id === id)).filter(Boolean);
  $('home-videos').replaceChildren(...(starters.length ? starters : state.videos.slice(0, 3)).map(videoCard));
  const featured = (document.body.dataset.featuredBooks || '').split(',').map(id => state.books.find(book => book.id === id)).filter(Boolean);
  $('home-books').replaceChildren(...featured.map(book => {
    const link = node('a', 'home-book');
    link.href = `${siteUrl('biblioteca')}#book-${encodeURIComponent(book.id)}`;
    const visual = node('div', 'home-book-image');
    if (book.cover?.src) {
      const image = node('img'); image.src = book.cover.src; image.alt = `Copertina di ${book.title}`;
      image.loading = 'lazy'; image.width = 100; image.height = 150; visual.append(image);
    }
    const copy = node('div');
    copy.append(node('p', 'eyebrow', 'DALLA BIBLIOTECA'), node('h3', '', book.title), node('p', '', book.author), node('span', 'text-link', 'Scopri il riferimento ↗'));
    link.append(visual, copy); return link;
  }));
}
async function start() {
  if (page === 'home') {
    const legacy = {archivio: 'video', biblioteca: 'biblioteca', ricerca: 'video', blog: 'progetto', progetto: 'progetto'};
    const fragment = window.location.hash.slice(1);
    const target = Object.prototype.hasOwnProperty.call(legacy, fragment) ? legacy[fragment] : null;
    if (target) { window.location.replace(siteUrl(target)); return; }
  }
  const datasets = {home: ['catalogo.json', 'libri.json', 'schede.json'], video: ['catalogo.json', 'schede.json'], biblioteca: ['libri.json'],
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
      if (new URLSearchParams(window.location.search).get('schede') === '1') $('filter').value = 'sheets';
      filterVideos();
    } else $('results').textContent = 'Catalogo momentaneamente non disponibile. Ricarica la pagina.';
  }
  if (page === 'biblioteca') {
    $('book-count').textContent = `${state.books.length} OPERE`;
    $('book-search').value = new URLSearchParams(window.location.search).get('q') || '';
    filterBooks(true, window.location.hash.slice(1));
  }
  if (page === 'scheda') {
    document.querySelectorAll('[data-play-video]').forEach(button => {
      button.addEventListener('click', () => playInlineVideo(button));
    });
  }
}
start().catch(() => {
  const message = node('p', 'wrap load-error', 'Impossibile caricare tutti i contenuti. Ricarica la pagina.');
  message.setAttribute('role', 'alert'); $('contenuto').append(message);
});
