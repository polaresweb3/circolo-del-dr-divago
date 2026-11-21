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
  function fromUrl(url) {
    const params = url.searchParams;
    const pageNumber = Number(params.get('pagina'));
    return {
      query: params.get('q') || '',
      year: params.get('anno') || 'all',
      long: params.get('durata') === 'long',
      page: Number.isSafeInteger(pageNumber) && pageNumber > 0 ? pageNumber - 1 : 0
    };
  }
  function updateUrl(url, {query, year, long, page}) {
    const values = {q: query, anno: year === 'all' ? '' : year, durata: long ? 'long' : '', pagina: page > 0 ? String(page + 1) : ''};
    for (const [key, value] of Object.entries(values)) {
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    }
    return url;
  }
  return {yearOf, years, matches, fromUrl, updateUrl};
});
