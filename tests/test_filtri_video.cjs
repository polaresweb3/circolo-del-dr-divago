const {test}=require('node:test'),assert=require('node:assert/strict'),F=require('../sito/filtri-video.js');
const videos=[{id:'a',title:'Libertà',upload_date:'2026-01-01',duration:1201},{id:'b',title:'Scuola',upload_date:'2025-12-31',duration:1200},{id:'c',title:'Filosofia',upload_date:'2026-06-01',duration:1800},{id:'d',title:'Senza data',duration:1900}];
test('Gli anni reali sono distinti, decrescenti e indipendenti dall’ordine dei video',()=>assert.deepEqual(F.years([...videos].reverse()),[2026,2025]));
test('Accetta date ISO e YouTube, esclude date assenti o non valide',()=>{
 assert.equal(F.yearOf({upload_date:'20240229'}),2024);assert.equal(F.yearOf({upload_date:'2025-02-29'}),null);assert.equal(F.yearOf({upload_date:'20261301'}),null);assert.equal(F.yearOf({timestamp:1790000000}),null);
});
test('Anno, durata e ricerca si intersecano senza escludere le altre scelte',()=>{
 assert.deepEqual(videos.filter(v=>F.matches(v,{year:'2026',long:true})).map(v=>v.id),['a','c']);
 assert.deepEqual(videos.filter(v=>F.matches(v,{year:'2026',long:true,query:'liberta'})).map(v=>v.id),['a']);
 assert.equal(F.matches(videos[2],{year:'2026',query:'Musil'},'Romanzo di Robert Musil'),true);
});
test('Oltre venti minuti esclude esattamente venti minuti e durate ignote',()=>{
 assert.equal(F.matches(videos[1],{long:true}),false);assert.equal(F.matches({...videos[1],duration:null},{long:true}),false);assert.equal(F.matches(videos[1]),true);
});
test('Una data mancante non diventa un anno inventato e resta ricercabile',()=>{
 assert.deepEqual(videos.filter(v=>F.matches(v,{year:'unknown',long:true})).map(v=>v.id),['d']);
 const original=JSON.stringify(videos);F.years(videos);videos.forEach(v=>F.matches(v,{year:'2026'}));assert.equal(JSON.stringify(videos),original);
});
