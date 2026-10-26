const {test} = require('node:test');
const assert = require('node:assert/strict');
const {format} = require('../sito/nomi_pubblici.js');

test('La firma pubblica riconosce nome, cognome e nome usato da solo', () => {
  assert.equal(format('Sergio Caldarella, Caldarella e Sergio discutono.'), 'Dr Divago, Dr Divago e Dr Divago discutono.');
  assert.equal(format('Dr. Divago'), 'Dr Divago');
});
test('Le altre persone chiamate Sergio mantengono il proprio nome', () => {
  for (const name of ['Sergio Mattarella', 'Sergio Harari', 'Sergio Landucci', 'Sergio Campailla', 'Sergio Claudio Perroni']) {
    assert.equal(format(name), name);
  }
});
