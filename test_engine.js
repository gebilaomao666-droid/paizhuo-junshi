const { evaluate7, simulate, handCategory, CAT_NAMES } = require('./engine.js');

// 解析 "As Kh Td 2c" 这种记法
const RANKS = '23456789TJQKA';
const SUITS = { s: 0, h: 1, d: 2, c: 3 };
function card(str) { return RANKS.indexOf(str[0]) * 4 + SUITS[str[1]]; }
function hand(str) { return str.trim().split(/\s+/).map(card); }

let pass = 0, fail = 0;
function check(name, cond) {
  if (cond) { pass++; }
  else { fail++; console.log('FAIL: ' + name); }
}

// ===== 评牌器单元测试 =====
const ev = (s) => evaluate7(hand(s));
const cat = (s) => handCategory(ev(s));

check('皇家同花顺=同花顺类', cat('As Ks Qs Js Ts 2h 3d') === 8);
check('同花顺', cat('9h 8h 7h 6h 5h Ac Kd') === 8);
check('A2345同花顺(轮子)', cat('Ah 2h 3h 4h 5h Kc Qd') === 8);
check('四条', cat('Kc Kd Kh Ks 3c 7h 2d') === 7);
check('葫芦', cat('Qc Qd Qh 7s 7c 2h 3d') === 6);
check('两组三条算葫芦', cat('Qc Qd Qh 7s 7c 7h 3d') === 6);
check('同花', cat('Ad Jd 8d 6d 2d Kc Qh') === 5);
check('顺子', cat('9s 8h 7d 6c 5s Ah Kd') === 4);
check('A2345顺子(轮子)', cat('Ah 2c 3d 4s 5h Kc 9d') === 4);
check('QKA23不是顺子', cat('Qh Kc Ad 2s 3h 7c 9d') === 0);
check('三条', cat('8c 8d 8h Ac Kd 4s 2h') === 3);
check('两对', cat('Jc Jd 4h 4s 9c 2d 7h') === 2);
check('一对', cat('Tc Td Ah 7s 4c 2d 9h') === 1);
check('高牌', cat('Ac Kd 9h 6s 3c 2d Jh') === 0);
check('4张同花不算同花', cat('Ad Jd 8d 6d 2c Kc Qh') === 0);

// 大小比较
check('最小同花>最大顺子', ev('7d 5d 4d 3d 2d Kc Qh') > ev('As Kh Qd Jc Ts 2h 3d'));
check('最烂两对>最好一对', ev('3c 3d 2h 2s 7c Kd 9h') > ev('Ac Ad Kh Qs Jc 9d 7h'));
check('葫芦先比三条: QQQ22>JJJAA', ev('Qc Qd Qh 2s 2c 7h 3d') > ev('Jc Jd Jh As Ac 7h 3d'));
check('踢脚牌: KK+A踢 > KK+Q踢', ev('Kc Kd Ah 9s 5c 2d 3h') > ev('Kh Ks Qh Jc Tc 2s 3s'));
check('同点数平局(花色无关)', ev('Ac Kc 9h 6s 3c 2d Jh') === ev('Ad Kd 9s 6h 3d 2c Js'));
check('公共牌打平: 公牌顺子双方平分', (() => {
  const board = '9s 8h 7d 6c 5s';
  return ev('2c 3d ' + board) === ev('Kh Qc ' + board);
})());
check('轮子<6高顺子', ev('Ah 2c 3d 4s 5h Kc 9d') < ev('6h 5c 4d 3s 2h Kc 9d'));

// ===== 蒙特卡洛基准（公认数值,允许±2%误差）=====
const N = 60000;
function eq(holeStr, boardStr, nOpp) {
  return simulate(hand(holeStr), boardStr ? hand(boardStr) : [], nOpp, N).equity * 100;
}
function near(name, got, expect, tol) {
  const ok = Math.abs(got - expect) <= tol;
  if (!ok) console.log(`FAIL: ${name} 得到 ${got.toFixed(1)}% 期望 ${expect}%`);
  else pass++;
  if (!ok) fail++;
}

near('AA vs 1人 ≈85.2%', eq('Ac Ad', '', 1), 85.2, 2);
near('AKs vs 1人 ≈67%', eq('Ac Kc', '', 1), 67.0, 2);
near('72o vs 1人 ≈34.6%', eq('7c 2d', '', 1), 34.6, 2);
near('AA vs 4人 ≈55.9%', eq('Ac Ad', '', 4), 55.9, 2.5);
near('22 vs 1人 ≈50.3%', eq('2c 2d', '', 1), 50.3, 2);
// 翻牌后:同花听牌(9补牌)在翻牌圈对1人,AhKh在QhTh2c上 vs 随机 应该很高(顶级听牌+高牌)
const flopEq = eq('Ah Kh', 'Qh Th 2c', 1);
check('坚果同花+顺子+高牌听牌 vs 随机 >70% (' + flopEq.toFixed(1) + '%)', flopEq > 70);
// 河牌圈已定: 坚果同花 vs 1人 = 100%赢或极高
const riverEq = eq('Ah Kh', 'Qh Th 2h 3c 8d', 1);
check('河牌坚果同花 ≈100% (' + riverEq.toFixed(1) + '%)', riverEq > 99);

// 性能
const t0 = Date.now();
simulate(hand('Ac Kc'), hand('Qh Th 2c'), 3, 10000);
const ms = Date.now() - t0;
check('1万次×3对手 <500ms (' + ms + 'ms)', ms < 500);

console.log(`\n通过 ${pass} / ${pass + fail}`);
if (fail > 0) process.exit(1);
