// 先.一三五-1gc（2026-11-01）：App 前端 _zonedParts／usMarketSession 跨美國夏令時間切換自測。
// 直接從 app.js 原文切出這兩個函式（不複製邏輯），餵台北時間的瞬間，確認美東盤別跟著 EDT／EST 平移。
// 不開瀏覽器、不連網；US_HOLIDAYS／usCloseMin 用假的（只測時區換算，不測休市表）。
// 用法：node scripts/selftest_app_zoned_dst.mjs
import { readFileSync } from 'node:fs';
const src = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
function cut(name) {
  const i = src.indexOf(`function ${name}(`);
  if (i < 0) throw new Error(`app.js 找不到 ${name}`);
  let depth = 0, j = src.indexOf('{', i);
  for (; j < src.length; j++) { if (src[j] === '{') depth++; else if (src[j] === '}' && --depth === 0) break; }
  return src.slice(i, j + 1);
}
const US_HOLIDAYS = new Set(['2026-11-26']);
const usCloseMin = () => 16 * 60;
const _usEtYmd = z => `${z.y}-${String(z.m).padStart(2, '0')}-${String(z.d).padStart(2, '0')}`;
const recordGlobalError = () => {};
const _zonedParts = new Function(`return (${cut('_zonedParts')})`)();
const usMarketSession = new Function('US_HOLIDAYS', 'usCloseMin', '_usEtYmd', 'recordGlobalError',
  `return (${cut('usMarketSession')})`)(US_HOLIDAYS, usCloseMin, _usEtYmd, recordGlobalError);
const tw = s => new Date(`${s}+08:00`);
const cases = [
  ['EDT：10/30 台北 21:35＝美東 09:35 盤中', '2026-10-30T21:35', 'regular'],
  ['EDT：10/31 台北 04:05＝美東 10/30 16:05 盤後', '2026-10-31T04:05', 'post'],
  ['切換當天 11/01(日) 台北 14:00 → 休市', '2026-11-01T14:00', 'closed'],
  ['EST：11/02 台北 21:35＝美東 08:35 盤前（EDT 時會是盤中）', '2026-11-02T21:35', 'pre'],
  ['EST：11/02 台北 22:35＝美東 09:35 盤中', '2026-11-02T22:35', 'regular'],
  ['EST：11/03 台北 04:55＝美東 15:55 盤中（EDT 時會是盤後）', '2026-11-03T04:55', 'regular'],
  ['EST：11/03 台北 05:05＝美東 16:05 盤後', '2026-11-03T05:05', 'post'],
  ['EST：11/03 台北 17:05＝美東 04:05 盤前', '2026-11-03T17:05', 'pre'],
  ['EST：11/26 感恩節 台北 23:00 → 休市', '2026-11-26T23:00', 'closed'],
  ['EDT 重新開始：2027-03-15 台北 21:35＝美東 09:35 盤中', '2027-03-15T21:35', 'regular'],
];
let bad = 0;
for (const [name, t, exp] of cases) {
  const got = usMarketSession(_zonedParts(tw(t), 'America/New_York'));
  const ok = got === exp; if (!ok) bad++;
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : `（實得 ${got}）`}`);
}
console.log(`合計 ${cases.length} 項，失敗 ${bad}`);
process.exit(bad ? 1 : 0);
