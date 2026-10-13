// App 冒煙測試（2026-08-27 新增，使用者要求「每次改完自己跑」）。
//
// 這是使用者原始規格要的 Node.js + Playwright 版本——`scripts/smoke_test.py`
// 是這台機器當時還沒裝 Node.js 時的替代版本（內容/檢查項目完全對應，只是
// 執行環境不同），2026-08-27（續8）這台機器已經裝好 Node.js（`winget install
// OpenJS.NodeJS.LTS`）+ `@playwright/test`（`npm install --save-dev`），改用
// 這支 .mjs 版本為主——兩支腳本現在都在，先跑哪支都可以，之後如果要精簡再議。
//
// 用法：`node scripts/smoke_test.mjs`（預設打 http://localhost:8792，需要先
// 在repo根目錄另開一個終端機跑 `python -m http.server 8792`；也可以用
// --url 指定別的位址）。每次commit前務必先跑一次，任一項FAIL就不要commit，
// 先修好（使用者原話）。
//
// 檢查項目（逐條對應使用者規格，跟 smoke_test.py 完全一致）：
// 1. 頁面載入無uncaught error / unhandledrejection。
// 2. 右上角時鐘的updateClocks() interval在3秒內確實被呼叫多次（monkeypatch
//    計數，不是看畫面文字有沒有變——休市時文字設計上是靜態的資料時間戳）。
// 3. 六個分頁（今日/市場/選股/交易/日誌/設定）都能切換且不拋錯。
// 4. 每個主要面板（已知容器id清單）渲染後innerHTML不是空的。
// 5. 市場頁三個市場切換（台股/美股/期貨）都不拋錯。
// 6. 互動元素可點擊性（類股卡/選股排行列/自選股列）。
// 7. 6a已併入，見下方7實為互動後仍無累積錯誤——實際check編號見程式內record()。
// 8.【2026-08-28新增】每個「重新整理」按鈕點擊後都會觸發實際網路請求（不是
//    只驗證不拋錯——onclick繫結斷掉時點下去既不拋錯也沒有任何反應，這正是
//    使用者回報「按鈕按不動」的真實樣態，只看uncaught error測不出來）。
// 9.【2026-08-28新增】模擬手機已裝舊版Service Worker快取（塞一份竄改過的假
//    index.html進CacheStorage），驗證network-first邏輯不會被舊快取覆蓋。
// 11.【2026-08-28新增】pull-to-refresh下拉手勢（合成touch事件）會觸發實際
//     網路請求。
// 13.【2026-08-28新增，P0-a，第6次時鐘問題永久斷言】頁面用fmtTzHHMM()換算
//     出來的台北/紐約時間，跟測試機自己用Intl.DateTimeFormat算出的當下
//     時間相差≤2分鐘——直接測時區轉換函式本身，不依賴裝置本地時區。
// 14.【2026-08-28新增，P0-b永久斷言】每個「重新整理」按鈕都帶有共用的
//     refresh-btn金色樣式class，不是靠巧合套到某個巢狀CSS選擇器。
// 15.【2026-09-02新增】用route攔截餵一份時間戳是「現在」的真實結構假資料
//     （今日事件卡片），確認對應面板真的把它畫出來，不是卡在SW快取住的
//     舊殼/渲染函式壞掉但沒拋錯的空狀態——「資料新鮮卻顯示無資料」防線。
// 16.【2026-09-02新增，同一精神但針對「圖」】用route攔截餵一份有效、至少2個
//     資料點的假sparkline/equity_curve資料，確認對應<svg>裡真的畫出了
//     <polyline>（points屬性不是空字串），不是只驗面板innerHTML非空——那樣
//     測不出「面板有文字但沒有真的畫線」這種情況（見2026-09-02圖表診斷任務
//     發現的櫃買指數sparkline漏傳bug，這條防線就是為了防止同類問題復發）。
// 17.【2026-09-02新增，B29美股個股頁財報UI】route攔截假us_financials.json，
//     驗有快照代號（AAPL）財報頁四指標真的畫出數字、無快照代號（TSLA）誠實
//     顯示「暫無」且不殘留切換前那檔股票的舊數字。
// 18.【2026-09-02新增，IBKR Paper下單UI卡片】驗美股/台股買進按鈕分工正確
//     （美股開真的IBKR下單卡片、台股維持示範版，不能混）、伺服器未啟動時
//     連線狀態有清楚提示、沒填token前端會擋下送出。
// 19.【2026-09-02新增，即時價格四修】route攔截假us_financials.json…（見
//     19號check本體）驗Yahoo備援指數正確標「Yahoo 延遲~15分」。
// 20.【2026-09-02新增，籌碼頁重新配置】市場頁籌碼入口卡摘要數字+點進去
//     完整市場籌碼總覽頁都正確渲染。
// 21.【2026-09-02新增，使用者原話「四大美股指數報價不得為null」】用實測
//     真實資料結構當fixture，驗四大美股指數在市場頁全部顯示數字，不是
//     任何一個「—」。
// 12. 整個測試過程（含8/9/11/13/14/15/16/17/18/19/20/21新增的重整/
//     reload/手勢/時區/防線操作）結束後仍無累積的uncaught error。
// 47/48.【2026-09-15新增，金流一.6驗收】data/sector_flow.json 兩條資料一致性
//     稽核：47每個產業合計＝成分股加總（容差1股）；48 meta.date必須等於
//     data/institutional_history.json（T86來源）的最新日期。

import { chromium } from "@playwright/test";
import { launchGuarded } from "./pw_guard.mjs";

const TABS = ["home", "market", "picks", "trade", "journal", "settings"];

// 跟 smoke_test.py 的 PANEL_IDS 保持一致。
const PANEL_IDS = [
  "wl-list", "home-idx-rows",
  "idx-rows", "heatmap", "inst-bars",
  "margin-summary",
  "picks-list",
];

function parseArgs() {
  const args = process.argv.slice(2);
  let url = "http://localhost:8792";
  let headed = false;
  let jsonOut = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--url") url = args[++i];
    if (args[i] === "--headed") headed = true;
    if (args[i] === "--json-out") jsonOut = args[++i];
  }
  return { url, headed, jsonOut };
}

// 常備.開發-27（2026-10-11）：雲端夜間冒煙（.github/workflows/smoke_cloud.yml）用 --json-out 把結果寫成
// data/smoke_cloud.json 給設定頁讀。只存結論與失敗項（不存全部 PASS 明細，檔案保持小）；
// 測試本身崩潰也要寫一份 crashed=true 的檔，不能讓「沒檔案更新」被誤讀成「沒出事」。
async function writeJsonOut(jsonOut, url, results, crashError = null) {
  if (!jsonOut) return;
  try {
    const fsw = await import("node:fs");
    const checks = (results && results.checks) || [];
    const env = process.env;
    const out = {
      generated_at: new Date().toISOString(),
      url,
      all_passed: !crashError && !!(results && results.all_passed),
      crashed: !!crashError,
      crash_error: crashError ? String(crashError.stack || crashError).slice(0, 2000) : null,
      total: checks.length,
      passed: checks.filter(c => c.passed).length,
      failed: checks.filter(c => !c.passed).length,
      failures: checks.filter(c => !c.passed).map(c => ({ name: c.name, detail: String(c.detail || "").slice(0, 600) })),
      global_errors_final: (results && results.global_errors_final) || [],
      run_url: env.GITHUB_RUN_ID ? `${env.GITHUB_SERVER_URL}/${env.GITHUB_REPOSITORY}/actions/runs/${env.GITHUB_RUN_ID}` : null,
      commit: env.GITHUB_SHA ? env.GITHUB_SHA.slice(0, 9) : null,
    };
    fsw.writeFileSync(jsonOut, JSON.stringify(out, null, 1) + "\n", "utf8");
    console.log(`已寫入 ${jsonOut}（${out.passed}/${out.total} 通過${out.crashed ? "，測試本身崩潰" : ""}）`);
  } catch (e) {
    console.error(`寫入 ${jsonOut} 失敗：`, e);
  }
}

