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
