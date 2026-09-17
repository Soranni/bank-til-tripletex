/**
 * Regresjonstest for bank-til-tripletex.
 *
 * Kjører den EKTE koden fra index.html mot testfilene i testfiler/, med en
 * minimal DOM-stub, og sjekker at hver fil gir forventet utfall.
 *
 * Kjør:  node test.js
 */

const fs = require('fs');
const path = require('path');

// ---------- Minimal DOM ----------
function El(tag) {
  const e = {
    tag: tag || 'div', children: [], className: '', hidden: false, value: '', selected: false,
    _text: '', _html: '', style: {}, classList: { add() {}, remove() {}, toggle() {} },
    append(...k) { e.children.push(...k); },
    appendChild(k) { e.children.push(k); return k; },
    addEventListener() {}, click() {}, select() {},
    querySelectorAll(sel) {
      const treff = [];
      (function gaa(n) { n.children.forEach(c => { if (c.tag === sel) treff.push(c); gaa(c); }); })(e);
      return treff;
    },
    get textContent() { return e._text; },
    set textContent(v) { e._text = v; if (v === '') e.children = []; },
    get innerHTML() { return e._html; },
    set innerHTML(v) { e._html = v; if (v === '') e.children = []; },
  };
  return e;
}
const reg = {};
// Kontovelgerne må ha verdier før koden leser dem.
function velger(v) { const e = El('select'); e.value = v; return e; }
global.document = {
  getElementById: id => (reg[id] = reg[id] || El()),
  createElement: tag => El(tag),
  addEventListener() {}, body: El(),
};
global.window = { addEventListener() {}, scrollTo() {} };
global.navigator = {};

reg.bankKonto = velger('1920');
reg.motKonto = velger('1909');
reg.skilletegn = El('select');
reg.startRad = El('input');
reg.mapperTabell = El('table');

// ---------- Last koden fra index.html ----------
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const js = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
(0, eval)(js + ';globalThis.__api={detectFormat,parseKontoinfo,parseOversiktKonti,' +
  'parseTransaksjonsliste,parseNordea,buildGBAT10,extractControlTotals,renderNotes,suggestFilename,forklarTomFil,' +
  'klargjorMapper,lesMedMapping,tolkBelop,tolkDato};');
const api = globalThis.__api;

// Leser filen slik nettleseren gjør det.
function lesFil(sti) {
  const buf = fs.readFileSync(sti);
  if (buf[0] === 0xEF && buf[1] === 0xBB && buf[2] === 0xBF) return new TextDecoder('utf-8').decode(buf);
  try { return new TextDecoder('utf-8', { fatal: true }).decode(buf); }
  catch (e) { return new TextDecoder('iso-8859-1').decode(buf); }
}

function kjor(fil) {
  const text = lesFil(path.join(__dirname, 'testfiler', fil));
  const fmt = api.detectFormat(text);
  const parsed = fmt === 'kontoinfo' ? api.parseKontoinfo(text)
    : fmt === 'oversiktkonti' ? api.parseOversiktKonti(text)
    : fmt === 'transaksjonsliste' ? api.parseTransaksjonsliste(text)
    : api.parseNordea(text);
  const t = parsed.transactions;
  const kontroll = api.extractControlTotals(text);

  let banner = 'ingen';
  if (t.length) {
    const inn = t.filter(x => x.is_credit).reduce((s, x) => s + x.amount, 0);
    const ut = t.filter(x => !x.is_credit).reduce((s, x) => s + x.amount, 0);
    banner = !kontroll ? 'gra'
      : (Math.abs(kontroll.inn - inn) < 0.005 && Math.abs(kontroll.ut - ut) < 0.005) ? 'gronn' : 'rod';
  }

  reg.notesList = El();
  reg.notes = El();
  if (t.length) api.renderNotes(t, kontroll, text);
  const merknader = reg.notesList.children.map(r => r.children[1].textContent);

  return { fmt, antall: t.length, banner, merknader,
           forklaring: t.length ? null : api.forklarTomFil(text),
           gbat10: t.length ? api.buildGBAT10(parsed.header, t) : '' };
}

// ---------- Forventninger ----------
const CASER = [
  { fil: 'demo-sparebank1-gyldig.csv',    fmt: 'kontoinfo', antall: 12, banner: 'gronn' },
  { fil: 'test-1-ukjent-bank.csv',        fmt: 'nordea',    antall: 0 },
  { fil: 'test-2-ingen-transaksjoner.csv', fmt: 'kontoinfo', antall: 0 },
  { fil: 'test-3-excel-lagret.csv',       fmt: 'kontoinfo', antall: 12, banner: 'gronn' },
  { fil: 'test-4-nytt-kolonnenavn.csv',   fmt: 'kontoinfo', antall: 12, banner: 'gronn' },
  { fil: 'test-7-excel-komma.csv',        fmt: 'kontoinfo', antall: 0, forklaring: 'komma som skilletegn' },
  { fil: 'test-5-avvik-i-sum.csv',        fmt: 'kontoinfo', antall: 12, banner: 'rod' },
  { fil: 'test-6-uleselige-linjer.csv',   fmt: 'kontoinfo', antall: 12, banner: 'gronn',
    merknad: 'ble ikke lest inn' },
];

