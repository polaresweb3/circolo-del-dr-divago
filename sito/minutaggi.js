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
