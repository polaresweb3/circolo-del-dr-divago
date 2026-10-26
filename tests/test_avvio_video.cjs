const {test} = require('node:test');
const assert = require('node:assert/strict');
const {fromPage, seconds, clock} = require('../sito/avvio_video.js');

test('Il passaggio indicato dall’utente rimane a quattro minuti e venti', () => {
  assert.equal(fromPage({search: '?t=260'}), 260);
  assert.equal(fromPage({search: '?t=260s'}), 260);
  assert.equal(clock(fromPage({search: '?t=260'})), '4:20');
});
test('Parametri assenti o non validi riportano all’inizio', () => {
  for (const value of [null, '', '-1', '4:20', '260.5', 'NaN', '999999999999999999999']) {
    assert.equal(seconds(value), 0);
  }
  assert.equal(fromPage({search: ''}), 0);
  assert.equal(fromPage({search: '?q=260'}), 0);
});
