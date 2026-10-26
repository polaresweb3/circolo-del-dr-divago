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
