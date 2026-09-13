// Frozen search engine from 841d0e62, before issue #5. Do not update with the new engine.
    var STOP_WORDS = {
        a: true, an: true, and: true, are: true, as: true, at: true, be: true,
        but: true, by: true, for: true, from: true, has: true, have: true,
        he: true, her: true, hers: true, him: true, his: true, i: true,
        in: true, is: true, it: true, its: true, me: true, my: true,
        of: true, on: true, or: true, our: true, ours: true, she: true,
        so: true, that: true, the: true, their: true, theirs: true,
        them: true, they: true, this: true, to: true, us: true,
        was: true, we: true, were: true, with: true, you: true,
        your: true, yours: true
    };
    function stem(word) {
        if (word.length <= 3) return word;
        if (/ies$/.test(word) && word.length > 4) return word.slice(0, -3) + 'y';
        var suffixes = ['ering', 'ness', 'ment', 'tion', 'sion', 'ious', 'eous',
            'ting', 'ing', 'ful', 'ous', 'ble', 'ers', 'est', 'ier', 'ely',
            'ens', 'ern', 'er', 'ed', 'ly', 'en', 'es', 'al', 'ty'];
        for (var i = 0; i < suffixes.length; i++) {
            var suffix = suffixes[i];
            if (word.endsWith(suffix) && word.length - suffix.length >= 3) {
                return word.slice(0, -suffix.length);
            }
        }
        if (word.endsWith('s') && !word.endsWith('ss') && word.length > 4) {
            return word.slice(0, -1);
        }
        return word;
    }

    /* English-layer tokens: stop-word filtered and stemmed. The stemmer is
       English-only and must never touch Roman queries or Roman corpus text. */
    function englishTokens(text) {
        var raw = (text || '').toLowerCase().match(/[a-z]+/g) || [];
        var words = [];
        for (var i = 0; i < raw.length; i++) {
            if (!STOP_WORDS[raw[i]]) words.push(stem(raw[i]));
        }
        return words;
    }

    /* Roman-layer tokens: the scheme writes nasals as (n), e.g. a(n)mrit.
       Replace (n) with n (never delete it) before tokenizing, or words like
       anmrit and gobind are unfindable. No stemming, no stop words. */
    function romanTokens(text) {
        return ((text || '').toLowerCase().replace(/\(n\)/g, 'n').match(/[a-z]+/g)) || [];
    }

    function inOrderBonus(queryWords, verseWords) {
        if (queryWords.length < 2) return 0;
        var pos = -1;
        var matched = 0;
        for (var i = 0; i < queryWords.length; i++) {
            var found = -1;
            for (var j = pos + 1; j < verseWords.length; j++) {
                if (verseWords[j] === queryWords[i]) {
                    found = j;
                    break;
                }
            }
            if (found === -1) continue;
            pos = found;
            matched++;
        }
        if (matched === queryWords.length) return 3;
        if (matched >= 2) return 1;
        return 0;
    }

    /* In-order bonus for Roman positions, where each position is a list of
       OR-alternatives from the normalization table. */
    function inOrderBonusAlts(positions, verseTokens) {
        if (positions.length < 2) return 0;
        var pos = -1;
        var matched = 0;
        for (var i = 0; i < positions.length; i++) {
            var found = -1;
            for (var j = pos + 1; j < verseTokens.length && found === -1; j++) {
                for (var a = 0; a < positions[i].length; a++) {
                    var alt = positions[i][a];
                    var fits = true;
                    for (var k = 0; k < alt.length; k++) {
                        if (verseTokens[j + k] !== alt[k]) { fits = false; break; }
                    }
                    if (fits) { found = j; break; }
                }
            }
            if (found === -1) continue;
            pos = found;
            matched++;
        }
        if (matched === positions.length) return 3;
        if (matched >= 2) return 1;
        return 0;
    }

    /* Two independent layer matches. Roman positions are OR-alternative lists
       (from the normalization table); positions are AND. English tokens are
       stemmed and must all match the stemmed English layer. A verse scores if
       either layer completes on its own; layers are never blended, so English
       stems can no longer collide with Roman words (the "Tu dayal" defect). */
    function scoreVerse(v, q, ql, romanPositions, engTokens) {
        var english = (v.english || '').toLowerCase();
        var translit = (v.transliteration || '').toLowerCase();
        if (english.indexOf(ql) !== -1 || translit.indexOf(ql) !== -1 || (v.gurmukhi || '').indexOf(q) !== -1) {
            return 1000;
        }

        var score = 0;

        if (romanPositions.length > 0) {
            var rlist = romanTokens(v.transliteration || '');
            var rset = {};
            for (var i = 0; i < rlist.length; i++) rset[rlist[i]] = true;
            var allRoman = true;
            for (var p = 0; p < romanPositions.length; p++) {
                var alts = romanPositions[p];
                var hit = false;
                for (var a = 0; a < alts.length; a++) {
                    var alt = alts[a];
                    if (alt.length === 1 ? rset[alt[0]] : seqInTokens(alt, rlist)) { hit = true; break; }
                }
                if (!hit) { allRoman = false; break; }
            }
            if (allRoman) {
                score = (romanPositions.length * 10) + inOrderBonusAlts(romanPositions, rlist);
            }
        }

        if (engTokens.length > 0) {
            var elist = englishTokens(v.english || '');
            var eset = {};
            for (var k = 0; k < elist.length; k++) eset[elist[k]] = true;
            var allEnglish = true;
            for (var m = 0; m < engTokens.length; m++) {
                if (!eset[engTokens[m]]) { allEnglish = false; break; }
            }
            if (allEnglish) {
                var eScore = (engTokens.length * 10) + inOrderBonus(engTokens, elist);
                if (eScore > score) score = eScore;
            }
        }

        return score;
    }

    /* Common-spelling normalization table. Single machine-readable source at
       metadata/search-normalization.json, shared with the MCP server and
       injected at build time; do not edit inline. Contract summary:
       alternatives are OR within a position, positions are AND, all satisfied
       within one text layer; compound aliases require contiguous ordered
       token sequences. The full contract lives in the table's _contract
       field. */
    var NORMALIZATION = {
  "_contract": "Alias target arrays are exhaustive alternatives for that query position. Alternatives are OR; separate query positions are AND; every required position must be satisfied within one text layer. Compound aliases map a fused spelling to a contiguous token sequence: the tokens must appear adjacently and in order within the Roman line, forming one required position (never independent positions, never alternatives). Adjacency applies only to compound aliases; ordinary multi-word queries remain independent unordered positions. Phrase aliases are recognized on contiguous token windows before per-token rules. Tokenization: lowercase, replace (n) with n, split [a-z]+. English stemming never touches Roman queries or Roman corpus text.",
  "token_aliases": {
    "tu": [
      "tu",
      "too",
      "toon"
    ],
    "dayal": [
      "daiaal"
    ],
    "dayaal": [
      "dayaal",
      "daiaal"
    ],
    "ardas": [
      "aradaas"
    ],
    "ardaas": [
      "aradaas"
    ],
    "waheguru": [
      "vaahiguroo"
    ],
    "wahiguru": [
      "vaahiguroo"
    ],
    "vaheguru": [
      "vaahiguroo"
    ],
    "vahiguru": [
      "vaahiguroo"
    ],
    "simran": [
      "simaran"
    ],
    "kirpa": [
      "kirapaa"
    ],
    "kirpaa": [
      "kirapaa"
    ],
    "pyar": [
      "piaar"
    ],
    "piar": [
      "piaar"
    ],
    "pyaar": [
      "piaar"
    ],
    "guru": [
      "guroo"
    ],
    "nanak": [
      "naanak"
    ],
    "shabad": [
      "sabad"
    ],
    "shabd": [
      "sabad"
    ],
    "seva": [
      "sevaa"
    ],
    "sewa": [
      "sevaa"
    ],
    "prabhu": [
      "prabh",
      "prabhoo"
    ],
    "akal": [
      "akal",
      "akaal"
    ],
    "karma": [
      "karam"
    ],
    "dharma": [
      "dharam"
    ],
    "amrit": [
      "anmrit"
    ],
    "bani": [
      "baanee"
    ],
    "kirtan": [
      "keeratan"
    ],
    "darshan": [
      "darasan"
    ],
    "satguru": [
      "satigur",
      "satiguroo"
    ],
    "satgur": [
      "satigur",
      "satiguroo"
    ],
    "onkar": [
      "oankaar",
      "ikoankaar"
    ],
    "oankar": [
      "oankaar",
      "ikoankaar"
    ],
    "onkaar": [
      "oankaar",
      "ikoankaar"
    ],
    "ram": [
      "ram",
      "raam"
    ],
    "allah": [
      "alahu",
      "alah"
    ],
    "mehl": [
      "mahalaa"
    ],
    "mehla": [
      "mahalaa"
    ],
    "anand": [
      "anand",
      "aanand"
    ]
  },
  "phrase_aliases": {
    "ik onkar": [
      "ikoankaar"
    ],
    "ik onkaar": [
      "ikoankaar"
    ],
    "ik oankar": [
      "ikoankaar"
    ],
    "ik oankaar": [
      "ikoankaar"
    ],
    "ek onkar": [
      "ikoankaar"
    ],
    "ek onkaar": [
      "ikoankaar"
    ],
    "ek oankar": [
      "ikoankaar"
    ],
    "ek oankaar": [
      "ikoankaar"
    ]
  },
  "compound_aliases": {
    "satnam": [
      "sat",
      "naam"
    ]
  }
}
;

    /* Build Roman query positions. Order matters: exact phrase aliases are
       recognized on contiguous token windows before any per-token rule
       runs, so "ik onkar" cannot be split and transformed token-by-token
       first. Compound aliases (satnam -> sat, naam) become a single
       position whose token sequence must appear contiguously and in order
       in the Roman line (issue #7). */
    function expandRomanQuery(ql) {
        var tokens = romanTokens(ql);
        var phraseKeys = Object.keys(NORMALIZATION.phrase_aliases).sort(function(a, b) {
            return b.length - a.length;
        });
        for (var p = 0; p < phraseKeys.length; p++) {
            var keyToks = phraseKeys[p].split(' ');
            for (var i = 0; i + keyToks.length <= tokens.length; i++) {
                var isMatch = true;
                for (var j = 0; j < keyToks.length; j++) {
                    if (tokens[i + j] !== keyToks[j]) { isMatch = false; break; }
                }
                if (isMatch) {
                    var replaced = [i, keyToks.length, { alts: NORMALIZATION.phrase_aliases[phraseKeys[p]] }];
                    Array.prototype.splice.apply(tokens, replaced);
                }
            }
        }
        /* Each position is a list of OR-alternatives; each alternative is a
           token SEQUENCE (usually one token). Compound aliases (satnam ->
           sat, naam) become ONE position whose single alternative must appear
           contiguously and in order in the Roman line (issue #7); ordinary
           multi-word queries remain independent unordered positions. */
        var positions = [];
        for (var t = 0; t < tokens.length; t++) {
            var tok = tokens[t];
            if (typeof tok === 'object') {
                positions.push(tok.alts.map(function (a) { return [a]; }));
                continue;
            }
            var compound = NORMALIZATION.compound_aliases[tok];
            if (compound) {
                positions.push([compound.slice()]);
                continue;
            }
            var aliases = NORMALIZATION.token_aliases[tok];
            positions.push((aliases || [tok]).map(function (a) { return [a]; }));
        }
        return positions;
    }

    /* True when seq (a token array) appears contiguously in verseTokens. */
    function seqInTokens(seq, verseTokens) {
        for (var s = 0; s + seq.length <= verseTokens.length; s++) {
            var ok = true;
            for (var j = 0; j < seq.length; j++) {
                if (verseTokens[s + j] !== seq[j]) { ok = false; break; }
            }
            if (ok) return true;
        }
        return false;
    }

