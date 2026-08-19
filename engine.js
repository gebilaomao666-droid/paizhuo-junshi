// 德州扑克核心引擎：7张牌评牌 + 蒙特卡洛胜率模拟
// 牌编码：0-51 的整数，rank = c>>2（0=2 … 12=A），suit = c&3（0♠ 1♥ 2♦ 3♣）

// 在 rank 位掩码里找顺子，返回顺子最大牌的 rank，没有返回 -1（A2345 返回 3，即 5 高）
function straightHigh(mask) {
  for (let hi = 12; hi >= 4; hi--) {
    let ok = true;
    for (let k = 0; k < 5; k++) {
      if (!((mask >> (hi - k)) & 1)) { ok = false; break; }
    }
    if (ok) return hi;
  }
  // 轮子：A 2 3 4 5
  if ((mask & 0b1000000001111) === 0b1000000001111) return 3;
  return -1;
}

// 评 7 张牌，返回可直接比大小的整数（越大越强）
// 编码：cat*16^5 + 5 个 4bit 决胜位（rank 0-12 各占一位）
function evaluate7(cards) {
  const cnt = new Array(13).fill(0);
  const suitCnt = [0, 0, 0, 0];
  const suitMask = [0, 0, 0, 0];
  let rankMask = 0;
  for (let i = 0; i < cards.length; i++) {
    const r = cards[i] >> 2, s = cards[i] & 3;
    cnt[r]++; suitCnt[s]++; suitMask[s] |= 1 << r; rankMask |= 1 << r;
  }

  const score = (cat, a, b, c, d, e) =>
    ((((cat * 16 + (a + 1)) * 16 + (b + 1)) * 16 + (c + 1)) * 16 + (d + 1)) * 16 + (e + 1);

  // 同花 / 同花顺
  let fs = -1;
  for (let s = 0; s < 4; s++) if (suitCnt[s] >= 5) fs = s;
  if (fs >= 0) {
    const sf = straightHigh(suitMask[fs]);
    if (sf >= 0) return score(8, sf, -1, -1, -1, -1);
  }

  // 按张数归类
  let quad = -1;
  const trips = [], pairs = [];
  for (let r = 12; r >= 0; r--) {
    if (cnt[r] === 4) quad = r;
    else if (cnt[r] === 3) trips.push(r);
    else if (cnt[r] === 2) pairs.push(r);
  }

  if (quad >= 0) {
    let kick = -1;
    for (let r = 12; r >= 0; r--) if (r !== quad && cnt[r] > 0) { kick = r; break; }
    return score(7, quad, kick, -1, -1, -1);
  }

  // 葫芦：三条+对子，或两组三条
  if (trips.length >= 1 && (pairs.length >= 1 || trips.length >= 2)) {
    const t = trips[0];
    const p = trips.length >= 2 ? Math.max(trips[1], pairs[0] !== undefined ? pairs[0] : -1) : pairs[0];
    return score(6, t, p, -1, -1, -1);
  }

  if (fs >= 0) {
    const ranks = [];
    for (let r = 12; r >= 0 && ranks.length < 5; r--) if ((suitMask[fs] >> r) & 1) ranks.push(r);
    return score(5, ranks[0], ranks[1], ranks[2], ranks[3], ranks[4]);
  }

  const st = straightHigh(rankMask);
  if (st >= 0) return score(4, st, -1, -1, -1, -1);

  if (trips.length >= 1) {
    const t = trips[0], kicks = [];
    for (let r = 12; r >= 0 && kicks.length < 2; r--) if (r !== t && cnt[r] > 0) kicks.push(r);
    return score(3, t, kicks[0], kicks[1], -1, -1);
  }

  if (pairs.length >= 2) {
    const p1 = pairs[0], p2 = pairs[1];
    let kick = -1;
    for (let r = 12; r >= 0; r--) if (r !== p1 && r !== p2 && cnt[r] > 0) { kick = r; break; }
    return score(2, p1, p2, kick, -1, -1);
  }

  if (pairs.length === 1) {
    const p = pairs[0], kicks = [];
    for (let r = 12; r >= 0 && kicks.length < 3; r--) if (r !== p && cnt[r] > 0) kicks.push(r);
    return score(1, p, kicks[0], kicks[1], kicks[2], -1);
  }

  const hs = [];
  for (let r = 12; r >= 0 && hs.length < 5; r--) if (cnt[r] > 0) hs.push(r);
  return score(0, hs[0], hs[1], hs[2], hs[3], hs[4]);
}

const CAT_NAMES = ['高牌', '一对', '两对', '三条', '顺子', '同花', '葫芦', '四条', '同花顺'];
function handCategory(scoreVal) { return Math.floor(scoreVal / (16 * 16 * 16 * 16 * 16)); }

