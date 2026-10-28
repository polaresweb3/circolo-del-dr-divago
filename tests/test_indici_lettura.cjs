const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ReadingData = require('../sito/indici_lettura.js');
const source = fs.readFileSync(path.join(__dirname, '../sito/dist/app.js'), 'utf8');
const boundary = source.indexOf("\n'use strict';\nconst state =");
const mod = {exports: {}};
new Function('module', 'exports', source.slice(0, boundary))(mod, mod.exports);
const Filters = mod.exports;

test('Richieste concorrenti e riferimenti dello stesso gruppo usano un solo caricamento', async () => {
  const calls = [];
  const values = {
    'manifest.hash.json': {schema: 1, datasets: {'data/libri.json': 'books.hash.json', 'data/schede.json': 'cards.hash.json'}},
    'books.hash.json': [{id: 'a', _details: 'details.hash.json'}, {id: 'b', _details: 'details.hash.json'}],
    'cards.hash.json': [], 'details.hash.json': {a: {id: 'a', source: 'Fonte'}, b: {id: 'b', status: 'identificazione_probabile'}}
  };
  const reader = ReadingData.create({root: '../', manifestPath: 'manifest.hash.json', fetch: async (url, options) => {
    calls.push([url, options.cache]); return {ok: true, json: async () => values[url.slice(3)]};
  }});
  const [books] = await Promise.all([reader.load('data/libri.json'), reader.load('data/schede.json')]);
  assert.deepEqual(calls.map(c => c[0]).sort(), ['../books.hash.json', '../cards.hash.json', '../manifest.hash.json']);
  assert.ok(calls.every(c => c[1] === 'force-cache'));
  const full = await reader.hydrate(books);
  assert.equal(full[1].status, 'identificazione_probabile');
  await reader.hydrate(books); await reader.load('data/libri.json');
  assert.equal(calls.length, 4);
  assert.equal(books[0].source, undefined, 'Il caricamento non altera i dati usati dai filtri');
});

test('Un caricamento fallito è riprovabile e non resta bloccato nella cache in memoria', async () => {
  let attempts = 0;
  const modes = [];
  const reader = ReadingData.create({manifestPath: 'manifest.hash.json', fetch: async (url, options) => {
    if (url.startsWith('manifest')) return {ok: true, json: async () => ({schema: 1, datasets: {'data/libri.json': 'books.hash.json'}})};
    modes.push(options.cache);
    if (++attempts === 1) return {ok: false};
    return {ok: true, json: async () => []};
  }});
  await assert.rejects(reader.load('data/libri.json'));
  assert.deepEqual(await reader.load('data/libri.json'), []);
  assert.equal(attempts, 2);
  assert.deepEqual(modes, ['force-cache', 'reload']);
});

test('Le anteprime offline funzionano senza rete e le vecchie pagine possono ancora caricare i dati', async () => {
  const book = {id: 'a', mentions: [], source: 'Fonte integrale'};
  const reader = ReadingData.create({embedded: {'data/libri.json': [book]}, fetch: () => {throw new Error('Richiesta inattesa');}});
  assert.deepEqual(await reader.hydrate(await reader.load('data/libri.json')), [book]);
  await assert.rejects(reader.load('data/schede.json'));
  let cache;
  const legacy = ReadingData.create({fetch: async (url, options) => {cache = options.cache; return {ok: true, json: async () => [book]};}});
  assert.deepEqual(await legacy.load('data/libri.json'), [book]);
  assert.equal(cache, 'no-cache');
});

test('L’indice reale mantiene risultati, ordinamento e conteggi dei filtri', () => {
  const data = path.join(__dirname, '../sito/dist/data');
  const books = JSON.parse(fs.readFileSync(path.join(data, 'libri.json')));
  const cards = JSON.parse(fs.readFileSync(path.join(data, 'schede.json')));
  const page = fs.readFileSync(path.join(__dirname, '../sito/dist/biblioteca.html'), 'utf8');
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../sito/dist', page.match(/data-index-manifest="([^"]+)"/)[1])));
  const small = name => JSON.parse(fs.readFileSync(path.join(__dirname, '../sito/dist', manifest.datasets['data/' + name])));
  const before = Filters.createIndex(books, cards), after = Filters.createIndex(small('libri.json'), small('schede.json'));
  const criteria = [{}, ...Filters.formats.map(([format]) => ({format})), ...Filters.kinds.map(([kind]) => ({kind})),
    ...Filters.themes.map(([theme]) => ({theme})), ...['main','repeated','with-card'].map(presence => ({presence})),
    ...['text','probable','title'].map(evidence => ({evidence})), ...['author','title','mentions'].map(sort => ({sort})),
    {q: 'sofisti'}, {q: 'orwell'}, {q: 'città'}, {format: 'film', theme: 'politics'}];
  for (const query of criteria) {
    assert.deepEqual(Filters.select(after, query).map(b => b.id), Filters.select(before, query).map(b => b.id), JSON.stringify(query));
    for (const field of ['format', 'kind', 'theme', 'author']) assert.deepEqual(Filters.counts(after, query, field), Filters.counts(before, query, field));
  }
  const videoText = card => [card.title, ...card.topics, ...card.books.map(b => `${b.title} ${b.author}`)].join(' ');
  assert.deepEqual(small('schede.json').map(videoText), cards.map(videoText));
});
