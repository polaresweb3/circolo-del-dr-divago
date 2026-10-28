/* Dati versionati nella cache HTTP; riferimenti completi solo per le opere visibili. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ReadingData = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  function create({root = '', manifestPath = '', fetch: request = globalThis.fetch, embedded = null} = {}) {
    const pending = new Map();
    const failed = new Set();
    function json(path, versioned = true) {
      if (!pending.has(path)) {
        const promise = Promise.resolve().then(() => request(root + path, {cache: failed.has(path) ? 'reload' : versioned ? 'force-cache' : 'no-cache'}))
          .then(response => {
            if (!response.ok) throw new Error('Impossibile caricare ' + path);
            return response.json();
          }).then(value => { failed.delete(path); return value; })
          .catch(error => { pending.delete(path); failed.add(path); throw error; });
        pending.set(path, promise);
      }
      return pending.get(path);
    }
    async function load(path) {
      if (embedded) {
        if (!(path in embedded)) throw new Error('Dati mancanti: ' + path);
        return embedded[path];
      }
      if (!manifestPath) return json(path, false); // Pagine precedenti e anteprime non rigenerate.
      const manifest = await json(manifestPath);
      if (manifest.schema !== 1 || !manifest.datasets[path]) throw new Error('Indice non disponibile: ' + path);
      return json(manifest.datasets[path]);
    }
    async function hydrate(books) {
      return Promise.all(books.map(async book => {
        if (!book._details) return book; // L'anteprima offline incorpora già tutti i riferimenti.
        const group = await json(book._details);
        if (!group[book.id] || group[book.id].id !== book.id) throw new Error('Riferimenti non disponibili');
        return group[book.id];
      }));
    }
    return {load, hydrate};
  }
  return {create};
});
