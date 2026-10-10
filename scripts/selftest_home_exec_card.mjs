// 常備.開發-11 自測：首頁「真錢執行總覽卡」的 autoPeriodSummary() 純函式。
// 從 app.js（常備.開發-20 拆檔後；找不到再退回 index.html）依 <auto-period-selftest> 標記抽出整段（含顯示對照表與 autoNextText），不連網、不開瀏覽器、
// 不碰任何真錢帳本。覆蓋「無紀錄／部分成交／全部成交」三態，另加「整批被擋（未入金）」與「緊急停止」的白話原因。
// 用法：node scripts/selftest_home_exec_card.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
// 常備.開發-20 把內嵌腳本拆到 app.js：先讀 app.js，再接 index.html，兩處都找得到標記段
const html = ["app.js", "index.html"].filter(f => fs.existsSync(path.join(root, f))).map(f => fs.readFileSync(path.join(root, f), "utf8")).join(String.fromCharCode(10));
const m = /\/\/ <auto-period-selftest>[^\n]*\n([\s\S]*?)\/\/ <\/auto-period-selftest>/.exec(html);
if (!m) { console.log("FAIL 找不到 <auto-period-selftest> 標記段"); process.exit(1); }
const api = new Function(m[1] + "\nreturn {autoPeriodSummary,autoPeriodBatchLabel};")();

const results = [];
const check = (name, ok, detail = "") => { results.push(!!ok); console.log((ok ? "PASS " : "FAIL ") + name + (ok || !detail ? "" : "：" + detail)); };

const st = (extra = {}) => ({ mode: "LIVE_WITH_VETO", stopped: false, status: {}, next_tranche: 2, tranche_total: 4,
  next_run: { date: "2026-10-15", time: "09:05", reason: "first_tranche" }, live_account: { empty: true }, ...extra });

// ① 無紀錄
let v = api.autoPeriodSummary(st(), { rows: [] });
check("無紀錄 → state=none、送出 0、成交比例 null", v.state === "none" && v.n_sent === 0 && v.fill_pct === null, JSON.stringify(v));
check("無紀錄 → 權重說明「尚無成交」、下一期含 10/15 與第 2／4 期", /尚無成交/.test(v.deviation_note) && /10\/15/.test(v.next) && /第 2／4 期/.test(v.next), v.deviation_note + " | " + v.next);
check("無紀錄且兩端點都空（null）也不拋錯", api.autoPeriodSummary(null, null).state === "none");

// ② 部分成交（一筆全成、一筆部分、另有撤單測試列不得算進本期）
const partialRows = [
  { date: "2026-10-12", symbol: "0050", qty: 1000, filled_qty: 1000, avg_price: 100, status: "FILLED", reason_codes: [], batch: "202610-T2" },
  { date: "2026-10-12", symbol: "00646", qty: 500, filled_qty: 200, avg_price: 50, status: "PARTIAL", reason_codes: [], batch: "202610-T2" },
  { date: "2026-10-13", symbol: "0050", qty: 1, filled_qty: 0, status: "CANCELLED", reason_codes: [], batch: "撤單測試" },
  { date: "2026-10-08", symbol: "全部", qty: 0, filled_qty: 0, status: "REJECT", reason_codes: ["INSUFFICIENT_CASH"], batch: "202610-T1" },
];
const la = { empty: false, holdings: [{ symbol: "0050", pct: 72.5, target_pct: 70, dev_pp: 2.5 }, { symbol: "00646", pct: 27.5, target_pct: 30, dev_pp: -2.5 }] };
v = api.autoPeriodSummary(st({ live_account: la }), { rows: partialRows });
check("部分成交 → state=partial、本期 202610-T2（撤單測試不算）", v.state === "partial" && v.batch === "202610-T2", JSON.stringify(v));
check("部分成交 → 送出 2 筆、成交 1200／1500 股＝80%", v.n_sent === 2 && v.filled_qty === 1200 && v.qty === 1500 && v.fill_pct === 80, `${v.n_sent} ${v.filled_qty}/${v.qty} ${v.fill_pct}`);
check("部分成交 → 期別白話「2026/10 第 2 期」、送單日 2026-10-12", v.period === "2026/10 第 2 期" && v.send_date === "2026-10-12", v.period + " " + v.send_date);
check("部分成交 → 權重偏離兩檔（+2.5／-2.5pp）", v.deviation.length === 2 && v.deviation[0].dev === 2.5 && v.deviation[1].dev === -2.5);

// ③ 全部成交（月底批次）
v = api.autoPeriodSummary(st({ live_account: la }), { rows: [
  { date: "2026-10-30", symbol: "0050", qty: 300, filled_qty: 300, status: "FILLED", reason_codes: [], batch: "202610-M" },
  { date: "2026-10-30", symbol: "00646", qty: 100, filled_qty: 100, status: "FILLED", reason_codes: [], batch: "202610-M" },
  ...partialRows] });
check("全部成交 → state=full、100%、期別「月底再平衡」", v.state === "full" && v.fill_pct === 100 && v.period === "2026/10 月底再平衡" && v.reasons.length === 0, JSON.stringify(v));

// ④ 整批被擋（未入金）：白話原因、不重複列「現金不足」代碼
v = api.autoPeriodSummary(st({ status: { last_error: "INSUFFICIENT_CASH:交割戶可用餘額 0 元，本批需 300,000 元；入金後次一交易日 09:05 自動重跑" } }),
  { rows: [partialRows[3]] });
check("未入金 → state=blocked、送出 0、原因白話含「尚未入金」與引擎說明", v.state === "blocked" && v.n_sent === 0 && v.reasons.length === 1 && /尚未入金/.test(v.reasons[0]) && /09:05/.test(v.reasons[0]), JSON.stringify(v.reasons));

// ⑤ 緊急停止＋拒單代碼
v = api.autoPeriodSummary(st({ stopped: true }), { rows: [{ date: "2026-10-12", symbol: "0050", qty: 1000, filled_qty: 0, status: "REJECT", reason_codes: ["STOP_FLAG"], batch: "202610-T2" }] });
check("緊急停止 → 原因含「緊急停止」與代碼白話", v.reasons.some(r => /緊急停止開關/.test(r)) && v.reasons.some(r => /被擋原因：緊急停止/.test(r)), JSON.stringify(v.reasons));

const ok = results.every(Boolean);
console.log(`\n${ok ? "全部通過" : "有 FAIL"}（${results.filter(Boolean).length}/${results.length}）`);
process.exit(ok ? 0 : 1);
