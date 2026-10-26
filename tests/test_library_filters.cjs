const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../sito/dist/app.js'), 'utf8');
const boundary = source.indexOf("\n'use strict';\nconst state =");
assert.ok(boundary > 0, 'Modulo filtri presente nel bundle pubblico');
const sandboxModule = {exports: {}};
new Function('module', 'exports', source.slice(0, boundary))(sandboxModule, sandboxModule.exports);
const F = sandboxModule.exports;

const book = (id, type, author, videos, extra = {}) => ({id, title: id, author, work_type: type,
  status: 'citazione_esplicita', mentions: videos.map(video_id => ({video_id})), ...extra});
const books = [
  book('film-a', 'film', 'Regista A', ['video-1', 'video-1', 'video-2'], {title: 'Città', original_title: 'City'}),
  book('film-b', 'opera cinematografica', 'Regista B', ['video-3'], {status: 'identificazione_probabile'}),
  book('serie', 'episodio di serie televisiva', 'Regista A', ['video-1']),
  book('saggio', 'saggio di storia e sociologia del cinema', 'Autore', ['video-2']),
  book('poesia', 'raccolta_poetica', 'Autore', ['video-3'], {status: 'citazione_probabile'}),
  book('ignoto', undefined, 'Autore', []),
  book('video', 'filmato documentario di esperimento scientifico', 'NASA', ['video-4']),
];
const cards = [
  {video_id: 'video-1', topics: ['Educazione e autonomia'], books: [{book_id: 'film-a', role: 'film discusso'}]},
  {video_id: 'video-2', topics: ['Cinema e memoria storica'], books: []}
];
const index = F.createIndex(books, cards);

test('Film distingue cinema, serie TV, filmati e saggi sul cinema', () => {
  assert.deepEqual(F.select(index, {format: 'film'}).map(b => b.id), ['film-a', 'film-b']);
  assert.equal(F.classify('film di fantascienza').format, 'film');
  assert.equal(F.classify('film_documentario').format, 'film');
  assert.equal(F.classify('miniserie documentaria').format, 'tv');
  assert.equal(F.classify('filmato documentario di esperimento scientifico').format, 'video');
  assert.equal(F.classify('saggio di storia e sociologia del cinema').format, 'text');
});
test('Non ricava il formato da un titolo che contiene film', () => {
  const entry = F.createIndex([book('Film', undefined, 'Autore', [])])[0];
  assert.equal(entry.format, 'unknown');
});
test('Riconosce varianti con spazi e underscore senza cambiare i metadati', () => {
  assert.deepEqual(F.classify('saggio_filosofico'), F.classify('saggio filosofico'));
  assert.equal(F.classify('raccolta_poetica').kind, 'poetry');
  assert.equal(F.classify('testo_teatrale').kind, 'theatre');
  assert.equal(F.classify('sūtra buddhista').kind, 'religious');
});
test('Ricerca per parole, accenti, titolo originale e alias', () => {
  assert.deepEqual(F.select(index, {q: 'CITTA regista a'}).map(b => b.id), ['film-a']);
  assert.equal(F.select(index, {q: 'City'})[0].id, 'film-a');
  const aliases = F.createIndex([book('x', 'romanzo', 'X', [], {search_aliases: ['Altro nome']})]);
  assert.equal(F.select(aliases, {q: 'altro nome'})[0].id, 'x');
});
test('I filtri si intersecano anche con autore, tema e riscontro', () => {
  assert.deepEqual(F.select(index, {format: 'film', author: 'Regista A', theme: 'history', evidence: 'text'}).map(b => b.id), ['film-a']);
  assert.equal(F.select(index, {format: 'film', kind: 'poetry'}).length, 0);
});
test('Più citati e più video contano video distinti', () => {
  assert.equal(index[0].videoIds.length, 2);
  assert.deepEqual(F.select(index, {presence: 'repeated'}).map(b => b.id), ['film-a']);
  assert.equal(F.select(index, {sort: 'mentions'})[0].id, 'film-a');
});
test('I temi provengono dai video collegati e restano distinti dal genere', () => {
  assert.ok(index[0].themes.includes('history'));
  assert.ok(index[0].themes.includes('education'));
  assert.equal(index[0].kind, 'film');
  assert.deepEqual(index.find(e => e.book.id === 'poesia').themes, []);
});
test('Opera centrale richiede un ruolo esplicito della stessa opera', () => {
  assert.deepEqual(F.select(index, {presence: 'main'}).map(b => b.id), ['film-a']);
  assert.equal(index.find(e => e.book.id === 'serie').main, false);
  assert.deepEqual(F.select(index, {presence: 'with-card'}).map(b => b.id).sort(), ['film-a', 'saggio', 'serie']);
});
test('Il filtro probabili comprende entrambi gli stati, esclusi dai riscontri testuali', () => {
  assert.deepEqual(F.select(index, {evidence: 'probable'}).map(b => b.id).sort(), ['film-b', 'poesia']);
  assert.ok(!F.select(index, {evidence: 'text'}).some(b => b.id === 'film-b'));
});
test('Conteggi delle faccette rispettano gli altri filtri', () => {
  const totals = F.counts(index, {format: 'film', author: 'Regista A'}, 'author');
  assert.equal(totals.get('Regista A'), 1);
  assert.equal(totals.get('Regista B'), 1);
  assert.equal(totals.has('Autore'), false);
});
test('La sorpresa rispetta i risultati e gestisce lo stato vuoto', () => {
  const films = F.select(index, {format: 'film'});
  assert.equal(F.randomBook(films, () => 0).id, 'film-a');
  assert.equal(F.randomBook(films, () => .99).id, 'film-b');
  assert.equal(F.randomBook([]), null);
});
test('Indicizzazione e ordinamento non modificano le opere', () => {
  const before = JSON.stringify(books);
  F.createIndex(books, cards); F.select(index, {sort: 'title'});
  assert.equal(JSON.stringify(books), before);
});
test('Catalogo reale: formati esaustivi, film esclusivi e dati preservati', () => {
  const actual = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/libri.json'), 'utf8'));
  const cards = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/schede.json'), 'utf8'));
  const before = JSON.stringify(actual);
  const indexed = F.createIndex(actual, cards);
  const films = F.select(indexed, {format: 'film'});
  assert.ok(films.length > 0);
  assert.ok(films.every(b => /^(film(?:\s|$)|opera cinematografica|cortometraggio)/.test(F.normalize(b.work_type))));
  assert.equal(F.formats.filter(([id]) => id !== 'all').reduce((sum, [id]) => sum + F.select(indexed, {format: id}).length, 0), actual.length);
  assert.equal(new Set(actual.map(b => b.id)).size, actual.length);
  assert.equal(JSON.stringify(actual), before);
  console.log(JSON.stringify({works: actual.length, films: films.length, tv: F.select(indexed, {format: 'tv'}).length}));
});

test('La serie documentaria Gutsy è reperibile tra le serie TV e nessun tipo del repertorio resta sconosciuto', () => {
  const actual = JSON.parse(fs.readFileSync(path.join(__dirname, '../docs/data/libri.json'), 'utf8'));
  const actualIndex = F.createIndex(actual);
  assert.equal(F.select(actualIndex, {format: 'tv'}).filter(b => b.id === 'gutsy-serie-documentaria-2022').length, 1);
  assert.equal(F.select(actualIndex, {format: 'film'}).filter(b => b.id === 'gutsy-serie-documentaria-2022').length, 0);
  assert.deepEqual(actualIndex.filter(e => e.format === 'unknown').map(e => e.book.id), []);
});
