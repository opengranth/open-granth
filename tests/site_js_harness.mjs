// Executes the built search worker engine or Verify page JavaScript against
// the released corpus. Search lifecycle/protocol coverage is separately in
// search_worker_lifecycle.mjs; this harness checks matching regressions.
//
// Usage:
//   node tests/site_js_harness.mjs search "Tu dayal"
//   node tests/site_js_harness.mjs verify "ih aradaas hamaaree"
//   node tests/site_js_harness.mjs verify-english "in maajh and saloks"
//   node tests/site_js_harness.mjs verify-gurmukhi "<gurmukhi text>"

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const repo = join(dirname(fileURLToPath(import.meta.url)), '..');

function makeEl(tag) {
  return {
    tagName: String(tag || 'div').toUpperCase(),
    children: [],
    style: {},
    attributes: {},
    className: '',
    textContent: '',
    innerHTML: '',
    value: '',
    href: undefined,
    setAttribute(k, v) { this.attributes[k] = v; if (k === 'href') this.href = v; },
    getAttribute(k) { return k === 'href' ? this.href : this.attributes[k]; },
    appendChild(c) { this.children.push(c); return c; },
    addEventListener() {},
    removeEventListener() {},
    focus() {},
    click() {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
  };
}

const byId = {};
const documentStub = {
  documentElement: makeEl('html'),
  getElementById(id) { return byId[id] || (byId[id] = makeEl('div')); },
  querySelector() { return makeEl('div'); },
  querySelectorAll() { return []; },
  createElement(t) { return makeEl(t); },
  createTextNode(text) { return { tagName: '#text', textContent: text, children: [] }; },
  createDocumentFragment() { return makeEl('#fragment'); },
  addEventListener() {},
  removeEventListener() {},
};
const windowStub = { matchMedia() { return { matches: false, addEventListener() {} }; }, location: { href: '' } };
const historyStub = { replaceState() {} };
const localStorageStub = { getItem() { return null; }, setItem() {} };
const fetchStub = () => new Promise(() => {});
class URLStub { constructor() { this.searchParams = { set() {}, delete() {}, get() { return null; } }; } }

const [mode, query] = process.argv.slice(2);
if (!mode || !query) {
  console.error('usage: node site_js_harness.mjs <search|verify|verify-english|verify-gurmukhi> "<query>"');
  process.exit(2);
}

const pagePath = mode.startsWith('verify') ? 'site/verify/index.html' : 'site/search/index.html';
const html = readFileSync(join(repo, pagePath), 'utf8');
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
// The main page script is the largest block (the others are theme/nav helpers).
const code = mode === 'search' ? readFileSync(join(repo, 'site/search/search-worker.js'), 'utf8') : blocks.reduce((a, b) => (b.length > a.length ? b : a), '');

const verses = JSON.parse(readFileSync(join(repo, 'site', 'data', 'verses.json'), 'utf8'));

// Security note: the Function body below is the repository's own built
// script (the same bytes a browser executes) plus the hardcoded hook literal
// underneath. Nothing user-supplied is interpolated into the code string; the
// CLI query is passed to the extracted functions as plain data arguments.
let hooks;
const hookLine = mode.startsWith('verify')
  ? ';__hooks({ tryTransliteration: tryTransliteration, tryEnglish: tryEnglish, verifyGurmukhi: verifyGurmukhi, cards: function () { return versesDiv.children; }, setVerses: function (v) { verses = v; } });'
  : ';__hooks({ search: function(v, q) { return searchPrepared(v.map(prepareVerse), q); }, setVerses: function() {} });';

new Function(
  'document', 'window', 'history', 'localStorage', 'fetch', 'URL',
  'setTimeout', 'clearTimeout', '__hooks', 'self',
  code + hookLine
)(
  documentStub, windowStub, historyStub, localStorageStub, fetchStub, URLStub,
  () => 0, () => {}, (h) => { hooks = h; }, {}
);

hooks.setVerses(verses);

if (mode === 'search') {
  const scored = hooks.search(verses, query);
  console.log(JSON.stringify({ angs: scored.map((s) => s.verse.ang), count: scored.length }));
} else {
  // Route by mode: verify (Roman), verify-english, verify-gurmukhi.
  if (mode === 'verify-english') hooks.tryEnglish(query);
  else if (mode === 'verify-gurmukhi') hooks.verifyGurmukhi(query);
  else hooks.tryTransliteration(query);
  const cards = hooks.cards()
    .filter((c) => c.className && String(c.className).indexOf('result-verse') !== -1)
    .map((c) => ({
      tag: c.tagName,
      href: c.href,
      text: (function collect(el) {
        let t = el.textContent || '';
        for (const child of el.children || []) t += ' ' + collect(child);
        return t;
      })(c),
    }));
  console.log(JSON.stringify({ cards }));
}
