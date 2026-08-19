/* 陪练 AI 强度评测：新 AI(prAiDecide) vs 旧 AI(prAiDecideV1)
   - 直接从 index.html 抽取 AI 源码，测的就是线上跑的那份，不会走样
   - 采用 duplicate(对倒)：同一副牌打两遍、两边换座，抵消发牌运气
   - 结果以 bb/100（每百手赢多少个大盲）计，扑克业界标准口径 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const engine = require('./engine.js');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const ranked = JSON.parse(fs.readFileSync(path.join(__dirname, 'ranking169.json'), 'utf8'));

/* ---------- 从 index.html 抽取源码（括号配对） ---------- */
function grab(startPattern, open, close) {
  open = open || '{'; close = close || '}';
  const m = html.match(startPattern);
  if (!m) throw new Error('抽取失败: ' + startPattern);
  const from = html.indexOf(open, m.index);
  let d = 0;
  for (let i = from; i < html.length; i++) {
    if (html[i] === open) d++;
    else if (html[i] === close) { if (--d === 0) return html.slice(m.index, i + 1); }
  }
  throw new Error('括号不配对: ' + startPattern);
}
function grabLine(pattern) {
  const m = html.match(pattern);
  if (!m) throw new Error('抽取失败: ' + pattern);
  return m[0];
}

