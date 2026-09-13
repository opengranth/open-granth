// Compare every matching verse, score and rank with the frozen pre-worker engine.
// Timings are Node engine measurements, not browser or real-phone benchmarks.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';
import { fileURLToPath } from 'node:url';
const repo = fileURLToPath(new URL('../', import.meta.url));
const read = path => readFileSync(repo + path, 'utf8');
const data = JSON.parse(read('site/data/verses.json'));
const baseline = new Function(read('tests/fixtures/search-before-worker.js') + ';return {scoreVerse, expandRomanQuery, englishTokens};')();
const current = new Function('self', 'fetch', read('site/search/search-worker.js') + ';return {prepareVerse,searchPrepared};')({}, () => new Promise(() => {}));
const queries = [
  'Tu dayal', 'Ih ardas', 'satnam', 'sat naam', 'naam sat', 'ik onkar', 'ek oankaar',
  'waheguru', 'vaahiguroo', 'amrit', 'a(n)mrit', 'gobind', 'kirpa', 'guru nanak',
  'shabad', 'sewa', 'prabhu', 'naam', '  Tu DAYAL  ', 'ih aradaas hamaaree',
  'the lord', 'truth', 'loving kindness', 'in maajh and saloks', 'and',
  'ਸਤਿ ਨਾਮੁ', 'ਵਾਹਿਗੁਰੂ', 'ਹੁਕਮਿ', 'ਸਲੋਕੁ', 'ੴ ਸਤਿ', 'ਨਾਮੁ naam',
  'noresultzzzz', '1234', '<script>', '!!!'
];
function oldSearch(query) {
  const q = query.trim(), ql = q.toLowerCase();
  const roman = baseline.expandRomanQuery(ql), english = baseline.englishTokens(ql);
  return data.map(verse => ({verse, score: baseline.scoreVerse(verse, q, ql, roman, english)}))
    .filter(v => v.score > 0).sort((a,b) => b.score-a.score || a.verse.ang-b.verse.ang || (a.verse.verse_index||0)-(b.verse.verse_index||0));
}
const ids = results => results.map(({verse:v,score}) => [v.ang,v.verse_index,v.line,score]);
if (global.gc) global.gc();
const heapBefore = process.memoryUsage().heapUsed;
const prepStart = performance.now();
const prepared = data.map(current.prepareVerse);
const preparationMs = performance.now()-prepStart;
if (global.gc) global.gc();
const cacheHeapMiB = (process.memoryUsage().heapUsed-heapBefore)/1024/1024;
const rows=[];
for (const query of queries) {
  const before=performance.now();
  const expected=oldSearch(query);
  const baselineMs=performance.now()-before;
  const after=performance.now();
  const actual=current.searchPrepared(prepared,query);
  const workerEngineMs=performance.now()-after;
  assert.deepEqual(ids(actual),ids(expected),query);
  rows.push({query,count:actual.length,baselineMs,workerEngineMs});
}
const median = values => values.sort((a,b)=>a-b)[Math.floor(values.length/2)];
console.log(JSON.stringify({runtime:process.version,verses:data.length,queries:queries.length,
  preparationMs,cacheHeapMiB:global.gc?cacheHeapMiB:null,
  medianBaselineMs:median(rows.map(r=>r.baselineMs)),medianWorkerEngineMs:median(rows.map(r=>r.workerEngineMs)),rows},null,2));