async function runSmokeTest(baseUrl, headless = true) {
  const results = { checks: [], all_passed: true };
  const record = (name, passed, detail = "") => {
    results.checks.push({ name, passed, detail });
    if (!passed) results.all_passed = false;
    console.log(`${passed ? "PASS" : "FAIL"} - ${name}${detail ? "：" + detail : ""}`);
  };

  // 先.七十-3：launchGuarded＝try/finally 必關瀏覽器、close 超過 30 秒強制結束、整體 25 分鐘硬上限、被砍也會先關。
  const { browser, close: closeBrowser } = await launchGuarded(chromium, { headless }, { label: "smoke_test", hardTimeoutMs: 25 * 60 * 1000 });
  try {
  // 2026-09-04（HTTPS方案A第二階段，先寫好不切換）：自簽憑證正式啟用後，這支測試若要
  // 連alpha_live_server.py的https端點，Playwright預設會因為不認得自簽CA而擋掉——加
  // ignoreHTTPSErrors讓瀏覽器層面忽略憑證信任錯誤（跟手機端「安裝CA後瀏覽器自然信任」
  // 不衝突，這裡純粹是測試環境的等效繞過，不影響手機端的真實信任鏈驗證）。目前伺服器
  // 仍是HTTP（ENABLE_HTTPS預設false），這個選項現在是no-op，先寫好等總司令核准切換。
  const page = await browser.newPage({ viewport: { width: 393, height: 852 }, ignoreHTTPSErrors: true });

  const pageErrors = [];
  page.on("pageerror", (exc) => pageErrors.push(String(exc)));
  // 先.六十九-1：主頁面的多項檢查會在同一頁內換假資料再重抓，關掉 App 的 60 秒資料記憶體快取；
  // 記憶體快取本身由 #90 在獨立 context（不關）實測。
  await page.addInitScript(() => { window.__ALPHA_FETCH_MEMCACHE_OFF = true; });

  await page.goto(`${baseUrl}/index.html`, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(1500);

  // 1. 無uncaught error / unhandledrejection——直接讀index.html自己的
  // GLOBAL_ERRORS（recordGlobalError()攔截window.onerror/unhandledrejection
  // 填進去的陣列）。這是`let`宣告的頂層變數，不會變成window的屬性，但
  // page.evaluate()執行的context看得到頁面的頂層詞法綁定，跟直接在
  // DevTools console打字一樣，用typeof檢查存在再讀。
  const globalErrors = await page.evaluate(
    "typeof GLOBAL_ERRORS !== 'undefined' ? GLOBAL_ERRORS : []"
  );
  record(
    "1. 頁面載入無uncaught error/unhandledrejection",
    globalErrors.length === 0 && pageErrors.length === 0,
    globalErrors.length || pageErrors.length
      ? `GLOBAL_ERRORS=${JSON.stringify(globalErrors)}, pageerror=${JSON.stringify(pageErrors)}`
      : ""
  );

  // 2. 時鐘interval真的在跑（monkeypatch計數，不是看文字有沒有變）
  await page.evaluate(() => {
    window.__clockCallCount = 0;
    const orig = window.updateClocks;
    window.updateClocks = function () {
      window.__clockCallCount++;
      return orig();
    };
  });
  await page.waitForTimeout(3200);
  const callCount = await page.evaluate(() => window.__clockCallCount);
  record(
    "2. 右上角時鐘interval在3秒內有執行",
    callCount >= 2,
    callCount < 2 ? `3.2秒內只呼叫了${callCount}次，預期至少2次（每秒一次）` : `呼叫了${callCount}次`
  );

  // 3. 六個分頁都能切換且不拋錯
  const tabErrors = [];
  for (const t of TABS) {
    try {
      await page.evaluate((tab) => window.go(tab), t);
      await page.waitForTimeout(400);
    } catch (e) {
      tabErrors.push(`${t}: ${e}`);
    }
  }
  record("3. 六個分頁都能切換且不拋錯", tabErrors.length === 0, tabErrors.join("; "));

  // 4. 每個主要面板innerHTML不是空的
  await page.evaluate(() => window.go("home"));
  await page.waitForTimeout(800);
  await page.evaluate(() => window.go("market"));
  await page.waitForTimeout(800);
  await page.evaluate(() => window.go("picks"));
  await page.waitForTimeout(800);
  const emptyPanels = [];
  for (const pid of PANEL_IDS) {
    const html = await page.evaluate((id) => {
      const el = document.getElementById(id);
      return el ? el.innerHTML.trim() : null;
    }, pid);
    if (html === null) continue; // 這個id在目前分頁不存在，不算失敗
    if (html === "") emptyPanels.push(pid);
  }
  record("4. 主要面板都有內容（不是完全空白）", emptyPanels.length === 0,
    emptyPanels.length ? `完全空白的面板：${JSON.stringify(emptyPanels)}` : "");

  // 5. 市場頁三個市場切換都不拋錯
  await page.evaluate(() => window.go("market"));
  await page.waitForTimeout(400);
  // 注意：MKT_STATE是`<script>`頂層用let/const宣告的變數，不會變成window的
  // 屬性（跟smoke_test.py發現的GLOBAL_ERRORS同一件事）——page.evaluate傳函式
  // 進去時，函式內容會在頁面context被序列化執行，對「裸的」頂層詞法綁定一樣
  // 看得到，所以這裡故意不寫`window.MKT_STATE`（那樣會是undefined）。
  const marketErrors = [];
  for (const m of ["TW", "US", "FUT"]) {
    try {
      await page.evaluate(async (market) => {
        MKT_STATE.market = market;
        await hydrateMarket();
      }, m);
      await page.waitForTimeout(400);
    } catch (e) {
      marketErrors.push(`${m}: ${e}`);
    }
  }
  record("5. 市場頁三個市場切換都不拋錯", marketErrors.length === 0, marketErrors.join("; "));

  // 6. 【2026-08-27新增，使用者要求】互動元素可點擊性檢查——逐一模擬點擊，
  // 確認有對應反應（開頁/開清單），沒反應即視為失敗。跟前5項不同：前5項是
  // 「不拋錯」，這項是「真的有效果」，用點擊前後的DOM狀態差異來判斷，不能
  // 只看有沒有uncaught error（onclick繫結錯誤/沒繫結都不會拋錯，但也不會有
  // 任何反應，是使用者這次B4類股卡回報過的真實案例）。
  const interactionErrors = [];
  // 6a. 類股卡（市場頁已經在上面切換過，MKT_STATE.market目前是FUT，先切回TW）
  await page.evaluate(async () => { MKT_STATE.market = "TW"; await hydrateMarket(); });
  await page.waitForTimeout(600);
  try {
    const tileCount = await page.evaluate(() => document.querySelectorAll("#heat-grid .tile").length);
    if (tileCount === 0) throw new Error("找不到任何類股卡（#heat-grid .tile），可能資料沒載入");
    await page.evaluate(() => document.querySelector("#heat-grid .tile").click());
    await page.waitForTimeout(500);
    const sheetOpen = await page.evaluate(() => document.getElementById("sector-sheet")?.classList.contains("open"));
    if (!sheetOpen) throw new Error("點擊類股卡後 #sector-sheet 沒有開啟，沒有對應反應");
    await page.evaluate(() => window.closeSectorSheet && window.closeSectorSheet());
  } catch (e) {
    interactionErrors.push(`類股卡: ${e.message || e}`);
  }
  // 6b. 選股排行列（picks-list的row，點擊應該打開個股評分報告畫面 #scr-report）
  try {
    await page.evaluate(() => window.go("picks"));
    await page.waitForTimeout(600);
    const rowCount = await page.evaluate(() => document.querySelectorAll("#picks-list .row").length);
    if (rowCount === 0) throw new Error("找不到任何選股排行列（#picks-list .row），可能scores.json沒有合格檔數");
    await page.evaluate(() => document.querySelector("#picks-list .row").click());
    await page.waitForTimeout(500);
    const reportActive = await page.evaluate(() => document.getElementById("scr-report")?.classList.contains("active"));
    if (!reportActive) throw new Error("點擊選股排行列後 #scr-report 沒有變成active，沒有對應反應");
  } catch (e) {
    interactionErrors.push(`選股排行列: ${e.message || e}`);
  }
  // 6c. 自選股列（wl-list的row，點擊應該打開個股頁 #scr-stock）
  try {
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(600);
    const wlRowCount = await page.evaluate(() => document.querySelectorAll("#wl-list .swipe-row").length);
    if (wlRowCount === 0) throw new Error("找不到任何自選股列（#wl-list .swipe-row），可能自選股清單是空的");
    await page.evaluate(() => document.querySelector("#wl-list .swipe-row").click());
    await page.waitForTimeout(500);
    const stockActive = await page.evaluate(() => document.getElementById("scr-stock")?.classList.contains("active"));
    if (!stockActive) throw new Error("點擊自選股列後 #scr-stock 沒有變成active，沒有對應反應");
  } catch (e) {
    interactionErrors.push(`自選股列: ${e.message || e}`);
  }
  record("6. 互動元素可點擊性（類股卡/選股排行列/自選股列）", interactionErrors.length === 0, interactionErrors.join("; "));

  // 2026-08-27修正（真bug，這次B4測試親自抓到）：check#1只在頁面剛載入時
  // 讀一次GLOBAL_ERRORS，之後checks 2-6的互動（尤其是點擊操作）如果觸發新的
  // unhandledrejection，原本這裡只是把finalErrors印出來，從來沒有真的拿它
  // 判斷PASS/FAIL——等於check#1「頁面載入無uncaught error」講的是「載入當下」
  // 而不是「整個測試過程中」，是一個測試框架本身測不出真錯誤的漏洞（跟先前
  // window.GLOBAL_ERRORS vs 裸GLOBAL_ERRORS同一類「測試本身有假陽性風險」問題）。
  // 這次實測：check#1-6全部顯示PASS，但finalErrors裡卻有一筆點擊選股排行列
  // 觸發的真實unhandledrejection（f.chips/f.technical欄位名不符導致.toFixed()
  // 對undefined拋錯）——這就是原本測試框架測不出來的具體案例。現在改成真的
  // 用finalErrors判斷這第7項。
  // 8.【2026-08-28新增，使用者回報「所有重新整理按鈕都按不動」】逐一點擊每個
  // 「重新整理」按鈕，用page.on('request')確認點擊後真的觸發了新的網路請求
  // （不是只看有沒有拋錯——onclick沒繫結到、或繫結到已經改名/刪除的函式，
  // 點下去不會拋錯也不會有任何請求，畫面就是靜靜地什麼都不做，使用者才會
  // 說「按不動」）。
  const requestLog = [];
  page.on("request", (req) => requestLog.push({ url: req.url(), t: Date.now() }));
  const refreshChecks = [
    { tab: "home", selector: '[onclick*="hydrateHome"]' },
    { tab: "market", selector: '[onclick*="hydrateMarket"]:not(#mainstream-refresh)' },
    { tab: "market", selector: "#mainstream-refresh" },
    { tab: "picks", selector: "#picks-refresh" },
  ];
  const refreshErrors = [];
  for (const rc of refreshChecks) {
    try {
      await page.evaluate((tab) => window.go(tab), rc.tab);
      await page.waitForTimeout(500);
      const before = requestLog.length;
      const found = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (!el) return false;
        el.click();
        return true;
      }, rc.selector);
      if (!found) throw new Error(`找不到按鈕（selector=${rc.selector}）`);
      await page.waitForTimeout(900);
      const after = requestLog.length;
      if (after <= before) {
        throw new Error(`點擊後900ms內沒有觸發任何新的網路請求（selector=${rc.selector}），視為按鈕失效`);
      }
    } catch (e) {
      refreshErrors.push(`${rc.tab}/${rc.selector}: ${e.message || e}`);
    }
  }
  record("8. 重新整理按鈕點擊後都會觸發實際網路請求", refreshErrors.length === 0, refreshErrors.join("; "));

  // 9.【2026-08-28 新增（使用者回報「時鐘/資料手機端卡在舊版」第五次）；2026-10-11 先.六十九-1 改寫】
  // 外殼改「快取優先、背景更新、點提示條才換版」後，防「卡在舊版」的保證改成版本切換：舊版快取裡就算塞了竄改內容，
  // 發布新版（sw.js 版本號變）→ 新 SW 背景裝好並等待 → 顯示「有新版」提示條 → 點下去 → 新 SW 接手、舊版快取刪除、
  // 畫面是真內容。用暫存目錄＋內建靜態伺服器跑完整流程（scripts/sw_update_check.mjs），不動工作目錄、不影響主頁面。
  let staleCachePassed = false, staleCacheResult = "";
  try {
    const { checkSwUpdateFlow } = await import("./sw_update_check.mjs");
    const r = await checkSwUpdateFlow(browser);
    staleCachePassed = !!r.ok;
    staleCacheResult = staleCachePassed
      ? `通過：舊版快取（${r.oldCache}，含竄改內容）→ 發布新版後 SW 等待中、提示條顯示 → 點擊換版 → 只剩 ${r.newCache}、畫面為真內容（APP_VERSION=${r.ver}）`
      : `失敗：${JSON.stringify({ waiting: r.waiting, banner: r.banner, keys: r.keys, fake: r.body, controlled: r.controlled })}`;
  } catch (e) {
    staleCacheResult = `執行時發生例外：${e.message || e}`;
  }
  record("9. 舊版快取殘留竄改內容時，發布新版→背景安裝→提示條→點擊換版→舊快取刪除、顯示真內容（先.六十九-1 快取優先）", staleCachePassed, staleCacheResult);

  // 11.【2026-08-28新增】pull-to-refresh手勢——用合成的touch事件模擬「在#main
  // 頂端往下拉超過門檻再放開」，確認會觸發實際網路請求（跟check 8驗證按鈕
  // 用同一個requestLog機制）。
  let ptrError = "";
  try {
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(400);
    const before = requestLog.length;
    await page.evaluate(() => {
      const main = document.getElementById("main");
      main.scrollTo(0, 0);
      const fire = (type, y) => {
        const t = new Touch({ identifier: 0, target: main, clientX: 100, clientY: y });
        main.dispatchEvent(new TouchEvent(type, { touches: type === "touchend" ? [] : [t], changedTouches: [t], bubbles: true, cancelable: true }));
      };
      fire("touchstart", 50);
      fire("touchmove", 200); // 下拉150px，超過PTR_THRESHOLD(64*0.5換算後的門檻)
      fire("touchend", 200);
    });
    await page.waitForTimeout(900);
    const after = requestLog.length;
    if (after <= before) ptrError = "下拉手勢後900ms內沒有觸發任何新的網路請求";
  } catch (e) {
    ptrError = `執行時發生例外：${e.message || e}`;
  }
  record("11. pull-to-refresh下拉手勢會觸發實際網路請求", ptrError === "", ptrError);

  // 13.【2026-08-28根治，P0-a，第6次時鐘問題】前一版只驗fmtTzHHMM()這個
  // 函式本身算得對不對，驗不到「畫面實際顯示的文字」——真因是mktPill()/
  // mktPillUS()把.tm欄位改成顯示data.fetched_at（資料時間，抓價間隔內
  // 完全不動），不是zonedNow(tz).hhmmss（現在時間，每秒動），函式驗證
  // 全綠但畫面看起來就是「時鐘停了/算錯」。改成直接讀#mkt-tw .tm / #mkt-us
  // .tm的textContent跟測試機算出的當下時間比對，並且等1.2秒後再讀一次
  // 確認畫面文字有隨秒數更新（不是只驗開頭那一次的靜態值）。
  function nowHHMMInTz(tz) {
    return new Intl.DateTimeFormat("en-US", { timeZone: tz, hour12: false, hour: "2-digit", minute: "2-digit" }).format(new Date());
  }
  function minutesDiff(hhmmA, hhmmB) {
    const [ha, ma] = hhmmA.split(":").map(Number);
    const [hb, mb] = hhmmB.split(":").map(Number);
    let diff = Math.abs((ha * 60 + ma) - (hb * 60 + mb));
    return Math.min(diff, 1440 - diff); // 跨日邊界（例如23:59 vs 00:00）取較小值
  }
  function readTm(sel) {
    return page.evaluate((s) => {
      const el = document.querySelector(s);
      return el ? el.textContent.trim() : null;
    }, sel);
  }
  const tzErrors = [];
  try {
    const pageTaipei1 = await readTm("#mkt-tw .tm");
    const expectTaipei1 = nowHHMMInTz("Asia/Taipei");
    if (pageTaipei1 === null) tzErrors.push("#mkt-tw .tm 找不到元素");
    else {
      const diff = minutesDiff(pageTaipei1, expectTaipei1);
      if (diff > 2) tzErrors.push(`#mkt-tw .tm: 畫面顯示${pageTaipei1}，測試機算出${expectTaipei1}，相差${diff}分鐘`);
    }

    const pageNY1 = await readTm("#mkt-us .tm");
    const expectNY1 = nowHHMMInTz("America/New_York");
    if (pageNY1 === null) tzErrors.push("#mkt-us .tm 找不到元素");
    else {
      const diff = minutesDiff(pageNY1, expectNY1);
      if (diff > 2) tzErrors.push(`#mkt-us .tm: 畫面顯示${pageNY1}，測試機算出${expectNY1}，相差${diff}分鐘`);
    }

    // 等1.2秒，確認畫面文字真的有隨setInterval(updateClocks,1000)更新，
    // 不是初始化時算一次之後就卡住不動（這正是第1~5次「完全停擺」bug的樣子）。
    await page.waitForTimeout(1200);
    const pageTaipei2 = await readTm("#mkt-tw .tm");
    const expectTaipei2 = nowHHMMInTz("Asia/Taipei");
    if (pageTaipei2 !== null) {
      const diff = minutesDiff(pageTaipei2, expectTaipei2);
      if (diff > 2) tzErrors.push(`#mkt-tw .tm(1.2秒後): 畫面顯示${pageTaipei2}，測試機算出${expectTaipei2}，相差${diff}分鐘`);
    }
  } catch (e) {
    tzErrors.push(`執行時發生例外：${e.message || e}`);
  }
  record("13. 台北/紐約時鐘畫面顯示值跟測試機一致且會隨秒數更新（誤差≤2分鐘，防止裝置本地時區依賴復發）",
    tzErrors.length === 0, tzErrors.join("; "));

  // 14.【2026-08-28新增，P0-b】永久斷言：每個「重新整理」按鈕都存在、可點擊、
  // 且帶有共用的refresh-btn class（不是靠巧合套到某個巢狀CSS選擇器）。
  const refreshBtnClassErrors = [];
  for (const rc of refreshChecks) {
    try {
      await page.evaluate((tab) => window.go(tab), rc.tab);
      await page.waitForTimeout(300);
      const hasClass = await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        return el ? el.classList.contains("refresh-btn") : null;
      }, rc.selector);
      if (hasClass === null) refreshBtnClassErrors.push(`${rc.tab}/${rc.selector}: 找不到元素`);
      else if (hasClass === false) refreshBtnClassErrors.push(`${rc.tab}/${rc.selector}: 存在但沒有refresh-btn class`);
    } catch (e) {
      refreshBtnClassErrors.push(`${rc.tab}/${rc.selector}: ${e.message || e}`);
    }
  }
  record("14. 每個重新整理按鈕都帶有共用的refresh-btn金色樣式class",
    refreshBtnClassErrors.length === 0, refreshBtnClassErrors.join("; "));

  // 15.【2026-09-02新增，使用者原話：「資料檔明明新鮮、App卻顯示無資料=FAIL
  // （SW快取壞殼那類）」】用route攔截餵一份時間戳是「現在」的真實結構假資料，
  // 確認對應面板真的把它畫出來，不是卡在某個舊版殼（例如SW快取住的舊JS
  // 邏輯、或渲染函式已經壞掉但沒有拋錯）而一直停在空狀態/載入中文字。
  const staleShellErrors = [];
  try {
    const freshEarnings = {
      meta: { generated_at: new Date().toISOString(), source: "smoke_test注入" },
      earnings: {
        AAPL: {
          next_earnings_date: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10),
          estimated_session: "post",
        },
      },
    };
    await page.route("**/data/earnings_calendar.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(freshEarnings) })
    );
    await page.evaluate(() => { EARNINGS_CALENDAR_CACHE = null; });
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(1200);
    const eventsHtml = await page.evaluate(() => {
      const el = document.getElementById("today-events");
      return el ? el.innerHTML : null;
    });
    if (eventsHtml === null) staleShellErrors.push("找不到#today-events元素");
    else if (!eventsHtml.includes("AAPL")) {
      staleShellErrors.push(`注入新鮮的earnings_calendar.json後，#today-events沒有顯示AAPL，可能卡在舊殼：${eventsHtml.slice(0, 200)}`);
    }
    await page.unroute("**/data/earnings_calendar.json**");
  } catch (e) {
    staleShellErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("15. 資料檔明明新鮮、App卻顯示無資料=FAIL（SW快取壞殼防線）",
    staleShellErrors.length === 0, staleShellErrors.join("; "));

  // 16.【2026-09-02新增，「圖該顯示卻空白」防線，跟check 15同精神但針對「圖」
  // 這個更具體的情況】只驗面板innerHTML非空測不出「面板有文字但沒有真的畫線」
  // ——2026-09-02圖表診斷任務就抓到一個真實案例：櫃買指數sparkline的資料
  // 物件漏傳sparkline欄位，面板本身照樣正常顯示數字/文字，只有那條線缺席，
  // 純看「面板有沒有內容」完全測不出來。這裡用route攔截餵一份有效、資料點
  // 足夠（至少2個點）的假sparkline/equity_curve資料，直接檢查對應<svg>裡
  // <polyline>的points屬性是不是有實際座標點（不是空字串/不存在）。
  const chartBlankErrors = [];
  try {
    // 16a. 自選股列表sparkline（spark()，讀quotes_tw.json::quotes[code].sparkline）
    const fakeQuotesTw = {
      generated_at: new Date().toISOString(),
      quotes: {
        "2330": {
          name: "台積電", price: 999, prev_close: 990, change: 9, change_pct: 0.91,
          time: "13:30:00", date: "20260101", stale: false,
          sparkline: [980, 985, 990, 995, 999],
        },
      },
    };
    await page.route("**/data/quotes_tw.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeQuotesTw) })
    );
    await page.evaluate(() => {
      // 確保自選股清單至少含2330，且強制重新fetch（不沿用舊快取變數）。
      const wl = JSON.parse(localStorage.getItem("alpha_wl") || "[]");
      if (!wl.includes("2330")) { wl.push("2330"); localStorage.setItem("alpha_wl", JSON.stringify(wl)); }
      INTRADAY_TW = null;
    });
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(1500);
    const wlPolyline = await page.evaluate(() => {
      const el = document.getElementById("wl-list");
      if (!el) return { found: false, reason: "找不到#wl-list" };
      const poly = el.querySelector("svg.spark polyline");
      if (!poly) return { found: false, reason: "沒有svg.spark polyline元素" };
      return { found: true, points: poly.getAttribute("points") };
    });
    if (!wlPolyline.found) chartBlankErrors.push(`自選股sparkline：${wlPolyline.reason}`);
    else if (!wlPolyline.points || !wlPolyline.points.trim()) chartBlankErrors.push(`自選股sparkline：polyline存在但points屬性是空字串`);
    await page.unroute("**/data/quotes_tw.json**");

    // 16b. 策略監控台權益曲線（spark()）。先.八十-6 起監控台改讀 data/strategy_curves.json 的 nav（原 strategies.json::forward_paper 已停用）
    const fakeCurves = {
      meta: { generated_at: new Date().toISOString(), bench: "0050" },
      lines: [{
        id: "smoke_test_fake", label: "冒煙測試假線", group: "paper", status: "模擬中", started: true,
        start_date: "2026-01-01", as_of: "2026-01-04", dates: ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"],
        nav: [100, 101.2, 99.5, 103.5], bench: [100, 100.5, 100.1, 101], comp_max_abs_pct: [],
        metrics: { days: 4, cum_pct: 3.5, bench_cum_pct: 1.0, mdd_pct: -1.7, bench_mdd_pct: -0.4, verdict: "尚不足以判斷" },
        note: "冒煙測試注入，非真實策略",
      }],
    };
    await page.route("**/data/strategy_curves.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeCurves) })
    );
    await page.evaluate(() => window.go("trade"));
    await page.waitForTimeout(300);
    await page.evaluate(() => {
      const b = [...document.querySelectorAll("#trade-tabs button")].find(x => x.dataset.sub === "monitor");
      if (b) b.click();
    });
    await page.waitForTimeout(1200);
    const monitorPolyline = await page.evaluate(() => {
      const el = document.getElementById("strategy-monitor-list");
      if (!el) return { found: false, reason: "找不到#strategy-monitor-list" };
      const poly = el.querySelector("svg.spark polyline");
      if (!poly) return { found: false, reason: "沒有svg.spark polyline元素" };
      return { found: true, points: poly.getAttribute("points") };
    });
    if (!monitorPolyline.found) chartBlankErrors.push(`策略監控台權益曲線：${monitorPolyline.reason}`);
    else if (!monitorPolyline.points || !monitorPolyline.points.trim()) chartBlankErrors.push(`策略監控台權益曲線：polyline存在但points屬性是空字串`);
    await page.unroute("**/data/strategy_curves.json**");
  } catch (e) {
    chartBlankErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("16. 圖該顯示卻空白防線（有效≥2點假資料，驗polyline的points屬性真的有座標）",
    chartBlankErrors.length === 0, chartBlankErrors.join("; "));

  // 17.【2026-09-02新增，B29美股個股頁財報UI】用route攔截餵一份us_financials.json
  // 假資料，確認：(a) 有快照的代號（AAPL）財報頁四指標（毛利率/營益率/營收年增/
  // FCF利潤率）真的被畫出實際數字，不是卡在舊版「美股尚未支援財報解析」文字；
  // (b) 沒有快照的代號（TSLA）誠實顯示「暫無財報快照」而不是空白/沿用上一檔
  // 股票殘留的數字（切換代號後沒有正確reset＝資料汙染，比空白更危險）。
  const usFinErrors = [];
  try {
    const fakeUsFin = {
      generated_at: new Date().toISOString(),
      financials: {
        AAPL: {
          period_end: "2025-09-30", prior_period_end: "2024-09-30",
          gross_margin: 0.4691, operating_margin: 0.3197, revenue_yoy: 0.0643,
          free_cash_flow: 98767000000.0, fcf_margin: 0.2373,
          missing_fields: [], warnings: [],
        },
      },
    };
    await page.route("**/data/us_financials.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeUsFin) })
    );
    await page.evaluate(() => { US_FINANCIALS_CACHE = null; });
    await page.evaluate((code) => window.openStock(code), "AAPL");
    await page.waitForTimeout(600);
    await page.evaluate(() => {
      const b = [...document.querySelectorAll("#stock-tabs button")].find(x => x.dataset.sub === "fin");
      if (b) b.click();
    });
    await page.waitForTimeout(300);
    const aaplVals = await page.evaluate(() => ({
      gross: document.getElementById("fin-gross")?.textContent,
      op: document.getElementById("fin-op")?.textContent,
      roe: document.getElementById("fin-roe")?.textContent,
      fcf: document.getElementById("fin-fcf")?.textContent,
      epsBars: document.getElementById("eps-bars")?.innerHTML || "",
    }));
    if (aaplVals.epsBars.includes("尚未支援")) usFinErrors.push("AAPL：eps-bars仍是舊版「美股尚未支援財報解析」文字，B29 UI沒接上");
    if (!aaplVals.gross || aaplVals.gross === "—") usFinErrors.push(`AAPL：毛利率沒有畫出數字（拿到"${aaplVals.gross}"）`);
    if (!aaplVals.op || aaplVals.op === "—") usFinErrors.push(`AAPL：營益率沒有畫出數字（拿到"${aaplVals.op}"）`);
    if (!aaplVals.roe || aaplVals.roe === "—") usFinErrors.push(`AAPL：營收年增沒有畫出數字（拿到"${aaplVals.roe}"）`);
    if (!aaplVals.fcf || aaplVals.fcf === "—") usFinErrors.push(`AAPL：FCF利潤率沒有畫出數字（拿到"${aaplVals.fcf}"）`);

    await page.evaluate((code) => window.openStock(code), "TSLA");
    await page.waitForTimeout(600);
    const tslaVals = await page.evaluate(() => ({
      gross: document.getElementById("fin-gross")?.textContent,
      note: document.getElementById("fin-note")?.textContent || "",
    }));
    if (tslaVals.gross !== "—") usFinErrors.push(`TSLA（無快照）：切換代號後毛利率沒有正確reset，殘留"${tslaVals.gross}"（資料汙染）`);
    if (!tslaVals.note.includes("暫無")) usFinErrors.push(`TSLA（無快照）：fin-note沒有誠實揭露查無資料，內容是"${tslaVals.note}"`);

    await page.unroute("**/data/us_financials.json**");
  } catch (e) {
    usFinErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("17. B29美股個股頁財報UI：有快照代號畫出四指標數字、無快照代號誠實顯示且不殘留舊代號數字",
    usFinErrors.length === 0, usFinErrors.join("; "));

  // 18.【2026-09-02新增，IBKR Paper下單UI卡片】驗：(a) 分工鐵律——美股個股頁
  // 按「買進」要開真的IBKR下單卡片（#ibkr-sheet），不是台股那個全示範版
  // （#sheet）；台股個股頁按「買進」要維持原本示範版行為（防止把美股邏輯
  // 誤接到台股，那是真的會打Paper API送單，混錯市場很危險）。(b) 本機下單
  // 伺服器沒啟動時（測試環境本來就沒有），連線狀態要顯示清楚的「未啟動」
  // 提示，不能是空白或掛掉的uncaught error。(c) 沒填token時按送出要擋下來，
  // 不能真的送出fetch請求。
  const ibkrUiErrors = [];
  try {
    await page.evaluate((code) => window.openStock(code), "AAPL");
    await page.waitForTimeout(300);
    await page.evaluate(() => document.getElementById("buy-cta-us-buy").click());
    await page.waitForTimeout(2500);
    const usSheetOpen = await page.evaluate(() => document.getElementById("ibkr-sheet")?.classList.contains("open"));
    if (!usSheetOpen) ibkrUiErrors.push("美股按買進後，#ibkr-sheet沒有打開");
    const healthText = await page.evaluate(() => document.getElementById("ibkr-health")?.textContent || "");
    if (!healthText || (!healthText.includes("未啟動") && !healthText.includes("失敗"))) {
      ibkrUiErrors.push(`測試環境沒有真的啟動ibkr_order_server.py，連線狀態應顯示未啟動/失敗訊息，實際："${healthText}"`);
    }
    await page.evaluate(() => { document.getElementById("ibkr-token").value = ""; });
    await page.evaluate(() => window.submitIbkrOrderUI());
    await page.waitForTimeout(300);
    const resultText = await page.evaluate(() => document.getElementById("ibkr-result")?.textContent || "");
    if (!resultText.includes("token")) ibkrUiErrors.push(`沒填token應該被前端擋下並提示，實際訊息："${resultText}"`);
    await page.evaluate(() => window.closeIbkrSheet());

    // 先.六十-A1：台股假下單抽屜已移除；台股個股頁不得出現 IBKR 下單鈕（分工鐵律：IBKR 下單卡只給美股）
    await page.evaluate(() => window.openStock("2330"));
    await page.waitForTimeout(300);
    const twIbkrBtnShown = await page.evaluate(() => { const b = document.getElementById("buy-cta-us-buy"); return !!b && getComputedStyle(b).display !== "none"; });
    if (twIbkrBtnShown) ibkrUiErrors.push("台股個股頁竟然顯示 IBKR 下單鈕（分工鐵律破功）");
  } catch (e) {
    ibkrUiErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("18. IBKR Paper下單UI卡片：美股/台股分工正確、伺服器未啟動時有清楚提示、無token時前端擋下送出",
    ibkrUiErrors.length === 0, ibkrUiErrors.join("; "));

  // 19.【2026-09-02新增，即時價格四修之一：指數Yahoo備援誠實標示】
  // route攔截假quotes_ibkr.json，模擬道瓊/費半這種IBKR無訂閱、改用Yahoo
  // 備援寫回的情境（data_type="YAHOO_DELAYED"），驗市場頁指數badge正確
  // 顯示「Yahoo 延遲~15分」，不是沿用舊邏輯誤標成「IBKR 未知」或忽略
  // 這個新data_type值。
  const yahooFallbackErrors = [];
  try {
    const fakeIbkr = {
      fetched_at: new Date().toISOString(), connected: true, account_type: "paper", error: null,
      quotes: {
        "^DJI": { last: 52999.12, bid: null, ask: null, close: 52766.88, change_pct: 0.44,
                  data_type: "YAHOO_DELAYED", source: "yahoo_fallback", exchange: "CME", label: "道瓊工業指數" },
      },
    };
    await page.route("**/data/quotes_ibkr.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeIbkr) })
    );
    await page.evaluate(() => { INTRADAY_IBKR = null; });
    await page.evaluate(() => window.go("market"));
    await page.waitForTimeout(300);
    await page.evaluate(() => window.setMarketToggle("market", "US"));
    await page.waitForTimeout(1500);
    const html = await page.evaluate(() => document.getElementById("us-idx-rows")?.innerHTML || "");
    // 2026-09-04修正：這個檢查跟「現在是不是美股盤中」有關——盤中該標「Yahoo 延遲~15分」，
    // 盤後（isTodayClose）該標「Yahoo 今日收盤」，兩者都是誠實的Yahoo來源標示；不能出現
    // 「IBKR 今日收盤」（把Yahoo備援冒充IBKR）。之前只在美股盤中跑過所以沒踩到。
    if (!html.includes("Yahoo 延遲") && !html.includes("Yahoo 今日收盤")) {
      yahooFallbackErrors.push(`YAHOO_DELAYED的道瓊指數沒有顯示「Yahoo 延遲」或「Yahoo 今日收盤」badge，實際內容片段：${html.slice(0, 300)}`);
    }
    if (html.includes("IBKR 今日收盤")) {
      yahooFallbackErrors.push("YAHOO_DELAYED在盤後被標成「IBKR 今日收盤」，把Yahoo備援冒充成IBKR");
    }
    if (html.includes("IBKR 未知") || html.includes("IBKR YAHOO_DELAYED")) {
      yahooFallbackErrors.push("YAHOO_DELAYED被誤標成IBKR來源，沒有誠實反映這其實是Yahoo備援");
    }
    await page.unroute("**/data/quotes_ibkr.json**");
  } catch (e) {
    yahooFallbackErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("19. 指數Yahoo備援誠實標示：IBKR無訂閱改用Yahoo時badge正確顯示「Yahoo 延遲~15分」",
    yahooFallbackErrors.length === 0, yahooFallbackErrors.join("; "));

  // 20.【2026-09-02新增，籌碼頁重新配置】市場頁「籌碼」精簡入口卡要顯示今日
  // 三大法人合計+融資維持率摘要（不是空的—），點下去要正確導到scr-chips-
  // market頁面並看到完整的三大法人買賣超圖+融資維持率圖（不是空白頁）。
  const chipsEntryErrors = [];
  try {
    await page.evaluate(() => window.go("market"));
    await page.waitForTimeout(2500);
    const entryVals = await page.evaluate(() => ({
      inst: document.getElementById("chips-entry-inst")?.textContent,
      margin: document.getElementById("chips-entry-margin")?.textContent,
    }));
    if (!entryVals.inst || entryVals.inst === "—") chipsEntryErrors.push(`籌碼入口卡「三大法人合計」沒有畫出數字，拿到"${entryVals.inst}"`);
    if (!entryVals.margin || entryVals.margin === "—") chipsEntryErrors.push(`籌碼入口卡「融資維持率」沒有畫出數字，拿到"${entryVals.margin}"`);
    await page.evaluate(() => window.go("chips-market"));
    await page.waitForTimeout(1000);
    const detailVisible = await page.evaluate(() => document.getElementById("scr-chips-market")?.classList.contains("active"));
    const instBarsHtml = await page.evaluate(() => document.getElementById("inst-bars")?.innerHTML || "");
    if (!detailVisible) chipsEntryErrors.push("點籌碼入口卡後沒有正確導到scr-chips-market頁面");
    if (!instBarsHtml || instBarsHtml.includes("載入中")) chipsEntryErrors.push(`市場籌碼總覽頁的三大法人買賣超圖沒有畫出內容，innerHTML="${instBarsHtml.slice(0,100)}"`);
    await page.evaluate(() => window.go("market"));
  } catch (e) {
    chipsEntryErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("20. 籌碼頁重新配置：市場頁入口卡顯示摘要數字、點進去正確看到完整市場籌碼總覽頁",
    chipsEntryErrors.length === 0, chipsEntryErrors.join("; "));

  // 21.【2026-09-02新增，使用者原話「四大美股指數報價不得為null」】用
  // 2026-09-02 23:25本機實測ibkr_quotes.py抓到的真實資料結構當fixture
  // （道瓊IBKR無訂閱走Yahoo備援、S&P500/NASDAQ/費半直接拿到IBKR DELAYED
  // 報價——見research/ibkr_quotes.py實測log），route攔截餵給前端，驗
  // 四大指數在市場頁「美股」分頁全部顯示實際數字，沒有任何一個是「—/
  // 查無資料」。這條測試曾經被誤會成「程式碼bug」，實際查證後發現是
  // 「quotes_ibkr.json從2026-09-01起沒有人手動重跑過，部署的資料本身
  // 是舊的、缺三個指數」，不是程式碼邏輯壞——這條測試用真實資料結構
  // 當防線，之後如果邏輯真的壞掉能立刻抓到，跟「資料沒更新」的情況分開。
  const fourIndicesErrors = [];
  try {
    const realWorldIbkr = {
      fetched_at: new Date().toISOString(), connected: true, account_type: "paper", error: null,
      quotes: {
        "^DJI": { last: 53070.5, bid: null, ask: null, close: 52766.88, change_pct: 0.5754,
                  data_type: "YAHOO_DELAYED", source: "yahoo_fallback", exchange: "CME", label: "道瓊工業指數" },
        "^GSPC": { last: 7670.4, bid: null, ask: null, close: 7631.47, change_pct: 0.5101,
                   data_type: "DELAYED", exchange: "CBOE", label: "S&P 500" },
        "^IXIC": { last: 26193.84, bid: null, ask: null, close: 26099.77, change_pct: 0.3604,
                   data_type: "DELAYED", exchange: "NASDAQ", label: "那斯達克綜合指數" },
        "^SOX": { last: 11322.03, bid: null, ask: null, close: 11288.61, change_pct: 0.2961,
                  data_type: "DELAYED", exchange: "PHLX", label: "費城半導體指數" },
      },
    };
    await page.route("**/data/quotes_ibkr.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(realWorldIbkr) })
    );
    await page.evaluate(() => { INTRADAY_IBKR = null; });
    await page.evaluate(() => window.go("market"));
    await page.waitForTimeout(300);
    await page.evaluate(() => window.setMarketToggle("market", "US"));
    await page.waitForTimeout(2000);
    const rows = await page.evaluate(() =>
      [...document.querySelectorAll("#us-idx-rows .row")].map(r => ({
        name: r.querySelector(".nm b")?.textContent,
        price: r.querySelector(".px b")?.textContent,
        src: r.querySelector(".nm span")?.textContent,
      }))
    );
    if (rows.length !== 4) fourIndicesErrors.push(`應該有4個指數列，實際${rows.length}個：${JSON.stringify(rows)}`);
    for (const r of rows) {
      if (!r.price || r.price === "—") fourIndicesErrors.push(`${r.name}顯示「—」（null），來源標籤="${r.src}"`);
    }
    await page.unroute("**/data/quotes_ibkr.json**");
  } catch (e) {
    fourIndicesErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("21. 四大美股指數報價不得為null（用2026-09-02實測真實資料結構當fixture）",
    fourIndicesErrors.length === 0, fourIndicesErrors.join("; "));

  // 22.【2026-09-03新增，B34 Shioaji逐筆tick串流】route攔截假quotes_
  // sinopac.json，模擬新的data_type="REALTIME_TICK"，驗自選股列表badge
  // 正確顯示「Shioaji 即時(tick)」，不是沿用舊的「即時」或顯示成「未知」。
  const tickBadgeErrors = [];
  try {
    const fakeSinopac = {
      fetched_at: new Date().toISOString(), connected: true, market_status: "open", error: null,
      quotes: {
        "2330": { last: 1050.0, close: 1035.0, change_pct: 1.5, data_type: "REALTIME_TICK",
                  volume_this_tick: 3, total_volume: 1200, exchange: "TSE" },
      },
    };
    await page.route("**/data/quotes_sinopac.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeSinopac) })
    );
    await page.evaluate(() => {
      const wl = JSON.parse(localStorage.getItem("alpha_wl") || "[]");
      if (!wl.includes("2330")) { wl.push("2330"); localStorage.setItem("alpha_wl", JSON.stringify(wl)); }
      INTRADAY_SINOPAC = null;
    });
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(1500);
    const wlHtml = await page.evaluate(() => document.getElementById("wl-list")?.innerHTML || "");
    if (!wlHtml.includes("即時(tick)")) {
      tickBadgeErrors.push(`自選股列表沒有顯示「即時(tick)」badge，片段：${wlHtml.slice(0, 400)}`);
    }
    await page.unroute("**/data/quotes_sinopac.json**");
  } catch (e) {
    tickBadgeErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("22. Shioaji逐筆tick串流誠實標示：data_type=REALTIME_TICK正確顯示「即時(tick)」badge",
    tickBadgeErrors.length === 0, tickBadgeErrors.join("; "));

  // 23.【2026-09-03新增，P0根因回歸測試，使用者原話「收盤後自選股每檔
  // 顯示價==quotes_sinopac對應last，不等即FAIL」】模擬market_status=
  // closed但fetched_at是「今天」的情境（收盤後、20分鐘閘門修復前的
  // bug重現條件），驗自選股卡顯示的價格數字精確等於quotes_sinopac.last，
  // 不是prev_close也不是別的資料源退回值——這是這次P0修復要防止無聲
  // 復發的核心斷言，比check 22（只驗badge文字）更直接驗數字本身。
  const closedTodayPriceErrors = [];
  try {
    const todayIso = new Date().toISOString();
    const fakeClosedToday = {
      fetched_at: todayIso, connected: false, market_status: "closed", error: null,
      quotes: {
        "2330": { last: 2390.0, close: 2385.0, change_pct: 0.21, data_type: "REALTIME_TICK",
                  volume_this_tick: 0, total_volume: 45000, exchange: "TSE" },
      },
    };
    await page.route("**/data/quotes_sinopac.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeClosedToday) })
    );
    await page.evaluate(() => {
      const wl = JSON.parse(localStorage.getItem("alpha_wl") || "[]");
      if (!wl.includes("2330")) { wl.push("2330"); localStorage.setItem("alpha_wl", JSON.stringify(wl)); }
      INTRADAY_SINOPAC = null;
    });
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(1500);
    const priceText = await page.evaluate(() => {
      const row = [...document.querySelectorAll("#wl-list .swipe-row")]
        .find(r => r.querySelector('[data-flash-code="2330"]'));
      return row ? row.querySelector('[data-flash-code="2330"]').textContent : null;
    });
    const wlHtml = await page.evaluate(() => document.getElementById("wl-list")?.innerHTML || "");
    if (priceText === null) closedTodayPriceErrors.push("找不到2330的價格元素");
    else if (priceText.replace(/,/g, "") !== "2390") {
      closedTodayPriceErrors.push(`收盤後自選股顯示價應該等於quotes_sinopac.last=2390，實際顯示"${priceText}"（懷疑退回prev_close=2385或其他資料源）`);
    }
    if (!wlHtml.includes("今日收盤")) {
      closedTodayPriceErrors.push(`收盤後badge應該顯示「今日收盤」，片段：${wlHtml.slice(0, 300)}`);
    }
    await page.unroute("**/data/quotes_sinopac.json**");
  } catch (e) {
    closedTodayPriceErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("23. 收盤後自選股顯示價必須等於quotes_sinopac的last（P0根因回歸防線，防止20分鐘閘門誤丟今日收盤價復發）",
    closedTodayPriceErrors.length === 0, closedTodayPriceErrors.join("; "));

  // 24.【2026-09-03新增，P0三-三.2】設定頁「資料新鮮度」卡片：每個監控項目都
  // 要畫出一列、每列的狀態只能是ok/overdue/missing三者之一、不能出現undefined/
  // NaN、摘要行不能停在「檢查中…」。這裡不斷言「全部正常」——逾期是真實狀態
  // （今天quotes.yml整天沒落地就該紅），要驗的是「判定有跑完、有誠實畫出來」。
  const freshnessErrors = [];
  try {
    await page.evaluate(() => window.go("settings"));
    await page.waitForFunction(
      () => document.querySelectorAll("#data-freshness-list .fresh-row").length > 0,
      null, { timeout: 15000 }
    ).catch(() => {});
    await page.waitForTimeout(500);
    const info = await page.evaluate(() => {
      const rows = [...document.querySelectorAll("#data-freshness-list .fresh-row")];
      return {
        expected: typeof FRESHNESS_ITEMS !== "undefined" ? FRESHNESS_ITEMS.length : -1,
        n: rows.length,
        statuses: rows.map(r => r.dataset.status),
        html: document.getElementById("data-freshness-list")?.innerHTML || "",
        summary: document.getElementById("data-freshness-summary")?.textContent || "",
      };
    });
    if (info.n === 0) freshnessErrors.push("沒有畫出任何資料檔列");
    if (info.expected > 0 && info.n !== info.expected) freshnessErrors.push(`應有${info.expected}列，實際${info.n}列`);
    const badStatus = info.statuses.filter(s => !["ok", "overdue", "missing"].includes(s));
    if (badStatus.length) freshnessErrors.push(`出現非法狀態值：${badStatus.join(",")}`);
    if (/undefined|NaN/.test(info.html)) freshnessErrors.push("列內容出現undefined/NaN");
    if (!info.summary || info.summary.includes("檢查中")) freshnessErrors.push(`摘要行未完成：「${info.summary}」`);
  } catch (e) {
    freshnessErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("24. 設定頁資料新鮮度卡片：每個監控檔都畫出一列、狀態值合法、無undefined/NaN、摘要有完成（逾期標紅只驗有跑完，不強求全綠）",
    freshnessErrors.length === 0, freshnessErrors.join("; "));

  // 25.【2026-09-03深夜新增，乙.4/乙.5】(a)未設定即時伺服器時首頁要誠實標
  // 「離線…顯示最後收盤」（使用者指定字眼）；(b)個股頁走勢圖改用lightweight-charts
  // 後必須真的畫出東西：canvas（函式庫載入成功）或退回SVG折線（離線/CDN故障）
  // 兩者擇一，但不能空白/停在「載入中」。FinMind日線用route餵假資料，避免測試
  // 結果被FinMind額度/封鎖左右（跟check 15/16同一精神）。
  const liveUiErrors = [];
  try {
    await page.evaluate(() => { try { localStorage.removeItem("alpha_live_url"); localStorage.removeItem("alpha_live_token"); } catch (e) {} });
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(500);
    const st = await page.evaluate(() => { loadLiveConfig(); renderLiveStatus(); return document.getElementById("home-live-status")?.textContent || ""; });
    if (!/離線/.test(st) || !/最後收盤/.test(st)) liveUiErrors.push(`首頁即時狀態列應標「離線…顯示最後收盤」，實際「${st}」`);
    const fakeRows = [];
    for (let i = 30; i >= 1; i--) {
      const d = new Date(Date.now() - i * 86400000); const ds = d.toISOString().slice(0, 10);
      const c = 1000 + (30 - i) * 3;
      fakeRows.push({ date: ds, stock_id: "2330", open: c - 5, max: c + 8, min: c - 9, close: c, spread: 3, Trading_Volume: 20000000, Trading_money: 20000000 * c });
    }
    await page.route("**/api.finmindtrade.com/**", (route) => {
      if (route.request().url().includes("TaiwanStockPrice")) route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ msg: "success", status: 200, data: fakeRows }) });
      else route.continue();
    });
    await page.evaluate(() => window.openStock("2330"));
    await page.waitForFunction(() => { const el = document.getElementById("trend-chart"); return el && (el.querySelector("canvas") || el.querySelector("svg polyline")); }, null, { timeout: 15000 }).catch(() => {});
    const ch = await page.evaluate(() => { const el = document.getElementById("trend-chart"); return { canvas: !!el.querySelector("canvas"), svg: !!el.querySelector("svg polyline"), text: (el.textContent || "").slice(0, 80), lwc: typeof LightweightCharts !== "undefined" }; });
    if (!ch.canvas && !ch.svg) liveUiErrors.push(`個股頁走勢圖沒有畫出canvas也沒有SVG折線（lightweight-charts載入=${ch.lwc}，內容「${ch.text}」）`);
    await page.unroute("**/api.finmindtrade.com/**");
    results.stock_chart_renderer = ch.canvas ? "lightweight-charts(canvas)" : (ch.svg ? "svg-fallback" : "none");
  } catch (e) {
    liveUiErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("25. 即時伺服器未設定時首頁誠實標「離線，顯示最後收盤」；個股頁走勢圖（lightweight-charts canvas或SVG退回）真的有畫出來",
    liveUiErrors.length === 0, liveUiErrors.join("; ") || `renderer=${results.stock_chart_renderer}`);

  // 26.【2026-09-04新增，籌碼分頁免費層第一單位】個股頁籌碼分頁的「三大法人逐日／
  // 累計」表：有資料就要有表格列，沒有就要是誠實空狀態文字（不能停在「載入中」）；
  // 免責文字（非投資建議／跟著大戶不等於獲利）必須在。check 25剛開完2330個股頁。
  const chipErrors = [];
  try {
    await page.evaluate(() => { document.querySelector('#stock-tabs button[data-sub="chip"]')?.click(); });
    await page.waitForFunction(() => { const t = document.getElementById("chip-trend-table")?.textContent || ""; return t && !t.includes("載入中"); }, null, { timeout: 15000 }).catch(() => {});
    const info = await page.evaluate(() => ({
      rows: document.querySelectorAll("#chip-trend-table tbody tr").length,
      text: (document.getElementById("chip-trend-table")?.textContent || "").slice(0, 80),
      disclaimer: document.getElementById("chip-disclaimer")?.textContent || "",
      cost: document.getElementById("chip-cost-note")?.textContent || "",
    }));
    if (info.rows === 0 && !/查無/.test(info.text)) chipErrors.push(`三大法人逐日表既無資料列也不是誠實空狀態：「${info.text}」`);
    // 先.七十二-A2：「非投資建議」改只放頁尾一處；籌碼卡保留「跟著大戶不等於會賺」的白話提醒
    if (!/不等於/.test(info.disclaimer) || /非投資建議/.test(info.disclaimer)) chipErrors.push("籌碼提醒缺「不等於」或卡內又重複免責");
    if (!/估算/.test(info.cost)) chipErrors.push(`估算成本欄位沒有標「估算」：「${info.cost}」`);
    results.chip_trend_rows = info.rows;
  } catch (e) {
    chipErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("26. 籌碼分頁三大法人逐日／累計表有資料列或誠實空狀態、免責文字與「估算」標示都在",
    chipErrors.length === 0, chipErrors.join("; ") || `rows=${results.chip_trend_rows}`);

  // 27.【2026-09-04新增，四修.二】未連即時伺服器時，市場頁櫃買指數列與類股熱力圖
  // 的來源標示必須帶收盤日期（今日/昨日/前次收盤（MM-DD）），不得讓盤後漲跌幅
  // 不標日期地顯示（總司令原話）。
  const idxDateErrors = [];
  try {
    await page.evaluate(() => { try { localStorage.removeItem("alpha_live_url"); localStorage.removeItem("alpha_live_token"); } catch (e) {} LIVE.connected = false; });
    await page.evaluate(() => window.go("market"));
    await page.waitForTimeout(300);
    await page.evaluate(() => window.setMarketToggle("market", "TW"));
    await page.waitForTimeout(1500);
    const info = await page.evaluate(() => {
      const rows = [...document.querySelectorAll("#idx-rows .row")];
      const tpex = rows.find(r => r.textContent.includes("櫃買指數"));
      return { tpexSrc: tpex ? tpex.querySelector(".nm span")?.textContent : null, heat: document.getElementById("heat-datatime")?.textContent || "", idx: document.getElementById("idx-datatime")?.textContent || "" };
    });
    if (!info.tpexSrc || !/收盤（\d{2}-\d{2}）/.test(info.tpexSrc)) idxDateErrors.push(`櫃買指數列來源標示沒有帶收盤日期：「${info.tpexSrc}」`);
    if (!/收盤（\d{2}-\d{2}）/.test(info.heat)) idxDateErrors.push(`類股熱力圖時間標示沒有帶收盤日期：「${info.heat}」`);
    if (!/收盤（\d{2}-\d{2}）/.test(info.idx)) idxDateErrors.push(`大盤指數時間標示沒有帶收盤日期：「${info.idx}」`);
  } catch (e) {
    idxDateErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("27. 未連即時源時，市場頁櫃買指數／類股熱力圖／大盤指數的盤後資料一律明標收盤日期（MM-DD）",
    idxDateErrors.length === 0, idxDateErrors.join("; "));

  // 28.【2026-09-04新增，四修.三】走勢線標籤：離線（未連即時）時自選股列的走勢線
  // 必須標「20日」（route餵一份含20點sparkline的quotes_tw.json，跟check 15同一手法），
  // 不能是無標籤的線。即時「今日」路徑需要live server，由Playwright端到端另行驗證。
  const sparkTagErrors = [];
  try {
    const fakeTw = { fetched_at: new Date().toISOString(), source: "test", meta: { trading_window: false, data_type: "prev_close" },
      quotes: { "2330": { name: "台積電", price: 1000, prev_close: 990, change: 10, change_pct: 1.01, time: "13:30:00", date: "20260904", stale: true,
        sparkline: Array.from({ length: 20 }, (_, i) => 950 + i * 2), sparkline_date: "2026-09-04" } } };
    await page.route("**/data/quotes_tw.json**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeTw) }));
    await page.evaluate(() => { const wl = JSON.parse(localStorage.getItem("alpha_wl") || "[]"); if (!wl.includes("2330")) { wl.push("2330"); localStorage.setItem("alpha_wl", JSON.stringify(wl)); } INTRADAY_TW = null; INTRADAY_TW_AT = 0; LIVE.connected = false; });
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(1500);
    const info = await page.evaluate(() => {
      const row = [...document.querySelectorAll("#wl-list .swipe-row")].find(r => r.querySelector('[data-flash-code="2330"]'));
      return { hasSpark: !!row?.querySelector("svg.spark polyline"), tag: row?.querySelector(".sparkwrap em")?.textContent || null };
    });
    if (!info.hasSpark) sparkTagErrors.push("餵了20點sparkline但自選股列沒有畫出走勢線");
    if (info.tag !== "20日") sparkTagErrors.push(`離線時走勢線標籤應為「20日」，實際「${info.tag}」`);
    await page.unroute("**/data/quotes_tw.json**");
  } catch (e) {
    sparkTagErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("28. 未連即時源時自選股走勢線必須標「20日」（即時時為當日1分K標「今日」，端到端另驗）",
    sparkTagErrors.length === 0, sparkTagErrors.join("; "));

  // 29.【2026-09-04新增，四修.四】「資料過舊」與「即時連線中」不得同頁矛盾：
  // (a) 台股盤中、Actions quotes_tw 過舊、但 Shioaji 即時源新鮮且 SSE 連線中 → 不得報
  //     「自選股台股報價 資料過舊」；(b) 即時源也沒有 → 仍要報（防線沒被拆掉）；
  // (c) SSE 連線中時輪詢文案必須是即時模式文案，不得出現「近即時輪詢」。
  const consistencyErrors = [];
  try {
    const r = await page.evaluate(() => {
      const out = {};
      const nowIso = new Date().toISOString();
      const saved = { tw: INTRADAY_TW, sp: INTRADAY_SINOPAC, conn: LIVE.connected, mode: LIVE.streamMode, src: LIVE.sourceMode };
      INTRADAY_TW = { fetched_at: new Date(Date.now() - 3 * 3600 * 1000).toISOString(), quotes: { "2330": { price: 1 } } }; // Actions冷檔過舊3小時
      INTRADAY_SINOPAC = { fetched_at: nowIso, connected: true, market_status: "open", quotes: { "2330": { last: 1180, data_type: "REALTIME_TICK" } } };
      LIVE.connected = true; LIVE.streamMode = "tick-push"; LIVE.sourceMode = "tick-push-memory";
      out.liveProblems = diagQuoteProblems(true, false).map(p => p.name);
      out.pollText = pollStatusText(true, false);
      LIVE.connected = false; INTRADAY_SINOPAC = null;
      out.offlineProblems = diagQuoteProblems(true, false).map(p => p.name);
      out.offlinePollText = pollStatusText(true, false);
      INTRADAY_TW = saved.tw; INTRADAY_SINOPAC = saved.sp; LIVE.connected = saved.conn; LIVE.streamMode = saved.mode; LIVE.sourceMode = saved.src;
      return out;
    });
    if (r.liveProblems.includes("自選股台股報價")) consistencyErrors.push("Shioaji即時源新鮮且SSE連線中，橫幅仍報「自選股台股報價 資料過舊」");
    if (!r.offlineProblems.includes("自選股台股報價")) consistencyErrors.push("即時源也沒有時，橫幅應該要報台股報價過舊，防線被拆掉了");
    if (!/即時串流連線中/.test(r.pollText) || /近即時輪詢/.test(r.pollText)) consistencyErrors.push(`SSE連線中的輪詢文案不對：「${r.pollText}」`);
    if (!/近即時輪詢/.test(r.offlinePollText)) consistencyErrors.push(`離線時輪詢文案應回到近即時輪詢：「${r.offlinePollText}」`);
  } catch (e) {
    consistencyErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("29. 「資料過舊」判定納入Shioaji即時源、SSE連線中輪詢文案改即時模式，兩者不同頁矛盾",
    consistencyErrors.length === 0, consistencyErrors.join("; "));

  // 30.【2026-09-04新增，P0產品.一 首頁重排版】結構斷言：細狀態列存在且摘要非空、自選股
  // 每列有來源小點且列不重複（hydrateHome競態回歸防線）、大盤速覽是膠囊帶（≥3顆）、
  // AI日報無內容時整張隱藏、走勢線包裝層寬度≤72px（不能被撐成整列）。
  const homeErrors = [];
  try {
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(1500);
    const info = await page.evaluate(() => {
      const codes = [...document.querySelectorAll("#wl-list .swipe-row [data-flash-code]")].map(e => e.dataset.flashCode);
      const wraps = [...document.querySelectorAll("#wl-list .sparkwrap")].map(w => w.getBoundingClientRect().width);
      return { summary: document.getElementById("home-status-summary")?.textContent || "", dots: document.querySelectorAll("#wl-list .wl-src-dot").length, rows: codes.length, dup: codes.length !== new Set(codes).size, caps: document.querySelectorAll("#home-idx-rows .idx-cap").length, aiHidden: !!document.getElementById("home-ai-card")?.hidden, aiBody: document.getElementById("home-ai-body")?.textContent || "", maxWrap: wraps.length ? Math.max(...wraps) : 0 };
    });
    if (!info.summary || /載入中/.test(info.summary)) homeErrors.push(`細狀態列摘要未完成：「${info.summary}」`);
    if (info.rows > 0 && info.dots < info.rows) homeErrors.push(`自選股列${info.rows}列但來源小點只有${info.dots}顆`);
    if (info.dup) homeErrors.push("自選股列重複出現（hydrateHome競態）");
    if (info.caps < 3) homeErrors.push(`大盤速覽膠囊只有${info.caps}顆`);
    // 常備.開發-2（2026-10-11）：盤前日報改讀 data/daily_brief.json（規則摘要），有內容時才顯示——
    // 斷言改成「無內容必須隱藏；顯示時必須有內容且標明規則摘要／非 AI 判斷／非投資建議」。
    if (!info.aiHidden && !info.aiBody.trim()) homeErrors.push("AI盤前日報無內容卻沒有隱藏整張卡");
    // 先.八十-5／10（2026-10-12）：「非投資建議」前台統一只在頁尾一處（#91），卡片內只標「規則摘要，非 AI 判斷」，且卡片內不得再出現「非投資建議」
    if (!info.aiHidden && info.aiBody.trim() && !(/規則摘要/.test(info.aiBody) && /非 AI 判斷/.test(info.aiBody)))
      homeErrors.push(`盤前日報顯示中卻沒標「規則摘要，非 AI 判斷」：「${info.aiBody.slice(0, 60)}」`);
    if (!info.aiHidden && /非投資建議/.test(info.aiBody)) homeErrors.push("盤前日報卡片內又出現「非投資建議」（應只在頁尾）");
    if (info.maxWrap > 72) homeErrors.push(`走勢線包裝層被撐到${info.maxWrap.toFixed(0)}px寬`);
  } catch (e) {
    homeErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("30. 首頁重排版結構：細狀態列有摘要、自選股列有來源小點且不重複、大盤速覽膠囊≥3、AI日報空卡隱藏、走勢線不被撐寬",
    homeErrors.length === 0, homeErrors.join("; "));

  // 31~34.【2026-09-04新增，總司令P0緊急原話的check 27~30（既有編號已用到30故順延）】
  // 先併發呼叫兩次hydrateHome()（模擬輪詢/SSE/重新整理/切分頁同時觸發），再做四項版面斷言。
  await page.evaluate(() => window.go("home"));
  await page.evaluate(async () => { await Promise.all([hydrateHome(), hydrateHome()]); });
  await page.waitForTimeout(800);
  const lay = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("#wl-list .swipe-row")];
    const codes = rows.map(r => r.querySelector("[data-flash-code]")?.dataset.flashCode).filter(Boolean);
    const caps = [...document.querySelectorAll("#home-idx-rows .idx-cap .cn")].map(e => e.textContent.trim());
    const inter = (a, b) => !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
    const overlaps = [], widths = [], heights = [];
    for (const r of rows) {
      heights.push(r.getBoundingClientRect().height);
      const svg = r.querySelector("svg.spark"); const px = r.querySelector(".px");
      if (svg) { const sb = svg.getBoundingClientRect(); widths.push(sb.width); if (px && inter(sb, px.getBoundingClientRect())) overlaps.push(r.querySelector("[data-flash-code]")?.dataset.flashCode); }
    }
    const z = zonedNow("Asia/Taipei"); const twOpen = z.wd >= 1 && z.wd <= 5 && (z.h * 60 + z.mi) >= 540 && (z.h * 60 + z.mi) < 810;
    const text = (document.getElementById("wl-list")?.innerText || "") + (document.getElementById("home-idx-rows")?.innerText || "");
    return { codes, caps, overlaps, maxW: widths.length ? Math.max(...widths) : 0, hDiff: heights.length ? Math.max(...heights) - Math.min(...heights) : 0, twOpen, hasPanZhong: /盤中/.test(text) };
  });
  const dupCodes = lay.codes.filter((c, i) => lay.codes.indexOf(c) !== i), dupCaps = lay.caps.filter((c, i) => lay.caps.indexOf(c) !== i);
  record("31. 併發呼叫兩次hydrateHome後，自選股每個代號在#wl-list只出現一次、大盤速覽每個指數只出現一次",
    dupCodes.length === 0 && dupCaps.length === 0 && lay.codes.length > 0, (dupCodes.length ? `重複代號：${dupCodes.join(",")}` : "") + (dupCaps.length ? ` 重複膠囊：${dupCaps.join(",")}` : "") + (lay.codes.length ? "" : " 沒有任何自選股列"));
  record("32. 自選股每列走勢SVG與價格/漲跌元素矩形不相交，且SVG實際寬度≤72px",
    lay.overlaps.length === 0 && lay.maxW <= 72, (lay.overlaps.length ? `相交：${lay.overlaps.join(",")}` : "") + (lay.maxW > 72 ? ` SVG寬${lay.maxW.toFixed(0)}px` : `SVG寬${lay.maxW.toFixed(0)}px`));
  record("33. 同一清單內自選股列高差異≤8px（有線沒線都一樣高）",
    lay.hDiff <= 8, `列高差${lay.hDiff.toFixed(1)}px`);
  record("34. 台股收盤時段首頁自選股/大盤速覽不得含「盤中」字樣（盤中時段此檢查視為通過）",
    lay.twOpen || !lay.hasPanZhong, lay.twOpen ? "測試時台股盤中，跳過" : (lay.hasPanZhong ? "收盤後仍出現「盤中」" : ""));

  // 35~36.【2026-09-05新增，週六.一 P0：千元以上股票整條管線消失】
  // 35 資料層：price_history.json 必須含這幾檔高價指標股——TWSE 價格欄是 '2,410.00' 這種帶千分位
  //    的字串，任何解析器忘了去逗號就會把 ≥1000 元的股票整條濾成空（2026-09-04/09-05 各中一次）。
  // 36 症狀層：自選股「拿得到 ≥2 筆歷史價、卻沒有畫出走勢線」＝FAIL。這條不管根因是解析、
  //    快取還是渲染，只要使用者看不到線就會被抓到。
  const dataGateErrors = [];
  try {
    const ph = await page.evaluate(async () => {
      const r = await fetch("data/price_history.json?t=" + Date.now());
      if (!r.ok) return { error: "HTTP " + r.status };
      const d = await r.json();
      const p = d.prices || {};
      const need = ["2330", "2454", "3008", "5274"];
      return { total: Object.keys(p).length, have: need.filter(c => (p[c] || []).length >= 2), lens: need.map(c => [c, (p[c] || []).length]) };
    });
    if (ph.error) dataGateErrors.push(`price_history.json 讀取失敗：${ph.error}`);
    else if (ph.have.length !== 4) dataGateErrors.push(`price_history.json 缺高價股歷史：${JSON.stringify(ph.lens)}`);
    results.price_history_total = ph.total;
  } catch (e) {
    dataGateErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("35. price_history.json 必含 2330/2454/3008/5274 且各 ≥2 筆（千分位逗號解析回歸防線）",
    dataGateErrors.length === 0, dataGateErrors.join("; ") || `全檔 ${results.price_history_total} 檔`);

  const sparkGateErrors = [];
  try {
    await page.evaluate(() => { try { localStorage.removeItem("alpha_live_url"); localStorage.removeItem("alpha_live_token"); } catch (e) {} LIVE.connected = false; });
    await page.evaluate(() => window.go("home"));
    await page.waitForTimeout(1800);
    const bad = await page.evaluate(async () => {
      const r = await fetch("data/quotes_tw.json?t=" + Date.now());
      const q = r.ok ? ((await r.json()).quotes || {}) : {};
      const out = [];
      for (const row of document.querySelectorAll("#wl-list .swipe-row")) {
        const code = row.querySelector("[data-flash-code]")?.dataset.flashCode;
        if (!code || !q[code]) continue;
        const hist = (q[code].sparkline || []).length;
        const drawn = !!row.querySelector("svg.spark polyline");
        if (hist >= 2 && !drawn) out.push({ code, hist, err: q[code].sparkline_error });
      }
      return out;
    });
    if (bad.length) sparkGateErrors.push(`有歷史價卻沒畫走勢線：${JSON.stringify(bad)}`);
  } catch (e) {
    sparkGateErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("36. 自選股有 ≥2 筆歷史價就必須畫出走勢線（沒畫＝FAIL，不管根因是解析/快取/渲染）",
    sparkGateErrors.length === 0, sparkGateErrors.join("; "));

  // 37.【2026-09-05新增，新一.6】評分頁不得再出現「需要新聞/供應鏈連動分析，下一輪實作」這類
  // 佔位字——八因子現在全部有真實資料源，缺漏的原因必須逐因子講清楚是哪個資料檔沒有這一檔。
  const placeholderErrors = [];
  try {
    const hit = await page.evaluate(() => {
      const bad = [];
      for (const k of Object.keys(FACTOR_MISSING_REASON)) {
        const t = FACTOR_MISSING_REASON[k] || "";
        if (/下一輪實作|待實作|TODO|尚未實作，之後/.test(t)) bad.push(k);
        if (!t || t.length < 10) bad.push(k + "(說明過短)");
      }
      return bad;
    });
    if (hit.length) placeholderErrors.push(`仍有佔位字/說明不足的因子：${hit.join(",")}`);
  } catch (e) {
    placeholderErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("37. 八因子的缺漏原因都是真實資料依賴說明，沒有「下一輪實作」這類佔位字",
    placeholderErrors.length === 0, placeholderErrors.join("; "));

  // 38.【2026-09-05新增，總司令「零」】全市場走勢線 data/sparklines.json：必須存在、涵蓋
  // 上市＋上櫃（用 stock_detail 有官方資料的4位數股票當基準）達 95%，並含高價股 2330/2454/3008/5274。
  const sparkFileErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const [spR, sdR] = await Promise.all([fetch("data/sparklines.json?t=" + Date.now()), fetch("data/stock_detail.json?t=" + Date.now())]);
      if (!spR.ok) return { error: "sparklines.json HTTP " + spR.status };
      const sp = (await spR.json()).sparklines || {};
      let universe = [], covered = 0;
      if (sdR.ok) {
        const sd = (await sdR.json()).stocks || {};
        universe = Object.keys(sd).filter(c => /^\d{4}$/.test(c) && (sd[c].institutional || sd[c].margin || sd[c].financials));
        covered = universe.filter(c => (sp[c] || []).length >= 2).length;
      }
      const need = ["2330", "2454", "3008", "5274"];
      return { total: Object.keys(sp).length, universe: universe.length, covered,
               pct: universe.length ? covered / universe.length * 100 : null,
               highPriced: need.map(c => [c, (sp[c] || []).length]) };
    });
    if (r.error) sparkFileErrors.push(r.error);
    else {
      if (r.pct !== null && r.pct < 95) sparkFileErrors.push(`上市+上櫃覆蓋率只有 ${r.pct.toFixed(1)}%（要求≥95%），${r.covered}/${r.universe}`);
      const badHigh = r.highPriced.filter(([, n]) => n < 2);
      if (badHigh.length) sparkFileErrors.push(`高價股沒有走勢線：${JSON.stringify(badHigh)}`);
      results.sparklines_total = r.total;
      results.sparklines_pct = r.pct;
    }
  } catch (e) {
    sparkFileErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("38. data/sparklines.json 全市場走勢線：上市+上櫃覆蓋率≥95%，且含 2330/2454/3008/5274",
    sparkFileErrors.length === 0, sparkFileErrors.join("; ") || `${results.sparklines_total} 檔，覆蓋率 ${(results.sparklines_pct || 0).toFixed(1)}%`);

  // 39.【2026-09-06新增，總司令 P0 稽核.一】資料一致性稽核閘門。
  // data/audit_report.json 由 scripts/data_audit.py 每晚產生；一致性違規率 >1%
  // 或有任何程式碼層級違規（空值直接 toFixed、float() 沒去千分位逗號）就 FAIL，
  // 不准 commit 到 main。報告檔不存在也算 FAIL——沒跑稽核不等於資料沒問題。
  const auditErrors = [];
  let auditInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const res = await fetch("data/audit_report.json?t=" + Date.now());
      if (!res.ok) return { error: "audit_report.json HTTP " + res.status };
      return await res.json();
    });
    if (r.error) auditErrors.push(r.error + "（代表稽核沒跑，先執行 python scripts/data_audit.py）");
    else {
      const rate = r.violation_rate == null ? null : r.violation_rate * 100;
      if (rate == null) auditErrors.push("報告缺 violation_rate 欄位");
      else if (rate > 1) auditErrors.push(`一致性違規率 ${rate.toFixed(2)}%>1%（${r.stocks_with_violation} 檔）`);
      if (r.code_free_violations) auditErrors.push(`程式碼層級違規 ${r.code_free_violations} 筆（空值格式化/千分位解析）`);
      auditInfo = `違規率 ${rate == null ? "—" : rate.toFixed(2) + "%"}、稽核 ${r.universe} 檔、完整度缺口 ${
        r.completeness_gap_rate == null ? "—" : (r.completeness_gap_rate * 100).toFixed(1) + "%"}`;
    }
  } catch (e) {
    auditErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("39. 資料一致性稽核閘門：一致性違規率≤1% 且無程式碼層級違規",
    auditErrors.length === 0, auditErrors.join("; ") || auditInfo);

  // 40.【2026-09-06新增】報告頁批次渲染不得拋未捕捉例外。
  // 光聖 6442 的「現價 1755、建議進場價 32」根因就是 renderReport() 對 peg=null 呼叫
  // .toFixed() 拋 TypeError，整段渲染中途死掉，上一檔的分批進場價就留在畫面上——
  // 名稱換了、數字沒換，而且完全沒有錯誤提示。這條檢查連開 30 檔報告頁，任何一檔
  // 讓頁面拋例外、或畫面出現 NaN/undefined 就 FAIL。
  const reportErrors = [];
  try {
    const pageErrors = [];
    const onPageError = (e) => pageErrors.push(String(e).slice(0, 160));
    page.on("pageerror", onPageError);
    const codes = await page.evaluate(async () => {
      if (typeof hydratePicks === "function") await hydratePicks(true);
      const c = typeof currentPicksCache === "function" ? currentPicksCache() : null;
      return (c && c.stocks || []).filter(x => x.rank).slice(0, 30).map(x => x.code);
    });
    for (const code of codes) {
      await page.evaluate((c) => showReport(c), code);
      await page.waitForTimeout(50);
      const txt = await page.evaluate(() => {
        const el = document.getElementById("report-industry-tech");
        return el ? el.innerText : "";
      });
      if (/NaN|undefined|Infinity/.test(txt)) reportErrors.push(`${code} 的數據面板出現 NaN/undefined`);
    }
    page.off("pageerror", onPageError);
    if (pageErrors.length) reportErrors.push(`報告頁拋出未捕捉例外 ${pageErrors.length} 次：${pageErrors[0]}`);
    if (!codes.length) reportErrors.push("拿不到任何有排名的股票，無法測試");
    else auditInfo = auditInfo;
  } catch (e) {
    reportErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("40. 連開30檔選股報告頁：不得拋未捕捉例外、數據面板不得出現NaN/undefined",
    reportErrors.length === 0, reportErrors.join("; "));

  // 41.【2026-09-06新增】選股榜單不得出現已下市/價格過期的股票。
  // 稽核第一份報告抓到三份榜單合計 161 檔已下市股票還在排名裡（矽品 2325 於 2018 年
  // 下市、勝華 2384 於 2014 年下市、康友-KY 6452 甚至是未來成長榜第 1 名），
  // 顯示的是 2010～2024 年的舊價格。
  const delistedErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const uniRes = await fetch("data/listed_universe.json?t=" + Date.now());
      if (!uniRes.ok) return { error: "listed_universe.json HTTP " + uniRes.status };
      const active = new Set((await uniRes.json()).active || []);
      if (active.size < 1000) return { error: `在市名冊只有 ${active.size} 檔，明顯不完整` };
      const bad = [];
      for (const f of ["scores.json", "scores_momentum.json", "scores_future.json"]) {
        const res = await fetch(f + "?t=" + Date.now());
        if (!res.ok) { bad.push(f + " HTTP " + res.status); continue; }
        const rows = (await res.json()).stocks || [];
        const miss = rows.filter(x => x.rank && !active.has(x.code)).map(x => x.code);
        if (miss.length) bad.push(`${f} 有 ${miss.length} 檔不在名冊：${miss.slice(0, 5).join(",")}`);
      }
      return { bad };
    });
    if (r.error) delistedErrors.push(r.error);
    else if (r.bad && r.bad.length) delistedErrors.push(r.bad.join("; "));
  } catch (e) {
    delistedErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("41. 三份選股榜單的排名股票都必須在官方在市名冊內（不得推薦已下市股票）",
    delistedErrors.length === 0, delistedErrors.join("; "));

  // 42.【2026-09-06新增，總司令實測.一】官方在市名冊內的股票不得出現「無報價」。
  // 總司令實測新增自選股後顯示「無報價」，但那些股票在 quotes_all_tw.json（2,837 檔）
  // 與 sparklines.json 裡都有價格——根因是各處只查 quotes_tw.json（Actions 只抓
  // 前 210 檔），查不到就放棄，沒有往後兩層退。這條檢查隨機抽 25 檔在市股票塞進
  // 自選股，任何一檔顯示「無報價」或價格是「—」就 FAIL。
  const quoteChainErrors = [];
  try {
    const r = await page.evaluate(async () => {
      await Promise.allSettled([ensureSparklines(), loadQuotesAllTw(), ensureListedUniverse()]);
      const active = [...LISTED_UNIVERSE];
      if (active.length < 1000) return { error: `在市名冊只有 ${active.length} 檔，不完整` };
      // 固定幾檔代表性標的（上櫃、千元股）＋隨機抽樣，兩者都要過
      const must = ["6442", "5274", "3008", "2454", "2330", "4966", "6488"];
      const pool = active.filter(c => !must.includes(c));
      const rnd = [];
      while (rnd.length < 18 && pool.length) rnd.push(pool[Math.floor(Math.random() * pool.length)]);
      const codes = [...new Set([...must, ...rnd])].slice(0, 25);
      // 名冊裡有官方停止交易股時，固定加驗一檔，確保新判準每輪都被測到（不靠隨機抽中）
      const suspAll = Object.keys((typeof LISTED_SUSPENDED !== "undefined" && LISTED_SUSPENDED) || {});
      if (suspAll.length && !codes.some(c => suspAll.includes(c))) codes.push(suspAll[0]);
      const bad = [];
      const susp = [];
      for (const c of codes) {
        // 2026-10-09 冒煙第 42 項判準修改（經總司令【先.五十六】A2 核准）：官方停止交易（SUSPENDED_OFFICIAL）者
        // 改驗「有沒有正確顯示停止交易說明」，不再要求有報價；其餘照舊必須有價。
        if (typeof suspendedInfo === "function" && suspendedInfo(c)) {
          susp.push(c);
          const lbl = typeof noQuoteLabel === "function" ? noQuoteLabel(c, false) : "";
          if (!String(lbl).includes("停止交易（官方")) bad.push(c + "(停止交易說明缺)");
          continue;
        }
        const q = resolveQuote(c, false);
        if (!q || q.price == null || !isFinite(q.price)) bad.push(c);
      }
      return { checked: codes.length, bad, susp };
    });
    if (r.error) quoteChainErrors.push(r.error);
    else if (r.bad.length) quoteChainErrors.push(`${r.bad.length}/${r.checked} 檔在市股票查不到報價：${r.bad.slice(0, 8).join(",")}`);
    else quoteChainErrors.length = 0;
    results.quote_chain_checked = r.checked || 0;
    results.quote_chain_suspended = (r.susp || []).join(",");
  } catch (e) {
    quoteChainErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("42. 官方在市名冊內的股票不得無報價（四層回退鏈：live→quotes_tw→quotes_all_tw→歷史收盤）",
    quoteChainErrors.length === 0, quoteChainErrors.join("; ") || `抽驗 ${results.quote_chain_checked} 檔全部有價或正確標示官方停止交易${results.quote_chain_suspended ? "（停止交易：" + results.quote_chain_suspended + "）" : ""}`);

  // 43.【2026-09-06新增，總司令健檢.一】診斷橫幅的「資料過舊」要看交易日曆，不是 rolling 24 小時。
  // 原本每逢週末與國定假日都會誤報「大盤/類股/三大法人 資料過舊」，但那些資料本來就只在
  // 交易日產生，週日看到星期五的收盤資料是完全正常的。誤報比不報更糟：叫久了使用者就
  // 不看橫幅，真的壞掉時也不會注意。這條同時驗「假日不誤報」與「真的過舊要照報」兩個方向。
  const calErrors = [];
  try {
    const r = await page.evaluate(() => {
      if (typeof isFreshForCalendar !== "function") return { error: "isFreshForCalendar 不存在" };
      const TW = ["Asia/Taipei", TW_HOLIDAYS_2026, 13, 30, 4 * 60];
      const US = ["America/New_York", US_HOLIDAYS_2026, 16, 0, 4 * 60];
      const t = s => new Date(s).getTime();
      const cases = [
        ["週日看週五收盤(台股)", isFreshForCalendar(t("2026-09-04T23:09:29Z"), ...TW, t("2026-09-06T04:00:00Z")), true],
        ["週日看上上週五(台股)", isFreshForCalendar(t("2026-08-28T23:09:29Z"), ...TW, t("2026-09-06T04:00:00Z")), false],
        ["交易日盤後資料停在上週五(台股)", isFreshForCalendar(t("2026-09-04T23:09:29Z"), ...TW, t("2026-09-08T12:00:00Z")), false],
        ["交易日盤中看前一交易日(台股)", isFreshForCalendar(t("2026-09-07T10:00:00Z"), ...TW, t("2026-09-08T03:00:00Z")), true],
        ["國定假日看前一交易日(台股)", isFreshForCalendar(t("2026-10-08T10:00:00Z"), ...TW, t("2026-10-09T04:00:00Z")), true],
        ["週日看週五收盤(美股)", isFreshForCalendar(t("2026-09-04T23:09:44Z"), ...US, t("2026-09-06T16:00:00Z")), true],
        ["感恩節看前一交易日(美股)", isFreshForCalendar(t("2026-11-25T22:00:00Z"), ...US, t("2026-11-26T18:00:00Z")), true],
        ["交易日盤後資料停在三天前(美股)", isFreshForCalendar(t("2026-09-08T22:00:00Z"), ...US, t("2026-09-11T23:00:00Z")), false],
      ];
      return { bad: cases.filter(c => c[1] !== c[2]).map(c => `${c[0]}：判定${c[1] ? "新鮮" : "過舊"}但預期${c[2] ? "新鮮" : "過舊"}`), n: cases.length };
    });
    if (r.error) calErrors.push(r.error);
    else if (r.bad.length) calErrors.push(r.bad.join("; "));
    results.calendar_cases = r.n || 0;
  } catch (e) {
    calErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("43. 資料過舊判定走交易日曆（假日不誤報、真過舊照報）",
    calErrors.length === 0, calErrors.join("; ") || `${results.calendar_cases} 個情境全部符合`);

  // 44.【2026-09-10新增（建置一.2）】估值區間卡必須真的算出東西，而且算法本身要正確。
  // 這張卡取代了原本的「目標價…本輪尚未實作」佔位字。檢查三件事：
  //   (a) 純函式單元檢查：近四季EPS必須拒絕「不連續」與「過期」的季報序列。
  //       stock_detail.json 的季報歷史 2025Q1~2026Q1 是空的，直接取最後四筆會得到
  //       橫跨兩年的假 TTM（2317 會算出 17.26、2603 會算出 67.88），生出離譜的估值。
  //   (b) 百分位用線性內插，與 numpy.percentile 預設法一致。
  //   (c) 實際開報告頁：卡片不得停在「載入中…」、不得出現 NaN/undefined、
  //       不得殘留「尚未實作」；有算出區間時必須 p25 ≤ p50 ≤ p75 且都 > 0。
  const valErrors = [];
  let valInfo = "";
  try {
    const unit = await page.evaluate(() => {
      const out = [];
      const mk = (qs) => ({ financials: { quarters: qs } });
      const y = new Date().getFullYear();
      const ok = epsTtmFromDetail(mk([
        { year: y - 1, quarter: 3, eps: 1 }, { year: y - 1, quarter: 4, eps: 2 },
        { year: y, quarter: 1, eps: 3 }, { year: y, quarter: 2, eps: 4 }]), null);
      if (!ok || Math.abs(ok.eps - 10) > 1e-9) out.push("連續四季應算出 EPS=10，實得 " + JSON.stringify(ok));
      const gap = epsTtmFromDetail(mk([
        { year: y - 2, quarter: 2, eps: 1 }, { year: y - 2, quarter: 3, eps: 2 },
        { year: y - 2, quarter: 4, eps: 3 }, { year: y, quarter: 2, eps: 4 }]), null);
      if (gap !== null) out.push("不連續季報應回 null，實得 " + JSON.stringify(gap));
      const stale = epsTtmFromDetail(mk([
        { year: y - 2, quarter: 1, eps: 1 }, { year: y - 2, quarter: 2, eps: 2 },
        { year: y - 2, quarter: 3, eps: 3 }, { year: y - 2, quarter: 4, eps: 4 }]), null);
      if (stale !== null) out.push("過期季報應回 null，實得 " + JSON.stringify(stale));
      const nul = epsTtmFromDetail(mk([
        { year: y - 1, quarter: 3, eps: 1 }, { year: y - 1, quarter: 4, eps: null },
        { year: y, quarter: 1, eps: 3 }, { year: y, quarter: 2, eps: 4 }]), null);
      if (nul !== null) out.push("含 null 的季報應回 null，實得 " + JSON.stringify(nul));
      const p = [1, 2, 3, 4, 5];
      if (Math.abs(percentileLinear(p, 0.25) - 2) > 1e-9) out.push("percentileLinear p25 應為 2");
      if (Math.abs(percentileLinear(p, 0.5) - 3) > 1e-9) out.push("percentileLinear p50 應為 3");
      if (Math.abs(percentileLinear([1, 2, 3, 4], 0.25) - 1.75) > 1e-9) out.push("percentileLinear 內插應為 1.75");
      return out;
    });
    valErrors.push(...unit);

    const codes = await page.evaluate(() => {
      const c = typeof currentPicksCache === "function" ? currentPicksCache() : null;
      return (c && c.stocks || []).filter(x => x.rank).slice(0, 12).map(x => x.code);
    });
    let withBand = 0, insufficient = 0;
    for (const code of codes) {
      await page.evaluate((c) => showReport(c), code);
      let txt = "";
      for (let i = 0; i < 60; i++) {           // 首檔要載 stock_detail.json，給足時間
        await page.waitForTimeout(250);
        txt = await page.evaluate(() => {
          const el = document.getElementById("report-valuation-band");
          return el ? el.innerText : "";
        });
        if (txt && !/載入中/.test(txt)) break;
      }
      if (!txt || /載入中/.test(txt)) { valErrors.push(`${code} 的估值區間卡停在「載入中…」`); continue; }
      if (/NaN|undefined|Infinity/.test(txt)) valErrors.push(`${code} 的估值區間卡出現 NaN/undefined/Infinity`);
      if (/尚未實作|下一輪/.test(txt)) valErrors.push(`${code} 的估值區間卡殘留佔位字`);
      if (/樣本不足無法估算|不適用|只涵蓋台股|查不到這檔的產業分類/.test(txt)) { insufficient++; continue; }
      const nums = await page.evaluate(() => {
        const el = document.getElementById("report-valuation-band");
        return [...el.querySelectorAll("div.num")].slice(0, 3)
          .map(x => parseFloat(x.textContent.replace(/,/g, "")));
      });
      if (nums.length !== 3 || nums.some(v => !isFinite(v) || v <= 0)) {
        valErrors.push(`${code} 的三個價位不是正數：${JSON.stringify(nums)}`);
      } else if (!(nums[0] <= nums[1] + 1e-9 && nums[1] <= nums[2] + 1e-9)) {
        valErrors.push(`${code} 的價位順序不對（應 p25≤p50≤p75）：${JSON.stringify(nums)}`);
      } else withBand++;
      if (!/樣本/.test(txt)) valErrors.push(`${code} 的估值區間卡沒有標示產業樣本數`);
    }
    if (!codes.length) valErrors.push("拿不到任何有排名的股票，無法測試");
    valInfo = `${codes.length} 檔：算出區間 ${withBand} 檔、誠實顯示樣本/資料不足 ${insufficient} 檔`;
  } catch (e) {
    valErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("44. 估值區間卡（同產業PE百分位×近四季EPS）：算法單元檢查 + 實開報告頁不得停在載入中/出現NaN/殘留佔位字",
    valErrors.length === 0, valErrors.join("; ") || valInfo);

  // 45.【2026-09-10新增，建置一.4驗收】個股頁（#scr-stock，五個分頁：總覽/營收/
  // 財報/籌碼/AI）不得殘留「尚未實作/下一輪/本輪」這幾個字——CLAUDE.md原話講清楚
  // 這條是「等功能做出來後自然歸零的檢查，不是叫你刪字」：建置一.1（新聞/事件）／
  // 建置一.2（估值區間）／建置一.3（美股類股/ADR）三張卡陸續做出真實資料後，這幾
  // 個字理應已經從個股頁消失。用真實開頁+切分頁掃innerText驗證（不是grep原始碼——
  // grep會抓到程式註解，那不是使用者實際看到的畫面）。刻意不擋「功能建置中」這類
  // 誠實揭露用語（AI個股簡報/券商報告雷達分頁目前仍是這種誠實空狀態，不在本次
  // 建置一範圍內，不該被這條檢查誤判）。
  const stockPagePlaceholderErrors = [];
  const PLACEHOLDER_RE = /尚未實作|下一輪|本輪/;
  const PLACEHOLDER_CODES = ["2330", "2603", "AAPL"];
  try {
    for (const code of PLACEHOLDER_CODES) {
      await page.evaluate((c) => window.openStock(c), code);
      await page.waitForTimeout(1200);
      for (const sub of ["ov", "rev", "fin", "chip", "ai"]) {
        await page.evaluate((s) => {
          document.querySelector(`#stock-tabs button[data-sub="${s}"]`)?.click();
        }, sub);
        await page.waitForTimeout(600);
        const txt = await page.evaluate(() => document.getElementById("scr-stock")?.innerText || "");
        const m = txt.match(PLACEHOLDER_RE);
        if (m) stockPagePlaceholderErrors.push(`${code} 的「${sub}」分頁出現佔位字「${m[0]}」`);
      }
    }
  } catch (e) {
    stockPagePlaceholderErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("45. 個股頁（總覽/營收/財報/籌碼/AI五分頁）不得殘留「尚未實作/下一輪/本輪」佔位字",
    stockPagePlaceholderErrors.length === 0, stockPagePlaceholderErrors.join("; "));

  // 45b.【2026-10-10 先.六十-A6】全 repo 掃描「功能建置中／尚未串接／原型階段」：用 git grep 掃所有追蹤檔，
  // 每一行命中都必須在 data/placeholder_allowlist.json 登記（path 相同，match 為 "*" 或該行包含 match），否則 FAIL。
  // 目的：假功能（例如先.六十 移除的台股假下單抽屜、規劃中機器人卡）不能再用「誠實佔位」字樣躲過檢查。
  const repoPlaceholderErrors = [];
  let repoPlaceholderInfo = "";
  try {
    const { execFileSync } = await import("node:child_process");
    const fs = await import("node:fs");
    const allow = JSON.parse(fs.readFileSync("data/placeholder_allowlist.json", "utf8"));
    const pats = allow.patterns || [];
    let out = "";
    try {
      out = execFileSync("git", ["grep", "-n", "-I", "-E", pats.join("|")], { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
    } catch (e) {
      if (e.status !== 1) throw e;  // git grep 沒有任何命中時 exit 1，不是錯誤
    }
    const hits = out.split(/\r?\n/).filter(Boolean).map((l) => {
      const m = l.match(/^(.*?):(\d+):(.*)$/);
      return m ? { path: m[1], line: +m[2], text: m[3] } : null;
    }).filter(Boolean);
    const used = new Set();
    for (const h of hits) {
      const idx = (allow.entries || []).findIndex((e) => e.path === h.path && (e.match === "*" || h.text.includes(e.match)));
      if (idx < 0) repoPlaceholderErrors.push(`${h.path}:${h.line} 未登記：${h.text.trim().slice(0, 70)}`);
      else used.add(idx);
    }
    const unused = (allow.entries || []).filter((e, i) => !used.has(i) && e.match !== "*").map((e) => `${e.path}「${e.match}」`);
    repoPlaceholderInfo = `命中 ${hits.length} 行、登記 ${(allow.entries || []).length} 條` + (unused.length ? `；已無命中可刪的登記：${unused.join("、")}` : "");
    if ((allow.entries || []).some((e) => !e.reason)) repoPlaceholderErrors.push("allowlist 有條目缺 reason");
  } catch (e) { repoPlaceholderErrors.push(`測試本身出錯：${e.message || e}`); }
  record("45b. 全 repo「功能建置中／尚未串接／原型階段」每一處都已在 data/placeholder_allowlist.json 登記理由", repoPlaceholderErrors.length === 0, repoPlaceholderErrors.slice(0, 8).join("; ") || repoPlaceholderInfo);

  // 46.【2026-09-10新增，健檢.四驗收】三份選股榜單（scores/scores_momentum/
  // scores_future）裡，官方在市名冊內的股票，row.industry 覆蓋率必須≥95%——
  // 個股頁「所屬產業」欄位（index.html「所屬產業」/report-industry）本來就有
  // 讀row.industry，健檢.四要修的是「來源缺」：generate_scores_*.py 要從
  // data/company_info.json 把 industry 併回每一列。這條檢查驗資料端，不是
  // UI端（UI端讀不讀得到值完全取決於這裡算出的覆蓋率）。
  const industryErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const uniRes = await fetch("data/listed_universe.json?t=" + Date.now());
      if (!uniRes.ok) return { error: "listed_universe.json HTTP " + uniRes.status };
      const active = new Set((await uniRes.json()).active || []);
      if (active.size < 1000) return { error: `在市名冊只有 ${active.size} 檔，明顯不完整` };
      const perBoard = {};
      for (const f of ["scores.json", "scores_momentum.json", "scores_future.json"]) {
        const res = await fetch(f + "?t=" + Date.now());
        if (!res.ok) { perBoard[f] = { error: "HTTP " + res.status }; continue; }
        const rows = ((await res.json()).stocks || []).filter(x => active.has(x.code));
        const withInd = rows.filter(x => x.industry).length;
        perBoard[f] = { total: rows.length, withInd, pct: rows.length ? withInd / rows.length * 100 : 0 };
      }
      return { perBoard };
    });
    if (r.error) industryErrors.push(r.error);
    else {
      for (const [f, v] of Object.entries(r.perBoard)) {
        if (v.error) { industryErrors.push(`${f}: ${v.error}`); continue; }
        if (v.total === 0) { industryErrors.push(`${f}: 在市個股列數為0，無法計算覆蓋率`); continue; }
        if (v.pct < 95) industryErrors.push(`${f} industry覆蓋率 ${v.pct.toFixed(1)}%<95%（${v.withInd}/${v.total}）`);
      }
      results.industry_coverage = r.perBoard;
    }
  } catch (e) {
    industryErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("46. 三份選股榜單在市個股 row.industry 覆蓋率 ≥95%（健檢.四）",
    industryErrors.length === 0, industryErrors.join("; ") ||
    Object.entries(results.industry_coverage || {}).map(([f, v]) => `${f}=${v.pct.toFixed(1)}%`).join("、"));

  // 47.【2026-09-15新增，金流一.6驗收】sector_flow.json 每個產業合計必須等於
  // 成分股加總（容差1股=0.001張）。build_sector_flow.py 把 sectors[產業].net_Xd_lots
  // 算成 sum(stocks_out[c].net_Xd.total_lots for c in 該產業)，理論上是恆等式；
  // 這裡不重播 build_sector_flow.py 的算法，只用 stocks 物件（成分股逐檔資料，
  // 使用者在 index.html 產業金流卡點開成分股排行時實際看到的同一批數字）重新
  // 加總，跟 sectors 物件（產業總計，使用者在同一張卡看到的標題數字）比對——
  // 兩端都是頁面/檔案上直接看得到的數字，符合稽核恆等式鐵律。逐一掃描每個
  // 已知視窗（meta.windows_usable），不是只挑一個。
  const sectorSumErrors = [];
  let sectorSumInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const res = await fetch("data/sector_flow.json?t=" + Date.now());
      if (!res.ok) return { error: "sector_flow.json HTTP " + res.status };
      const d = await res.json();
      const sectors = d.sectors || {};
      const stocks = d.stocks || {};
      const windows = (d.meta && d.meta.windows_usable) || [];
      if (!windows.length) return { error: "meta.windows_usable 是空的，無視窗可驗" };
      const bad = [];
      let checked = 0;
      for (const [ind, agg] of Object.entries(sectors)) {
        for (const w of windows) {
          const lotsKey = `net_${w}d_lots`;
          if (!(lotsKey in agg)) continue;
          let sum = 0;
          for (const s of Object.values(stocks)) {
            if (s.industry !== ind) continue;
            const nw = s[`net_${w}d`];
            sum += (nw && typeof nw.total_lots === "number") ? nw.total_lots : 0;
          }
          checked++;
          const diff = Math.abs(sum - agg[lotsKey]);
          if (diff > 0.001) {
            bad.push(`${ind}/${w}日：產業合計${agg[lotsKey]}張 vs 成分股加總${sum.toFixed(3)}張，差${diff.toFixed(3)}張`);
          }
        }
      }
      return { bad, checked, sectorCount: Object.keys(sectors).length, windows };
    });
    if (r.error) sectorSumErrors.push(r.error);
    else {
      sectorSumErrors.push(...r.bad);
      sectorSumInfo = `${r.sectorCount} 個產業 × 視窗${JSON.stringify(r.windows)}，共驗 ${r.checked} 組，全部一致`;
    }
  } catch (e) {
    sectorSumErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("47. sector_flow.json 每個產業合計＝成分股加總（容差1股）",
    sectorSumErrors.length === 0, sectorSumErrors.join("; ") || sectorSumInfo);

  // 48.【2026-09-15新增，金流一.6驗收】sector_flow.json 的 meta.date 必須等於
  // T86 最新日期。「T86最新日期」取 data/institutional_history.json（金流一.1
  // 規格明載：這支檔案是「每日管線既有呼叫」把 T86／TPEx 三大法人歷史累積
  // 出來的來源，見 sector_flow.json meta.source），也就是它 dates 陣列的最後
  // 一筆——不重新實作 build_sector_flow.py 內部的覆蓋率篩選邏輯（那是產生
  // 端的演算法，稽核不能自己重播演算法），只驗兩份檔案上「日期」這個欄位
  // 彼此對得上，這是使用者/協作者都能直接在檔案裡看到的兩個數字。
  const t86DateErrors = [];
  let t86DateInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const [flowRes, histRes] = await Promise.all([
        fetch("data/sector_flow.json?t=" + Date.now()),
        fetch("data/institutional_history.json?t=" + Date.now()),
      ]);
      if (!flowRes.ok) return { error: "sector_flow.json HTTP " + flowRes.status };
      if (!histRes.ok) return { error: "institutional_history.json HTTP " + histRes.status };
      const flow = await flowRes.json();
      const hist = await histRes.json();
      const flowDate = flow.meta && flow.meta.date;
      const dates = hist.dates || [];
      const t86Latest = dates.length ? dates[dates.length - 1] : null;
      return { flowDate, t86Latest };
    });
    if (r.error) t86DateErrors.push(r.error);
    else if (!r.flowDate) t86DateErrors.push("sector_flow.json 缺 meta.date 欄位");
    else if (!r.t86Latest) t86DateErrors.push("institutional_history.json 的 dates 陣列是空的，無法比對");
    else if (r.flowDate !== r.t86Latest) {
      t86DateErrors.push(`sector_flow.json meta.date=${r.flowDate} ≠ institutional_history.json 最新日期=${r.t86Latest}`);
    } else {
      t86DateInfo = `兩者皆為 ${r.flowDate}`;
    }
  } catch (e) {
    t86DateErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("48. sector_flow.json 的 date 必須等於 T86（institutional_history.json）最新日期",
    t86DateErrors.length === 0, t86DateErrors.join("; ") || t86DateInfo);

  // 49.【2026-09-15新增，週六.三／稽核二.五】三大法人柱狀圖零基線：正值柱要從
  // 共用基線往上長、負值柱從同一條基線往下長，不是舊版「單一bar在盒子裡置中」
  // （那樣正負值視覺上各自往兩邊對稱伸展，沒有共用基線，容易誤讀漲跌幅度）。
  // 用getBoundingClientRect直接量畫面上的像素座標（不重播render邏輯），
  // 斷言：(a) 每一欄.up-zone底邊與.dn-zone頂邊的y座標相等（=該欄自己的基線）；
  // (b) 所有欄位的基線y座標彼此相等（=全圖共用同一條基線，不是各欄自己置中）；
  // (c) 正值柱（.u）底邊y＝基線y、負值柱（.dn）頂邊y＝基線y（原始P0裁示原文
  // 「正值柱底y必須等於基線y」的字面斷言)。
  const barBaselineErrors = [];
  let barBaselineInfo = "";
  try {
    await page.evaluate(() => window.go("market"));
    await page.waitForTimeout(500);
    await page.evaluate(() => window.go("chips-market"));
    await page.waitForTimeout(1000);
    const r = await page.evaluate(() => {
      const cols = Array.from(document.querySelectorAll("#inst-bars .db"));
      if (!cols.length) return { error: "#inst-bars 沒有任何柱狀欄位（可能仍在載入中或查無資料）" };
      const baselines = [];
      const bad = [];
      for (const col of cols) {
        const upZone = col.querySelector(".up-zone");
        const dnZone = col.querySelector(".dn-zone");
        if (!upZone || !dnZone) { bad.push("欄位缺少.up-zone或.dn-zone"); continue; }
        const upRect = upZone.getBoundingClientRect();
        const dnRect = dnZone.getBoundingClientRect();
        const baselineY = upRect.bottom;
        if (Math.abs(dnRect.top - baselineY) > 1) {
          bad.push(`.up-zone底邊y=${upRect.bottom.toFixed(1)} 與 .dn-zone頂邊y=${dnRect.top.toFixed(1)} 不相等`);
        }
        baselines.push(baselineY);
        const bar = col.querySelector(".u, .dn");
        if (bar) {
          const barRect = bar.getBoundingClientRect();
          const barIsUp = bar.classList.contains("u");
          const barEdge = barIsUp ? barRect.bottom : barRect.top;
          if (Math.abs(barEdge - baselineY) > 1) {
            bad.push(`${barIsUp ? "正值柱底" : "負值柱頂"}y=${barEdge.toFixed(1)} ≠ 基線y=${baselineY.toFixed(1)}`);
          }
        }
      }
      const baselineSpread = baselines.length ? Math.max(...baselines) - Math.min(...baselines) : 0;
      if (baselineSpread > 1) bad.push(`各欄基線y座標不一致，最大差${baselineSpread.toFixed(1)}px（應共用同一條基線）`);
      return { bad, colCount: cols.length, baselineSpread };
    });
    if (r.error) barBaselineErrors.push(r.error);
    else {
      barBaselineErrors.push(...r.bad);
      barBaselineInfo = `${r.colCount}欄，基線y座標最大差${r.baselineSpread.toFixed(1)}px`;
    }
    await page.evaluate(() => window.go("market"));
  } catch (e) {
    barBaselineErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("49. 三大法人柱狀圖零基線：正值柱底/負值柱頂皆等於共用基線y座標",
    barBaselineErrors.length === 0, barBaselineErrors.join("; ") || barBaselineInfo);

  // 50.【2026-09-15新增，週六.六／稽核二.五】首頁狀態列文案：週末/國定假日要顯示
  // 「休市」而不是「已收盤」——已收盤暗示「今天有開、現在收了」，週末/假日根本沒
  // 開盤，是不同的狀態。`renderHomeStatusSummary()`內部直接呼叫`new Date()`（真實
  // 的「現在」），無法從外部注入測試時間，所以改為直接單元測試驅動這段文案的
  // `isTradingDay()`（跟健檢.一「資料過舊」判斷同一份函式與同一份TW_HOLIDAYS_2026
  // 假日表，不是另外造一套邏輯），涵蓋週六/週日/國定假日（2026-09-25，剛好是
  // 星期五但落在假日表——驗證「純看星期幾」不夠、真的有查假日表）三種「休市」情境
  // 與兩種一般交易日情境。
  const closedLabelErrors = [];
  let closedLabelInfo = "";
  try {
    const r = await page.evaluate(() => {
      if (typeof isTradingDay !== "function") return { error: "isTradingDay 不存在" };
      if (typeof TW_HOLIDAYS_2026 === "undefined") return { error: "TW_HOLIDAYS_2026 不存在" };
      const cases = [
        ["2026-09-19T10:00:00+08:00", false, "週六"],
        ["2026-09-20T10:00:00+08:00", false, "週日"],
        ["2026-09-25T10:00:00+08:00", false, "國定假日（教師節，星期五）"],
        ["2026-09-15T10:00:00+08:00", true, "週二交易日"],
        ["2026-09-18T10:00:00+08:00", true, "週五交易日"],
      ];
      const bad = [];
      for (const [iso, expected, label] of cases) {
        const got = isTradingDay(new Date(iso), "Asia/Taipei", TW_HOLIDAYS_2026);
        if (got !== expected) bad.push(`${label}(${iso})：isTradingDay判定${got}，預期${expected}（會讓首頁狀態列文案錯誤）`);
      }
      return { bad, n: cases.length };
    });
    if (r.error) closedLabelErrors.push(r.error);
    else {
      closedLabelErrors.push(...r.bad);
      closedLabelInfo = `${r.n} 個情境全部符合`;
    }
  } catch (e) {
    closedLabelErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("50. 首頁狀態列「休市」vs「已收盤」文案：isTradingDay()正確區分週末/國定假日與一般交易日",
    closedLabelErrors.length === 0, closedLabelErrors.join("; ") || closedLabelInfo);

  // 51.【2026-10-01新增，先.八-三】選股頁「供給觀察」頁籤：固定標示免責句、顯示I1–I4原始值與
  // 桶內百分位、可依產業篩選與單一指標排序；整張卡不得出現買進／綜合分數／排名／報酬／績效字樣。
  const supplyErrors = [];
  let supplyInfo = "";
  try {
    await page.evaluate(() => go("picks"));
    await page.waitForTimeout(400);
    await page.evaluate(() => switchSupplyView());
    await page.waitForFunction(() => (typeof SUPPLY_CACHE !== "undefined" && SUPPLY_CACHE && document.querySelectorAll("#supply-list > div b").length > 0) || /尚未產生/.test(document.getElementById("supply-list").textContent), null, { timeout: 8000 });
    const r = await page.evaluate(() => {
      const card = document.getElementById("picks-supply-card");
      const vis = el => !!el && el.offsetParent !== null;
      const text = card.innerText;
      const out = { visible: vis(card), text: text.length };
      out.disclaimer = text.includes("描述性資料，未經回測驗證；紙上追蹤中，滿8季前不得作為真錢依據");
      out.rows = document.querySelectorAll("#supply-list > div").length;
      out.lbHidden = !vis(document.getElementById("picks-list-card")) && !vis(document.getElementById("picks-chips"));
      out.bad = ["買進", "綜合", "排名", "報酬", "績效", "勝率", "夏普", "Sortino"].filter(w => text.includes(w));
      const firstCode = () => { const b = document.querySelector("#supply-list > div b"); return b ? b.textContent : ""; };
      out.first1 = firstCode();
      // 先.十-三：覆蓋率<80%不得顯示百分位，只顯示「資料準備中（已涵蓋 x／N 檔）」；達標後才顯示百分位
      const cov = SUPPLY_CACHE.meta.coverage_period;
      out.cov = cov;
      out.lowNoPct = !document.getElementById("supply-list").innerText.includes("桶內");
      out.lowMsg = /資料準備中（已涵蓋 \d+／[\d,]+ 檔）/.test(document.getElementById("supply-meta-line").innerText);
      const saved = SUPPLY_CACHE.meta.coverage_period;
      SUPPLY_CACHE.meta.coverage_period = 0.9; renderSupply();
      out.highHasPct = document.getElementById("supply-list").innerText.includes("桶內") && !/資料準備中/.test(document.getElementById("supply-meta-line").innerText);
      SUPPLY_CACHE.meta.coverage_period = saved; renderSupply();
      if (typeof onSupplySort === "function") { onSupplySort("I2"); out.first2 = firstCode(); onSupplySort("I2"); out.first3 = firstCode(); onSupplySort("I1"); }
      const sel = document.getElementById("supply-industry");
      out.nOpt = sel ? sel.options.length : 0;
      if (sel && sel.options.length > 1) {
        sel.value = sel.options[1].value; onSupplyFilter(sel.value);
        out.filtered = [...document.querySelectorAll("#supply-list > div")].every(d => d.textContent.includes(sel.value));
        out.nFiltered = document.querySelectorAll("#supply-list > div").length;
        onSupplyFilter("");
      }
      return out;
    });
    if (!r.visible) supplyErrors.push("供給觀察卡不可見");
    if (!r.disclaimer) supplyErrors.push("缺固定免責句");
    if (!r.lbHidden) supplyErrors.push("切到供給觀察後排行榜未隱藏");
    if (r.bad.length) supplyErrors.push("出現禁用字樣：" + r.bad.join(","));
    if (r.rows === 0) supplyErrors.push("沒有任何資料列");
    if (r.cov < 0.8) {
      if (!r.lowNoPct) supplyErrors.push("覆蓋率<80%仍顯示桶內百分位");
      if (!r.lowMsg) supplyErrors.push("覆蓋率<80%缺「資料準備中（已涵蓋 x／N 檔）」");
    }
    if (!r.highHasPct) supplyErrors.push("覆蓋率達標（模擬0.9）後未顯示百分位或仍顯示資料準備中");
    if (r.nOpt > 1 && r.filtered === false) supplyErrors.push("產業篩選後仍有他產業列");
    supplyInfo = `覆蓋率${(r.cov*100).toFixed(1)}%：低覆蓋不顯示百分位=${r.lowNoPct}、達標模擬顯示百分位=${r.highHasPct}；列數${r.rows}、產業選項${r.nOpt - 1}、篩選後${r.nFiltered ?? "-"}列、排序前後首列：${r.first1}→${r.first2}→${r.first3}`;
    await page.screenshot({ path: "scripts/_supply_tab.png", fullPage: false });
    await page.evaluate(() => switchPicksBoard("value"));
    await page.waitForTimeout(300);
    const back = await page.evaluate(() => ({ lb: document.getElementById("picks-list-card").offsetParent !== null, sup: document.getElementById("picks-supply-card").offsetParent !== null }));
    if (!back.lb || back.sup) supplyErrors.push("切回價值成長榜後版面未還原");
    await page.evaluate(() => go("home"));
  } catch (e) {
    supplyErrors.push(`測試本身出錯：${e.message || e}`);
  }
  record("51. 選股頁「供給觀察」頁籤：固定免責句、I1–I4原始值、覆蓋率<80%不顯示桶內百分位而顯示資料準備中、達標才顯示百分位、產業篩選、單指標排序、無禁用字樣、切回榜單版面還原",
    supplyErrors.length === 0, supplyErrors.join("; ") || supplyInfo);

  const btErrors = [];
  try {
    const bt = await page.evaluate(() => btCalc({ nw: 6e6, pmt: 0, target: Date.UTC(2038, 0, 13), now: Date.UTC(2026, 9, 6), rate: 0.1019 }));
    const within = (x, t) => Math.abs(x - t) / t <= 0.02;
    if (!within(bt.fvNo, 17.9e6)) btErrors.push(`不投入推算 ${Math.round(bt.fvNo)} 偏離 17.9M 超過2%`);
    if (!within(bt.needPmt, 340e3)) btErrors.push(`所需月投入 ${Math.round(bt.needPmt)} 偏離 340k 超過2%`);
    const out = await page.evaluate(() => { localStorage.setItem("alpha_bt_path", JSON.stringify({ nw: "6000000", pmt: "300000", birth: "1998-01-13", age: "40" })); renderBtPath(); return document.getElementById("bt-out").textContent; });
    if (!out.includes("目標日期：2038-01-13")) btErrors.push(`卡片未顯示目標日期：${out.slice(0, 120)}`);
    await page.evaluate(() => localStorage.removeItem("alpha_bt_path"));
  } catch (e) { btErrors.push(`測試本身出錯：${e.message || e}`); }
  record("52. 破億路徑公式驗算：淨資產600萬、目標2038-01-13、10.19%→推算約1790萬、所需月投入約34萬（各在2%內）；卡片可渲染",
    btErrors.length === 0, btErrors.join("; "));

  // 53.【2026-10-06 先.三十五】inline 事件處理器呼叫的函式都必須在頁面全域存在。
  // 起因：先.三十一-一 只加了「開啟本裝置推播／測試推播」按鈕，pushEnable／pushTest 根本不存在，
  // 按了只會在 console 拋 ReferenceError，舊冒煙沒有任何一項會點到它，所以「全部通過」是假的。
  // 掃描範圍：原始 index.html 的靜態屬性＋測試結束時 DOM 上（含動態產生）的屬性。
  const handlerErrors = [];
  let handlerInfo = "";
  try {
    const res = await page.evaluate(async () => {
      // 常備.開發-20 丙案：分頁程式點到該頁才載入；先把全部分頁檔載入，再檢查「整個 App 的程式」裡處理器函式都存在
      //（未載入的分頁其處理器所在畫面根本還看不到；載入失敗本身會讓 loadAppModule reject → 本項 FAIL）。
      if (typeof loadAppModule === "function") for (const m of ["shared", "market", "picks", "stock", "trade", "journal", "settings"]) await loadAppModule(m);
      const src = (await Promise.all(["index.html", "app.js", "app.css", "app-shared.js", "app-market.js", "app-picks.js", "app-stock.js", "app-trade.js", "app-journal.js", "app-settings.js"].map(async u => (await fetch(u, { cache: "no-store" })).text()))).join("\n");  // 常備.開發-20：CSS/JS 已拆出，全部合併掃描（丙案再拆分頁檔）
      const KW = new Set(["if", "for", "while", "switch", "return", "typeof", "function", "new", "catch", "void", "await", "async", "delete", "in", "of", "do"]);
      const vals = [];
      const re = /\son(?:click|input|change)\s*=\s*"([^"]*)"/gi;
      let m; while ((m = re.exec(src))) vals.push(m[1].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&"));
      for (const el of document.querySelectorAll("[onclick],[oninput],[onchange]")) for (const a of ["onclick", "oninput", "onchange"]) { const v = el.getAttribute(a); if (v) vals.push(v); }
      const names = new Set();
      for (const v of vals) {
        const code = v.replace(/'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|`(?:[^`\\]|\\.)*`/g, "''");
        const r2 = /(^|[^.\w$])([A-Za-z_$][\w$]*)\s*\(/g; let k;
        while ((k = r2.exec(code))) if (!KW.has(k[2])) names.add(k[2]);
      }
      const missing = [];
      for (const n of names) { let t; try { t = (0, eval)("typeof " + n); } catch (e) { t = "error"; } if (t !== "function") missing.push(n + "(" + t + ")"); }
      return { count: vals.length, names: names.size, missing };
    });
    handlerInfo = `掃描 ${res.count} 個處理器屬性、${res.names} 個不同函式名`;
    if (res.missing.length) handlerErrors.push("未定義：" + res.missing.join("、"));
  } catch (e) { handlerErrors.push(`測試本身出錯：${e.message || e}`); }
  record("53. index.html 所有 onclick／oninput／onchange 呼叫的函式都在頁面全域定義（缺一個即 FAIL）",
    handlerErrors.length === 0, handlerErrors.join("; ") || handlerInfo);

  // 54.【2026-10-06 先.三十五】推播兩顆按鈕存在且綁定的函式是 function
  const pushBtnErrors = [];
  try {
    const r = await page.evaluate(() => ({
      enableBtn: !!document.querySelector('button[onclick="pushEnable()"]'),
      testBtn: !!document.getElementById("push-test-btn"),
      enable: typeof pushEnable, test: typeof pushTest, note: !!document.getElementById("push-note"),
    }));
    if (!r.enableBtn) pushBtnErrors.push("找不到「開啟本裝置推播」按鈕");
    if (!r.testBtn) pushBtnErrors.push("找不到「測試推播」按鈕");
    if (r.enable !== "function") pushBtnErrors.push(`pushEnable 是 ${r.enable}`);
    if (r.test !== "function") pushBtnErrors.push(`pushTest 是 ${r.test}`);
    if (!r.note) pushBtnErrors.push("找不到 #push-note 狀態列");
  } catch (e) { pushBtnErrors.push(`測試本身出錯：${e.message || e}`); }
  record("54. 推播按鈕存在，且 pushEnable／pushTest 皆為 function", pushBtnErrors.length === 0, pushBtnErrors.join("; "));

  // 55.【2026-10-07 先.四十一】git 追蹤檔不得含本機 .env 的證券帳號（SINOPAC_EXPECTED_ACCOUNT_ID）。
  // 在本機比對、絕不印出數值；.env 沒設定這個鍵時無從比對，照實標「未設定」而不是假裝檢查過。
  const accErrors = [];
  let accInfo = "";
  try {
    const fsm = await import("node:fs");
    const cp = await import("node:child_process");
    const envTxt = fsm.existsSync(".env") ? fsm.readFileSync(".env", "utf8") : "";
    const m = envTxt.split(/\r?\n/).map((l) => l.trim()).find((l) => /^SINOPAC_EXPECTED_ACCOUNT_ID\s*=/.test(l));
    const acc = m ? m.split("=").slice(1).join("=").trim().replace(/^["']|["']$/g, "") : "";
    if (!acc) {
      accInfo = "本機 .env 未設定 SINOPAC_EXPECTED_ACCOUNT_ID，無從比對（請總司令自行填入）";
    } else if (acc.length < 7) {
      accInfo = "帳號長度不足 7 位，依規格不比對";
    } else {
      const r = cp.spawnSync("git", ["grep", "-l", "-F", "--", acc], { encoding: "utf8" });
      const files = (r.stdout || "").split(/\r?\n/).filter(Boolean);
      if (r.status !== 0 && r.status !== 1) accErrors.push(`git grep 執行失敗（exit ${r.status}）`);
      else if (files.length) accErrors.push(`有 ${files.length} 個追蹤檔含帳號：${files.join("、")}`);
      else accInfo = "追蹤檔皆不含帳號（數值未印出）";
    }
  } catch (e) { accErrors.push(`測試本身出錯：${e.message || e}`); }
  record("55. git 追蹤檔不得含本機 .env 的證券帳號（本機比對、不印數值）", accErrors.length === 0, accErrors.join("; ") || accInfo);

  // 56.【2026-10-08 先.五十二】融資維持率卡：日期用資料日、口徑換算比值讀 data/margin_ratio_calibration.json（不得寫死）
  const mgErrors = [];
  let mgInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const src = (await Promise.all(["index.html", "app.js", "app.css", "app-shared.js", "app-market.js", "app-picks.js", "app-stock.js", "app-trade.js", "app-journal.js", "app-settings.js"].map(async u => (await fetch(u, { cache: "no-store" })).text()))).join("\n");  // 常備.開發-20：CSS/JS 已拆出，全部合併掃描（丙案再拆分頁檔）
      await loadMarginMaintenance();
      const sum = (document.getElementById("margin-summary") || {}).innerText || "";
      const conv = (document.getElementById("margin-calib") || {}).innerText || "";
      const cal = await (await fetch("data/margin_ratio_calibration.json", { cache: "no-store" })).json();
      // 先.五十六-B5：線性模式時說明顯示的是 β（本站 × β ± |α|），以 β 比對；其餘模式比對 k
      return { hard: /0\.881|0\.8815/.test(src), sum, conv,
               ratio: cal.mode === "linear" && cal.beta != null ? cal.beta : (cal.k != null ? cal.k : cal.ratio_mean),
               crash: ((document.getElementById("margin-crash-low") || {}).innerText || "") };
    });
    if (r.hard) mgErrors.push("index.html 寫死了 0.881 比值");
    if (!/資料日/.test(r.sum)) mgErrors.push("卡片沒有顯示資料日：" + r.sum.slice(0, 80));
    if (/資料不完整/.test(r.sum) && !/上一筆有效/.test(r.sum)) mgErrors.push("資料不完整時沒有顯示上一筆有效日期");
    if (r.conv && !r.conv.includes(String(r.ratio))) mgErrors.push("對齊籌碼K說明的係數與 calibration 檔不一致");
    mgInfo = `摘要：${r.sum.replace(/\s+/g, " ").slice(0, 60)}｜換算：${r.conv.slice(0, 40) || "（無有效值）"}｜${r.crash.slice(0, 40)}`;
  } catch (e) { mgErrors.push(`測試本身出錯：${e.message || e}`); }
  record("56. 融資維持率卡：資料日、資料不完整顯示上一筆有效、口徑換算比值讀檔不寫死", mgErrors.length === 0, mgErrors.join("; ") || mgInfo);

  // 57.【2026-10-08 先.五十二】新版提示：sw.js 版本比頁面新才顯示「有新版，點此更新」
  const nvErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const el = document.getElementById("new-version-banner");
      const real = window.fetch;
      await checkNewVersion();
      const sameHidden = el && el.style.display === "none";
      window.fetch = async () => new Response("const CACHE = 'alpha-v9999-12-31.2359';");
      try { await checkNewVersion(); } finally { window.fetch = real; }
      const newerShown = el && el.style.display === "block" && /有新版，點此更新/.test(el.textContent);
      await checkNewVersion();
      return { exists: !!el, sameHidden, newerShown, fn: typeof applyNewVersion };
    });
    if (!r.exists) nvErrors.push("找不到 #new-version-banner");
    if (!r.sameHidden) nvErrors.push("版本相同時不該顯示");
    if (!r.newerShown) nvErrors.push("sw.js 版本較新時沒有顯示提示");
    if (r.fn !== "function") nvErrors.push("applyNewVersion 不是 function");
  } catch (e) { nvErrors.push(`測試本身出錯：${e.message || e}`); }
  record("57. 新版提示：版本相同不顯示、sw.js 較新時頂端顯示「有新版，點此更新」", nvErrors.length === 0, nvErrors.join("; "));


  // 58.【2026-10-08 先.五十三-A】維持率主數字改用對齊籌碼K（ratio_pct_ck）；係數 k、N、最大誤差讀校準檔；
  // 校準檔 warn=true 時顯示「校準待更新」但不隱藏數字；股災段標「校準未驗證」
  const ckErrors = [];
  let ckInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const hist = await (await fetch("data/margin_maintenance.json", { cache: "no-store" })).json();
      const cal = await (await fetch("data/margin_ratio_calibration.json", { cache: "no-store" })).json();
      await loadMarginMaintenance();
      const valid = hist.filter((h) => !h.data_incomplete && h.ratio_pct != null);
      const last = hist[hist.length - 1], prev = valid[valid.length - 1];
      const ref = last.data_incomplete ? prev : last;
      const sum = (document.getElementById("margin-summary") || {}).innerText || "";
      const calib = (document.getElementById("margin-calib") || {}).innerText || "";
      const unv = !!document.getElementById("margin-crash-unverified");
      const entry = (document.getElementById("chips-entry-margin") || {}).textContent || "";
      // 模擬 warn=true：攔截一次 fetch，確認只降級成警告、數字仍在
      const of = window.fetch;
      window.fetch = (u, o) => String(u).includes("margin_ratio_calibration")
        ? Promise.resolve(new Response(JSON.stringify({ ...cal, warn: true }), { status: 200 })) : of(u, o);
      try { await loadMarginMaintenance(); } finally { window.fetch = of; }
      const warnShown = !!document.getElementById("margin-calib-warn");
      const sumW = (document.getElementById("margin-summary") || {}).innerText || "";
      await loadMarginMaintenance();
      return { ck: ref && ref.ratio_pct_ck, raw: ref && ref.ratio_pct, sum, calib, k: cal.k, n: cal.n_points, mx: cal.max_err_pp, unv, entry, warnShown, sumW,
               mode: cal.mode, alpha: cal.alpha, beta: cal.beta };
    });
    if (r.ck == null) ckErrors.push("資料檔最新有效紀錄沒有 ratio_pct_ck");
    else {
      if (!r.sum.includes(r.ck.toFixed(1) + "%")) ckErrors.push(`主數字不是 ratio_pct_ck（${r.ck}）`);
      if (!r.sum.includes("本站原值 " + r.raw.toFixed(1) + "%")) ckErrors.push("灰字沒附本站原值");
      if (!r.entry.includes(r.ck.toFixed(1) + "%")) ckErrors.push("市場頁入口卡沒用 ratio_pct_ck");
    }
    // 先.五十六-B5：線性模式改驗 α、β（本站 × β ± |α|），其餘模式驗係數 k
    const coefOk = r.mode === "linear" ? (r.calib.includes(String(r.beta)) && r.calib.includes(String(Math.abs(r.alpha))))
                                       : r.calib.includes(String(r.k));
    if (!(coefOk && r.calib.includes(String(r.n)) && r.calib.includes(String(r.mx)))) ckErrors.push("「對齊籌碼K」說明的係數／日數／最大誤差與校準檔不一致：" + r.calib);
    if (!r.warnShown) ckErrors.push("校準檔 warn=true 時沒有顯示「校準待更新」");
    if (r.ck != null && !r.sumW.includes(r.ck.toFixed(1) + "%")) ckErrors.push("warn=true 時數字被隱藏（只應降級成警告）");
    if (!r.unv) ckErrors.push("股災段沒有標「校準未驗證」");
    ckInfo = `主數字 ${r.ck}%（本站 ${r.raw}%）｜${r.calib.slice(0, 50)}｜warn 測試：${r.warnShown ? "顯示警告、數字保留" : "未顯示"}`;
  } catch (e) { ckErrors.push(`測試本身出錯：${e.message || e}`); }
  record("58. 維持率主數字對齊籌碼K（ratio_pct_ck）、係數讀檔、warn 只降級警告、股災段標校準未驗證", ckErrors.length === 0, ckErrors.join("; ") || ckInfo);

  // 59.【2026-10-10 先.五十九-B6】破億卡達標機率：固定種子下結果可重現；示例參數與 R2（Python，10,000 次）對照在 4pp 內
  const probErrors = [];
  let probInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const d = await (await fetch("data/strategy_monthly_returns.json", { cache: "no-store" })).json();
      const o = { nw: 6e6, pmt: 3e5, nmon: 135, B: 5000, block: 12, seed: 20261010 };
      const a = btProbCalc(d.returns, o), b = btProbCalc(d.returns, o), c = btProbCalc(d.returns, Object.assign({}, o, { seed: 7 }));
      return { a, b, c, label: d.label, n: d.months.length };
    });
    if (JSON.stringify(r.a) !== JSON.stringify(r.b)) probErrors.push("同一種子兩次結果不同（不可重現）");
    if (JSON.stringify(r.a) === JSON.stringify(r.c)) probErrors.push("換種子結果完全相同（種子沒有作用）");
    if (r.label !== "回測，非保證") probErrors.push(`月報酬檔缺「回測，非保證」標示：${r.label}`);
    if (r.n !== 258) probErrors.push(`月報酬檔月數 ${r.n} ≠ 258（2003-07～2024-12）`);
    const ref = { "0050": 0.460, "Bb-90": 0.334, "S3-C6": 0.460, "R1-A": 0.559, "R1-C": 0.621 };
    for (const [k, v] of Object.entries(ref)) {
      if (!r.a[k]) { probErrors.push(`缺策略 ${k}`); continue; }
      if (Math.abs(r.a[k].p - v) > 0.04) probErrors.push(`${k} 機率 ${(r.a[k].p * 100).toFixed(1)}% 與 R2 ${(v * 100).toFixed(1)}% 差超過 4pp`);
      if (!(r.a[k].p5 <= r.a[k].p50 && r.a[k].p50 <= r.a[k].p95)) probErrors.push(`${k} 百分位順序錯`);
    }
    probInfo = Object.entries(r.a).map(([k, v]) => `${k} ${(v.p * 100).toFixed(1)}%`).join("、");
  } catch (e) { probErrors.push(`測試本身出錯：${e.message || e}`); }
  record("59. 破億卡達標機率：固定種子可重現、換種子會變；月報酬檔 258 個月且標「回測，非保證」；示例參數與 R2 差 ≤4pp", probErrors.length === 0, probErrors.join("; ") || probInfo);

  // 60.【2026-10-10 先.五十九-B6】未輸入參數時只顯示說明、不顯示機率；輸入後才顯示
  const probUiErrors = [];
  try {
    const r = await page.evaluate(async () => {
      localStorage.removeItem("alpha_bt_path"); renderBtPath();
      const empty = document.getElementById("bt-prob").textContent;
      localStorage.setItem("alpha_bt_path", JSON.stringify({ nw: "6000000", pmt: "300000", birth: "1998-01-13", age: "40" })); renderBtPath();
      for (let i = 0; i < 80 && !/已下架/.test(document.getElementById("bt-prob").textContent); i++) await new Promise(f => setTimeout(f, 100));
      const filled = document.getElementById("bt-prob").textContent;
      localStorage.removeItem("alpha_bt_path"); renderBtPath();
      return { empty, filled };
    });
    if (/\d+(\.\d+)?%/.test(r.empty)) probUiErrors.push(`未輸入參數卻顯示了百分比：${r.empty.slice(0, 80)}`);
    if (!r.empty.includes("請先填入")) probUiErrors.push(`未輸入參數時缺說明文字：${r.empty.slice(0, 80)}`);
    // 先.八十-7（2026-10-12）：樣本內重抽的機率數字已下架——輸入後也不得出現任何百分比，必須寫明下架原因
    if (/\d+(\.\d+)?%/.test(r.filled)) probUiErrors.push(`輸入後仍顯示機率數字（應已下架）：${r.filled.slice(0, 120)}`);
    if (!r.filled.includes("樣本內重抽，偏樂觀，不能當依據")) probUiErrors.push(`缺下架說明：${r.filled.slice(0, 120)}`);
  } catch (e) { probUiErrors.push(`測試本身出錯：${e.message || e}`); }
  record("60. 破億卡：樣本內重抽機率已下架，輸入前後都不顯示機率數字、寫明「樣本內重抽，偏樂觀，不能當依據」（先.八十-7）", probUiErrors.length === 0, probUiErrors.join("; "));

  // 61.【2026-10-10 先.五十九-A1／A2】紙.四 卡存在且固定揭露文字一字不差
  const p4Errors = [];
  try {
    const r = await page.evaluate(async () => { await loadPaper7030(); const el = document.getElementById("paper4-disclosure"); return { has: !!document.getElementById("paper4-card"), txt: el ? el.textContent : "" }; });
    if (!r.has) p4Errors.push("找不到紙.四 卡");
    const want = "回測 2003–2024 年化 15.1%／最大跌幅 −36.2%；同一閘門在 2025–26 樣本外 21 個月中有 13 個月關閉並大幅落後 0050；無樣本外驗證，僅紙上追蹤";
    if (!r.txt.includes(want)) p4Errors.push(`揭露文字不符：${r.txt.slice(0, 100)}`);
  } catch (e) { p4Errors.push(`測試本身出錯：${e.message || e}`); }
  record("61. 紙.四 卡存在且固定揭露文字（回測 15.1%／−36.2%、樣本外 13／21 月關閉、無樣本外驗證）", p4Errors.length === 0, p4Errors.join("; "));

  // 62.【2026-10-10 先.六十-A1／A6】不得存在台股假下單：confirmOrder 函式、#sheet 假抽屜、「委託已送出」假成功字樣都不得存在；
  // 台股個股頁只顯示唯讀說明（沒有買進／賣出鈕），美股個股頁仍是 IBKR 模擬帳戶下單卡。
  const fakeOrderErrors = [];
  try {
    const fs = await import("node:fs");
    const src = ["index.html", "app.js", "app.css", "app-shared.js", "app-market.js", "app-picks.js", "app-stock.js", "app-trade.js", "app-journal.js", "app-settings.js"].map(f => fs.readFileSync(f, "utf8")).join("\n");  // 常備.開發-20：CSS/JS 已拆出，全部合併掃描（丙案再拆分頁檔）
    if (/function\s+confirmOrder\b/.test(src)) fakeOrderErrors.push("index.html 仍有 function confirmOrder");
    if (/委託已送出\s*·\s*\d{2}:\d{2}/.test(src)) fakeOrderErrors.push("index.html 仍有寫死時間的「委託已送出」假成功字樣");  // IBKR Paper 真送單後的回報 toast 不算
    if (/id="sheet"/.test(src)) fakeOrderErrors.push("index.html 仍有 #sheet 假下單抽屜");
    const r = await page.evaluate(async () => {
      const o = { cf: typeof window.confirmOrder, ots: typeof window.openTradeSheet };
      window.openStock("2330"); await new Promise((f) => setTimeout(f, 400));
      const vis = (id) => { const el = document.getElementById(id); return !!el && getComputedStyle(el).display !== "none"; };
      o.twNote = vis("buy-cta-tw"); o.twBuy = vis("buy-cta-us-buy");
      o.twTxt = (document.getElementById("buy-cta-tw") || {}).textContent || "";
      window.openStock("AAPL"); await new Promise((f) => setTimeout(f, 400));
      o.usNote = vis("buy-cta-tw"); o.usBuy = vis("buy-cta-us-buy");
      return o;
    });
    if (r.cf !== "undefined") fakeOrderErrors.push("window.confirmOrder 仍存在");
    if (r.ots !== "undefined") fakeOrderErrors.push("window.openTradeSheet 仍存在");
    if (!r.twNote || r.twBuy) fakeOrderErrors.push(`台股個股頁應只顯示唯讀說明（說明=${r.twNote}，買進鈕=${r.twBuy}）`);
    if (!r.twTxt.includes("這裡不下單")) fakeOrderErrors.push(`台股唯讀說明文字不符：${r.twTxt.slice(0, 60)}`);
    if (r.usNote || !r.usBuy) fakeOrderErrors.push(`美股個股頁應顯示 IBKR 模擬下單鈕（說明=${r.usNote}，買進鈕=${r.usBuy}）`);
  } catch (e) { fakeOrderErrors.push(`測試本身出錯：${e.message || e}`); }
  record("62. 不得存在台股假下單（confirmOrder／#sheet／「委託已送出」）；台股個股頁唯讀說明、美股維持 IBKR 模擬卡", fakeOrderErrors.length === 0, fakeOrderErrors.join("; "));

  // 63.【2026-10-10 先.六十-A2／A3／A6】交易頁文案不得含「尚未串接任何真實券商」；不得再有策略 A/B/C 開關與 Kill Switch 按鈕；
  // 關於／免責聲明要寫明「台股由 Shioaji 自動執行 Bb-90（真錢，附否決窗）；美股未串接下單」。
  const tradeCopyErrors = [];
  try {
    const r = await page.evaluate(() => ({
      trade: (document.getElementById("scr-trade") || {}).textContent || "",
      killer: !!document.querySelector("#scr-trade .killer"),
      switches: document.querySelectorAll("#trade-sub-bots .switch").length,
      settings: (document.getElementById("scr-settings") || {}).textContent || "",
      rc: !!document.getElementById("rc-daily-loss"),
    }));
    if (r.trade.includes("尚未串接任何真實券商")) tradeCopyErrors.push("交易頁仍含「尚未串接任何真實券商」");
    if (r.killer) tradeCopyErrors.push("交易頁仍有 Kill Switch 按鈕（應統一由設定頁緊急停止負責）");
    if (r.switches) tradeCopyErrors.push(`交易頁機器人分頁仍有 ${r.switches} 個開關`);
    const want = "台股由 Shioaji 自動執行 Bb-90（真錢，附否決窗）；美股未串接下單";
    const n = r.settings.split(want).length - 1;
    if (n < 2) tradeCopyErrors.push(`設定頁（關於＋免責聲明）應至少出現 2 次「${want}」，實際 ${n} 次`);
    if (r.settings.includes("原型階段")) tradeCopyErrors.push("設定頁仍寫「原型階段」");
    if (r.rc) tradeCopyErrors.push("設定頁仍有引擎不讀的可編輯風控參數（rc-daily-loss）");
  } catch (e) { tradeCopyErrors.push(`測試本身出錯：${e.message || e}`); }
  record("63. 交易頁無「尚未串接任何真實券商」、無 Kill Switch／策略開關；關於與免責聲明寫明 Bb-90 真錢自動執行、美股未串接下單", tradeCopyErrors.length === 0, tradeCopyErrors.join("; "));

  // 64.【2026-10-10 先.六十-A2／A4／A5】機器人卡、日誌頁、風控唯讀、推播偏好：用假的本機伺服器回應（替換 liveFetch，不連網）驗顯示；
  // 帳本無成交時顯示「首批尚未執行」；有成交時顯示本週／累計損益；畫面不得出現帳號樣式字串。
  const ledgerUiErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { lf: window.liveFetch, url: LIVE.url, conf: LIVE.configured };
      const status = { ok: true, mode: "LIVE_WITH_VETO", drill: false, stopped: false, status: {}, next_tranche: 1, tranche_total: 4,
        next_run: { date: "2026-10-12", time: "09:05", reason: "first_tranche" },
        last_result: { date: "2026-10-08", batch: "202610-T1", counts: { REJECT: 1 }, reason_codes: ["INSUFFICIENT_CASH"] },
        limits: { whitelist: ["0050", "00646", "00697B"], per_order_cap_twd: 123456, max_price_dev_pct: 1.0, max_data_age_days: 4, veto_minutes: 30 } };
      let ledger = { ok: true, rows: [{ date: "2026-10-08", symbol: "全部", qty: 0, filled_qty: 0, avg_price: null, status: "REJECT", reason_codes: ["INSUFFICIENT_CASH"], batch: "202610-T1" }], first_batch_done: false, pnl: null };
      const prefs = { ok: true, prefs: { veto: true, reject: true, complete: false, missed: true } };
      window.liveFetch = async (p) => new Response(JSON.stringify(p === "/auto/status" ? status : p === "/auto/ledger" ? ledger : p === "/push/prefs" ? prefs : {}), { status: 200 });
      LIVE.url = "https://smoke.invalid"; LIVE.configured = true;
      const o = {};
      try {
        await loadTradeBots();
        o.mode = document.getElementById("bot-mode").textContent; o.next = document.getElementById("bot-next").textContent; o.last = document.getElementById("bot-last").textContent;
        await loadJournalLedger();
        o.pnl0 = document.getElementById("journal-pnl").textContent; o.tr0 = document.getElementById("journal-trades").textContent;
        ledger = { ok: true, rows: [{ date: "2026-10-12", symbol: "0050", qty: 1000, filled_qty: 1000, avg_price: 190.5, status: "FILLED", reason_codes: [], batch: "202610-T1" }], first_batch_done: true, pnl: { as_of: "2026-10-12", week_start: "2026-10-12", total: 1500, total_pct: 0.79, week: 1500 } };
        await loadJournalLedger();
        o.pnl1 = document.getElementById("journal-pnl").textContent; o.tr1 = document.getElementById("journal-trades").textContent;
        await loadRiskLimits(); o.cap = document.getElementById("rl-cap").textContent;
        await loadNotif(); o.notif = ["reject", "complete", "missed"].map((k) => document.getElementById("notif-" + k).classList.contains("on"));
        o.veto = document.getElementById("notif-veto").classList.contains("on");
      } finally { window.liveFetch = saved.lf; LIVE.url = saved.url; LIVE.configured = saved.conf; }
      return o;
    });
    if (!r.mode.includes("真錢")) ledgerUiErrors.push(`機器人卡模式顯示不符：${r.mode}`);
    if (!r.next.includes("10/12") || !r.next.includes("第 1")) ledgerUiErrors.push(`機器人卡下一期不符：${r.next}`);
    if (!r.last.includes("拒單") || !r.last.includes("現金不足")) ledgerUiErrors.push(`機器人卡上次結果不符：${r.last}`);
    if (!r.pnl0.includes("首批尚未執行")) ledgerUiErrors.push(`無成交時應顯示「首批尚未執行」：${r.pnl0.slice(0, 60)}`);
    if (!r.tr0.includes("拒單")) ledgerUiErrors.push(`無成交時應列出拒單紀錄：${r.tr0.slice(0, 60)}`);
    if (!r.pnl1.includes("本週") || !r.pnl1.includes("累計") || !r.pnl1.includes("+1,500")) ledgerUiErrors.push(`有成交時損益顯示不符：${r.pnl1.slice(0, 80)}`);
    if (!r.tr1.includes("0050") || !r.tr1.includes("190.5")) ledgerUiErrors.push(`有成交時交易紀錄不符：${r.tr1.slice(0, 80)}`);
    if (/\d{7,}/.test(r.tr0 + r.tr1)) ledgerUiErrors.push("交易紀錄出現 7 位以上連續數字（疑似帳號）");
    if (!r.cap.includes("123,456")) ledgerUiErrors.push(`風控單次上限未顯示引擎實際值：${r.cap}`);
    if (JSON.stringify(r.notif) !== "[true,false,true]" || !r.veto) ledgerUiErrors.push(`推播偏好顯示不符：${JSON.stringify(r.notif)} veto=${r.veto}`);
  } catch (e) { ledgerUiErrors.push(`測試本身出錯：${e.message || e}`); }
  record("64. 機器人卡（模式／下一期／上次結果）、日誌頁（首批尚未執行／本週與累計損益）、風控唯讀實際值、推播偏好（否決窗固定開）", ledgerUiErrors.length === 0, ledgerUiErrors.join("; "));

  // 65.【2026-10-10 先.六十一】STATUS.json 瘦身：檔案 < 100 KB；還原價異常明細只在 data/adjustment_anomalies.json，
  // STATUS.json 只留 n_warnings＋檔案連結；設定頁資料健康卡讀新檔顯示筆數。
  const statusSizeErrors = [];
  try {
    const fs = await import("node:fs");
    const size = fs.statSync("data/STATUS.json").size;
    if (size >= 100 * 1024) statusSizeErrors.push(`data/STATUS.json ${(size / 1024).toFixed(1)} KB ≥ 100 KB 上限`);
    const st = JSON.parse(fs.readFileSync("data/STATUS.json", "utf8"));
    const aw = st.adjustment_anomaly_warnings || {};
    if ("warnings" in aw) statusSizeErrors.push("STATUS.json 仍內嵌 adjustment_anomaly_warnings.warnings 明細");
    if (aw.file !== "data/adjustment_anomalies.json" || typeof aw.n_warnings !== "number") statusSizeErrors.push(`STATUS.json 摘要欄位不符：${JSON.stringify(aw).slice(0, 80)}`);
    const an = JSON.parse(fs.readFileSync("data/adjustment_anomalies.json", "utf8"));
    if (an.n_warnings !== aw.n_warnings) statusSizeErrors.push(`兩檔 n_warnings 不一致（${an.n_warnings} vs ${aw.n_warnings}）`);
    if (!an.generated_at) statusSizeErrors.push("adjustment_anomalies.json 缺 generated_at");
    const txt = await page.evaluate(async () => { await loadAdjAnomalies(); return document.getElementById("adj-anomaly-note").textContent; });
    if (!/還原價異常警告.*\d.*筆/.test(txt)) statusSizeErrors.push(`設定頁未顯示異常筆數：${txt.slice(0, 60)}`);
    if (!statusSizeErrors.length) statusSizeErrors.info = `STATUS.json ${(size / 1024).toFixed(1)} KB；異常 ${an.n_warnings} 筆`;
  } catch (e) { statusSizeErrors.push(`測試本身出錯：${e.message || e}`); }
  record("65. STATUS.json < 100 KB；還原價異常明細移到 data/adjustment_anomalies.json，STATUS 只留摘要＋連結；設定頁讀新檔", statusSizeErrors.length === 0, statusSizeErrors.join("; ") || statusSizeErrors.info || "");

  // 66.【2026-10-11 常備.開發-3】首頁持倉損益卡：用假的 /live/positions、/live/balance（替換 liveFetch，不連網）驗顯示——
  // 張數、市值（張×1000×現價）、未實現損益（券商回傳值）、合計；總資產卡持股市值同樣以張×1000 計；
  // 未連線本機伺服器時卡片顯示說明文字而非空白；畫面不得出現帳號樣式字串。
  const posCardErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { lf: window.liveFetch, url: LIVE.url, conf: LIVE.configured };
      const pos = { sinopac: { available: true, positions: [{ code: "2330", direction: "Buy", quantity: 2, price: 900, last_price: 1000, pnl: 199000 }] }, ibkr: null, generated_at: "2026-10-12T10:00:00+08:00" };
      const bal = { sinopac: { available: true, balance: { acc_balance: 50000 } }, ibkr: { connected: false } };
      window.liveFetch = async (p) => new Response(JSON.stringify(p === "/live/positions" ? pos : p === "/live/balance" ? bal : {}), { status: 200 });
      const o = {};
      try {
        LIVE.url = "https://smoke.invalid"; LIVE.configured = true;
        await loadHomeBrokerCard();
        o.body = document.getElementById("home-pos-body").textContent;
        o.total = Number(document.getElementById("home-asset-total").dataset.ntd);
        LIVE.configured = false;
        await loadHomeBrokerCard();
        o.off = document.getElementById("home-pos-body").textContent;
        o.offVisible = !document.getElementById("home-pos-card").hidden;
      } finally { window.liveFetch = saved.lf; LIVE.url = saved.url; LIVE.configured = saved.conf; }
      return o;
    });
    if (!r.body.includes("2330") || !r.body.includes("2 張")) posCardErrors.push(`持倉列缺代號或張數：${r.body.slice(0, 80)}`);
    if (!r.body.includes("2,000,000")) posCardErrors.push(`市值應為 2,000,000（2 張×1000×1000）：${r.body.slice(0, 120)}`);
    if (!r.body.includes("+199,000")) posCardErrors.push(`未實現損益應顯示券商回傳 +199,000：${r.body.slice(0, 120)}`);
    if (r.total !== 2050000) posCardErrors.push(`總資產應為 2,050,000（現金 5 萬＋持股 200 萬），實得 ${r.total}`);
    if (!r.off.trim() || !/未連線|連上電腦/.test(r.off) || !r.offVisible) posCardErrors.push(`未連線時應顯示說明而非空白：「${r.off}」 visible=${r.offVisible}`);
    if (/\d{7,}/.test(r.body)) posCardErrors.push("持倉卡出現 7 位以上連續數字（疑似帳號）");
  } catch (e) { posCardErrors.push(`測試本身出錯：${e.message || e}`); }
  record("66. 首頁持倉損益卡（張數／市值／未實現損益／合計；總資產持股市值以張×1000 計；未連線顯示說明）", posCardErrors.length === 0, posCardErrors.join("; "));

  // 67.【2026-10-11 常備.開發-5】美股事件分頁時間軸：用假的 us_events／earnings_calendar 快取（不連網）驗——
  // 有 8-K 與下一次財報日時列出時間軸；不在追蹤清單的代號顯示原因；外國發行人顯示 6-K 說明；不得再出現「尚未串接美股」。
  const usEvErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { k: US_8K_CACHE, e: EARNINGS_CALENDAR_CACHE, cc: currentCode };
      const day = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);
      US_8K_CACHE = { fetched_at: new Date().toISOString(), tickers: { AAPL: { filings: [{ filed_at: day(-5), filing_type: "8-K", items: ["Item 2.02: Results of Operations"], url: "https://www.sec.gov/x" }, { filed_at: day(-200), filing_type: "8-K", items: ["Item 8.01: Old"], url: "https://www.sec.gov/y" }] }, TSM: { filings: [] } } };
      EARNINGS_CALENDAR_CACHE = { earnings: { AAPL: { next_earnings_date: day(20), estimated_session: "post", eps_estimate: 1.5 } } };
      const host = document.getElementById("stock-events-list"), o = {};
      try {
        for (const c of ["AAPL", "TSM", "ZZZZ"]) { currentCode = c; await renderStockEventsTab(c); o[c] = host.innerText; }
      } finally { US_8K_CACHE = saved.k; EARNINGS_CALENDAR_CACHE = saved.e; currentCode = saved.cc; }
      return o;
    });
    if (!r.AAPL.includes("財報日") || !r.AAPL.includes("Item 2.02")) usEvErrors.push(`AAPL 應列財報日與 8-K：${r.AAPL.slice(0, 100)}`);
    if (r.AAPL.includes("Item 8.01: Old")) usEvErrors.push("超過 90 天的 8-K 不應出現");
    if (!r.TSM.includes("6-K")) usEvErrors.push(`TSM 應說明外國發行人 6-K：${r.TSM.slice(0, 100)}`);
    if (!r.ZZZZ.includes("不在") ) usEvErrors.push(`不在清單代號應說明原因：${r.ZZZZ.slice(0, 100)}`);
    if (/尚未串接美股/.test(r.AAPL + r.TSM + r.ZZZZ)) usEvErrors.push("仍出現「尚未串接美股」舊佔位");
  } catch (e) { usEvErrors.push(`測試本身出錯：${e.message || e}`); }
  record("67. 美股事件分頁時間軸（8-K 近 90 天＋下一次財報日；無資料說明原因；外國發行人 6-K 說明）", usEvErrors.length === 0, usEvErrors.join("; "));

  // 68.【2026-10-11 常備.開發-7】台股財報分頁 FCF：data/cash_flow.json 有的代號顯示「億」與來源（FinMind 現金流量表，非官方），
  // 沒有的代號（例如金控）說明原因而非只有「—」。
  const fcfErrors = [];
  try {
    const fs = await import("node:fs");
    const cf = JSON.parse(fs.readFileSync("data/cash_flow.json", "utf8"));
    if (!(cf.count > 1000)) fcfErrors.push(`cash_flow.json 檔數過少：${cf.count}`);
    const r = await page.evaluate(async () => {
      const o = {};
      for (const c of ["2330", "2880"]) {
        currentCode = c; await loadFinancials(c);
        o[c] = { fcf: document.getElementById("fin-fcf").textContent, note: document.getElementById("fin-note").textContent };
      }
      return o;
    });
    if (cf.stocks["2330"] && !/億/.test(r["2330"].fcf)) fcfErrors.push(`2330 FCF 應顯示億：${r["2330"].fcf}`);
    if (!/FinMind|公開資料/.test(r["2330"].note)) fcfErrors.push(`2330 備註應標 FinMind 來源：${r["2330"].note.slice(-80)}`);
    if (!cf.stocks["2880"] && !/不在 (FinMind|公開資料) 現金流量表快取/.test(r["2880"].note)) fcfErrors.push(`2880 無資料應說明原因：${r["2880"].note.slice(-80)}`);
  } catch (e) { fcfErrors.push(`測試本身出錯：${e.message || e}`); }
  record("68. 台股財報分頁 FCF（近四季，標 FinMind 來源；無資料說明原因）", fcfErrors.length === 0, fcfErrors.join("; "));

  // 69.【2026-10-11 常備.開發-8】多自選清單：舊單一清單格式自動遷移進「我的自選」、建立／切換／下架清單，
  // 切換後 WL 與 localStorage alpha_wl 跟著換；只剩一個清單時不得下架；首頁顯示清單分頁。
  const wlErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { wl: localStorage.getItem("alpha_wl"), lists: localStorage.getItem("alpha_wl_lists"), WL: WL.slice() };
      const o = {};
      try {
        localStorage.removeItem("alpha_wl_lists"); WL = ["2330", "2317"]; localStorage.setItem("alpha_wl", JSON.stringify(WL));
        const m = wlListsRead(); o.migrated = m.active === "我的自選" && JSON.stringify(m.lists["我的自選"]) === '["2330","2317"]';
        o.create = wlCreate("測試清單"); o.afterCreate = JSON.stringify(WL);
        WL.push("2454"); localStorage.setItem("alpha_wl", JSON.stringify(WL));
        wlSwitch("我的自選"); o.back = JSON.stringify(WL) + "|" + localStorage.getItem("alpha_wl");
        wlSwitch("測試清單"); o.again = JSON.stringify(WL);
        o.tabs = document.getElementById("wl-tabs")?.innerText || "";
        o.remove = wlRemove("測試清單"); o.afterRemove = JSON.parse(localStorage.getItem("alpha_wl_lists")).active + "|" + JSON.stringify(WL);
        o.lastGuard = wlRemove("我的自選");
        o.payload = Object.keys(_collectLocalSettings()).join(",");
      } finally {
        if (saved.lists == null) localStorage.removeItem("alpha_wl_lists"); else localStorage.setItem("alpha_wl_lists", saved.lists);
        if (saved.wl == null) localStorage.removeItem("alpha_wl"); else localStorage.setItem("alpha_wl", saved.wl);
        WL = saved.WL; renderWLTabs();
      }
      return o;
    });
    if (!r.migrated) wlErrors.push("舊單一清單未自動遷移進「我的自選」");
    if (!r.create || r.afterCreate !== "[]") wlErrors.push(`建立新清單後應切到空清單：${r.create} ${r.afterCreate}`);
    if (r.back !== '["2330","2317"]|["2330","2317"]') wlErrors.push(`切回我的自選後 WL／alpha_wl 不符：${r.back}`);
    if (r.again !== '["2454"]') wlErrors.push(`切回測試清單應保留 2454：${r.again}`);
    if (!/測試清單/.test(r.tabs) || !/我的自選/.test(r.tabs)) wlErrors.push(`首頁清單分頁未顯示兩個清單：${r.tabs}`);
    if (!r.remove || r.afterRemove !== '我的自選|["2330","2317"]') wlErrors.push(`下架後應回到我的自選：${r.afterRemove}`);
    if (r.lastGuard !== false) wlErrors.push("只剩一個清單時不得下架");
    if (!/watchlists/.test(r.payload)) wlErrors.push(`/settings 同步內容缺 watchlists：${r.payload}`);
  } catch (e) { wlErrors.push(`測試本身出錯：${e.message || e}`); }
  record("69. 多自選清單（舊格式遷移、建立／切換／下架、至少保留一個、/settings 同步含 watchlists）", wlErrors.length === 0, wlErrors.join("; "));

  // 70.【2026-10-11 常備.開發-10】美股 1 分 K：伺服器回 501 時 App 顯示誠實說明（不是「取得失敗」），退回日線，不記入錯誤 log。
  const k501Errors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { lf: window.liveFetch, mode: STOCK_CHART.mode, errs: (window.GLOBAL_ERRORS || []).length };
      window.liveFetch = async () => new Response(JSON.stringify({ detail: "美股（AAPL）1分K尚未實作" }), { status: 501 });
      try { STOCK_CHART.mode = "intraday"; await loadIntradayBars("AAPL"); return { note: document.getElementById("trend-note")?.textContent || "", mode: STOCK_CHART.mode }; }
      finally { window.liveFetch = saved.lf; }
    });
    if (!r.note.includes("美股 1 分 K 尚未提供") || !r.note.includes("請看日線")) k501Errors.push(`501 說明文字不符：「${r.note}」`);
    if (r.note.includes("取得失敗")) k501Errors.push("501 不應顯示成「取得失敗」");
    if (r.mode !== "daily") k501Errors.push(`501 後應退回日線，實得 ${r.mode}`);
  } catch (e) { k501Errors.push(`測試本身出錯：${e.message || e}`); }
  record("70. 美股 1 分 K 收到 501 顯示誠實說明並退回日線", k501Errors.length === 0, k501Errors.join("; "));

  // 71.【2026-10-11 常備.開發-11】首頁真錢執行總覽卡：用假的 /auto/status、/auto/ledger（替換 liveFetch，不連網、不下單）驗——
  // 部分成交時顯示期別／送出筆數／成交比例／權重偏離／下一期；未入金時白話原因；未連線時顯示說明而非空白；
  // 只有 ledger 失敗時 status 部分照畫（錯誤隔離）。三態純函式另見 scripts/selftest_home_exec_card.mjs。
  const execErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { lf: window.liveFetch, url: LIVE.url, conf: LIVE.configured, errs: GLOBAL_ERRORS.length };
      const st = { ok: true, mode: "LIVE_WITH_VETO", drill: false, stopped: false, status: {}, next_tranche: 2, tranche_total: 4,
        next_run: { date: "2026-10-15", time: "09:05", reason: "first_tranche" },
        live_account: { empty: false, holdings: [{ symbol: "0050", pct: 72.5, target_pct: 70, dev_pp: 2.5 }] } };
      const lg = { ok: true, rows: [
        { date: "2026-10-12", symbol: "0050", qty: 1000, filled_qty: 1000, status: "FILLED", reason_codes: [], batch: "202610-T2" },
        { date: "2026-10-12", symbol: "00646", qty: 500, filled_qty: 200, status: "PARTIAL", reason_codes: [], batch: "202610-T2" }] };
      const body = () => document.getElementById("home-exec-body").textContent;
      const o = {};
      try {
        LIVE.url = "https://smoke.invalid"; LIVE.configured = true;
        window.liveFetch = async (p) => new Response(JSON.stringify(p === "/auto/status" ? st : p === "/auto/ledger" ? lg : {}), { status: 200 });
        await loadHomeExecCard(); o.partial = body();
        const cash = { ...st, live_account: { empty: true }, status: { last_error: "INSUFFICIENT_CASH:交割戶可用餘額 0 元" } };
        const rej = { ok: true, rows: [{ date: "2026-10-08", symbol: "全部", qty: 0, filled_qty: 0, status: "REJECT", reason_codes: ["INSUFFICIENT_CASH"], batch: "202610-T1" }] };
        window.liveFetch = async (p) => new Response(JSON.stringify(p === "/auto/status" ? cash : p === "/auto/ledger" ? rej : {}), { status: 200 });
        await loadHomeExecCard(); o.cash = body();
        window.liveFetch = async (p) => p === "/auto/status" ? new Response(JSON.stringify(st), { status: 200 }) : new Response("{}", { status: 500 });
        await loadHomeExecCard(); o.half = body();
        LIVE.configured = false;
        await loadHomeExecCard(); o.off = body();
      } finally {
        window.liveFetch = saved.lf; LIVE.url = saved.url; LIVE.configured = saved.conf;
        GLOBAL_ERRORS.length = Math.min(GLOBAL_ERRORS.length, saved.errs);  // 「ledger 500」是刻意製造的失敗，不留在全域錯誤 log
      }
      return o;
    });
    for (const k of ["2026/10 第 2 期", "部分成交", "送出 2 筆", "80%", "0050 72.5%／70%", "+2.5 個百分點", "10/15"])
      if (!r.partial.includes(k)) execErrors.push(`部分成交畫面缺「${k}」：${r.partial.slice(0, 160)}`);
    if (!r.cash.includes("尚未入金") || !r.cash.includes("整批被擋")) execErrors.push(`未入金應白話說明：${r.cash.slice(0, 160)}`);
    if (!r.half.includes("讀不到 /auto/ledger") || !r.half.includes("10/15")) execErrors.push(`ledger 失敗時 status 部分應照畫：${r.half.slice(0, 160)}`);
    if (!/尚未連線|連上電腦/.test(r.off)) execErrors.push(`未連線應顯示說明：「${r.off}」`);
  } catch (e) { execErrors.push(`測試本身出錯：${e.message || e}`); }
  record("71. 首頁真錢執行總覽卡（期別／送出筆數／成交比例／權重偏離／下一期；未入金白話原因；單端點失敗隔離；未連線說明）", execErrors.length === 0, execErrors.join("; "));

  // 72.【2026-10-11 常備.開發-12】日誌頁真錢績效對照：用假的 /auto/ledger（替換 liveFetch，不連網、不下單）驗——
  // 無成交顯示「尚無部位」；有 perf 序列時畫出兩條折線（自動交易／0050 全持有）、報酬與差距、標「含手續費、未含稅」；
  // perf 回 error 時顯示原因不空白；未連線顯示說明。伺服器端算法見 scripts/selftest_auto_ledger_view.py。
  const perfErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { lf: window.liveFetch, url: LIVE.url, conf: LIVE.configured };
      const el = () => document.getElementById("journal-perf");
      const o = {};
      let lg = { ok: true, rows: [], first_batch_done: false, pnl: null, perf: null };
      try {
        LIVE.url = "https://smoke.invalid"; LIVE.configured = true;
        window.liveFetch = async (p) => new Response(JSON.stringify(p === "/auto/ledger" ? lg : {}), { status: 200 });
        await loadJournalLedger(); o.none = el().textContent;
        lg = { ok: true, rows: [{ date: "2026-10-12", symbol: "0050", qty: 1000, filled_qty: 1000, avg_price: 100, status: "FILLED", reason_codes: [], batch: "202610-T1" }],
          first_batch_done: true, pnl: { as_of: "2026-10-14", week_start: "2026-10-12", total: 500, total_pct: 0.5, week: 500 },
          perf: { bench: "0050", start: "2026-10-12", as_of: "2026-10-14", nav_pct: 2.1, bench_pct: 1.4, note: "含手續費（牌告 0.1425% 不打折、每筆最低 1 元）、未含稅",
            points: [{ date: "2026-10-12", nav: 0.9986, bench: 0.9986, cost: 100142 }, { date: "2026-10-13", nav: 1.01, bench: 1.005, cost: 100142 }, { date: "2026-10-14", nav: 1.021, bench: 1.014, cost: 100142 }] } };
        await loadJournalLedger(); o.has = el().textContent; o.lines = el().querySelectorAll("svg polyline").length;
        o.pts = [...el().querySelectorAll("svg polyline")].map((p) => p.getAttribute("points").split(" ").length);
        lg = { ...lg, perf: { error: "price_history 缺白名單標的收盤價，無法畫績效對照" } };
        await loadJournalLedger(); o.err = el().textContent;
        LIVE.configured = false;
        await loadJournalLedger(); o.off = el().textContent;
      } finally { window.liveFetch = saved.lf; LIVE.url = saved.url; LIVE.configured = saved.conf; }
      return o;
    });
    if (!r.none.includes("尚無部位")) perfErrors.push(`無成交應顯示「尚無部位」：${r.none.slice(0, 80)}`);
    if (r.lines !== 2 || r.pts.some((n) => n !== 3)) perfErrors.push(`有成交應畫 2 條各 3 點的折線，實際 ${r.lines} 條 ${JSON.stringify(r.pts)}`);
    for (const k of ["+2.1%", "+1.4%", "+0.7 個百分點", "0050 全持有", "含手續費、未含稅", "3 個交易日"])
      if (!r.has.includes(k)) perfErrors.push(`有成交畫面缺「${k}」：${r.has.slice(0, 160)}`);
    if (!r.err.includes("缺白名單")) perfErrors.push(`perf error 應顯示原因：${r.err.slice(0, 80)}`);
    if (!r.off.includes("尚未連線")) perfErrors.push(`未連線應顯示說明：${r.off.slice(0, 80)}`);
  } catch (e) { perfErrors.push(`測試本身出錯：${e.message || e}`); }
  record("72. 日誌頁真錢績效對照（無成交「尚無部位」；有成交兩條折線＋報酬差距＋「含手續費、未含稅」；perf 錯誤顯示原因；未連線說明）", perfErrors.length === 0, perfErrors.join("; "));

  // 86.【2026-10-11 常備.開發-23】日誌頁盤後復盤：用假的 /auto/ledger（替換 liveFetch，不連網、不下單）驗——
  // review=null 顯示「尚無復盤」；有復盤時列出成交率／加權滑價／逐筆滑價／零股驗證／偏離／下期；review.error 顯示原因；
  // 舊版伺服器（沒有 review 欄位）提示重啟；未連線顯示說明。產生端算法見 scripts/selftest_auto_trading_review.py。
  const reviewErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const saved = { lf: window.liveFetch, url: LIVE.url, conf: LIVE.configured };
      const el = () => document.getElementById("journal-review");
      const o = {};
      let lg = { ok: true, rows: [], first_batch_done: false, pnl: null, perf: null, review: null };
      try {
        LIVE.url = "https://smoke.invalid"; LIVE.configured = true;
        window.liveFetch = async (p) => new Response(JSON.stringify(p === "/auto/ledger" ? lg : {}), { status: 200 });
        await loadJournalLedger(); o.none = el().textContent;
        lg = { ...lg, review: { date: "2026-10-12", generated_at: "2026-10-12T13:40:30+08:00", batches: ["202610-T1"],
          summary: { n_orders: 2, n_filled: 1, n_rejects: 1, fill_rate_pct: 91.7, slippage_pct_weighted: 0.164, all_final: true },
          orders: [{ symbol: "0050", lot: "整股", qty: 1000, filled_qty: 1000, avg_price: 100.2, ref_price: 100, ref_source: "shioaji_reference", slippage_pct: 0.2, status: "FILLED" },
            { symbol: "0050", lot: "零股", qty: 200, filled_qty: 100, avg_price: 99.8, ref_price: 100, ref_source: "prev_close", slippage_pct: -0.2, status: "EXPIRED" }],
          rejects: [{ symbol: "00697B", codes: ["CAP"] }], odd_lot: { status: "MATCH" },
          deviation: { max_abs_pp: 6.2, threshold_pp: 5 }, next_run: { date: "2026-10-13", time: "09:05", reason: "open_batch" } } };
        await loadJournalLedger(); o.has = el().textContent; o.trs = el().querySelectorAll("tr").length;
        lg = { ...lg, review: { error: "讀取復盤檔失敗（JSONDecodeError）" } };
        await loadJournalLedger(); o.err = el().textContent;
        const { review, ...old } = lg; lg = old;
        await loadJournalLedger(); o.old = el().textContent;
        LIVE.configured = false;
        await loadJournalLedger(); o.off = el().textContent;
      } finally { window.liveFetch = saved.lf; LIVE.url = saved.url; LIVE.configured = saved.conf; }
      return o;
    });
    if (!r.none.includes("尚無復盤")) reviewErrors.push(`review=null 應顯示「尚無復盤」：${r.none.slice(0, 80)}`);
    if (r.trs !== 3) reviewErrors.push(`逐筆表應有表頭＋2 列，實際 ${r.trs} 列`);
    for (const k of ["2026-10-12", "成交率 91.7%", "+0.164%", "+0.2%", "-0.2%", "100*", "相符", "6.2 個百分點", "2026-10-13", "續跑進行中批次", "超過單次上限", "非投資建議"])
      if (!r.has.includes(k)) reviewErrors.push(`有復盤畫面缺「${k}」：${r.has.slice(0, 200)}`);
    if (!r.err.includes("JSONDecodeError")) reviewErrors.push(`review.error 應顯示原因：${r.err.slice(0, 80)}`);
    if (!r.old.includes("需重啟")) reviewErrors.push(`舊版伺服器應提示重啟：${r.old.slice(0, 80)}`);
    if (!r.off.includes("尚未連線")) reviewErrors.push(`未連線應顯示說明：${r.off.slice(0, 80)}`);
  } catch (e) { reviewErrors.push(`測試本身出錯：${e.message || e}`); }
  record("86. 日誌頁盤後復盤（無復盤「尚無復盤」；有復盤列成交率／加權與逐筆滑價／零股驗證／偏離／下期；錯誤顯示原因；舊版伺服器提示重啟；未連線說明）", reviewErrors.length === 0, reviewErrors.join("; "));

  // 73.【2026-10-11 常備.開發-13】個股簡報（規則版）：①合成資料驗五條要點的算法（連買賣天數、融資增減、
  // 處置／注意、事件 30 日窗）②真實檔案 2330 畫出 5 條＋「規則摘要，非 AI 判斷」③美股顯示誠實說明
  // ④五份來源全空時每條都寫「查無」不崩潰。
  const briefErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const o = {};
      const hist = { series: { "9999": { "20261001": [10, 1, 0], "20261002": [-5, 2, 0], "20261005": [-3, 3, 1], "20261006": [-1, 4, -2] } } };
      const pts = buildStockBriefPoints("9999", {
        fund: { month_revenue: [{ year: 2026, month: 9, revenue: 2.5e9, yoy: 0.123 }] },
        detail: { margin: { margin_balance_today: 1200, margin_balance_prev: 1000 } },
        hist,
        flag: { kind: "disposal", start: "2026-10-08", end: "2026-10-15", interval: "5分鐘" },
        events: [{ code: "9999", date: "2026-10-01", title: "甲事件" }, { code: "9999", date: "2026-08-01", title: "太舊事件" },
          { code: "9999", date: "2026-10-20", title: "乙除息" }, { code: "8888", date: "2026-10-05", title: "別檔" }],
        todayIso: "2026-10-11" });
      o.syn = pts.map((p) => p.k + "|" + p.t);
      o.empty = buildStockBriefPoints("0000", { fund: {}, detail: {}, hist: null, flag: null, events: [], todayIso: "2026-10-11" }).map((p) => p.t);
      const saved = currentCode;
      try {
        currentCode = "2330"; await renderStockBrief("2330");
        const el = document.getElementById("ai-brief-body");
        o.realLi = el.querySelectorAll("li").length; o.real = el.textContent;
        currentCode = "AAPL"; await renderStockBrief("AAPL"); o.us = el.textContent;
      } finally { currentCode = saved; }
      o.placeholder = document.getElementById("sub-ai").textContent.includes("籌碼綜合分析資料");
      return o;
    });
    const syn = r.syn.join(" / ");
    if (r.syn.length !== 5) briefErrors.push(`合成資料應 5 條，實際 ${r.syn.length}`);
    for (const k of ["營收|2026 年 9 月營收 25.0 億元，年增 +12.3%", "三大法人合計連買 2 日", "外資連賣 3 日", "投信連買 4 日",
      "融資餘額 1,200 張，較前一日增加 200 張（+20.0%）", "處置中：2026-10-08～2026-10-15，每 5分鐘撮合一次", "10-01 甲事件", "即將 10-20 乙除息"])
      if (!syn.includes(k)) briefErrors.push(`合成資料缺「${k}」：${syn.slice(0, 200)}`);
    if (syn.includes("太舊事件") || syn.includes("別檔")) briefErrors.push(`事件窗或代號過濾錯誤：${syn}`);
    if (r.empty.length !== 5 || !r.empty.every((t) => t.includes("查無") || t.includes("不是處置股"))) briefErrors.push(`全空應每條寫查無：${JSON.stringify(r.empty)}`);
    if (r.realLi !== 5) briefErrors.push(`2330 真實資料應 5 條，實際 ${r.realLi}：${r.real.slice(0, 120)}`);
    if (!r.real.includes("規則摘要，非 AI 判斷")) briefErrors.push("缺「規則摘要，非 AI 判斷」標示");
    if (!r.us.includes("美股暫不提供")) briefErrors.push(`美股應顯示誠實說明：${r.us.slice(0, 80)}`);
    if (r.placeholder) briefErrors.push("AI 分頁仍殘留個股簡報「功能建置中」佔位");
  } catch (e) { briefErrors.push(`測試本身出錯：${e.message || e}`); }
  record("73. 個股頁 AI 分頁個股簡報（規則版 5 條：營收年增／法人連買賣／融資變化／處置注意／近期事件；標「規則摘要，非 AI 判斷」；全空寫查無；美股誠實說明）", briefErrors.length === 0, briefErrors.join("; "));

  // 74.【2026-10-11 常備.開發-14】營收解讀與盤勢解讀（規則版）：①合成資料驗營收三段（月增／年增／累計年增，
  // 含「去年同月缺金額時用官方年增回推」與「缺月照實寫」）②合成資料驗盤勢四行（大盤漲跌、類股最強／最弱前三、
  // 法人合計、融資維持率水位與「最新一筆不完整改列上一筆」）③真實檔案 2330 營收三段＋市場頁盤勢解讀四行＋盤前資訊
  // ④美股營收解讀誠實說明 ⑤營收分頁不再殘留「功能建置中」。
  const readErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const o = {};
      const hist = [{ year: 2025, month: 2, revenue: 100e8, yoy: null }, { year: 2025, month: 3, revenue: 100e8, yoy: null }];
      const mr = [{ year: 2026, month: 1, revenue: 110e8, yoy: 0.1 }, { year: 2026, month: 2, revenue: 120e8, yoy: null }, { year: 2026, month: 3, revenue: 90e8, yoy: -0.1 }];
      o.rev = buildRevenueReadPoints({ month_revenue: mr, revenue_history_scoring: hist }).map((p) => p.k + "|" + p.t);
      o.revMiss = buildRevenueReadPoints({ month_revenue: mr.slice(1) }).map((p) => p.t);
      o.revEmpty = buildRevenueReadPoints({}).map((p) => p.t);
      const mkt = { taiex: { close: 20000, change_pct: -1.234, sparkline_dates: ["2026-10-07", "2026-10-08"] },
        sectors: [{ name: "甲類指數", change_pct: 3 }, { name: "乙類指數", change_pct: 2 }, { name: "丙類指數", change_pct: 1 },
          { name: "丁類指數", change_pct: 0 }, { name: "戊類指數", change_pct: -1 }, { name: "己類指數", change_pct: -2 }, { name: "庚類指數", change_pct: -3 }],
        institutional_history: [{ date: "20261007", total_net_lots: 9 }, { date: "20261008", total_net_lots: -1500, foreign_net_lots: -2000, trust_net_lots: 300, dealer_net_lots: 200 }] };
      const margin = [{ date: "2026-10-08", margin_money_date: "2026-10-07", ratio_pct: 180, ratio_pct_ck: 165 },
        { date: "2026-10-09", margin_money_date: "2026-10-08", ratio_pct: 172, ratio_pct_ck: 158.4 },
        { date: "2026-10-10", data_incomplete: true, ratio_pct: null }];
      o.mk = buildMarketReadLines({ mkt, margin });
      o.mkEmpty = buildMarketReadLines({ mkt: null, margin: null });
      const saved = currentCode;
      try {
        currentCode = "2330"; await renderRevenueRead("2330");
        const el = document.getElementById("ai-rev-body");
        o.realLi = el.querySelectorAll("li").length; o.real = el.textContent;
        currentCode = "AAPL"; await renderRevenueRead("AAPL"); o.us = el.textContent;
      } finally { currentCode = saved; }
      o.placeholder = document.getElementById("sub-rev").textContent.includes("功能建置中");
      await loadMarketBrief();
      const mb = document.getElementById("market-brief-body");
      o.mbText = mb.textContent; o.mbLines = mb.querySelectorAll("div").length;
      return o;
    });
    const rev = r.rev.join(" / ");
    for (const k of ["月增|2026 年 3 月營收 90.0 億元，較上月 120 億元減少 -25.0%", "年增|2026 年 3 月較去年同月衰退 -10.0%（官方年增率）",
      "累計年增|2026 年 1～3 月累計營收 320 億元，較去年同期 300 億元成長 +6.7%"])
      if (!rev.includes(k)) readErrors.push(`營收合成資料缺「${k}」：${rev.slice(0, 240)}`);
    if (!r.revMiss[2].includes("缺 1、2 月")) readErrors.push(`缺月應照實寫：${r.revMiss[2]}`);
    if (r.revEmpty.length !== 3 || !r.revEmpty.every((t) => t.includes("查無"))) readErrors.push(`全空應三段查無：${JSON.stringify(r.revEmpty)}`);
    const mk = r.mk.join(" / ");
    for (const k of ["大盤：加權指數（2026-10-08 收盤） 20,000，下跌 -1.23%", "最強 甲 +3.00%、乙 +2.00%、丙 +1.00%", "最弱 庚 -3.00%、己 -2.00%、戊 -1.00%",
      "法人（10/08）：三大法人合計賣超 1,500 張（外資賣超 2,000 張、投信買超 300 張、自營商買超 200 張）",
      "融資維持率：158.4%（注意", "資料日 2026-10-08", "較前一筆-6.6 個百分點", "最新一筆資料不完整，改列上一筆有效值"])
      if (!mk.includes(k)) readErrors.push(`盤勢合成資料缺「${k}」：${mk.slice(0, 300)}`);
    if (r.mk.length !== 4) readErrors.push(`盤勢應 4 行，實際 ${r.mk.length}`);
    if (r.mkEmpty.length !== 4 || !r.mkEmpty.every((t) => t.includes("查無"))) readErrors.push(`盤勢全空應四行查無：${JSON.stringify(r.mkEmpty)}`);
    if (r.realLi !== 3) readErrors.push(`2330 營收解讀應 3 段，實際 ${r.realLi}：${r.real.slice(0, 120)}`);
    if (!r.real.includes("規則摘要，非 AI 判斷")) readErrors.push("營收解讀缺「規則摘要，非 AI 判斷」標示");
    if (!r.us.includes("美股暫不提供")) readErrors.push(`美股應顯示誠實說明：${r.us.slice(0, 80)}`);
    if (r.placeholder) readErrors.push("營收分頁仍殘留「功能建置中」佔位");
    for (const k of ["盤勢解讀", "大盤：", "類股（", "法人（", "融資維持率：", "盤前資訊", "規則摘要，非 AI 判斷"])
      if (!r.mbText.includes(k)) readErrors.push(`市場頁盤勢卡（真實檔）缺「${k}」：${r.mbText.slice(0, 200)}`);
  } catch (e) { readErrors.push(`測試本身出錯：${e.message || e}`); }
  record("74. 營收解讀（月增／年增／累計年增三段）與市場頁盤勢解讀（大盤／類股強弱前三／法人合計／融資維持率水位）規則版；標「規則摘要，非 AI 判斷」；全空寫查無；美股誠實說明", readErrors.length === 0, readErrors.join("; "));

  // 75.【2026-10-11 常備.開發-15】目標價與評等（公開來源）：①合成資料驗評等家數長條與買進類占比趨勢
  // ②美股不在涵蓋清單／檔案缺 → 寫「查無評等」＋原因 ③台股顯示「沒有合法的免費來源」誠實說明
  // ④目標價一律標「待採購」⑤AI 分頁不得殘留「券商報告雷達／功能建置中」。
  const analystErrors = [];
  try {
    const r = await page.evaluate(async () => {
      const o = {};
      const div = document.createElement("div");
      const txt = (h) => { div.innerHTML = h; return div.textContent; };
      const data = { generated_at: "2026-10-11T00:00:00+00:00", coverage: ["ZZZZ", "YYYY"],
        tickers: { ZZZZ: [{ period: "2026-10-01", strongBuy: 10, buy: 20, hold: 8, sell: 2, strongSell: 0 },
          { period: "2026-09-01", strongBuy: 8, buy: 16, hold: 12, sell: 4, strongSell: 0 }] } };
      o.syn = txt(buildAnalystRadarHtml("AAPL", { ...data, tickers: { AAPL: data.tickers.ZZZZ } }));
      o.notCovered = txt(buildAnalystRadarHtml("AAPL", data));
      o.noFile = txt(buildAnalystRadarHtml("AAPL", null));
      o.tw = txt(buildAnalystRadarHtml("2330", data));
      const saved = currentCode;
      try {
        currentCode = "2330"; await renderAnalystRadar("2330");
        o.twLive = document.getElementById("analyst-radar-body").textContent;
        currentCode = "AAPL"; await renderAnalystRadar("AAPL");
        o.usLive = document.getElementById("analyst-radar-body").textContent;
      } finally { currentCode = saved; }
      o.sub = document.getElementById("sub-ai").textContent;
      return o;
    });
    for (const k of ["2026-10-01 期，共 40 家券商評等", "強力買進", "買進類占比 75%，較 2026-09-01 期上升 15 個百分點", "待採購"])
      if (!r.syn.includes(k)) analystErrors.push(`合成資料缺「${k}」：${r.syn.slice(0, 200)}`);
    if (r.syn.includes("非投資建議")) analystErrors.push("卡片內又出現「非投資建議」（先.八十-5：只在頁尾）");
    if (!r.notCovered.includes("查無評等") || !r.notCovered.includes("不在清單內")) analystErrors.push(`不在涵蓋清單應寫原因：${r.notCovered.slice(0, 120)}`);
    if (!r.noFile.includes("查無評等") || !r.noFile.includes("尚未產生或讀取失敗")) analystErrors.push(`檔案缺應寫原因：${r.noFile.slice(0, 120)}`);
    if (!r.tw.includes("沒有合法的免費來源")) analystErrors.push(`台股應誠實說明：${r.tw.slice(0, 120)}`);
    if (!r.twLive.includes("沒有合法的免費來源")) analystErrors.push(`台股實際畫面應誠實說明：${r.twLive.slice(0, 120)}`);
    if (!(r.usLive.includes("券商評等") || r.usLive.includes("查無評等")) || !r.usLive.includes("待採購")) analystErrors.push(`AAPL 實際畫面異常：${r.usLive.slice(0, 160)}`);
    if (r.sub.includes("券商報告雷達") || r.sub.includes("功能建置中")) analystErrors.push("AI 分頁仍殘留「券商報告雷達／功能建置中」");
  } catch (e) { analystErrors.push(`測試本身出錯：${e.message || e}`); }
  record("75. 個股頁目標價與評等（公開來源）：美股評等家數長條＋買進類占比趨勢；查無時寫原因；台股誠實說明無合法免費來源；目標價標待採購；無「功能建置中」", analystErrors.length === 0, analystErrors.join("; "));

  // 76.【2026-10-11 常備.開發-18】設定頁到價與事件推播：未連本機顯示 CTA；連線後台股自選股列出漲跌幅／到價／事件三種設定，
  // 美股誠實寫暫不支援；儲存時整份規則 POST /alerts/rules。（伺服器端三種觸發由 research/price_alerts_selftest.py 驗）
  const alertErrors = [];
  try {
    await page.evaluate(() => window.go("settings"));
    const r = await page.evaluate(async () => {
      const saved = { lf: window.liveFetch, f: window.fetch, url: LIVE.url, conf: LIVE.configured, wl: WL };
      const o = {};
      try {
        LIVE.configured = false; LIVE.url = "";
        await loadAlerts();
        o.ctaOff = getComputedStyle(document.getElementById("alert-cta")).display;
        o.bodyOff = document.getElementById("alert-body").textContent;
        WL = ["2330", "AAPL", "0050"];
        const data = { ok: true, rules: { "2330": { pct: 3, above: 1200, below: null, event: true } }, fired: { "2330": { kind: "pct", at: "2026-10-12T09:31:00+08:00", delivered: 1 } },
          last_check: "2026-10-12T09:31:00+08:00", live_quotes: true, in_market_hours: true };
        window.liveFetch = async (p) => new Response(JSON.stringify(p === "/alerts/rules" ? data : {}), { status: 200 });
        let posted = null;
        window.fetch = async (u, opt) => { if (String(u).startsWith("https://smoke.invalid/alerts/rules")) { posted = opt && opt.body; return new Response(JSON.stringify({ ok: true, rules: {} }), { status: 200 }); } return saved.f.call(window, u, opt); };
        LIVE.url = "https://smoke.invalid"; LIVE.configured = true;
        await loadAlerts();
        o.ctaOn = getComputedStyle(document.getElementById("alert-cta")).display;
        o.rows = [...document.querySelectorAll("#alert-body .alert-row")].map((x) => x.dataset.code);
        o.body = document.getElementById("alert-body").textContent;
        o.note = document.getElementById("alert-note").textContent;
        o.pctVal = document.querySelector('#alert-body .alert-row[data-code="2330"] input[data-k="pct"]').value;
        document.querySelector('#alert-body .alert-row[data-code="0050"] input[data-k="below"]').value = "180";
        await saveAlerts();
        o.posted = posted;
      } finally { window.liveFetch = saved.lf; window.fetch = saved.f; LIVE.url = saved.url; LIVE.configured = saved.conf; WL = saved.wl; }
      return o;
    });
    if (r.ctaOff === "none") alertErrors.push("未連本機時應顯示 CTA");
    if (r.bodyOff.trim()) alertErrors.push(`未連本機時不應顯示設定列：${r.bodyOff.slice(0, 60)}`);
    if (r.ctaOn !== "none") alertErrors.push("已連線時 CTA 應隱藏");
    if (JSON.stringify(r.rows) !== '["2330","0050"]') alertErrors.push(`只應列台股自選股：${JSON.stringify(r.rows)}`);
    for (const k of ["漲跌幅", "漲到", "跌到", "事件前一日", "今日已推"]) if (!r.body.includes(k)) alertErrors.push(`設定列缺「${k}」`);
    if (r.pctVal !== "3") alertErrors.push(`既有規則未回填：pct=${r.pctVal}`);
    if (!r.note.includes("AAPL") || !r.note.includes("暫不支援")) alertErrors.push(`美股應誠實說明暫不支援：${r.note.slice(0, 120)}`);
    // 先.八十-5：「非投資建議」前台統一只在頁尾一處，卡片說明不再重複
    if (!r.note.includes("每檔每日最多一則")) alertErrors.push(`說明缺每日上限：${r.note.slice(0, 120)}`);
    if (r.note.includes("非投資建議")) alertErrors.push("卡片說明又出現「非投資建議」（應只在頁尾）");
    let pj = null; try { pj = JSON.parse(r.posted || "null"); } catch (e) { /* 下面會判失敗 */ }
    if (!pj || !pj.rules || !pj.rules["2330"] || pj.rules["2330"].above !== 1200 || !pj.rules["2330"].event || !pj.rules["0050"] || pj.rules["0050"].below !== 180)
      alertErrors.push(`儲存的規則內容不符：${r.posted}`);
  } catch (e) { alertErrors.push(`測試本身出錯：${e.message || e}`); }
  record("76. 設定頁到價與事件推播（未連本機顯示 CTA；台股自選股可設漲跌幅±X%／漲到／跌到／事件前一日；美股誠實寫暫不支援；儲存整份 POST /alerts/rules）", alertErrors.length === 0, alertErrors.join("; "));

  // 77.【2026-10-11 常備.開發-19】全域搜尋：用 repo 內真實 data/news.json／events.json／strategies.json，
  // 輸入「台積電」「除息」各有結果（分組顯示：股票／新聞／事件／策略）；單一來源失敗只影響該組。
  const gsErrors = [];
  try {
    await page.evaluate(() => window.go("home"));
    const r = await page.evaluate(async () => {
      const o = {};
      await openSearch();
      const inp = document.getElementById("search-input");
      const grab = (q) => {
        inp.value = q; doSearch();
        const g = {};
        document.querySelectorAll("#search-results .gs-group").forEach((x) => { g[x.dataset.group] = { rows: x.querySelectorAll(".sr").length, text: x.textContent }; });
        return g;
      };
      o.tsmc = grab("台積電");
      o.exdiv = grab("除息");
      o.strat = grab("動能");
      const saved = GS_STATE.strategies;
      GS_STATE.strategies = "err";
      o.isolated = grab("台積電");
      GS_STATE.strategies = saved;
      o.title = document.querySelector("#search-sheet h2").textContent;
      closeSearch();
      return o;
    });
    if (r.title !== "全域搜尋") gsErrors.push(`標題應為「全域搜尋」：${r.title}`);
    for (const k of ["stocks", "news", "events", "strategies"]) if (!r.tsmc[k]) gsErrors.push(`「台積電」缺 ${k} 分組`);
    if (!r.tsmc.stocks || !r.tsmc.stocks.text.includes("2330")) gsErrors.push("「台積電」股票組應含 2330");
    const tsmcOther = (r.tsmc.news ? r.tsmc.news.rows : 0) + (r.tsmc.events ? r.tsmc.events.rows : 0);
    if (tsmcOther < 1) gsErrors.push(`「台積電」新聞＋事件應至少 1 筆：${JSON.stringify(r.tsmc).slice(0, 200)}`);
    if (!r.exdiv.events || r.exdiv.events.rows < 1 || !r.exdiv.events.text.includes("除")) gsErrors.push(`「除息」事件組應有結果：${JSON.stringify(r.exdiv.events || {}).slice(0, 200)}`);
    if (!r.strat.strategies || r.strat.strategies.rows < 1 || !r.strat.strategies.text.includes("題材動能榜")) gsErrors.push(`「動能」策略組應含題材動能榜：${JSON.stringify(r.strat.strategies || {}).slice(0, 200)}`);
    if (!r.isolated.strategies || !r.isolated.strategies.text.includes("載入失敗")) gsErrors.push("策略來源失敗時應只在策略組顯示載入失敗");
    if (!r.isolated.stocks || !r.isolated.stocks.text.includes("2330")) gsErrors.push("策略來源失敗不應影響股票組");
    console.log(`  77 細節：台積電 股票${r.tsmc.stocks && r.tsmc.stocks.rows}／新聞${r.tsmc.news && r.tsmc.news.rows}／事件${r.tsmc.events && r.tsmc.events.rows}；除息 事件${r.exdiv.events && r.exdiv.events.rows}；動能 策略${r.strat.strategies && r.strat.strategies.rows}`);
  } catch (e) { gsErrors.push(`測試本身出錯：${e.message || e}`); }
  record("77. 全域搜尋（股票／新聞／事件／策略分組；「台積電」「除息」各有結果；單一來源失敗只影響該組）", gsErrors.length === 0, gsErrors.join("; "));

  // 78.【2026-10-11 常備.開發-20】首頁首次載入不得下載大檔：全新環境（無快取、無 SW）開首頁 8 秒內，
  // 不得請求整份 stock_detail.json／events.json／fundamentals.json，也不得載入 lightweight-charts；
  // sparklines.json 不得重複下載。另印出實測傳輸量（gzip 模擬 GitHub Pages），供對照 <300KB 目標。
  const flErrors = [];
  let flInfo = "";
  try {
    const { measureFirstLoad } = await import("./measure_first_load.mjs");
    const m = await measureFirstLoad(browser, baseUrl, 8000);
    const urls = m.rows.map(x => x.url);
    for (const bad of ["/data/stock_detail.json", "/data/events.json", "/data/fundamentals.json", "lightweight-charts"]) {
      if (urls.some(u => u.endsWith(bad) || (bad === "lightweight-charts" && u.includes(bad)))) flErrors.push(`首頁載入時下載了 ${bad}`);
    }
    // 常備.開發-20 丙案：首頁不得載入任何分頁程式檔（app-<頁>.js 要點到該頁才載）
    const modUrls = urls.filter(u => /\/app-[a-z]+\.js$/.test(u));
    if (modUrls.length) flErrors.push(`首頁載入時就下載了分頁程式：${modUrls.map(u => u.replace(/.*\//, "")).join("、")}`);
    const sp = urls.filter(u => u.endsWith("/data/sparklines.json")).length;
    if (sp > 1) flErrors.push(`sparklines.json 下載了 ${sp} 次`);
    // 常備.開發-20（先.六十七）：首頁自選股改讀 data/quote_lite/{代號}.json，不得再下載整份這三檔
    for (const bad of ["/data/sparklines.json", "/data/quotes_all_tw.json", "/data/company_info.json"]) {
      if (urls.some(u => u.endsWith(bad))) flErrors.push(`首頁載入時下載了整份 ${bad}`);
    }
    if (!urls.some(u => /\/data\/quote_lite\/[^/]+\.json$/.test(u))) flErrors.push("首頁沒有抓任何 data/quote_lite 小檔（自選股走勢線／收盤來源斷了？）");
    if (m.total >= 350 * 1024) flErrors.push(`首頁首次載入 ${(m.total / 1024).toFixed(1)} KB ≥ 350KB（先.六十五／六十七驗收門檻）`);
    flInfo = `首頁首次載入實測 ${(m.total / 1024).toFixed(1)} KB（${m.rows.length} 個請求；目標 <350KB，先.六十五丙案）`;
  } catch (e) { flErrors.push(`測試本身出錯：${e.message || e}`); }
  record("78. 首頁首次載入 <350KB，不下載整份 stock_detail／events／fundamentals／sparklines／quotes_all_tw／company_info、不預載圖表函式庫", flErrors.length === 0, flErrors.join("; ") || flInfo);

  // 87.【2026-10-11 常備.開發-20 先.六十七】首頁小檔 data/quote_lite/{代號}.json 必須與整份檔原樣一致
  // （走勢線＝sparklines.json、收盤＝quotes_all_tw.json、名稱＝company_info.json），且查無代號回 404。
  const qlErrors = [];
  let qlInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const j = async (u) => { const x = await fetch(u + "?t=" + Date.now()); return x.ok ? x.json() : null; };
      const [sp, qa, ci] = await Promise.all([j("data/sparklines.json"), j("data/quotes_all_tw.json"), j("data/company_info.json")]);
      const out = { bad: [], n: 0 };
      // 先.六十九-3：兩層——熱門代號有單檔，其餘在 data/quote_lite/p/{前兩碼（00 開頭前三碼）}.json 分片
      const shardOf = async (c) => { const sh = await j("data/quote_lite/p/" + (/^00/.test(c) ? c.slice(0, 3) : c.slice(0, 2)) + ".json"); return sh && sh[c]; };
      out.tiers = {};
      for (const code of ["2330", "2454", "TAIEX", "0050", "8299", "1101", "00878", "9958"]) {
        let lite = await j("data/quote_lite/" + code + ".json");
        out.tiers[code] = lite ? "單檔" : "分片";
        if (!lite) lite = await shardOf(code);
        if (!lite) { out.bad.push(code + " 單檔與分片都不存在"); continue; }
        out.n++;
        if (JSON.stringify(lite.s || null) !== JSON.stringify(sp.sparklines[code] || null)) out.bad.push(code + " 走勢線不一致");
        if (JSON.stringify(lite.a || null) !== JSON.stringify(qa.quotes[code] || null)) out.bad.push(code + " 全市場收盤不一致");
        if ((lite.sd || null) !== ((sp.stale_dates || {})[code] || null)) out.bad.push(code + " stale_dates 不一致");
        if ((lite.n || null) !== ((ci.companies[code] || {}).name || null)) out.bad.push(code + " 名稱不一致");
        if (lite.asof !== (sp.meta || {}).data_asof) out.bad.push(code + " asof 不一致");
      }
      const miss = await fetch("data/quote_lite/ZZZZ9.json?t=" + Date.now());
      if (miss.status !== 404) out.bad.push("查無代號應回 404，實得 " + miss.status);
      return out;
    });
    qlErrors.push(...r.bad);
    qlInfo = `抽驗 ${r.n} 檔（${Object.entries(r.tiers).map(([c, t]) => c + t).join("、")}）與整份檔一致；查無代號回 404`;
  } catch (e) { qlErrors.push(`測試本身出錯：${e.message || e}`); }
  record("87. 首頁小檔 data/quote_lite/{代號}.json（含先.六十九 分片）與 sparklines／quotes_all_tw／company_info 原樣一致", qlErrors.length === 0, qlErrors.join("; ") || qlInfo);

  // 79.【2026-10-11 常備.開發-20】個股明細改每檔獨立檔延遲載入：loadStockDetail('2330') 與整份檔同一檔內容相同；
  // 估值卡用的 EPS 精簡檔最後四季與整份檔一致；不存在的代號回 {} 不拋錯。
  const sdErrors = [];
  let sdInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const one = await loadStockDetail("2330");
      const full = await (await fetch("data/stock_detail.json", { cache: "no-store" })).json();
      const eps = await loadStockDetailEps();
      const miss = await loadStockDetail("ZZZZ99");
      const fq = ((full.stocks["2330"] || {}).financials || {}).quarters || [];
      const eq = ((eps["2330"] || {}).financials || {}).quarters || [];
      const last4 = fq.slice(-4).map(q => [q.year, q.quarter, q.eps]);
      return { same: JSON.stringify(one) === JSON.stringify(full.stocks["2330"]), epsSame: JSON.stringify(eq.map(q => [q.year, q.quarter, q.eps])) === JSON.stringify(last4),
               epsN: Object.keys(eps).length, missEmpty: miss && typeof miss === "object" && !Object.keys(miss).length, hasFin: !!(one.financials && one.financials.quarters && one.financials.quarters.length) };
    });
    if (!r.same) sdErrors.push("data/stock_detail/2330.json 與整份檔 stocks['2330'] 不一致");
    if (!r.hasFin) sdErrors.push("2330 拆檔沒有財報季資料");
    if (!r.epsSame) sdErrors.push("EPS 精簡檔 2330 最後四季與整份檔不一致");
    if (r.epsN < 1000) sdErrors.push(`EPS 精簡檔只有 ${r.epsN} 檔`);
    if (!r.missEmpty) sdErrors.push("不存在的代號沒有回傳 {}");
    sdInfo = `2330 內容一致；EPS 精簡檔 ${r.epsN} 檔`;
  } catch (e) { sdErrors.push(`測試本身出錯：${e.message || e}`); }
  record("79. 個股明細每檔獨立檔（data/stock_detail/{代號}.json）內容與整份檔一致；估值卡 EPS 精簡檔一致；查無代號回 {}", sdErrors.length === 0, sdErrors.join("; ") || sdInfo);

  // 80.【2026-10-11 常備.開發-20】PWA 離線仍可開啟：另開環境讓 SW 安裝並接管，確認快取含 app.js／app.css，
  // 斷網後重新整理，頁面仍套用樣式、主程式函式存在、分頁列可見（資料抓不到是預期，不算錯）。
  const offErrors = [];
  let offInfo = "";
  // 常備.開發-27：雲端冒煙打 Pages 正式網址時站台在 /alpha-app/ 底下，快取路徑要帶前綴（本機 localhost 前綴為空字串，檢查內容不變）。
  const basePath = new URL(baseUrl).pathname.replace(/\/+$/, "");
  try {
    const octx = await browser.newContext({ viewport: { width: 393, height: 852 } });
    const op = await octx.newPage();
    const opErrors = [];
    op.on("pageerror", e => opErrors.push(String(e)));
    await op.goto(`${baseUrl}/index.html`, { waitUntil: "load", timeout: 30000 });
    await op.evaluate(async () => { await navigator.serviceWorker.ready; });
    await op.reload({ waitUntil: "load" });
    await op.waitForTimeout(2000);
    const cached = await op.evaluate(async () => {
      const out = [];
      for (const k of await caches.keys()) { const c = await caches.open(k); for (const req of await c.keys()) out.push(new URL(req.url).pathname); }
      return { list: out, controlled: !!navigator.serviceWorker.controller };
    });
    for (const f of ["/app.js", "/app.css", "/index.html", "/app-shared.js", "/app-market.js", "/app-picks.js", "/app-stock.js", "/app-trade.js", "/app-journal.js", "/app-settings.js"]) if (!cached.list.includes(basePath + f)) offErrors.push(`SW 快取缺 ${basePath + f}`);
    if (!cached.controlled) offErrors.push("SW 沒有接管頁面");
    await octx.setOffline(true);
    await op.reload({ waitUntil: "load", timeout: 30000 });
    await op.waitForTimeout(1500);
    const st = await op.evaluate(() => ({
      fn: typeof openStock === "function" && typeof hydrateHome === "function",
      css: getComputedStyle(document.body).backgroundColor,
      nav: !!document.querySelector("nav, .tabbar, #tabbar, .nav"),
      ver: typeof APP_VERSION !== "undefined" ? APP_VERSION : null,
    }));
    if (!st.fn) offErrors.push("離線重新整理後 app.js 主程式沒有載入");
    // 常備.開發-20 丙案：離線時點到分頁仍要能從 SW 快取載入該頁程式（真函式取代轉接殼）
    const offMod = await op.evaluate(async () => {
      const bad = [];
      for (const [m, fn] of [["stock", "openStock"], ["market", "hydrateMarket"], ["settings", "hydrateSettings"]]) {
        try { await loadAppModule(m); if (window[fn]._lazyStub) bad.push(`${m}：${fn} 仍是轉接殼`); } catch (e) { bad.push(`${m}：${e.message || e}`); }
      }
      return bad;
    });
    if (offMod.length) offErrors.push("離線載入分頁程式失敗：" + offMod.join("；"));
    if (!st.css || st.css === "rgba(0, 0, 0, 0)" || st.css === "rgb(255, 255, 255)") offErrors.push(`離線重新整理後樣式沒有套用（body 背景 ${st.css}）`);
    const syntaxErr = opErrors.filter(e => /SyntaxError|Unexpected token/.test(e));
    if (syntaxErr.length) offErrors.push("離線時腳本解析錯誤：" + syntaxErr.join(" | ").slice(0, 200));
    offInfo = `快取 ${cached.list.length} 個外殼項目；離線版本 ${st.ver}；body 背景 ${st.css}`;
    await octx.close();
  } catch (e) { offErrors.push(`測試本身出錯：${e.message || e}`); }
  record("80. PWA 離線仍可開啟（SW 快取含 index.html／app.js／app.css／app-<頁>.js；斷網重新整理後樣式與主程式都在、分頁程式可從快取載入）", offErrors.length === 0, offErrors.join("; ") || offInfo);

  // 81.【2026-10-11 常備.開發-22】法說會事件附 MOPS 簡報官方連結：①合成資料——法說會列有
  // mopsov.twse.com.tw 法說會簡報查詢頁連結（co_id 為該代號、新分頁開啟），非法說會列與不合法代號沒有；
  // ②真實 data/events_by_code 取一筆法說會事件，事件列 HTML 含該代號的 MOPS 連結。只驗連結字串，不連 MOPS。
  const irErrors = [];
  let irInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const box = document.createElement("div");
      box.innerHTML = eventsRowsHtml([
        { code: "2330", date: "2026-10-08", type: "法說會", title: "召開法人說明會", url: "https://mops.twse.com.tw/mops/web/t05st01" },
        { code: "2330", date: "2026-10-07", type: "月營收", title: "9月營收", url: "" },
        { code: "<x>", date: "2026-10-06", type: "法說會", title: "壞代號", url: "" },
      ], 10);
      const links = [...box.querySelectorAll("a.mops-ir-link")].map(a => ({ href: a.href, target: a.target, text: a.textContent }));
      const ev = await fetch("data/events.json").then(x => x.json());
      const one = (ev.events || []).find(e => e.type === "法說會");
      let real = null;
      if (one) {
        const b2 = document.createElement("div");
        b2.innerHTML = eventsRowsHtml([one], 1);
        const a = b2.querySelector("a.mops-ir-link");
        real = { code: one.code, href: a ? a.href : null };
      }
      return { links, real };
    });
    if (r.links.length !== 1) irErrors.push(`合成資料應只有 1 個 MOPS 連結（法說會且代號合法），實得 ${r.links.length}`);
    const l = r.links[0];
    if (l && !(l.href.startsWith("https://mopsov.twse.com.tw/mops/web/ajax_t100sb07_1?") && l.href.endsWith("co_id=2330"))) irErrors.push(`連結網址不對：${l.href}`);
    if (l && l.target !== "_blank") irErrors.push("連結應另開分頁");
    if (!r.real) irErrors.push("真實 events.json 找不到任何法說會事件（無法驗證真實資料）");
    else if (!r.real.href || !r.real.href.endsWith("co_id=" + encodeURIComponent(r.real.code))) irErrors.push(`真實法說會事件 ${r.real.code} 沒有對應 MOPS 連結：${r.real.href}`);
    if (r.real) irInfo = `真實法說會事件 ${r.real.code} → ${r.real.href}`;
  } catch (e) { irErrors.push(`測試本身出錯：${e.message || e}`); }
  record("81. 法說會事件附 MOPS 法說會簡報官方連結（只有法說會列有、代號正確、另開分頁）", irErrors.length === 0, irErrors.join("; ") || irInfo);

  // 82～84.【2026-10-11 先.六十六】版面結構永久檢查。根因：dec42448（常備.開發-17）多寫一個 </div>，
  // HTML 解析器提早關閉 #app／<main>，後面的分頁、<nav> 全部變成 body 直接子元素，手機版面整個散掉；
  // 既有冒煙只看「有沒有內容、能不能切換」，結構錯了照樣全綠，所以補三道結構檢查。
  const layout = await page.evaluate(() => {
    const kids = [...document.body.children].map(e => e.tagName === "SCRIPT" ? "script" : (e.id ? `#${e.id}` : e.tagName.toLowerCase()));
    const screens = [...document.querySelectorAll(".screen")].map(e => ({ id: e.id, inMain: !!e.closest("main#main") }));
    const nav = document.querySelector("nav#nav");
    return { kids, screens, navInApp: !!(nav && nav.closest("#app")),
             domSection: document.querySelectorAll("section").length, domNav: document.querySelectorAll("nav").length };
  });
  const badKids = layout.kids.filter(k => !["#new-version-banner", "#app", "script"].includes(k));
  record("82. body 直接子元素白名單（只能是 #new-version-banner、#app、script）", badKids.length === 0,
    badKids.length ? `不允許的直接子元素：${badKids.join("、")}` : `${layout.kids.length} 個子元素`);
  const outMain = layout.screens.filter(s => !s.inMain).map(s => s.id);
  record("83. 每個 .screen 都在 main#main 內、nav 在 #app 內", outMain.length === 0 && layout.navInApp && layout.screens.length > 0,
    `${layout.screens.length} 個 .screen${outMain.length ? `；脫離 main：${outMain.join("、")}` : ""}；nav 在 #app 內=${layout.navInApp}`);
  // 原始碼去掉註解、<script>／<style> 內容後，比對 <section>／<nav> 數量與 DOM 一致，並檢查 <div> 開關數平衡
  // （多一個 </div> 時解析器會吞掉，DOM 數量仍一樣，所以 div 用原始碼開關數直接比）
  const srcInfo = await page.evaluate(async () => {
    const raw = await (await fetch(location.href.split("#")[0], { cache: "no-store" })).text();
    const body = raw.replace(/<!--[\s\S]*?-->/g, "").replace(/<script\b[\s\S]*?<\/script>/gi, "").replace(/<style\b[\s\S]*?<\/style>/gi, "");
    const n = (re) => (body.match(re) || []).length;
    return { section: n(/<section\b/gi), sectionClose: n(/<\/section>/gi), nav: n(/<nav\b/gi), navClose: n(/<\/nav>/gi),
             divOpen: n(/<div\b/gi), divClose: n(/<\/div>/gi) };
  });
  const balErr = [];
  if (srcInfo.section !== layout.domSection || srcInfo.section !== srcInfo.sectionClose) balErr.push(`section 原始碼開 ${srcInfo.section}／關 ${srcInfo.sectionClose}／DOM ${layout.domSection}`);
  if (srcInfo.nav !== layout.domNav || srcInfo.nav !== srcInfo.navClose) balErr.push(`nav 原始碼開 ${srcInfo.nav}／關 ${srcInfo.navClose}／DOM ${layout.domNav}`);
  if (srcInfo.divOpen !== srcInfo.divClose) balErr.push(`div 原始碼開 ${srcInfo.divOpen}／關 ${srcInfo.divClose}`);
  record("84. 靜態標記標籤數量平衡（section／nav 原始碼＝DOM、div 開關數相等）", balErr.length === 0,
    balErr.join("；") || `section ${srcInfo.section}、nav ${srcInfo.nav}、div ${srcInfo.divOpen}`);

  // 85.【2026-10-11 常備.開發-20 丙案】分頁程式點到該頁才載入：全新環境開首頁，不得請求任何 app-<頁>.js；
  // 依序點導覽列五個分頁＋開個股頁，每次都要載到對應的分頁檔、該頁真函式取代轉接殼、畫面切換成功、無 pageerror。
  const lzErrors = [];
  let lzInfo = "";
  try {
    const lctx = await browser.newContext({ viewport: { width: 393, height: 852 }, serviceWorkers: "block" });
    const lp = await lctx.newPage();
    const lpErrors = [];
    lp.on("pageerror", e => lpErrors.push(String(e)));
    const loaded = [];
    lp.on("request", r => { const mm = r.url().match(/\/app-([a-z]+)\.js/); if (mm) loaded.push(mm[1]); });
    await lp.goto(`${baseUrl}/index.html`, { waitUntil: "load", timeout: 30000 });
    await lp.waitForTimeout(3000);
    if (loaded.length) lzErrors.push(`首頁就載入了分頁程式：${loaded.join("、")}`);
    const steps = [["market", "scr-market", "hydrateMarket"], ["picks", "scr-picks", "hydratePicks"], ["trade", "scr-trade", "onTradeInit"], ["journal", "scr-journal", "renderJournalChips"], ["settings", "scr-settings", "hydrateSettings"]];
    for (const [scr, id, fn] of steps) {
      await lp.click(`#nav button[data-scr="${scr}"]`);
      await lp.waitForTimeout(1500);
      const st = await lp.evaluate(([id, fn]) => ({ active: document.getElementById(id).classList.contains("active"), real: typeof window[fn] === "function" && !window[fn]._lazyStub }), [id, fn]);
      if (!loaded.includes(scr)) lzErrors.push(`點「${scr}」沒有載入 app-${scr}.js`);
      if (!st.active) lzErrors.push(`點「${scr}」畫面沒切過去`);
      if (!st.real) lzErrors.push(`點「${scr}」後 ${fn} 仍是轉接殼`);
    }
    await lp.evaluate(() => openStock("2330"));
    await lp.waitForTimeout(2000);
    const sk = await lp.evaluate(() => ({ active: document.getElementById("scr-stock").classList.contains("active"), real: !openStock._lazyStub, name: (document.getElementById("sh-name") || {}).textContent || "" }));
    if (!loaded.includes("stock")) lzErrors.push("開個股頁沒有載入 app-stock.js");
    if (!sk.active || !sk.real) lzErrors.push(`個股頁未正常開啟（active=${sk.active} real=${sk.real}）`);
    const ge = await lp.evaluate(() => (typeof GLOBAL_ERRORS !== "undefined" ? GLOBAL_ERRORS : []).filter(x => /loadAppModule|分頁程式|is not defined/.test(x.label + " " + x.msg)));
    if (ge.length) lzErrors.push("錯誤 log：" + JSON.stringify(ge).slice(0, 300));
    if (lpErrors.length) lzErrors.push("pageerror：" + lpErrors.join(" | ").slice(0, 300));
    lzInfo = `依序載入：${[...new Set(loaded)].join("→")}；個股頁標題「${sk.name}」`;
    await lctx.close();
  } catch (e) { lzErrors.push(`測試本身出錯：${e.message || e}`); }
  record("85. 分頁程式點到該頁才載入（首頁不載 app-<頁>.js；五個分頁＋個股頁各自載入、真函式取代轉接殼、無錯誤）", lzErrors.length === 0, lzErrors.join("; ") || lzInfo);

  // 【2026-10-11 先.六十八】「策略 vs 0050」卡。資料 data/strategy_curves.json（build_strategy_curves.py，選股三榜重疊組合法）。
  // (a) 任一策略曲線單日變動不得超過其成分當日最大漲跌幅（＋0.5pp 進出場成本容許）——舊卡「依序串接複利」這種放大錯誤會在這裡爆；
  // (b) 0050 灰線累計報酬＝price_history 同期實際收盤報酬（±0.1pp）；(c) 卡片 UI：改名、八個分頁可切換、<60 日判讀固定文字。
  const scErrs = [], scInfo = [];
  try {
    const sc = await page.evaluate(async () => {
      const a = await (await fetch("data/strategy_curves.json", { cache: "no-store" })).json();
      const p = await (await fetch("data/price_history.json", { cache: "no-store" })).json();
      const px = {};
      for (const r of (p.prices && p.prices["0050"]) || []) px[r.date] = r.close;
      return { lines: a.lines || [], px };
    });
    let nChecked = 0;
    for (const l of sc.lines) {
      if (!l.started || !l.nav || l.nav.length < 2) continue;
      const cm = l.comp_max_abs_pct || [];
      if (cm.length === l.nav.length) {
        for (let i = 1; i < l.nav.length; i++) {
          const mv = Math.abs(l.nav[i] / l.nav[i - 1] - 1) * 100;
          if (mv > cm[i] + 0.5) { scErrs.push(`${l.label} ${l.dates[i]} 單日 ${mv.toFixed(2)}% > 成分最大 ${cm[i]}%+0.5`); break; }
        }
      }
      const p0 = sc.px[l.dates[0]], p1 = sc.px[l.dates[l.dates.length - 1]];
      if (p0 && p1) {
        const want = (p1 / p0 - 1) * 100, got = (l.bench[l.bench.length - 1] / l.bench[0] - 1) * 100;
        if (Math.abs(want - got) > 0.1) scErrs.push(`${l.label} 0050 線 ${got.toFixed(2)}% ≠ price_history ${want.toFixed(2)}%`);
        nChecked++;
      } else if (l.id !== "live_bb90") scErrs.push(`${l.label} 起訖日在 price_history 找不到 0050 收盤`);
    }
    scInfo.push(`${nChecked} 條已啟動曲線`);
  } catch (e) { scErrs.push(`測試本身出錯：${e.message || e}`); }
  record("88. 策略曲線單日變動 ≤ 成分當日最大漲跌幅、0050 線累計＝price_history 同期（±0.1pp）", scErrs.length === 0, scErrs.join("; ") || scInfo.join("；"));

  const uiErrs = [], uiInfo = [];
  try {
    await page.click('nav#nav button[data-scr="home"]');
    await page.waitForTimeout(400);
    const ui = await page.evaluate(async () => {
      const card = document.getElementById("strategy-curves-card");
      if (!card) return { err: "找不到 #strategy-curves-card" };
      const pos = document.getElementById("sc-positioning"), tabsEl = document.getElementById("sc-tabs");
      const out = { title: card.querySelector("h3").textContent.trim(), old: !!document.getElementById("benchmark-comparison-card"), tabs: [], verdicts: [], goals: [],
        // 先.七十-5：卡頂固定一句，且位置在分頁列之上
        positioning: pos ? pos.textContent.trim() : "", posAbove: !!(pos && tabsEl && (pos.compareDocumentPosition(tabsEl) & Node.DOCUMENT_POSITION_FOLLOWING)) };
      const tabs = [...card.querySelectorAll("#sc-tabs .sc-tab")].map(t => t.dataset.tab);
      for (const t of tabs) {
        SC_TAB = t; renderStrategyCurves();
        const body = document.getElementById("sc-body");
        out.tabs.push({ t, len: body.textContent.length, svg: !!body.querySelector("svg") });
        if (t !== "all") out.goals.push({ t, g: (body.querySelector(".sc-goal") || {}).textContent || "" });
        const v = body.querySelector(".sc-verdict");
        if (v) out.verdicts.push(v.textContent);
        if (t === "boards") out.correction = body.textContent.includes("放大約 5 倍");
      }
      SC_TAB = "all"; renderStrategyCurves();  // 先.七十三：還原成預設分頁（全部疊加）
      return out;
    });
    if (ui.err) uiErrs.push(ui.err);
    else {
      if (ui.title !== "跟 0050 比") uiErrs.push(`標題是「${ui.title}」`);
      if (ui.old) uiErrs.push("舊「我們 vs 0050」卡仍在");
      if (ui.tabs.length !== 8) uiErrs.push(`分頁數 ${ui.tabs.length}（應為 8）`);
      for (const t of ui.tabs) if (t.len < 10) uiErrs.push(`分頁 ${t.t} 內容空白`);
      if (!ui.correction) uiErrs.push("選股榜單分頁沒有更正註記");
      if (ui.positioning !== "守回檔的策略大漲時會落後 0050，這是設計；看滿 60 個交易日與最大跌幅") uiErrs.push(`卡頂定位句不符：「${ui.positioning}」`);
      if (!ui.posAbove) uiErrs.push("卡頂定位句不在分頁列上方");
      const wantGoal = { live: "守住回檔", paper_1: "守住回檔", paper_3: "守住回檔", paper_4: "贏大盤也守回檔", boards: "選股研究" };
      for (const g of ui.goals) {
        if (!g.g.startsWith("設計目標：")) uiErrs.push(`分頁 ${g.t} 沒有設計目標欄`);
        else if (wantGoal[g.t] && !g.g.includes(wantGoal[g.t])) uiErrs.push(`分頁 ${g.t} 設計目標應為「${wantGoal[g.t]}」，實為「${g.g}」`);
      }
      for (const v of ui.verdicts) {
        const m = v.match(/樣本 (\d+) 個交易日/);
        if (m && Number(m[1]) < 60 && !v.includes("尚不足以判斷")) uiErrs.push(`<60 日判讀不是固定文字：${v}`);
        if (/領先|落後|優於|勝過|表現/.test(v)) uiErrs.push(`判讀含推論文字：${v}`);
      }
      uiInfo.push(`${ui.tabs.length} 分頁、判讀 ${ui.verdicts.length} 則`);
    }
  } catch (e) { uiErrs.push(`測試本身出錯：${e.message || e}`); }
  record("89. 「跟 0050 比」卡（原策略 vs 0050）：改名、八分頁可切換、選股榜單附更正註記、判讀為固定規則文字、卡頂定位句＋各線設計目標（先.七十-5）", uiErrs.length === 0, uiErrs.join("; ") || uiInfo.join("；"));

  // 90.【2026-10-11 先.六十九-1】外殼快取優先＋資料 60 秒記憶體快取：模擬 4G（1.6Mbps／RTT 150ms）第二次開啟首頁
  // 「可互動」（核心 app.js 執行完畢，window.__ALPHA_BOOT_MS）<1.5 秒、SW 已接管，且 10 秒內同一個 data/*.json 不重複打網路。
  const soErrs = [];
  let soInfo = "";
  try {
    const { measureSecondOpen } = await import("./measure_second_open.mjs");
    const so = await measureSecondOpen(browser, baseUrl);
    if (!(so.secondBootMs < 1500)) soErrs.push(`第二次開啟可互動 ${so.secondBootMs}ms ≥ 1500ms`);
    if (!so.controlled) soErrs.push("第二次開啟時 SW 沒有接管（外殼沒走快取）");
    if (so.dups.length) soErrs.push("重複抓取：" + so.dups.map(([p, n]) => p + "×" + n).join("、"));
    soInfo = `第一次 ${so.firstBootMs}ms、第二次 ${so.secondBootMs}ms（DCL ${so.secondDclMs}ms），外殼快取 ${so.shellCached} 檔，資料請求 ${so.dataRequests} 次無重複`;
  } catch (e) { soErrs.push(`測試本身出錯：${e.message || e}`); }
  record("90. 4G 模擬第二次開啟可互動 <1.5 秒、SW 接管、資料檔不重複抓取（先.六十九-1）", soErrs.length === 0, soErrs.join("; ") || soInfo);

  // 91.【2026-10-11 先.七十二-A1／A2】前台文案規則（data/ui_glossary.json）：卡片標題 ≤8 字且無括號、按鈕 ≤6 字、
  // 看得到的說明 ≤40 字（超過要收成「ⓘ 說明」）、內部代號不得出現在前台（只准設定頁「進階」）、「非投資建議」前台只在頁尾一處。
  // 用 scripts/ux_copy_audit.mjs 同一套規則逐頁（五個分頁＋設定＋個股頁）檢查看得到的文字，任一命中即 FAIL。
  const uxErrs = [];
  let uxInfo = "";
  try {
    const { auditApp, loadGlossary } = await import("./ux_copy_audit.mjs");
    const ux = await auditApp(page, baseUrl, loadGlossary());
    let n = 0;
    for (const [pg, r] of Object.entries(ux)) {
      if (r.error) { uxErrs.push(`${pg}：${r.error}`); continue; }
      for (const k of ["titles", "buttons", "notes", "terms"]) for (const x of r[k]) { n++; uxErrs.push(`${pg}/${k}：${x}`); }
      if (r.disclaimers > 0) { n++; uxErrs.push(`${pg}：卡片裡又出現「非投資建議」（${r.disclaimerWhere.join("、")}）`); }
    }
    const footer = await page.evaluate(() => [...document.querySelectorAll("[data-ui-footer-disclaimer]")].map(e => e.textContent.trim()));
    if (footer.length !== 1 || !/非投資建議/.test(footer[0] || "")) uxErrs.push(`頁尾免責應恰好一處含「非投資建議」，實際 ${footer.length} 處`);
    uxInfo = `${Object.keys(ux).length} 頁 0 處違規；頁尾免責 1 處`;
    await page.evaluate(() => { const b = document.querySelector('nav#nav button[data-scr="home"]'); if (b) b.click(); });
    await page.waitForTimeout(400);
  } catch (e) { uxErrs.push(`測試本身出錯：${e.message || e}`); }
  record("91. 前台文案規則：標題 ≤8 字無括號、按鈕 ≤6 字、說明 ≤40 字、內部代號只在進階、免責只在頁尾（先.七十二-A1／A2）", uxErrs.length === 0, uxErrs.slice(0, 12).join("; ") || uxInfo);

  // 92.【先.七十二-A3】紅色橫幅兩段式：狀況（≤20 字）＋下一步（›），原始訊息收在「細節」；比不到規則的訊息也要先轉白話
  const banErrs = [];
  try {
    const b = await page.evaluate(() => {
      const el = document.getElementById("auto-banner");
      const save = Object.assign({}, AUTO_BAN);
      const out = [];
      for (const raw of ["現金不足：INSUFFICIENT_CASH 需 12,345 元", "自動交易排程未執行（電腦可能關機或離線）：今日盤前任務沒有心跳", "未知錯誤 Bb-90 LIVE preflight XYZ_42"]) {
        AUTO_BAN.offline = ""; AUTO_BAN.hb = ""; AUTO_BAN.px = ""; AUTO_BAN.local = raw;
        renderAutoBanner();
        const sit = el.querySelector(".ui-ban-sit"), nx = el.querySelector(".ui-ban-next"), det = el.querySelector("details.ui-ban-detail");
        out.push({ raw, summary: (el.querySelector("details.ui-ban-detail > summary") || {}).textContent, shown: getComputedStyle(el).display !== "none", sit: sit && sit.textContent, next: nx && nx.textContent,
          detOpen: det && det.open, detRaw: det && (det.querySelector("[data-ui-raw]") || {}).textContent, visible: el.innerText });
      }
      Object.assign(AUTO_BAN, save); renderAutoBanner();
      return out;
    });
    const want = ["還沒入金，這一期不會下單", "電腦沒在跑，自動投資暫停"];
    b.forEach((x, i) => {
      if (!x.shown) banErrs.push(`第 ${i + 1} 則沒顯示`);
      if (!x.sit || [...x.sit].length > 20) banErrs.push(`狀況過長或缺：${x.sit}`);
      if (!x.next || !x.next.includes("›")) banErrs.push(`缺下一步：${x.next}`);
      if (x.detOpen) banErrs.push("細節預設不該展開");
      if (x.summary !== "看細節") banErrs.push(`細節按鈕應為「看細節」，實為「${x.summary}」`);
      if (!x.detRaw || !x.detRaw.includes(x.raw.slice(0, 10))) banErrs.push("原始訊息沒保留在細節裡");
      if (want[i] && x.sit !== want[i]) banErrs.push(`第 ${i + 1} 則狀況應為「${want[i]}」，實為「${x.sit}」`);
      if (/\d/.test(x.sit || "")) banErrs.push(`第一行不得有技術數字：${x.sit}`);
      if (/Bb-?90|\bLIVE\b/.test(x.visible)) banErrs.push(`看得到的橫幅文字仍有內部代號：${x.visible.slice(0, 40)}`);
    });
  } catch (e) { banErrs.push(`測試本身出錯：${e.message || e}`); }
  record("92. 紅色橫幅「狀況＋下一步」兩段式、細節收合、原始訊息經白話轉換（先.七十二-A3）", banErrs.length === 0, banErrs.join("; "));

  // 93.【2026-10-11 先.七十二-B】資訊架構：首頁順序（狀態列→我的資產→自動投資這一期→自選股→大盤一眼→跟 0050 比→今日事件）、
  // 電腦沒連線時兩張錢的卡收成一行；設定頁常用／進階兩層；個股頁 4 分頁（總覽／籌碼／財務／事件）；市場頁冷門卡收進「更多」。
  const iaErrs = [];
  try {
    await page.evaluate(() => { const b = document.querySelector('nav#nav button[data-scr="home"]'); if (b) b.click(); });
    await page.waitForTimeout(500);
    // 偶發「Resulting promise was garbage collected／Execution context was destroyed」（頁面執行環境被重建）只重試一次；其他錯誤照常 FAIL
    const iaRun = () => page.evaluate(() => {
      const pos = (sel) => { const el = typeof sel === "string" ? document.querySelector(sel) : sel; if (!el) return -1;
        return [...document.querySelectorAll("#scr-home *")].indexOf(el); };
      const h3 = (t) => [...document.querySelectorAll("#scr-home .card h3")].find(h => h.textContent.trim().startsWith(t));
      const order = [pos("#home-status-strip"), pos("#home-offline-line"), pos("#home-money-card"), pos("#home-exec-card"),
        pos(h3("自選股") && h3("自選股").closest(".card")), pos(h3("大盤一眼") && h3("大盤一眼").closest(".card")),
        pos("#strategy-curves-card"), pos("#home-events-card")];
      const vis = (id) => { const e = document.getElementById(id); return !!(e && !e.hidden && getComputedStyle(e).display !== "none" && e.getBoundingClientRect().height > 0); };
      const out = { order, offlineLine: vis("home-offline-line"), money: vis("home-money-card"), exec: vis("home-exec-card"),
        liveConfigured: !!(window.LIVE && LIVE.configured && LIVE.url) };
      // 設定頁兩層
      document.querySelector('nav#nav button[data-scr="settings"]').click();
      const advCards = [...document.querySelectorAll("#scr-settings [data-ui-advanced]")];
      const commonCards = [...document.querySelectorAll("#scr-settings > .card:not([data-ui-advanced])")];
      const shown = (els) => els.filter(e => getComputedStyle(e).display !== "none").length;
      out.set0 = { adv: shown(advCards), common: shown(commonCards), nAdv: advCards.length, nCommon: commonCards.length };
      uiSettingsLayer("adv");
      out.set1 = { adv: shown(advCards), common: shown(commonCards) };
      uiSettingsLayer("common");
      out.commonTitles = commonCards.map(c => (c.querySelector("h3") || {}).textContent.trim().split(/\s/)[0]);
      // 個股頁 4 分頁
      out.stockTabs = [...document.querySelectorAll("#stock-tabs button")].map(b => b.textContent.trim());
      // 市場頁「更多」
      out.more = ["market-tw-panel", "market-us-panel"].map(id => { const d = document.querySelector(`#${id} details.ui-more`); return d ? { open: d.open, n: d.querySelectorAll(".card").length } : null; });
      return out;
    });
    let ia;
    // 先.八十-6：同一偶發錯誤最多重試 3 次（每次間隔遞增）；其他錯誤照常 FAIL
    for (let t = 0; ; t++) {
      try { ia = await iaRun(); break; } catch (e) {
        if (t >= 3 || !/garbage collected|context was destroyed/i.test(String(e && e.message))) throw e;
        await page.waitForTimeout(800 * (t + 1));
      }
    }
    const o = ia.order;
    if (o.some(x => x < 0)) iaErrs.push(`首頁區塊缺漏：${JSON.stringify(o)}`);
    else for (let i = 1; i < o.length; i++) if (o[i] < o[i - 1]) { iaErrs.push(`首頁順序不對：${JSON.stringify(o)}`); break; }
    if (!ia.liveConfigured && !(ia.offlineLine && !ia.money && !ia.exec)) iaErrs.push(`離線時應只顯示一行（offline=${ia.offlineLine}, money=${ia.money}, exec=${ia.exec}）`);
    if (ia.set0.adv !== 0 || ia.set0.common !== ia.set0.nCommon) iaErrs.push(`設定頁預設應只顯示常用（${JSON.stringify(ia.set0)}）`);
    if (ia.set1.common !== 0 || ia.set1.adv < ia.set0.nAdv - 1) iaErrs.push(`切到進階應只顯示進階（${JSON.stringify(ia.set1)}）`);
    for (const t of ["券商帳戶", "自動投資", "通知", "自選股", "顯示偏好", "破億試算"]) if (!ia.commonTitles.includes(t)) iaErrs.push(`常用缺「${t}」`);
    if (JSON.stringify(ia.stockTabs) !== JSON.stringify(["總覽", "籌碼", "財務", "事件"])) iaErrs.push(`個股頁分頁應為總覽／籌碼／財務／事件：${ia.stockTabs}`);
    if (ia.more.some(m => !m || m.open || m.n < 1)) iaErrs.push(`市場頁「更多」應存在、預設收合且有卡：${JSON.stringify(ia.more)}`);
    // 個股頁「財務」分頁同時顯示營收與財報
    await page.evaluate(() => openStock("2330"));
    await page.waitForTimeout(800);
    const fin = await page.evaluate(() => {
      document.querySelector('#stock-tabs button[data-sub="fin"]').click();
      const a = (id) => document.getElementById(id).classList.contains("active");
      const r = { rev: a("sub-rev"), fin: a("sub-fin"), ov: a("sub-ov") };
      document.querySelector('#stock-tabs button[data-sub="ov"]').click();
      r.ovGroup = a("sub-ov") && a("sub-tech") && a("sub-ai");
      return r;
    });
    if (!(fin.rev && fin.fin && !fin.ov)) iaErrs.push(`「財務」應同時顯示營收＋財報：${JSON.stringify(fin)}`);
    if (!fin.ovGroup) iaErrs.push("「總覽」應包含走勢、K 線、研判三組");
    await page.evaluate(() => { const b = document.querySelector('nav#nav button[data-scr="home"]'); if (b) b.click(); });
    await page.waitForTimeout(300);
  } catch (e) { iaErrs.push(`測試本身出錯：${e.message || e}`); }
  record("93. 資訊架構：首頁順序＋離線一行、設定常用／進階、個股 4 分頁、市場「更多」（先.七十二-B）", iaErrs.length === 0, iaErrs.join("; "));

  // 94.【2026-10-11 先.七十二-C8】390×844 逐頁首屏（捲到最上、底部導覽列以上）：.card 不得超過 3 張、說明文字（.note）不得超過 2 行。
  // 與 scripts/ux_screens.mjs 同一套量法（該腳本另存截圖到 research/ux_shots/，不進 repo）。
  const fsErrs = [];
  let fsInfo = "";
  try {
    const { checkFirstScreens, MAX_CARDS } = await import("./ux_screens.mjs");
    await page.setViewportSize({ width: 390, height: 844 });
    const fsr = await checkFirstScreens(page, { settle: 1200 });
    for (const [k, r] of Object.entries(fsr)) {
      if (r.cards.length > MAX_CARDS) fsErrs.push(`${k} 首屏 ${r.cards.length} 張卡（${r.cards.join("／")}）`);
      for (const n of r.longNotes) fsErrs.push(`${k} 說明超過 2 行：${n}`);
    }
    fsInfo = Object.entries(fsr).map(([k, r]) => `${k} ${r.cards.length}`).join("、");
    await page.setViewportSize({ width: 393, height: 852 });
    await page.evaluate(() => { const b = document.querySelector('nav#nav button[data-scr="home"]'); if (b) b.click(); });
    await page.waitForTimeout(300);
  } catch (e) { fsErrs.push(`測試本身出錯：${e.message || e}`); }
  record("94. 390×844 逐頁首屏 ≤3 張卡、首屏說明 ≤2 行（先.七十二-C8）", fsErrs.length === 0, fsErrs.join("; ") || "首屏卡數：" + fsInfo);

  // 95.【2026-10-11 先.七十三】「跟 0050 比」卡：預設分頁＝全部疊加且排第一；還沒開始的策略分頁變灰、只顯示一行、不得有空白 svg；
  // 疊圖圖例數＝有資料的線數＋1（0050 灰色排第一）；未開始的線列在「即將加入」；按住圖顯示該日各線數值。
  const scfErrs = [];
  let scfInfo = "";
  try {
    await page.evaluate(() => { const b = document.querySelector('nav#nav button[data-scr="home"]'); if (b) b.click(); });
    await page.waitForTimeout(300);
    const r = await page.evaluate(() => {
      const out = {};
      // 冷啟動預設值（卡片第一次畫出時的分頁）
      out.defaultTab = SC_TAB;
      SC_TAB = "all"; renderStrategyCurves();
      const tabs = [...document.querySelectorAll("#sc-tabs .sc-tab")];
      out.firstTab = tabs[0] && tabs[0].dataset.tab;
      out.firstOn = tabs[0] && /var\(--accent\)/.test(tabs[0].getAttribute("style") || "");
      const lines = scLines();
      const started = lines.filter(l => scHasData(l));  // 與 App 同一個定義（先.七十五：剛建倉只有一天也算）
      out.nStarted = started.length;
      out.legend = [...document.querySelectorAll("#sc-body .sc-legend-item")].map(e => e.textContent.trim());
      out.allSvg = !!document.querySelector("#sc-body svg polyline");
      out.soon = (document.querySelector("#sc-body .sc-soon") || {}).textContent || "";
      out.notStartedLabels = lines.filter(l => !scHasData(l)).map(l => l.label);
      // 按住圖
      const svg = document.getElementById("sc-svg");
      if (svg) {
        const rc = svg.getBoundingClientRect();
        svg.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientX: rc.left + rc.width * 0.99, clientY: rc.top + rc.height / 2, pointerType: "touch" }));
        const tip = document.getElementById("sc-tip");
        out.tipShown = !!tip && !tip.hidden; out.tipRows = tip ? tip.querySelectorAll("div").length - 1 : 0;
        svg.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
        out.tipHidden = !!tip && tip.hidden;
      }
      // 每個分頁
      out.tabs = [];
      for (const t of tabs) {
        SC_TAB = t.dataset.tab; renderStrategyCurves();
        const body = document.getElementById("sc-body");
        const chipNow = document.querySelector(`#sc-tabs .sc-tab[data-tab="${t.dataset.tab}"]`);
        out.tabs.push({ t: t.dataset.tab, has: chipNow.dataset.hasData === "1", dim: /opacity:\s*\.45/.test(chipNow.getAttribute("style") || ""),
          // 先.七十六：沒有紙上資料的分頁可以有歷史段圖（.sc-hist），但不得有紙上段的圖；任何圖都不得空白
          svg: [...body.querySelectorAll("svg")].some(s => !s.classList.contains("sc-hist") && !s.closest(".sc-seg-label")), emptySvg: [...body.querySelectorAll("svg")].filter(s => !s.closest(".sc-seg-label")).some(s => !s.querySelector("polyline, circle, rect")),
          notyet: (body.querySelector(".sc-notyet") || {}).textContent || "" });
      }
      SC_TAB = "all"; renderStrategyCurves();
      return out;
    });
    if (r.defaultTab !== "all" && r.defaultTab !== undefined) scfErrs.push(`預設分頁應為全部疊加，實為 ${r.defaultTab}`);
    if (r.firstTab !== "all" || !r.firstOn) scfErrs.push(`第一個分頁應為全部疊加且選中（${r.firstTab}）`);
    if (r.nStarted && r.legend.length !== r.nStarted + 1) scfErrs.push(`圖例 ${r.legend.length} 項 ≠ 有資料的線 ${r.nStarted}＋1`);
    if (r.legend[0] !== "0050") scfErrs.push(`圖例第一個應為 0050，實為「${r.legend[0]}」`);
    for (const lb of r.notStartedLabels) { const short = lb.replace(/\s*(三檔分散|供給緊縮|景氣閘門|加速|穩健)$/, ""); if (!r.soon.includes(short)) scfErrs.push(`「即將加入」缺 ${short}`); }
    if (r.nStarted && !(r.tipShown && r.tipRows === r.nStarted + 1 && r.tipHidden)) scfErrs.push(`按住圖應顯示 ${r.nStarted + 1} 列數值、放開收起（shown=${r.tipShown} rows=${r.tipRows} hidden=${r.tipHidden}）`);
    for (const t of r.tabs) {
      if (t.emptySvg) scfErrs.push(`分頁 ${t.t} 出現空白 svg`);
      if (!t.has && t.t !== "all") {
        if (!t.dim) scfErrs.push(`分頁 ${t.t} 沒資料卻沒變灰`);
        if (t.svg) scfErrs.push(`分頁 ${t.t} 沒資料卻畫了圖`);
        if (!/開始，現在還沒有資料$/.test(t.notyet.trim())) scfErrs.push(`分頁 ${t.t} 應只顯示「X 月 X 日開始，現在還沒有資料」：${t.notyet}`);
      }
    }
    scfInfo = `有資料 ${r.nStarted} 條、圖例 ${r.legend.length} 項（${r.legend.join("／")}）；即將加入：${r.soon.replace(/^即將加入：/, "")}`;
  } catch (e) { scfErrs.push(`測試本身出錯：${e.message || e}`); }
  record("95. 「跟 0050 比」卡：預設疊圖、未開始分頁變灰無空白圖、圖例＝有資料線數＋1、即將加入、按住看數值（先.七十三）", scfErrs.length === 0, scfErrs.join("; ") || scfInfo);

  // 96.【2026-10-11 先.七十六】歷史段：①回測／樣本外／紙上三段不得重疊（回測迄 < 樣本外起；樣本外最後一個月 < 紙上起日；
  // 畫面上樣本外點線最後一點 < 紙上實線第一點）②歷史段年化與最大跌幅＝原結果檔（±0.05pp），樣本外逐月報酬原樣搬運
  // ③有歷史段的分頁畫出三個固定標籤與 1 年／3 年／全部切換（預設 3 年）。
  const hsErrs = [];
  let hsInfo = "";
  try {
    const r = await page.evaluate(async () => {
      const j = async (u) => (await fetch(u, { cache: "no-store" })).json();
      const h = await j("data/strategy_history.json");
      const out = { errs: [], n: 0, cmp: 0 };
      const get = (d, p) => p.reduce((a, k) => (a == null ? a : a[k]), d);
      const srcCache = {};
      const segs = [];
      for (const [id, s] of Object.entries(h.lines || {})) for (const [kind, seg] of Object.entries(s)) segs.push({ id, kind, seg });
      for (const [kind, seg] of Object.entries(h.bench_0050 || {})) segs.push({ id: "0050", kind, seg });
      for (const { id, kind, seg } of segs) {
        out.n++;
        const src = srcCache[seg.source] || (srcCache[seg.source] = await j(seg.source));
        const node = get(src, seg.path);
        if (!node) { out.errs.push(`${id}/${kind} 原檔路徑不存在：${seg.path.join("/")}`); continue; }
        for (const k of ["cagr", "mdd"]) {
          if (seg[k] == null && node[k] == null) continue;
          if (Math.abs((seg[k] - node[k]) * 100) > 0.05) out.errs.push(`${id}/${kind} ${k} ${(seg[k] * 100).toFixed(2)}% ≠ 原檔 ${(node[k] * 100).toFixed(2)}%`);
          else out.cmp++;
        }
        if (kind === "oos" && JSON.stringify(seg.monthly) !== JSON.stringify(node.monthly)) out.errs.push(`${id} 樣本外逐月報酬與原檔不一致`);
        // 先.七十七-5：回測月序列——畫曲線的那幾條，月序列算出的年化必須＝原結果檔 ±0.05pp；對不上必須標 IRREPRODUCIBLE 且不附序列
        if (kind === "backtest" && seg.repro && seg.repro.status !== "NO_SERIES") {
          const rp = seg.repro;
          if (seg.monthly) {
            const rs = Object.keys(seg.monthly).sort().map(k => seg.monthly[k]);
            let v = 1; for (const x of rs) v *= 1 + x;
            const c = Math.pow(v, 12 / rs.length) - 1;
            if (Math.abs((c - node.cagr) * 100) > 0.05) out.errs.push(`${id} 回測月序列年化 ${(c * 100).toFixed(2)}% ≠ 原檔 ${(node.cagr * 100).toFixed(2)}% 卻仍畫曲線`);
            else out.cmp++;
            if (!rp.draw_curve) out.errs.push(`${id} 有附月序列但 draw_curve=false`);
          } else if (rp.draw_curve) out.errs.push(`${id} draw_curve=true 卻沒附月序列`);
          // 先.八十-7：只差最大跌幅（月資料看不到月中跌幅）標 MONTHLY_APPROX（前台「月頻近似」）；年化也不一致才標 IRREPRODUCIBLE
          const want = rp.cagr_ok && rp.mdd_ok ? "OK" : (rp.cagr_ok ? "MONTHLY_APPROX" : "IRREPRODUCIBLE");
          if (rp.status !== want) out.errs.push(`${id} 可重現性應標 ${want}，實為 ${rp.status}`);
          if (rp.status === "MONTHLY_APPROX" && rp.label !== "月頻近似") out.errs.push(`${id} 月頻近似標籤文字不對：${rp.label}`);
          out.repro = (out.repro || []).concat(`${id}:${rp.status}${rp.draw_curve ? "(曲線)" : ""}`);
        }
        // ① 期間不重疊
        const end = (seg.period || [])[1];
        if (kind === "backtest" && !(end < "2025-01-01")) out.errs.push(`${id} 回測段迄日 ${end} 與樣本外重疊`);
        if (kind === "oos") {
          const lastM = Object.keys(seg.monthly || {}).sort().slice(-1)[0];
          if (!(lastM + "-31" < h.meta.paper_start)) out.errs.push(`${id} 樣本外最後一月 ${lastM} 與紙上段（${h.meta.paper_start} 起）重疊`);
        }
      }
      // 畫面：每個有歷史段的分頁
      out.ui = [];
      for (const id of Object.keys(h.lines || {})) {
        const tab = id === "live_bb90" ? "live" : id;
        SC_TAB = tab; SC_RANGE = "3y"; renderStrategyCurves();
        const blk = document.querySelector("#sc-body .sc-hist-block");
        const svg = blk && blk.querySelector("svg.sc-hist");
        const oos = svg ? [...svg.querySelectorAll('[data-seg="oos"]')] : [], pap = svg ? [...svg.querySelectorAll('[data-seg="paper"]')] : [];
        const xs = (el) => el.tagName === "circle" ? [+el.getAttribute("cx")] : el.getAttribute("points").trim().split(/\s+/).map(p => +p.split(",")[0]);
        const oosMax = oos.length ? Math.max(...oos.flatMap(xs)) : null, papMin = pap.length ? Math.min(...pap.flatMap(xs)) : null;
        SC_RANGE = "all"; renderStrategyCurves();
        const svgAll = document.querySelector("#sc-body .sc-hist-block svg.sc-hist");
        const bt = svgAll ? [...svgAll.querySelectorAll('[data-seg="backtest"]')].filter(e => e.tagName === "polyline") : [];
        const oosA = svgAll ? [...svgAll.querySelectorAll('[data-seg="oos"]')] : [];
        const btMax = bt.length ? Math.max(...bt.flatMap(xs)) : null, oosMinA = oosA.length ? Math.min(...oosA.flatMap(xs)) : null;
        const drawCurve = !!(((h.lines[id] || {}).backtest || {}).repro || {}).draw_curve;
        SC_RANGE = "3y"; renderStrategyCurves();
        out.ui.push({ id, blk: !!blk, labels: blk ? [...blk.querySelectorAll(".sc-seg-label")].map(e => e.textContent.trim()) : [],
          ranges: blk ? [...blk.querySelectorAll(".sc-range")].map(e => e.dataset.range) : [], rangeOn: SC_RANGE,
          overlap: oosMax != null && papMin != null && !(oosMax < papMin), hasOos: oos.length > 0,
          btOverlap: btMax != null && oosMinA != null && btMax > oosMinA + 0.5, btDrawn: bt.length > 0, drawCurve });
      }
      SC_TAB = "all"; SC_RANGE = "3y"; renderStrategyCurves();
      return out;
    });
    hsErrs.push(...r.errs);
    for (const u of r.ui) {
      if (!u.blk) { hsErrs.push(`${u.id} 分頁沒有歷史段`); continue; }
      if (JSON.stringify(u.labels) !== JSON.stringify(["回測＝用來挑策略的資料", "樣本外＝只考過一次", "紙上＝今天起才算數"])) hsErrs.push(`${u.id} 三個固定標籤不符：${u.labels}`);
      if (JSON.stringify(u.ranges) !== JSON.stringify(["1y", "3y", "all"])) hsErrs.push(`${u.id} 範圍切換應為 1 年／3 年／全部`);
      if (u.overlap) hsErrs.push(`${u.id} 圖上樣本外點線與紙上實線重疊`);
      if (u.btOverlap) hsErrs.push(`${u.id} 圖上回測虛線與樣本外點線重疊`);
      if (u.btDrawn !== u.drawCurve) hsErrs.push(`${u.id} 回測曲線畫了／沒畫與 draw_curve 不符（畫=${u.btDrawn}）`);
    }
    hsInfo = `${r.n} 段、${r.cmp} 個數字與原檔一致；${r.ui.length} 個分頁有歷史段；回測可重現性 ${(r.repro || []).join("、")}`;
  } catch (e) { hsErrs.push(`測試本身出錯：${e.message || e}`); }
  record("96. 歷史段：回測／樣本外／紙上不重疊、年化與最大跌幅＝原結果檔 ±0.05pp、回測月序列可重現性標記、三標籤與範圍切換（先.七十六／七十七-5）", hsErrs.length === 0, hsErrs.join("; ") || hsInfo);

  // 97.【2026-10-11 先.七十八-2】交易頁「明天會買」：讀 status.t1_plan_preview（晚間唯讀預檢的純計算預覽）。
  // 每筆列出；超過單筆上限要標警告；可用餘額只顯示夠／不足（不得出現餘額數字）；沒有預覽就整塊隱藏。
  const ppErrs = [];
  try {
    const r = await page.evaluate(async () => {
      await window.go("trade");
      await new Promise(res => setTimeout(res, 400));
      if (typeof renderPlanPreview !== "function") return { err: "renderPlanPreview 未載入" };
      const el = document.getElementById("bot-plan-preview");
      renderPlanPreview({ label: "T1", orders: [
        { symbol: "0050", lot: "Common", qty: 1000, limit_price: 115.5, amount: 115500, cap_ok: true },
        { symbol: "00646", lot: "IntradayOdd", qty: 300, limit_price: 78.7, amount: 23610, cap_ok: false }],
        total: 139110, need_with_buffer: 139527.33, available_ok: false });
      const o = { shown: !el.hidden, rows: el.querySelectorAll(".plan-row").length, text: el.innerText };
      renderPlanPreview(null);
      o.hiddenAfter = el.hidden;
      return o;
    });
    if (r.err) ppErrs.push(r.err);
    else {
      if (!r.shown || r.rows !== 2) ppErrs.push(`應顯示 2 筆（shown=${r.shown} rows=${r.rows}）`);
      if (!/明天會買/.test(r.text)) ppErrs.push("缺「明天會買」標題");
      if (!/超過單筆上限/.test(r.text)) ppErrs.push("超過上限的那筆沒有警告");
      if (!/可用餘額：不足/.test(r.text)) ppErrs.push("可用餘額應只顯示夠／不足");
      if (!/預覽，非委託/.test(r.text)) ppErrs.push("缺「預覽，非委託」");
      if (!r.hiddenAfter) ppErrs.push("沒有預覽時應隱藏");
    }
  } catch (e) { ppErrs.push(`測試本身出錯：${e.message || e}`); }
  record("97. 交易頁「明天會買」預覽：逐筆、超上限警告、可用只顯示夠／不足、無預覽隱藏（先.七十八-2）", ppErrs.length === 0, ppErrs.join("; "));

  // 98.【2026-10-11 常備.開發-27】設定頁「雲端夜間冒煙」卡：route 餵兩份 data/smoke_cloud.json——
  // (a) 剛跑完、1 項失敗 → 要顯示「1 項失敗」與失敗項名稱；(b) 全過但 48 小時前 → 要標「沒更新」，不能顯示成沒問題。
  const scfcErrs = [];
  try {
    let fixture = null;
    await page.route("**/data/smoke_cloud.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fixture) }));
    const nowIso = new Date().toISOString();
    fixture = { generated_at: nowIso, all_passed: false, crashed: false, total: 98, passed: 97, failed: 1,
      failures: [{ name: "假失敗項-雲端冒煙測試用", detail: "fixture" }] };
    const a = await page.evaluate(async () => {
      if (typeof loadSmokeCloud !== "function") return { err: "loadSmokeCloud 未載入" };
      await loadSmokeCloud();
      return { sum: document.getElementById("smoke-cloud-summary").innerText, list: document.getElementById("smoke-cloud-list").innerText };
    });
    if (a.err) scfcErrs.push(a.err);
    else {
      if (!/1 項失敗/.test(a.sum)) scfcErrs.push(`(a) 摘要應含「1 項失敗」：${a.sum}`);
      if (/沒更新/.test(a.sum)) scfcErrs.push("(a) 剛跑完不應標沒更新");
      if (!/假失敗項-雲端冒煙測試用/.test(a.list)) scfcErrs.push("(a) 未列出失敗項名稱");
    }
    fixture = { generated_at: new Date(Date.now() - 48 * 3600 * 1000).toISOString(), all_passed: true, crashed: false, total: 98, passed: 98, failed: 0, failures: [] };
    const b = await page.evaluate(async () => { await loadSmokeCloud(); return document.getElementById("smoke-cloud-summary").innerText; });
    if (!/全部通過/.test(b)) scfcErrs.push(`(b) 應顯示全部通過：${b}`);
    if (!/沒更新/.test(b)) scfcErrs.push(`(b) 48 小時前的結果應標沒更新：${b}`);
    await page.unroute("**/data/smoke_cloud.json**");
  } catch (e) { scfcErrs.push(`測試本身出錯：${e.message || e}`); }
  record("98. 設定頁「雲端夜間冒煙」卡：失敗項列出、逾 36 小時標沒更新（常備.開發-27）", scfcErrs.length === 0, scfcErrs.join("; "));

  // 100.【2026-10-11 常備.開發-28】設定頁「資料檔 schema 守門」卡：route 餵 data/schema_guard/*.json——
  // (a) market 攔下 1 檔、其餘 404 → 要顯示「1 個資料檔被攔下」與檔名；(b) 全部 404 → 顯示尚未產生，不得拋錯。
  const sgErrs = [];
  try {
    let fixtures = {};
    await page.route("**/data/schema_guard/**", (route) => {
      const name = new URL(route.request().url()).pathname.split("/").pop().replace(/\.json$/, "");
      const body = fixtures[name];
      return body ? route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) })
        : route.fulfill({ status: 404, body: "not found" });
    });
    fixtures = { market: { generated_at: new Date().toISOString(), label: "market", checked: ["data/fx.json"], guard_error: null,
      rejected: [{ file: "data/fx.json", errors: ["缺必要欄位 usd_twd"], action: "已還原成上一版（HEAD），本次不發布" }] } };
    const a = await page.evaluate(async () => {
      if (typeof loadSchemaGuard !== "function") return { err: "loadSchemaGuard 未載入" };
      await loadSchemaGuard();
      return { sum: document.getElementById("schema-guard-summary").innerText, list: document.getElementById("schema-guard-list").innerText };
    });
    if (a.err) sgErrs.push(a.err);
    else {
      if (!/1 個資料檔被攔下/.test(a.sum)) sgErrs.push(`(a) 摘要應含「1 個資料檔被攔下」：${a.sum}`);
      if (!/data\/fx\.json/.test(a.list) || !/usd_twd/.test(a.list)) sgErrs.push(`(a) 未列出被攔下的檔與原因：${a.list}`);
      if (/讀不到/.test(a.sum)) sgErrs.push("(a) 404 不應算讀不到");
    }
    fixtures = {};
    const b = await page.evaluate(async () => { await loadSchemaGuard(); return document.getElementById("schema-guard-summary").innerText; });
    if (!/尚未產生/.test(b)) sgErrs.push(`(b) 全部 404 應顯示尚未產生：${b}`);
    await page.unroute("**/data/schema_guard/**");
  } catch (e) { sgErrs.push(`測試本身出錯：${e.message || e}`); }
  record("100. 設定頁「資料檔 schema 守門」卡：被攔下的檔與原因列出、尚未產生不拋錯（常備.開發-28）", sgErrs.length === 0, sgErrs.join("; "));

  // 101.【2026-10-12 先.八十-1】漲跌正負號：MI_INDEX「漲跌百分比」本身帶號，舊程式再乘一次「漲跌」欄的 -1，跌變漲。
  // 加權（與櫃買）change_pct 的正負號必須等於走勢線方向（收盤＝走勢線最後一點時比最後兩點，否則比收盤與最後一點）；類股不得全為非負。
  const sgnErrs = [];
  try {
    const mt = JSON.parse((await import("node:fs")).readFileSync("data/market_tw.json", "utf8"));
    const sg = v => (v > 0 ? 1 : v < 0 ? -1 : 0);
    const dirOf = (close, sp) => {
      if (!Array.isArray(sp) || sp.length < 2 || close == null) return null;
      const last = sp[sp.length - 1];
      return Math.abs(close - last) < 1 ? sg(last - sp[sp.length - 2]) : sg(close - last);
    };
    const tx = mt.taiex || {};
    const d1 = dirOf(tx.close, tx.sparkline);
    if (tx.change_pct == null || d1 == null) sgnErrs.push("加權缺 change_pct 或走勢線");
    else if (sg(tx.change_pct) !== d1) sgnErrs.push(`加權 change_pct ${tx.change_pct} 與走勢線方向 ${d1} 不一致`);
    const tp = mt.tpex;
    if (tp && tp.change_pct != null && Array.isArray(tp.sparkline)) {
      const d2 = dirOf(tp.close, tp.sparkline);
      if (d2 != null && sg(tp.change_pct) !== d2) sgnErrs.push(`櫃買 change_pct ${tp.change_pct} 與走勢線方向 ${d2} 不一致`);
    }
    const secs = (mt.sectors || []).filter(x => x.change_pct != null);
    if (secs.length < 10) sgnErrs.push(`類股筆數過少：${secs.length}`);
    else if (secs.every(x => x.change_pct >= 0)) sgnErrs.push(`類股 ${secs.length} 筆全部非負（正負號疑似又被吃掉）`);
  } catch (e) { sgnErrs.push(`測試本身出錯：${e.message || e}`); }
  record("101. 大盤／類股漲跌正負號：加權與櫃買 change_pct 正負＝走勢線方向、類股不得全為非負（先.八十-1）", sgnErrs.length === 0, sgnErrs.join("; "));

  // 102.【2026-10-12 先.八十-2】電腦離線統一狀態：本機伺服器連不上（Failed to fetch）時，交易頁自動投資卡、首頁兩張卡收成一行
  // 「電腦離線（最後連線 MM/DD HH:MM）」；不得計入 GLOBAL_ERRORS、畫面不得出現英文原始錯誤（Failed to fetch／Load failed）。
  const offErrs = [];
  try {
    const r = await page.evaluate(async () => {
      if (typeof liveOfflineText !== "function" || typeof _isOfflineErr !== "function") return { err: "liveOfflineText／_isOfflineErr 未載入" };
      const saved = { url: LIVE.url, conf: LIVE.configured, fetch: window.fetch, ls: localStorage.getItem("alpha_live_last_ok") };
      const n0 = GLOBAL_ERRORS.length;
      try {
        localStorage.setItem("alpha_live_last_ok", "2026-10-11T06:05:00Z");
        LIVE.url = "https://smoke.invalid"; LIVE.configured = true;
        window.fetch = (u, o) => (String(u).startsWith("https://smoke.invalid") ? Promise.reject(new TypeError("Failed to fetch")) : saved.fetch(u, o));
        await window.go("trade");
        await new Promise(res => setTimeout(res, 300));
        if (typeof loadTradeBots === "function") await loadTradeBots();
        const tradeNote = (document.getElementById("bot-bb90-note") || {}).textContent || "";
        const recHidden = !!(document.getElementById("bot-recent-orders") || {}).hidden;
        await loadHomeExecCard();
        const line = document.getElementById("home-offline-line");
        const homeLine = line && !line.hidden ? line.textContent : "";
        const body = document.body.innerText;
        return { text: liveOfflineText(), tradeNote, recHidden, homeLine, added: GLOBAL_ERRORS.length - n0,
                 english: /Failed to fetch|Load failed/.test(body), never: (localStorage.removeItem("alpha_live_last_ok"), liveOfflineText()) };
      } finally {
        window.fetch = saved.fetch; LIVE.url = saved.url; LIVE.configured = saved.conf;
        if (saved.ls) localStorage.setItem("alpha_live_last_ok", saved.ls); else localStorage.removeItem("alpha_live_last_ok");
        try { await loadHomeExecCard(); } catch (e) { console.warn("[smoke 102 restore]", e); }
      }
    });
    if (r.err) offErrs.push(r.err);
    else {
      if (r.text !== "電腦離線（最後連線 10/11 14:05）") offErrs.push(`離線文字不對：${r.text}`);
      if (r.tradeNote !== r.text) offErrs.push(`交易頁自動投資卡應只顯示一行離線：${r.tradeNote}`);
      if (!r.recHidden) offErrs.push("離線時帳本區應收起");
      if (!/^電腦離線（最後連線 10\/11 14:05）/.test(r.homeLine)) offErrs.push(`首頁應收成一行離線：${r.homeLine}`);
      if (r.added !== 0) offErrs.push(`離線被計入程式錯誤 ${r.added} 筆`);
      if (r.english) offErrs.push("畫面出現英文原始錯誤");
      if (r.never !== "電腦離線（還沒連上過）") offErrs.push(`沒連上過時文字不對：${r.never}`);
    }
  } catch (e) { offErrs.push(`測試本身出錯：${e.message || e}`); }
  record("102. 電腦離線統一一行：交易頁／首頁收成「電腦離線（最後連線 MM/DD HH:MM）」、不計程式錯誤、不顯示英文（先.八十-2）", offErrs.length === 0, offErrs.join("; "));

  // 103.【2026-10-12 先.八十-3】試驗帳本索引：loadTrials 真的有執行（設定頁顯示「共 N 筆」）；trials_index.json 的列認定與
  // selection_bias_ledger 總 N 相同（第一欄編號＋第二欄日期，FDR 對照表的排名列不得混入）、count＝列數、跳脫的 \| 不截斷欄位。
  const trErrs = [];
  try {
    const fsx = await import("node:fs");
    const ti = JSON.parse(fsx.readFileSync("data/trials_index.json", "utf8"));
    const led = fsx.readFileSync("research/TRIALS_LEDGER.md", "utf8").split(/\r?\n/);
    let n = 0;
    for (const l of led) {
      if (!l.startsWith("|")) continue;
      const c = l.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map(x => x.trim());
      if (c.length >= 6 && /^\d+$/.test(c[0]) && /^\d{4}-\d{2}-\d{2}$/.test(c[1])) n++;
    }
    // 先.八十-13：count＝總 N（框架驗證列列出但不計入），必須等於 TRIALS_LEDGER.md 開頭「目前累積總數」
    const counted = ti.rows.filter(r => r.counted !== false).length;
    if (ti.count !== counted) trErrs.push(`count ${ti.count} ≠ 計入列數 ${counted}`);
    const head = (led.join("\n").match(/目前累積總數（可統計檢定的試驗）：(\d+)/) || [])[1];
    if (Number(head) !== ti.count) trErrs.push(`帳本開頭總數 ${head} ≠ 索引 count ${ti.count}（試驗總數不一致）`);
    if (ti.rows.length !== n) trErrs.push(`索引 ${ti.rows.length} 列 ≠ 帳本試驗列 ${n}`);
    if (ti.rows.some(r => !/^\d{4}-\d{2}-\d{2}$/.test(r.date))) trErrs.push("有非日期列混入（FDR 對照表排名列）");
    const keys = new Set(ti.rows.map(r => r.id + "|" + r.date + "|" + r.name));
    if (keys.size !== ti.rows.length) trErrs.push("有完全重複的列");
    const dupIds = Object.entries(ti.rows.reduce((m, r) => (m[r.id] = (m[r.id] || 0) + 1, m), {})).filter(([, v]) => v > 1).map(([k]) => +k);
    if (dupIds.some(id => !ti.rows.filter(r => r.id === id).every(r => r.dup_id))) trErrs.push("帳本共用編號的列沒標 dup_id");
    const meta = await page.evaluate(async () => {
      await window.go("settings");
      for (let i = 0; i < 30; i++) { const t = (document.getElementById("trials-meta") || {}).textContent || ""; if (/^共 \d+ 筆/.test(t)) return t; await new Promise(r => setTimeout(r, 200)); }
      return (document.getElementById("trials-meta") || {}).textContent || "";
    });
    if (!new RegExp("^共 " + ti.count + " 筆").test(meta)) trErrs.push(`設定頁 loadTrials 沒執行或筆數不符：${meta}`);
  } catch (e) { trErrs.push(`測試本身出錯：${e.message || e}`); }
  record("103. 試驗帳本索引：loadTrials 有執行、列數＝帳本試驗列（＝總 N）、無 FDR 排名列混入、共用編號有標示（先.八十-3）", trErrs.length === 0, trErrs.join("; "));

  // 104.【2026-10-12 先.八十-4】選股頁產業篩選籤：切美股再切回台股、搜尋後清空，籤列仍是 flex 單列不重疊；顯示／隱藏只切 class。
  const chErrs = [];
  try {
    const r = await page.evaluate(async () => {
      await window.go("picks");
      for (let i = 0; i < 40 && !document.querySelector("#picks-chips > *"); i++) await new Promise(res => setTimeout(res, 200));
      const el = document.getElementById("picks-chips");
      if (!el) return { err: "找不到 #picks-chips" };
      const st = () => getComputedStyle(el).display;
      const oneRow = () => { const k = [...el.children].filter(c => c.offsetParent); return k.length < 2 || new Set(k.map(c => c.offsetTop)).size === 1; };
      const out = { n: el.children.length, inline: el.style.display };
      MKT_STATE.picks = "US"; onPicksToggleChange(); out.us = st();
      MKT_STATE.picks = "TW"; onPicksToggleChange(); out.tw = st(); out.twRow = oneRow();
      if (typeof onPicksSearchInput === "function") { onPicksSearchInput("2330"); out.search = st(); onPicksSearchInput(""); out.after = st(); out.afterRow = oneRow(); }
      return out;
    });
    if (r.err) chErrs.push(r.err);
    else {
      if (r.n < 2) chErrs.push(`篩選籤沒產生（${r.n}）`);
      if (r.inline) chErrs.push(`仍有 inline style.display＝${r.inline}`);
      if (r.us !== "none") chErrs.push(`美股時籤列應隱藏（${r.us}）`);
      if (r.tw !== "flex" || !r.twRow) chErrs.push(`切回台股應為 flex 單列（${r.tw}，單列=${r.twRow}）`);
      if (r.search !== "none") chErrs.push(`搜尋中籤列應隱藏（${r.search}）`);
      if (r.after !== "flex" || !r.afterRow) chErrs.push(`清空搜尋後應為 flex 單列（${r.after}，單列=${r.afterRow}）`);
    }
  } catch (e) { chErrs.push(`測試本身出錯：${e.message || e}`); }
  record("104. 選股頁篩選籤：切市場／搜尋後仍為 flex 單列不重疊、只切 class 不設 style.display（先.八十-4）", chErrs.length === 0, chErrs.join("; "));

  // 105.【2026-10-12 先.八十-5】40 字自動收合只收說明類（data-ui-explain），卡片主內容（程式填的狀態／內容）不收；
  // 時鐘每秒改字不得觸發收合重掃（觀察器只處理落在說明類元素裡的變動）。
  const cpErrs = [];
  try {
    const r = await page.evaluate(async () => {
      if (typeof uiCompactNote !== "function") return { err: "uiCompactNote 未載入" };
      const host = document.querySelector("#scr-home") || document.getElementById("app");
      const content = document.createElement("div"); content.className = "note"; content.id = "smoke105-content";
      const explain = document.createElement("div"); explain.className = "note"; explain.setAttribute("data-ui-explain", "");
      host.appendChild(content); host.appendChild(explain);
      const long = "這是一段超過四十個字的測試文字，用來確認自動收合只會收說明類的附註，而不會把卡片主內容也收起來，造成使用者看不到重點。";
      content.textContent = long; explain.textContent = long;
      await new Promise(res => setTimeout(res, 400));
      const out = { contentCollapsed: !!content.querySelector("details[data-ui-detail]"), explainCollapsed: !!explain.querySelector("details[data-ui-detail]"),
                    summary: (explain.querySelector("summary") || {}).textContent };
      content.remove(); explain.remove();
      await new Promise(res => setTimeout(res, 300));
      const s0 = window.__uiCompactScans;
      await new Promise(res => setTimeout(res, 3200));  // 期間時鐘至少改字 3 次
      out.scansDuringClock = window.__uiCompactScans - s0;
      out.marked = document.querySelectorAll("#app .note[data-ui-explain]").length;
      out.idMarked = [...document.querySelectorAll("#app .note[id][data-ui-explain]")].map(n => n.id);
      return out;
    });
    if (r.err) cpErrs.push(r.err);
    else {
      if (r.contentCollapsed) cpErrs.push("卡片主內容（有 id、未標說明）被收合了");
      if (!r.explainCollapsed || r.summary !== "ⓘ 說明") cpErrs.push(`說明類超過 40 字應收成「ⓘ 說明」（${r.explainCollapsed}，${r.summary}）`);
      if (r.scansDuringClock !== 0) cpErrs.push(`時鐘改字期間觸發收合重掃 ${r.scansDuringClock} 次`);
      if (r.marked < 5) cpErrs.push(`說明類標記過少（${r.marked}）`);
    }
  } catch (e) { cpErrs.push(`測試本身出錯：${e.message || e}`); }
  record("105. 自動收合只收說明類、不收卡片主內容；時鐘每秒改字不觸發重掃（先.八十-5）", cpErrs.length === 0, cpErrs.join("; "));

  // 106.【2026-10-12 先.八十-6】交易頁策略監控台改讀 strategy_curves.json（名稱＝檔內 label，照 UI_GLOSSARY），
  // 整個 App 不得再請求 strategy_performance.json；監控台卡片數＝曲線檔線數、每張名稱與檔內 label 相同；有資料的線同時列 0050。
  const monErrs = [];
  try {
    const perfReqs = [];
    const onReq = (req) => { if (/strategy_performance\.json/.test(req.url())) perfReqs.push(req.url()); };
    page.on("request", onReq);
    const curves = JSON.parse((await import("node:fs")).readFileSync("data/strategy_curves.json", "utf8"));
    const r = await page.evaluate(async () => {
      await window.go("trade");
      const b = [...document.querySelectorAll("#trade-tabs button")].find(x => x.dataset.sub === "monitor"); if (b) b.click();
      for (let i = 0; i < 30 && !document.querySelector("#strategy-monitor-list [data-sid]"); i++) await new Promise(res => setTimeout(res, 200));
      if (typeof loadMyHoldingsEvents === "function") { try { await loadMyHoldingsEvents(); } catch (e) { console.warn("[smoke106]", e); } }
      const cards = [...document.querySelectorAll("#strategy-monitor-list [data-sid]")];
      return cards.map(c => ({ id: c.dataset.sid, name: (c.querySelector("b") || {}).textContent, text: c.innerText }));
    });
    page.off("request", onReq);
    if (r.length !== curves.lines.length) monErrs.push(`監控台 ${r.length} 張卡 ≠ 曲線檔 ${curves.lines.length} 條線`);
    for (const l of curves.lines) {
      const c = r.find(x => x.id === l.id);
      if (!c) { monErrs.push(`缺 ${l.id}`); continue; }
      if (c.name !== l.label) monErrs.push(`${l.id} 名稱「${c.name}」≠ 檔內「${l.label}」`);
      if (l.started && (l.nav || []).length && !/0050/.test(c.text)) monErrs.push(`${l.id} 有資料但沒列 0050 對照`);
    }
    if (perfReqs.length) monErrs.push(`仍在請求 strategy_performance.json（${perfReqs.length} 次）`);
  } catch (e) { monErrs.push(`測試本身出錯：${e.message || e}`); }
  record("106. 策略監控台讀 strategy_curves.json、名稱照定案、列 0050 對照，App 不再請求 strategy_performance.json（先.八十-6）", monErrs.length === 0, monErrs.join("; "));

  // 107.【2026-10-12 先.八十-8】跟 0050 比：①樣本外格同時寫「策略 +X%／0050 +Y%」②疊圖各線從自己的起始日接在當天 0050 的值
  // （不是一律從 100 起）③台指期膠囊有近月日線時畫走勢線（餵 2 點以上的 tx_futures.sparkline）。
  const sc8Errs = [];
  try {
    const r = await page.evaluate(async () => {
      const out = {};
      await window.go("home");
      // ① 樣本外格
      SC_TAB = "paper_3"; renderStrategyCurves();
      const oos = document.querySelector('#sc-body .sc-hist-metrics [data-seg="oos"] .sc-oos-pair');
      out.oos = oos ? oos.textContent : null;
      // ② 疊圖對齊：假資料兩條線，A 從 d1 起、B 從 d3 起；灰線（A 的同期 0050）在 d3 為 110
      const fake = { meta: {}, lines: [
        { id: "fa", label: "A", group: "paper", status: "模擬中", started: true, dates: ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"], nav: [100, 102, 104, 106], bench: [100, 105, 110, 111], metrics: {} },
        { id: "fb", label: "B", group: "paper", status: "模擬中", started: true, dates: ["2026-01-03", "2026-01-04"], nav: [100, 103], bench: [100, 101], metrics: {} }] };
      const saveD = SC_DATA, saveL = SC_LIVE, saveT = SC_TAB;
      try {
        SC_DATA = fake; SC_LIVE = null; SC_TAB = "all"; renderStrategyCurves();
        out.align = Object.assign({}, SC_ALIGN);
        const pb = document.querySelector('#sc-body polyline[data-line="fb"]'), pg = document.querySelector('#sc-body polyline[data-line="bench_0050"]');
        const pts = el => el ? el.getAttribute("points").trim().split(/\s+/).map(p => p.split(",").map(Number)) : [];
        const b = pts(pb), g = pts(pg);
        out.bStartY = b[0] && b[0][1]; out.gAtD3Y = g[2] && g[2][1];
        out.note = (document.querySelector("#sc-body .note") || {}).textContent || "";
      } finally { SC_DATA = saveD; SC_LIVE = saveL; SC_TAB = saveT; renderStrategyCurves(); }
      // ③ 台指期膠囊走勢線
      const cap = idxCapsuleHtml("台指期近月", "期交所", { close: 49349, change_pct: -1.24, liveKey: "", sparkline: [49100, 49968, 49349] });
      const div = document.createElement("div"); div.innerHTML = cap;
      out.capSvg = !!div.querySelector("svg polyline");
      return out;
    });
    if (!r.oos || !/^策略 [+-]\d+\.\d%／0050 [+-]\d+\.\d%$/.test(r.oos.trim())) sc8Errs.push(`樣本外格應為「策略 +X%／0050 +Y%」：${r.oos}`);
    if (Math.abs((r.align.fb || 0) - 1.1) > 1e-9) sc8Errs.push(`B 線對齊係數應為 1.10（起始日 0050＝110），實為 ${r.align.fb}`);
    if (Math.abs((r.align.fa || 0) - 1) > 1e-9) sc8Errs.push(`A 線（最早起始）對齊係數應為 1，實為 ${r.align.fa}`);
    if (r.bStartY == null || r.gAtD3Y == null || Math.abs(r.bStartY - r.gAtD3Y) > 0.6) sc8Errs.push(`B 線起點應與當天灰線同高（${r.bStartY} vs ${r.gAtD3Y}）`);
    if (!r.capSvg) sc8Errs.push("台指期膠囊有 3 點日線卻沒畫走勢線");
  } catch (e) { sc8Errs.push(`測試本身出錯：${e.message || e}`); }
  record("107. 跟 0050 比：樣本外格雙數字、疊圖各線起點接在當天 0050、台指期膠囊有日線就畫走勢線（先.八十-8）", sc8Errs.length === 0, sc8Errs.join("; "));

  // 108.【2026-10-12 先.八十-9】price_history 全市場缺日自測（scripts/selftest_price_history_gaps.py 同一套判定）＋
  // picks_ledger 資料不完整批次有標註、曲線檔的「不完整批次數」與帳本一致。
  const gapErrs = [];
  try {
    const { execFileSync } = await import("node:child_process");
    const fsx = await import("node:fs");
    const py = fsx.existsSync("C:/Program Files/Python313/python.exe") ? "C:/Program Files/Python313/python.exe" : "python";
    let out = "";
    try { out = execFileSync(py, ["scripts/selftest_price_history_gaps.py"], { encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" }, timeout: 240000 }); }
    catch (e) { out = String(e.stdout || "") + String(e.stderr || ""); gapErrs.push("全市場缺日自測未通過：" + out.split(/\r?\n/).filter(l => /^FAIL/.test(l)).join(" | ").slice(0, 300)); }
    const led = JSON.parse(fsx.readFileSync("data/picks_ledger.json", "utf8"));
    const withStatus = led.snapshots.filter(s => s.data_status);
    if (withStatus.length < 50) gapErrs.push(`有 data_status 的批次過少（${withStatus.length}）`);
    const inc = withStatus.filter(s => s.data_status.complete === false);
    if (led.meta.incomplete_batches !== inc.length) gapErrs.push(`meta.incomplete_batches ${led.meta.incomplete_batches} ≠ 實際 ${inc.length}`);
    for (const s of inc) if (!(s.data_status.missing_entry || s.data_status.missing_exit || (s.data_status.market_gap_days || []).length)) gapErrs.push(`${s.snapshot_date} ${s.board} 標不完整卻沒有原因`);
    const curves = JSON.parse(fsx.readFileSync("data/strategy_curves.json", "utf8"));
    for (const l of curves.lines.filter(x => x.group === "board" && x.started)) {
      const b = l.id.replace("board_", "");
      const n = inc.filter(s => s.board === b).length;
      if (l.incomplete_batches !== n) gapErrs.push(`${l.id} 曲線檔不完整批次 ${l.incomplete_batches} ≠ 帳本 ${n}`);
      if (n && !/批有個股缺進出場收盤/.test(l.note)) gapErrs.push(`${l.id} 有不完整批次但 note 沒註明`);
    }
  } catch (e) { gapErrs.push(`測試本身出錯：${e.message || e}`); }
  record("108. 價格歷史全市場缺日自測通過；選股紀錄資料不完整批次有標註、曲線檔批次數與帳本一致（先.八十-9）", gapErrs.length === 0, gapErrs.join("; "));

  // 109.【2026-10-12 先.八十-10】日期顯示最後交易日（跟 0050 比卡、盤前日報頁尾）；法人張數千分位；FinMind Token 假欄位已移除；
  // 規則摘要卡不再標「AI」；稽核某項檢查 0 筆時顯示「未檢查」，整份 0 筆時總結也是「未檢查」（不是通過）。
  const i10Errs = [];
  try {
    const fsx = await import("node:fs");
    const curves = JSON.parse(fsx.readFileSync("data/strategy_curves.json", "utf8"));
    const brief = JSON.parse(fsx.readFileSync("data/daily_brief.json", "utf8"));
    const fakeAudit = { generated_at: new Date().toISOString(), universe: 1900, gate_pass: true, violation_rate: 0, completeness_gap_rate: 0,
      by_check: { a_price: { checked: 1900, violations: 0 }, b_empty: { checked: 0, violations: 0 } }, top_20: [] };
    const zeroAudit = { generated_at: new Date().toISOString(), universe: 0, gate_pass: true, by_check: { a_price: { checked: 0, violations: 0 } } };
    let auditBody = fakeAudit;
    await page.route("**/data/audit_report.json**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(auditBody) }));
    const r = await page.evaluate(async () => {
      const o = {};
      await window.go("home");
      SC_TAB = "all"; renderStrategyCurves();
      o.scFoot = [...document.querySelectorAll("#sc-body .note")].map(n => n.textContent).find(t => /資料到|更新於/.test(t)) || "";
      o.aiTags = [...document.querySelectorAll(".ai-tag")].map(e => e.textContent.trim());
      o.tokenField = !!document.getElementById("set-finmind-token");
      await window.go("picks");
      for (let i = 0; i < 20 && typeof fmtN !== "function"; i++) await new Promise(r => setTimeout(r, 200));
      o.fmt = typeof fmtN === "function" ? fmtN(12345, 0, " 張") : null;
      await window.go("settings");
      await loadDataAudit(true);
      o.rowEmpty = (document.querySelector('[data-audit-check="b_empty"]') || {}).textContent || "";
      o.rowOk = (document.querySelector('[data-audit-check="a_price"]') || {}).textContent || "";
      return o;
    });
    auditBody = zeroAudit;
    const z = await page.evaluate(async () => { await loadDataAudit(true); return document.getElementById("audit-summary").textContent; });
    await page.unroute("**/data/audit_report.json**");
    await page.evaluate(async () => { try { await loadDataAudit(true); } catch (e) { console.warn("[smoke109 restore]", e); } });
    const pa = String(curves.meta.price_asof || "").slice(5).replace("-", "/");
    if (!r.scFoot.includes(`資料到 ${pa}（最後交易日）`)) i10Errs.push(`跟 0050 比卡應寫「資料到 ${pa}（最後交易日）」：${r.scFoot}`);
    if (/更新於/.test(r.scFoot)) i10Errs.push("跟 0050 比卡仍顯示產生時間");
    if (!brief.data_asof) i10Errs.push("daily_brief.json 缺 data_asof");
    if (r.aiTags.some(t => /\bAI\b/.test(t))) i10Errs.push(`規則摘要卡仍標 AI：${r.aiTags.join("／")}`);
    if (r.tokenField) i10Errs.push("FinMind Token 假欄位仍在");
    if (r.fmt !== "12,345 張") i10Errs.push(`法人張數應有千分位：${r.fmt}`);
    if (!/未檢查/.test(r.rowEmpty)) i10Errs.push(`檢查 0 筆的項目應顯示「未檢查」：${r.rowEmpty}`);
    if (/未檢查/.test(r.rowOk)) i10Errs.push("有檢查的項目不該標未檢查");
    if (!/^未檢查/.test(z.trim()) || /通過/.test(z)) i10Errs.push(`整份 0 筆時總結應為「未檢查」：${z.slice(0, 60)}`);
  } catch (e) { i10Errs.push(`測試本身出錯：${e.message || e}`); }
  record("109. 日期顯示最後交易日、法人千分位、FinMind Token 假欄位移除、規則摘要卡不標 AI、稽核 0 筆顯示未檢查（先.八十-10）", i10Errs.length === 0, i10Errs.join("; "));

  // 110.【2026-10-12 先.八十-12】研究口徑：①00631L 2026-03-31 以前的 adj_close＝close÷22（分割還原）②曲線檔紙上線註明還原權息／現金計息／
  // 建倉已扣手續費，模擬 A 建倉後第一天起反映手續費 ③#418 聯集日曆重跑結果另存、原結果檔不被覆蓋、天數變多且純台股配置不受影響。
  const rsErrs = [];
  try {
    const fsx = await import("node:fs");
    const ph = JSON.parse(fsx.readFileSync("data/price_history.json", "utf8"));
    const l = ph.prices["00631L"] || [];
    const pre = l.filter(r => r.date < "2026-03-31"), post = l.filter(r => r.date >= "2026-03-31");
    if (!pre.length || pre.some(r => Math.abs(r.adj_close * 22 - r.close) > 0.01 * r.close)) rsErrs.push("00631L 分割前 adj_close 不等於 close÷22");
    if (post.some(r => r.adj_close != null && Math.abs(r.adj_close - r.close) > 0.01 * r.close)) rsErrs.push("00631L 分割後不該再除");
    if (!(ph.meta.splits_applied || []).includes("00631L@2026-03-31x22.0")) rsErrs.push("meta.splits_applied 缺 00631L 紀錄");
    const cv = JSON.parse(fsx.readFileSync("data/strategy_curves.json", "utf8"));
    for (const x of cv.lines.filter(x => x.group === "paper" && x.started)) {
      if (!/還原權息/.test(x.note) || !/現金與定存按一個月定存利率計息/.test(x.note) || !/建倉已扣手續費/.test(x.note)) rsErrs.push(`${x.id} note 缺口徑說明：${x.note}`);
    }
    const p1 = cv.lines.find(x => x.id === "paper_1");
    if (p1 && p1.nav.length >= 2 && !(p1.nav[0] === 100)) rsErrs.push("模擬 A 起點應為 100（扣費前）");
    const a = JSON.parse(fsx.readFileSync("research/data/core_allocation_result.json", "utf8"));
    const b = JSON.parse(fsx.readFileSync("research/data/core_allocation_result_unioncal.json", "utf8"));
    if (a.calendar) rsErrs.push("#418 原結果檔被覆蓋了（出現 calendar 欄位）");
    if (!(b.period.n_days > a.period.n_days)) rsErrs.push(`聯集日曆天數應多於台股日曆（${a.period.n_days}→${b.period.n_days}）`);
    // 純台股配置只會因月底再平衡日落在美股交易日而有極小差異（≤0.05 個百分點）
    if (Math.abs(a.grid["Aa-70"].cagr - b.grid["Aa-70"].cagr) > 0.0005) rsErrs.push(`純台股配置 Aa-70 不應受美股日曆影響（差 ${((b.grid["Aa-70"].cagr - a.grid["Aa-70"].cagr) * 100).toFixed(3)} 個百分點）`);
  } catch (e) { rsErrs.push(`測試本身出錯：${e.message || e}`); }
  record("110. 研究口徑：00631L 1:22 分割還原、紙上曲線還原權息／現金計息／建倉扣費、#418 聯集日曆重跑另存且純台股不受影響（先.八十-12）", rsErrs.length === 0, rsErrs.join("; "));

  // 111.【2026-10-13 先.八十一-1】market_tw 資料日＝price_history 最後交易日（0050 最後一筆）；落後時 App 顯示「大盤資料停在 MM/DD」。
  const mdErrs = [];
  try {
    const fsx = await import("node:fs");
    const mt = JSON.parse(fsx.readFileSync("data/market_tw.json", "utf8"));
    const ph = JSON.parse(fsx.readFileSync("data/price_history.json", "utf8"));
    const last = ((ph.prices["0050"] || []).slice(-1)[0] || {}).date;
    const dd = mt.data_date || (mt.taiex || {}).data_date;
    if (!dd) mdErrs.push("market_tw 缺 data_date");
    else if (dd !== last) mdErrs.push(`market_tw 資料日 ${dd} ≠ price_history 最後交易日 ${last}${mt.stale_note ? "（stale_note：" + mt.stale_note + "）" : ""}`);
    if ((mt.taiex || {}).sparkline_dates && mt.taiex.sparkline_dates.slice(-1)[0] !== dd) mdErrs.push(`走勢線最後一天 ${mt.taiex.sparkline_dates.slice(-1)[0]} ≠ 資料日 ${dd}`);
    const r = await page.evaluate(() => twCloseDateLabel({ data_date: "2026-10-08", taiex: { data_date: "2026-10-08" }, stale_note: "大盤資料停在 10/08" }));
    if (!/大盤資料停在 10\/08/.test(r)) mdErrs.push(`落後時標籤應顯示「大盤資料停在 10/08」：${r}`);
  } catch (e) { mdErrs.push(`測試本身出錯：${e.message || e}`); }
  record("111. 大盤資料日＝價格歷史最後交易日、走勢線同日；落後時顯示「大盤資料停在 MM/DD」（先.八十一-1）", mdErrs.length === 0, mdErrs.join("; "));

  // 99.【2026-10-11 先.七十九-5】自動投資「已暫停：等紙上策略打贏 0050」：STOP 開著＋status.strategy_frozen → 下一期與橫幅都顯示暫停；
  // 只有 STOP（緊急停止、無 strategy_frozen）→ 不得顯示暫停文字；暫停前有 flow_verification_plan → 顯示流程驗證單說明。純函式，不打本機伺服器。
  const fzErrs = [];
  try {
    const r = await page.evaluate(() => {
      if (typeof autoFreezeText !== "function" || typeof autoNextText !== "function" || typeof autoFlowPlanText !== "function") return { err: "autoFreezeText／autoFlowPlanText 未載入" };
      const frozen = { stopped: true, status: { strategy_frozen: { since: "2026-10-12T14:00:00+08:00", reason: "等紙上策略打贏 0050" } }, next_run: { date: "2026-11-02", time: "09:05", reason: "first_tranche" } };
      const estop = { stopped: true, status: {}, next_run: { date: "2026-11-02", time: "09:05", reason: "first_tranche" } };
      const plan = { stopped: false, status: { flow_verification_plan: { note: "流程驗證單：10/12 只跑第 1 期" } } };
      return { f: autoFreezeText(frozen), fn: autoNextText(frozen), e: autoFreezeText(estop), en: autoNextText(estop),
               fr: autoPeriodReasons(frozen, []).join("|"), p: autoFlowPlanText(plan), pf: autoFlowPlanText({ ...frozen, status: { ...frozen.status, flow_verification_plan: { note: "x" } } }) };
    });
    if (r.err) fzErrs.push(r.err);
    else {
      if (r.f !== "已暫停：等紙上策略打贏 0050") fzErrs.push(`暫停文字不對：${r.f}`);
      if (r.fn !== r.f) fzErrs.push(`下一期應改顯示暫停：${r.fn}`);
      if (r.e) fzErrs.push("單純緊急停止不應顯示「已暫停：等紙上策略…」");
      if (!/11\/02/.test(r.en)) fzErrs.push(`緊急停止時下一期應照常顯示日期：${r.en}`);
      if (!/已暫停：等紙上策略打贏 0050/.test(r.fr) || /緊急停止開關開著/.test(r.fr)) fzErrs.push(`本期原因應寫暫停、不寫緊急停止：${r.fr}`);
      if (!/流程驗證單/.test(r.p)) fzErrs.push("暫停前應顯示流程驗證單說明");
      if (r.pf) fzErrs.push("已暫停後不應再顯示流程驗證單說明");
    }
  } catch (e) { fzErrs.push(`測試本身出錯：${e.message || e}`); }
  record("99. 自動投資「已暫停：等紙上策略打贏 0050」：STOP＋strategy_frozen 才顯示、緊急停止不混用、暫停前顯示流程驗證單（先.七十九-5）", fzErrs.length === 0, fzErrs.join("; "));

  const finalErrors = await page.evaluate(
    "typeof GLOBAL_ERRORS !== 'undefined' ? GLOBAL_ERRORS : []"
  );
  record("12. 整個測試過程（含所有互動操作，含8/9/11/13/14/15/16/17/18/19/20/21/22/23/24/25/26/27/28/29/30/31/32/33/34/35/36/37/38/39/40/41/42/43/44/45/45b/46/47/48/49/50/51/52/53/54/55/56/57/58/59/60/61/62/63/64/65/66/67/68/69/70/71/72/73/74/75/76/77/78/79/80/81/82/83/84/85/86/87/88/89/90/91/92/93/94/95/96/97/98/99/100/101/102/103/104/105/106/107/108/109/110/111新增檢查）結束後仍無累積的uncaught error",
    finalErrors.length === 0,
    finalErrors.length ? `GLOBAL_ERRORS=${JSON.stringify(finalErrors)}` : "");
  results.global_errors_final = finalErrors;

  return results;
  } finally {
    await closeBrowser();
  }
}

async function main() {
  const { url, headed, jsonOut } = parseArgs();
  let results;
  try {
    results = await runSmokeTest(url, !headed);
  } catch (e) {
    await writeJsonOut(jsonOut, url, null, e);
    throw e;
  }
  await writeJsonOut(jsonOut, url, results);

  console.log();
  console.log(`=== 冒煙測試結果：${results.all_passed ? "全部通過" : "有項目FAIL，不要commit，先修好"} ===`);
  if (results.global_errors_final && results.global_errors_final.length) {
    console.log(`最終GLOBAL_ERRORS：${JSON.stringify(results.global_errors_final)}`);
  }

  const ts = new Date().toLocaleString("zh-TW", { timeZone: "Asia/Taipei", hour12: false });
  const lines = [`### 冒煙測試(Node.js/Playwright) ${ts}（${results.all_passed ? "全部通過" : "有FAIL"}）`];
  for (const c of results.checks) {
    lines.push(`- [${c.passed ? "x" : " "}] ${c.name}${c.detail ? "：" + c.detail : ""}`);
  }
  console.log("\n--- 可直接貼進PROGRESS.md的摘要 ---");
  console.log(lines.join("\n"));

  process.exit(results.all_passed ? 0 : 1);
}

main().catch((e) => {
  console.error("smoke_test.mjs 執行時發生未預期例外：", e);
  process.exit(1);
});
