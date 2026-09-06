// 實測.二.補.3 驗收腳本：當日曲線必須從 09:00 開盤起算
//
// 這一項沒辦法在收盤時段驗——要驗的正是「常駐行程晚啟動、股票晚訂閱，曲線第一根
// 仍然是 09:00～09:01」，收盤時沒有當日 K 可以比對。所以做成一支可以在週一盤中
// 直接跑的腳本。
//
// 【操作步驟（總司令或我在週一盤中執行）】
//   1. 09:15（刻意晚於開盤）啟動常駐行程：
//        cd C:\alpha\alpha-app\research
//        python shioaji_quotes.py
//   2. 確認 live server 有在跑（8001）。
//   3. 09:20 把一檔冷門股加進動態訂閱（模擬使用者當下新增自選股）：
//        curl -X POST http://127.0.0.1:8001/subscribe ^
//          -H "Content-Type: application/json" ^
//          -H "X-Alpha-Local-Token: <token>" ^
//          -d "{\"codes\":[\"2330\",\"6158\"]}"
//   4. 09:30 之後跑這支腳本：
//        node scripts/kbars_open_check.mjs
//
// 驗收條件（任一不符就 FAIL）：
//   - 早啟動的代號（2330）與晚訂閱的冷門股，第一根都必須 ≤ 09:01
//   - 中間不得有超過 3 分鐘的缺口
//   - 當日 api.kbars() 呼叫次數必須遠低於官方盤中上限 270
import fs from "fs";
import path from "path";
import { chromium } from "@playwright/test";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, "$1"), "..");
const LIVE = process.env.ALPHA_LIVE_URL || "http://127.0.0.1:8001";
const APP = process.env.ALPHA_APP_URL || "http://127.0.0.1:8792/index.html";
// 預設驗兩檔：2330（啟動時就在固定清單裡）與 6158 禾昌（冷門上櫃股，模擬盤中才加）
const CODES = (process.env.ALPHA_CHECK_CODES || "2330,6158").split(",").map(s => s.trim());

function token() {
  const p = path.join(ROOT, "research", ".alpha_live_token");
  if (!fs.existsSync(p)) throw new Error(`找不到 ${p}，先啟動一次 alpha_live_server.py`);
  return fs.readFileSync(p, "utf8").trim();
}

const T = token();
const hdr = { "X-Alpha-Local-Token": T };
let fails = 0;
const say = (ok, msg) => { if (!ok) fails++; console.log(`${ok ? "PASS" : "FAIL"} - ${msg}`); };

const minuteOf = b => String(b.t || b.ts || "").slice(11, 16);

for (const code of CODES) {
  const r = await fetch(`${LIVE}/live/kbars?code=${code}`, { headers: hdr });
  if (!r.ok) { say(false, `${code} 取 /live/kbars 失敗：HTTP ${r.status}`); continue; }
  const d = await r.json();
  const bars = d.bars || [];
  if (!bars.length) { say(false, `${code} 沒有任何 bar（mode=${d.mode}）`); continue; }
  const first = minuteOf(bars[0]);
  const last = minuteOf(bars[bars.length - 1]);
  say(first <= "09:01", `${code} 第一根是 ${first}（要求 ≤ 09:01）｜最後一根 ${last}｜${bars.length} 根｜mode=${d.mode}${d.backfill ? "｜" + d.backfill : ""}`);

  let worstGap = 0, worstAt = "";
  for (let i = 1; i < bars.length; i++) {
    const a = minuteOf(bars[i - 1]), b = minuteOf(bars[i]);
    const ta = +a.slice(0, 2) * 60 + +a.slice(3), tb = +b.slice(0, 2) * 60 + +b.slice(3);
    if (tb - ta > worstGap) { worstGap = tb - ta; worstAt = `${a}→${b}`; }
  }
  say(worstGap <= 3, `${code} 最大缺口 ${worstGap} 分鐘${worstAt ? "（" + worstAt + "）" : ""}（要求 ≤ 3）`);
}

const h = await (await fetch(`${LIVE}/health`, { headers: hdr })).json();
const u = h.kbars_usage || {};
say((u.calls_today ?? 0) < 270,
  `當日 api.kbars() 呼叫 ${u.calls_today ?? "?"} 次（自訂上限 ${u.daily_budget ?? "?"}、官方盤中上限 270）`);
console.log(`動態訂閱：${JSON.stringify(h.dynamic_subscriptions || {})}`);

// 截圖：把 live server 設進 App，畫面上應該看到當日曲線
const browser = await chromium.launch();
const page = await (await browser.newContext({ viewport: { width: 393, height: 852 } })).newPage();
await page.goto(APP, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(1200);
await page.evaluate(([u, t, cs]) => {
  localStorage.setItem("alpha_live_url", u);
  localStorage.setItem("alpha_live_token", t);
  localStorage.setItem("alpha_wl", JSON.stringify(cs));
}, [LIVE, T, CODES]);
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(9000);
const shot = path.join(ROOT, "kbars_open_check.png");
await page.screenshot({ path: shot });
console.log(`截圖：${shot}`);
await browser.close();

console.log(fails ? `\n${fails} 項 FAIL` : "\n全部通過");
process.exit(fails ? 1 : 0);
