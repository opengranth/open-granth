// Exercise shipped page orchestration with a controlled worker and clock, then
// execute the shipped worker in a real Node thread with a local fetch adapter.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { Worker } from 'node:worker_threads';
const repo = fileURLToPath(new URL('../', import.meta.url));
const html = readFileSync(repo+'site/search/index.html','utf8');
const page = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]).sort((a,b)=>b.length-a.length)[0];
function setup({url='https://example.test/search/',fail=false}={}) {
  const els={}, timers=new Map(), sent=[]; let timerId=0, worker;
  const element=()=>({children:[],value:'',textContent:'',style:{},disabled:true,
    handlers:{},addEventListener(k,f){this.handlers[k]=f;},appendChild(c){this.children.push(c);},focus(){},
    classList:{toggle(){},remove(){},add(){}},setAttribute(){}});
  const document={addEventListener(){},getElementById:id=>els[id]||(els[id]=element()),createElement:element,createDocumentFragment:element};
  class FakeWorker {
    constructor(path){if(fail)throw new Error('blocked');assert.match(path,/^\.\/search-worker.js\?v=[a-f0-9]{12}$/);worker=this;}
    postMessage(message){sent.push(message);}
    terminate(){this.terminated=true;}
  }
  new Function('document','window','history','URL','Worker','setTimeout','clearTimeout',page)(
    document,{location:url,matchMedia(){return {addEventListener(){}}}},{replaceState(){}},URL,FakeWorker,
    f=>{timers.set(++timerId,f);return timerId;},id=>timers.delete(id));
  return {els,sent,worker,
    message:data=>worker.onmessage({data}),
    type(value){els['search-input'].value=value;els['search-input'].handlers.input();},
    enter(){els['search-input'].handlers.keydown({key:'Enter'});},
    tick(){const jobs=[...timers.values()];timers.clear();jobs.forEach(f=>f());}};
}
const s=setup();
assert.equal(s.els['search-input'].disabled,true);
s.message({type:'ready',count:60555});
assert.equal(s.els['search-input'].disabled,false);
s.type('naam');s.tick();assert.equal(s.sent.length,1);
const first=s.sent[0];
s.type('satnam');
s.message({type:'results',id:first.id,count:0,matches:[]});
assert.equal(s.els['search-status'].textContent,''); // stale even before debounce
s.tick();assert.equal(s.sent.length,2);
s.type('Tu dayal');s.tick();s.type('Ih ardas');s.tick();
assert.equal(s.sent.length,2); // only one active search
s.message({type:'results',id:s.sent[1].id,count:0,matches:[]});
assert.equal(s.sent.length,3);assert.equal(s.sent[2].query,'Ih ardas');
s.type('');s.tick();
s.message({type:'results',id:s.sent[2].id,count:12,matches:[]});
assert.equal(s.els['search-status'].textContent,'');
s.type('x');s.enter();assert.equal(s.els['search-status'].textContent,'Type at least 2 characters');
s.type('fuck');s.tick();assert.match(s.els['search-status'].textContent,/not suitable/);
assert.equal(s.sent.length,3);
s.type('noresultzzzz');s.enter();s.tick();assert.equal(s.sent.length,4);
s.message({type:'results',id:s.sent[3].id,count:0,matches:[]});
assert.equal(s.els['search-status'].textContent,'0 results');
s.type('naam');s.tick();s.message({type:'search-error',id:s.sent[4].id});
assert.match(s.els['search-status'].textContent,/could not complete/);
s.worker.onerror();assert.equal(s.worker.terminated,true);assert.equal(s.els['search-input'].disabled,true);
assert.match(setup({fail:true}).els['search-status'].textContent,/Reload/);
const load=setup();load.message({type:'load-error'});assert.equal(load.worker.terminated,true);
const deep=setup({url:'https://example.test/search/?q=Ih%20ardas'});
deep.message({type:'ready',count:60555});assert.equal(deep.sent[0].query,'Ih ardas');