let feil = 0;
for (const c of CASER) {
  const r = kjor(c.fil);
  const problemer = [];
  if (r.fmt !== c.fmt) problemer.push(`format ${r.fmt} != ${c.fmt}`);
  if (r.antall !== c.antall) problemer.push(`antall ${r.antall} != ${c.antall}`);
  if (c.banner && r.banner !== c.banner) problemer.push(`banner ${r.banner} != ${c.banner}`);
  if (c.merknad && !r.merknader.some(m => m.includes(c.merknad)))
    problemer.push(`manglet merknad "${c.merknad}"`);
  if (c.forklaring && !(r.forklaring || '').includes(c.forklaring))
    problemer.push(`manglet forklaring "${c.forklaring}"`);

  // Hvert bilag må balansere til null.
  if (r.gbat10) {
    const saldo = {};
    r.gbat10.trim().split('\n').forEach(l => {
      const k = l.split(';');
      saldo[k[1]] = (saldo[k[1]] || 0) + parseFloat(k[8]);
    });
    const ubalanse = Object.keys(saldo).filter(k => Math.abs(saldo[k]) > 0.001);
    if (ubalanse.length) problemer.push(`${ubalanse.length} bilag balanserer ikke`);
  }

  if (problemer.length) { feil++; console.log(`FEIL  ${c.fil}\n      ${problemer.join('\n      ')}`); }
  else console.log(`ok    ${c.fil.padEnd(32)} ${r.fmt.padEnd(14)} ${r.antall} tx  ${r.banner}`);
}

// ---------- Kolonnevelgeren ----------
// En bank vi ikke stotter skal kunne leses ved at brukeren peker ut kolonnene.
// Her sjekker vi at gjettingen treffer, og at resultatet blir riktig.
(function testKolonnevelger() {
  const fil = 'test-1-ukjent-bank.csv';
  const text = fs.readFileSync(path.join(__dirname, 'testfiler', fil), 'utf8');
  api.klargjorMapper({ name: fil, size: text.length }, text);

  const problemer = [];
  if (reg.skilletegn.value !== ',') problemer.push(`skilletegn ${JSON.stringify(reg.skilletegn.value)} != ","`);
  if (String(reg.startRad.value) !== '2') problemer.push(`startrad ${reg.startRad.value} != 2`);

  const selects = reg.mapperTabell.querySelectorAll('select');
  const roller = selects.map(sel => {
    const v = sel.children.filter(o => o.selected)[0];
    sel.value = v ? v.value : '';
    return sel.value;
  });
  if (roller.join('|') !== 'dato|tekst|ut|inn|') problemer.push(`roller ${roller.join('|')}`);

  api.lesMedMapping();
  const html = reg.summary.innerHTML;
  if (!/Transaksjoner<\/td><td>2 \(1 inn \/ 1 ut\)/.test(html)) problemer.push('feil antall transaksjoner');
  // nb-NO bruker hardt mellomrom som tusenskille, derfor \s og ikke vanlig mellomrom.
  if (!/Sum inn<\/td><td[^>]*>\+12\s500,00 kr/.test(html)) problemer.push('feil sum inn');
  if (reg.step2.hidden || reg.step3.hidden) problemer.push('steg 2/3 ble ikke vist');

  // Tallformat: norsk og engelsk skal begge tolkes riktig.
  const tall = [['1.234,56', 1234.56], ['1,234.56', 1234.56], ['2450.00', 2450], ['-8 681,93', -8681.93]];
  tall.forEach(t => {
    if (Math.abs(api.tolkBelop(t[0]) - t[1]) > 0.001) problemer.push(`tolkBelop("${t[0]}") != ${t[1]}`);
  });

  if (problemer.length) { feil++; console.log(`FEIL  kolonnevelger\n      ${problemer.join('\n      ')}`); }
  else console.log('ok    kolonnevelger'.padEnd(38) + 'gjettet skilletegn, startrad og 4 kolonneroller');
})();

console.log(feil === 0 ? `\nAlle ${CASER.length + 1} testene passerte.` : `\n${feil} test(er) feilet.`);
process.exit(feil === 0 ? 0 : 1);
