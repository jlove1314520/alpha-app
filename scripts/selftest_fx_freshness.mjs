// 先.一三五-1mp（2026-11-07）自測：資料健康頁「匯率 USD/TWD」改用 usd_twd.date 對台股交易日判新鮮。
// 用法：先跑 python scripts/ensure_smoke_server.py，再 node scripts/selftest_fx_freshness.mjs
// ① 直接呼叫 _freshnessJudgeDataDate() 餵固定 now；② 用 Playwright 攔截 data/fx.json 換成假檔，確認畫面那一列變成非綠。
import { chromium } from "@playwright/test";
const URL = process.argv[2] || "http://localhost:8792/";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ serviceWorkers: "block" });  // SW 會攔掉 data/*.json，page.route 看不到
const page = await ctx.newPage();
// 先.一三五-1mq（2026-11-08）：同一套畫面檢查也套到 data/market_tw.json（data_date）
const fakes = {};
for (const f of ["fx", "market_tw", "strategy_performance"]) await page.route(new RegExp("data/" + f + "\\.json"), r => fakes[f] ? r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakes[f]) }) : r.continue());
await page.addInitScript(() => { window.__ALPHA_FETCH_MEMCACHE_OFF = true; });  // 60 秒記憶體快取會讓假檔換不進去
await page.goto(URL, { waitUntil: "load" });
await page.evaluate(() => go("settings"));
await page.waitForFunction(() => typeof _freshnessJudgeDataDate === "function", null, { timeout: 30000 });
const cases = [
  // [資料日期, 台北現在時間, 期望]
  // 10/23 臨時休市、10/26 休市（trading_calendar.json），所以 10/22 之後第一個交易日是 10/27
  ["2026-10-22", "2026-10-26T19:00:00+08:00", "ok"],      // 休市日不算落後
  ["2026-10-22", "2026-10-27T10:00:00+08:00", "ok"],      // 交易日 18:00 前允許前一交易日
  ["2026-10-22", "2026-10-27T19:00:00+08:00", "overdue"], // 18:00 後須是當日
  ["2026-10-22", "2026-10-29T19:00:00+08:00", "overdue"], // 停 3 交易日（10/27、10/28、10/29）
  ["2026-11-06", "2026-11-07T12:00:00+08:00", "ok"],      // 週六看週五
  ["2026-11-06", "2026-11-09T10:00:00+08:00", "ok"],      // 週一盤中看上週五
  ["2026-11-05", "2026-11-09T10:00:00+08:00", "overdue"], // 落後 2 交易日
  ["bad", "2026-11-09T10:00:00+08:00", "missing"],
];
let fail = 0;
for (const [d, now, want] of cases) {
  const got = await page.evaluate(([d, now]) => _freshnessJudgeDataDate(d, new Date(now)), [d, now]);
  const ok = got.status === want; if (!ok) fail++;
  console.log(`${ok ? "PASS" : "FAIL"} 資料日 ${d} @ ${now} → ${got.status}（期望 ${want}）｜${got.rule}`);
}
// 畫面：假檔 fetched_at=現在（舊邏輯會判綠），資料日停在 3 個交易日以前 → 要非綠
const stale = await page.evaluate(() => {
  let n = 0, c = new Date(Date.now()), out = null;
  for (let i = 0; i < 20 && n < 4; i++) { c = new Date(c.getTime() - 864e5); if (isTradingDay(c, "Asia/Taipei", TW_HOLIDAYS)) { n++; out = c; } }
  const z = _zonedParts(out, "Asia/Taipei"); return _ymd(z);
});
const TARGETS = [
  ["fx", "data/fx.json", dd => ({ fetched_at: new Date().toISOString(), errors: [], usd_twd: { rate: 32.0, date: dd, source: "selftest" } })],
  ["market_tw", "data/market_tw.json", dd => ({ fetched_at: new Date().toISOString(), data_date: dd, expected_trading_day: dd, source: "selftest" })],
  // 先.一三五-1mr（2026-11-08）：策略前向紙上績效看 as_of_trading_date
  ["strategy_performance", "data/strategy_performance.json", dd => ({ generated_at: new Date().toISOString(), as_of_trading_date: dd, strategies: [] })],
];
for (const [key, file, mk] of TARGETS) {
  for (const [label, date, want] of [["停滯", stale, "overdue"], ["正常（今天往前最近交易日）", null, "ok"]]) {
    const dd = date || await page.evaluate(() => { const h = _zonedParts(new Date(), "Asia/Taipei").h; let c = new Date(); for (let i = 0; i < 20; i++) { const td = isTradingDay(c, "Asia/Taipei", TW_HOLIDAYS); if (td && !(i === 0 && h < 18)) return _ymd(_zonedParts(c, "Asia/Taipei")); c = new Date(c.getTime() - 864e5); } });
    for (const k of Object.keys(fakes)) delete fakes[k];
    fakes[key] = mk(dd);
    await page.evaluate(() => loadDataFreshness());
    const st = await page.evaluate(f => { const el = document.querySelector(`.fresh-row[data-file="${f}"]`); return el ? el.dataset.status + "｜" + el.innerText.replace(/\s+/g, " ") : null; }, file);
    const ok = st && st.startsWith(want); if (!ok) fail++;
    console.log(`${ok ? "PASS" : "FAIL"} 畫面 ${file} ${label}（資料日 ${dd}）→ ${st}`);
  }
}
await browser.close();
console.log(fail ? `FAIL ${fail} 項` : "全部 PASS");
process.exit(fail ? 1 : 0);