// 蒙特卡洛：我的底牌 hole(2张) + 已知公共牌 board(0/3/4/5张)，对 nOpp 个对手
// allowed: 可选，Uint8Array(52*52)，allowed[c1*52+c2]=1 表示对手可能拿这两张（对手范围）；不传=随机牌
// bluffP: 可选，0-1，对手每次有这个概率在"演"（无视范围拿随机牌）
// restAllowed/tightN: 可选，前 tightN 个对手用 allowed(+bluffP)，其余对手用 restAllowed；不传 tightN=全部用 allowed
function simulate(hole, board, nOpp, iters, allowed, bluffP, restAllowed, tightN) {
  if (tightN === undefined) tightN = nOpp;
  const used = new Set(hole.concat(board));
  const deck = [];
  for (let c = 0; c < 52; c++) if (!used.has(c)) deck.push(c);
  const L = deck.length, bneed = 5 - board.length;
  let win = 0, tie = 0, tieShare = 0;
  const my7 = hole.concat(board);
  for (let i = 0; i < iters; i++) {
    // 洗前缀发剩余公共牌
    for (var j = 0; j < bneed; j++) {
      const k = j + Math.floor(Math.random() * (L - j));
      const t = deck[j]; deck[j] = deck[k]; deck[k] = t;
    }
    const full = my7.slice();
    for (j = 0; j < bneed; j++) full.push(deck[j]);
    const mine = evaluate7(full);
    let maxOpp = -1, cntMax = 0, start = bneed;
    for (let o = 0; o < nOpp; o++) {
      // 从 deck[start..L) 抽对手两张；带范围时拒绝采样，抽不到就兜底随机
      // 前 tightN 个对手按 allowed（每次有 bluffP 概率在"演"拿随机牌），其余按 restAllowed
      const base2 = o < tightN ? allowed : restAllowed;
      const filter = base2 && !(o < tightN && bluffP && Math.random() < bluffP) ? base2 : null;
      let c1, c2, ok = false;
      for (let tr = 0; tr < 30 && !ok; tr++) {
        const ii = start + Math.floor(Math.random() * (L - start));
        let jj = start + Math.floor(Math.random() * (L - start));
        if (jj === ii) continue;
        c1 = deck[ii]; c2 = deck[jj];
        if (!filter || filter[c1 * 52 + c2]) {
          let tmp = deck[ii]; deck[ii] = deck[start]; deck[start] = tmp;
          if (jj === start) jj = ii;
          tmp = deck[jj]; deck[jj] = deck[start + 1]; deck[start + 1] = tmp;
          ok = true;
        }
      }
      if (!ok) { c1 = deck[start]; c2 = deck[start + 1]; }
      const oc = [c1, c2];
      for (j = 2; j < 7; j++) oc.push(full[j]);
      const v = evaluate7(oc);
      if (v > maxOpp) { maxOpp = v; cntMax = 1; }
      else if (v === maxOpp) cntMax++;
      start += 2;
    }
    if (mine > maxOpp) win++;
    else if (mine === maxOpp) { tie++; tieShare += 1 / (1 + cntMax); } // 平分底池按人数均分
  }
  return { win: win / iters, tie: tie / iters, equity: (win + tieShare) / iters };
}

// 把「最强前 pct% 的起手牌」编成 52×52 允许矩阵；ranked=169个牌型代码按强度降序
const RANK_CODE_E = ['2','3','4','5','6','7','8','9','T','J','Q','K','A'];
function buildAllowed(pct, ranked) {
  const set = new Set();
  let cum = 0;
  for (const code of ranked) {
    const w = code.length === 2 ? 6 : code[2] === 's' ? 4 : 12;
    if (cum > 0 && (cum + w) / 1326 * 100 > pct) break;
    cum += w; set.add(code);
  }
  const allowed = new Uint8Array(52 * 52);
  for (let a = 0; a < 52; a++) for (let b = 0; b < 52; b++) {
    if (a === b) continue;
    const r1 = a >> 2, r2 = b >> 2;
    let code;
    if (r1 === r2) code = RANK_CODE_E[r1] + RANK_CODE_E[r2];
    else {
      const hi = Math.max(r1, r2), lo = Math.min(r1, r2);
      code = RANK_CODE_E[hi] + RANK_CODE_E[lo] + ((a & 3) === (b & 3) ? 's' : 'o');
    }
    if (set.has(code)) allowed[a * 52 + b] = 1;
  }
  return allowed;
}

if (typeof module !== 'undefined') module.exports = { evaluate7, simulate, handCategory, CAT_NAMES, straightHigh, buildAllowed };