// Bound raw input, including URL-loaded and whitespace-padded queries. Never
// silently truncate an oversized query into a different, executable search.
const limited=setup();limited.message({type:'ready',count:60555});
limited.type('Ih ardas'.padEnd(500));limited.enter();
assert.equal(limited.sent.length,1);assert.equal(limited.sent[0].query,'Ih ardas');
for (const oversized of ['a'.repeat(501), 'ਨ'.repeat(501), 'Ih ardas'.padEnd(501)]) {
  limited.type(oversized);limited.tick();
  assert.match(limited.els['search-status'].textContent,/500 characters or fewer/);
  assert.equal(limited.sent.length,1);
}
limited.message({type:'results',id:limited.sent[0].id,count:1,matches:[]});
assert.match(limited.els['search-status'].textContent,/500 characters or fewer/);
limited.type('Ih ardas');limited.enter();assert.equal(limited.sent.length,2);
const oversizedLink=setup({url:'https://example.test/search/?q='+'a'.repeat(501)});
oversizedLink.message({type:'ready',count:60555});
assert.equal(oversizedLink.sent.length,0);
assert.match(oversizedLink.els['search-status'].textContent,/500 characters or fewer/);

const workerCode=readFileSync(repo+'site/search/search-worker.js','utf8');
async function runWorker(fetchBody,check) {
  const adapter=`const {parentPort}=require('node:worker_threads');
    globalThis.self={postMessage:data=>parentPort.postMessage(data)};
    parentPort.on('message',data=>self.onmessage({data}));
    globalThis.fetch=async url=>{if(url!=='../data/verses.json')throw Error('Unexpected URL');${fetchBody}};`;
  const worker=new Worker(adapter+workerCode,{eval:true});
  const next=()=>new Promise((resolve,reject)=>{
    const cleanup=()=>{clearTimeout(timeout);worker.off('error',onError);worker.off('message',onMessage);};
    const onError=error=>{cleanup();reject(error);};
    const onMessage=value=>{cleanup();resolve(value);};
    const timeout=setTimeout(()=>onError(Error('worker timeout')),15000);
    worker.once('error',onError);worker.once('message',onMessage);
  });
  try {await check(worker,next);} finally {await worker.terminate();}
}
await runWorker(`return {ok:true,json:async()=>JSON.parse(require('node:fs').readFileSync(${JSON.stringify(repo+'site/data/verses.json')},'utf8'))};`,async(worker,next)=>{
  assert.deepEqual(await next(),{type:'ready',count:60555});
  let response=next();worker.postMessage({type:'search',id:9,query:'Ih ardas'});
  const found=await response;assert.equal(found.id,9);assert.equal(found.count,1);
  assert.equal(found.matches[0].ang,747);assert.equal(found.matches[0].verse_index,12);
  assert.equal(found.matches[0].romanSet,undefined);
  response=next();worker.postMessage({type:'search',id:10,query:'naam'});
  const many=await response;assert.equal(many.matches.length,50);assert.ok(many.count>50);
  // Invalid envelopes are ignored; a subsequent valid request must still work.
  response=next();
  for (const malformed of [null, undefined, 'search', 42, [], {},
    {type:'unknown',id:1,query:'naam'}, {type:'search',query:'naam'},
    ...[null,'1',0,-1,1.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1].map(id=>({type:'search',id,query:'naam'}))]) {
    worker.postMessage(malformed);
  }
  worker.postMessage({type:'search',id:11,query:'Ih ardas'.padEnd(500)});
  const boundary=await response;assert.equal(boundary.type,'results');
  assert.equal(boundary.id,11);assert.equal(boundary.count,1);
  for (const query of [undefined,null,7,{},[], '', ' ', 'x',
    'a'.repeat(501),'ਨ'.repeat(501),'Ih ardas'.padEnd(501)]) {
    response=next();worker.postMessage({type:'search',id:12,query});
    assert.deepEqual(await response,{type:'search-error',id:12});
  }
  response=next();worker.postMessage({type:'search',id:13,query:'Ih ardas'});
  const recovered=await response;assert.equal(recovered.type,'results');assert.equal(recovered.count,1);
});
for(const fetchBody of ['return {ok:false};','throw Error("offline");','return {ok:true,json:async()=>[]};','return {ok:true,json:async()=>{throw Error("invalid JSON")}};']) {
  await runWorker(fetchBody,async(worker,next)=>assert.deepEqual(await next(),{type:'load-error'}));
}
console.log('PASS: page queue, stale responses, input limits, malformed messages, recovery, Enter, deep links, errors, worker initialization and result protocol');