const pieces = [
  grabLine(/var PR_SB = [^\n]*/),
  grabLine(/var PR_ITERS = [^\n]*/),
  grab(/var RANK_CODE\s*=/, '[', ']') + ';',
  grab(/var PR_STYLE_DEF\s*=/) + ';',
  grab(/var PR_POS_MUL\s*=/) + ';',
  grab(/function holeCode\s*\(/),
  grab(/function prPosOf\s*\(/),
  grab(/function prTexture\s*\(/),
  grab(/function prStats\s*\(/),
  grab(/function prFoldLean\s*\(/),
  grab(/function prAggroPct\s*\(/),
  grab(/function prSizeFor\s*\(/),
  grab(/function prAiDecide\s*\(/),
  grab(/function prAiDecideV1\s*\(/),
];
/* 自检：确认抽到的是真货，index.html 改动后若走样会立刻报错 */
if (!/PR_ITERS = 4000/.test(pieces[1])) throw new Error('PR_ITERS 异常');
if (!/getAllowed/.test(pieces[12])) throw new Error('新 AI 未含范围建模，抽取有误');
if (!/300\)/.test(pieces[13])) throw new Error('旧 AI 抽取有误');

/* ---------- 可复现随机源 ---------- */
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rng = mulberry32(20260819);

/* ---------- 沙箱：提供 AI 所需的全局 ---------- */
const allowedCache = {};
const ctx = {
  Math: Object.create(Math),
  simulate: engine.simulate,
  evaluate7: engine.evaluate7,
  getAllowed: function (pct) {
    if (!allowedCache[pct]) allowedCache[pct] = engine.buildAllowed(pct, ranked);
    return allowedCache[pct];
  },
  PCTL: {},
  pr: null,
  prPotTotal: function () { let s = 0; ctx.pr.players.forEach(p => { s += p.contrib; }); return s; },
  prAlive: function () { return ctx.pr.players.filter(p => !p.folded); },
};
ctx.Math.random = rng;
vm.createContext(ctx);
vm.runInContext(pieces.join('\n'), ctx);
/* PCTL：与 index.html 同一公式 */
(function () {
  let cum = 0;
  for (const c of ranked) {
    const w = c.length === 2 ? 6 : c[2] === 's' ? 4 : 12;
    cum += w; ctx.PCTL[c] = cum / 1326 * 100;
  }
})();

const PR_SB = ctx.PR_SB, PR_BB = ctx.PR_BB, PR_STACK = ctx.PR_STACK;

/* ---------- 无界面牌局（与 index.html 的规则逐条对齐） ---------- */
function post(p, amt) {
  amt = Math.min(amt, p.stack);
  p.stack -= amt; p.bet += amt; p.contrib += amt;
  if (p.stack === 0) p.allin = true;
  return amt;
}
function applyAct(st, p, act) {
  const s = ctx.prStats(p);
  if (st.currentBet - p.bet > 0) { s.faced++; if (act.type === 'fold') s.folds++; }
  if (act.type === 'call') s.calls++;
  if (act.type === 'raise') { s.raises++; if (st.board.length === 0) st.preRaised = true; }
  if (act.type === 'fold') { p.folded = true; return; }
  if (act.type === 'check') return;
  if (act.type === 'call') { post(p, st.currentBet - p.bet); return; }
  const target = Math.min(act.to, p.bet + p.stack);
  post(p, target - p.bet);
  if (p.bet > st.currentBet) {
    st.minRaise = Math.max(st.minRaise, p.bet - st.currentBet);
    st.currentBet = p.bet;
    st.players.forEach(q => { if (q !== p && !q.folded && !q.allin) q.acted = false; });
  }
}
function bettingRound(st, startIdx) {
  let idx = startIdx, guard = 0;
  while (guard++ < 300) {
    if (st.players.filter(p => !p.folded).length <= 1) return;
    const pending = st.players.filter(p => !p.folded && !p.allin && (!p.acted || p.bet < st.currentBet));
    if (pending.length === 0) return;
    const p = st.players[idx];
    if (!p.folded && !p.allin && (!p.acted || p.bet < st.currentBet)) {
      const act = p.isNew ? ctx.prAiDecide(p) : ctx.prAiDecideV1(p);
      applyAct(st, p, act);
      p.acted = true;
    }
    idx = (idx + 1) % st.n;
  }
}
function settle(st) {
  const alive = st.players.filter(p => !p.folded);
  const pot = st.players.reduce((s, p) => s + p.contrib, 0);
  if (alive.length === 1) { alive[0].stack += pot; return; }
  alive.forEach(p => { p.val = engine.evaluate7(p.hole.concat(st.board)); });
  const levels = [...new Set(st.players.filter(p => p.contrib > 0).map(p => p.contrib))].sort((a, b) => a - b);
  let prev = 0;
  for (const lv of levels) {
    let amt = 0;
    st.players.forEach(p => { amt += Math.max(0, Math.min(p.contrib, lv) - prev); });
    const elig = alive.filter(p => p.contrib >= lv);
    if (!elig.length) { prev = lv; continue; }
    const best = Math.max.apply(null, elig.map(p => p.val));
    const winners = elig.filter(p => p.val === best);
    const base = Math.floor(amt / winners.length);
    winners.forEach((w, i) => { w.stack += base + (i === 0 ? amt - base * winners.length : 0); });
    prev = lv;
  }
}
/* 用给定牌堆打一手；newSeats 指定哪些座位坐新 AI */
function playHand(n, dealer, deck, newSeats) {
  const styles = ['loose', 'normal', 'tight', 'normal', 'loose', 'normal'];
  const players = [];
  for (let i = 0; i < n; i++) {
    players.push({
      name: 'P' + i, stack: PR_STACK, bet: 0, contrib: 0,
      folded: false, allin: false, acted: false,
      isNew: newSeats.has(i), style: styles[i % styles.length],
    });
  }
  const st = { n: n, dealer: dealer, players: players, board: [], currentBet: PR_BB, minRaise: PR_BB, preRaised: false };
  ctx.pr = st;
  let di = 0;
  players.forEach(p => { p.hole = [deck[di++], deck[di++]]; });
  let sb, bb;
  if (n === 2) { sb = dealer; bb = (dealer + 1) % 2; }
  else { sb = (dealer + 1) % n; bb = (dealer + 2) % n; }
  post(players[sb], PR_SB); post(players[bb], PR_BB);
  bettingRound(st, n === 2 ? sb : (bb + 1) % n);
  const streets = [3, 1, 1];
  for (let s = 0; s < 3; s++) {
    if (players.filter(p => !p.folded).length <= 1) break;
    for (let k = 0; k < streets[s]; k++) st.board.push(deck[di++]);
    players.forEach(p => { p.bet = 0; p.acted = false; });
    st.currentBet = 0; st.minRaise = PR_BB;
    bettingRound(st, (dealer + 1) % n);
  }
  while (st.board.length < 5) st.board.push(deck[di++]);
  settle(st);
  return players.map(p => p.stack - PR_STACK);
}

/* ---------- A/B 主流程 ---------- */
const N = +(process.argv[2] || 600);
const n = 6;
const evenSeats = new Set([0, 2, 4]);
let newNet = 0, oldNet = 0, seatHands = 0;
const perDeck = [];
const t0 = Date.now();
for (let h = 0; h < N; h++) {
  const deck = [];
  for (let c = 0; c < 52; c++) deck.push(c);
  for (let i = 51; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); const t = deck[i]; deck[i] = deck[j]; deck[j] = t; }
  const dealer = h % n;
  const a = playHand(n, dealer, deck.slice(), evenSeats);                 // 新AI坐偶数位
  const b = playHand(n, dealer, deck.slice(), new Set([1, 3, 5]));        // 同一副牌，新AI换到奇数位
  let hn = 0, ho = 0;
  for (let i = 0; i < n; i++) {
    if (evenSeats.has(i)) { hn += a[i]; ho += b[i]; } else { ho += a[i]; hn += b[i]; }
  }
  newNet += hn; oldNet += ho; seatHands += n;
  perDeck.push(hn / n);
  if ((h + 1) % 100 === 0) {
    process.stdout.write('  已打 ' + (h + 1) + '/' + N + ' 副 · 新AI ' + (newNet / seatHands / PR_BB * 100).toFixed(1) + ' bb/100   \r');
  }
}
const secs = ((Date.now() - t0) / 1000).toFixed(1);
const newBB = newNet / seatHands / PR_BB * 100;
const oldBB = oldNet / seatHands / PR_BB * 100;
const mean = perDeck.reduce((x, y) => x + y, 0) / perDeck.length;
const sd = Math.sqrt(perDeck.reduce((s, x) => s + Math.pow(x - mean, 2), 0) / Math.max(1, perDeck.length - 1));
const ciBB = 1.96 * (sd / Math.sqrt(perDeck.length)) / PR_BB * 100;

console.log('\n');
console.log('════════ 陪练 AI 强度评测 ════════');
console.log('对局方式   6人桌 · duplicate对倒(同牌换座) · ' + N + ' 副牌 × 2 遍');
console.log('总样本     ' + seatHands + ' 个座位手 · 耗时 ' + secs + 's');
console.log('');
console.log('新 AI      ' + (newBB >= 0 ? '+' : '') + newBB.toFixed(1) + ' bb/100');
console.log('旧 AI      ' + (oldBB >= 0 ? '+' : '') + oldBB.toFixed(1) + ' bb/100');
console.log('净胜       ' + (newBB - oldBB >= 0 ? '+' : '') + (newBB - oldBB).toFixed(1) + ' bb/100   (95%置信区间 ±' + (ciBB * 2).toFixed(1) + ')');
console.log('');
if (Math.abs(newBB) > ciBB) {
  console.log(newBB > 0 ? '✅ 新 AI 显著强于旧 AI（差距超出95%置信区间）' : '❌ 新 AI 显著弱于旧 AI');
} else {
  console.log('⚠️  样本不足，差距未达统计显著，请加大手数');
}
process.exit(newBB > 0 ? 0 : 1);
