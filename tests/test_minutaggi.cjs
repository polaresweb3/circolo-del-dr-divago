const {test}=require('node:test');
const assert=require('node:assert/strict');
const T=require('../sito/minutaggi.js');
test('Punti del video comprensibili anche dopo un’ora',()=>{
 assert.equal(T.format('Film nominato da 2873 s nella critica.'),'Film nominato da 47 minuti e 53 secondi nella critica.');
 assert.equal(T.format('A 7633 secondi.'),'A 2 ore, 7 minuti e 13 secondi.');
 assert.equal(T.format('A 3600 s.'),'A 1 ora.');
});
test('Intervalli e tempi frazionari leggibili al secondo senza modificare i dati',()=>{
 assert.equal(T.format('Segmenti 713–729, 2873,90–2922,94 s.'),'Segmenti 713–729, 47 minuti e 53 secondi–48 minuti e 42 secondi.');
 assert.equal(T.format('Fra 309.49 e 313.63 secondi.'),'Fra 5 minuti e 9 secondi e 5 minuti e 13 secondi.');
 assert.equal(T.format('A 202.019–207.879 secondi.'),'A 3 minuti e 22 secondi–3 minuti e 27 secondi.');
});
test('Titoli, ID, URL, ISBN, segmenti e orari esistenti non cambiano',()=>{
 for (const text of ['1980s','49s-VJkUYxk','2873 saggio','ISBN 9788816412873','Segmenti 713–729','https://www.youtube.com/watch?v=49s-VJkUYxk&t=2873','A 47:53 e 1:02:03.']) assert.equal(T.format(text),text);
});
test('La conversione è idempotente e lascia i numeri dei link invariati',()=>{
 const source={seconds:2873,url:'https://www.youtube.com/watch?v=5rie3TZMlxw&t=2873',note:'Da 2873 s.'};
 const snapshot=JSON.stringify(source),text=T.format(source.note);
 assert.equal(T.format(text),text);assert.equal(JSON.stringify(source),snapshot);assert.equal(T.format(2873),2873);
 assert.equal(T.format('A 0 s, poi 1 s.'),'A 0 secondi, poi 1 secondo.');
});
