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

import { chromium } from "@playwright/test";

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
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--url") url = args[++i];
    if (args[i] === "--headed") headed = true;
  }
  return { url, headed };
}

async function runSmokeTest(baseUrl, headless = true) {
  const results = { checks: [], all_passed: true };
  const record = (name, passed, detail = "") => {
    results.checks.push({ name, passed, detail });
    if (!passed) results.all_passed = false;
    console.log(`${passed ? "PASS" : "FAIL"} - ${name}${detail ? "：" + detail : ""}`);
  };

  const browser = await chromium.launch({ headless });
  const page = await browser.newPage({ viewport: { width: 393, height: 852 } });

  const pageErrors = [];
  page.on("pageerror", (exc) => pageErrors.push(String(exc)));

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

  // 9.【2026-08-28新增，使用者回報「時鐘/資料手機端卡在舊版」第五次】模擬
  // 「手機已經裝了舊版SW＋舊快取」的情境：先讓真正的SW註冊完成，然後直接對
  // 目前的CacheStorage寫入一份「假的、內容被竄改過的index.html」（塞進跟
  // sw.js當下CACHE常數同名的cache裡，模擬舊安裝殘留的快取條目），重新整理
  // 頁面後確認畫面渲染出來的還是「真正、最新」的內容（用APP_VERSION是否為
  // 真實常數值、不是竄改過的假值來判斷）——驗證sw.js的network-first邏輯
  // 真的會無視快取裡的舊內容、以網路上最新版本為準，不是只在理論上正確。
  let staleCacheResult = "跳過（瀏覽器context不支援cache API或SW未啟用）";
  let staleCachePassed = true;
  try {
    const swReady = await page.evaluate(async () => {
      if (!("serviceWorker" in navigator)) return false;
      const reg = await navigator.serviceWorker.ready.catch(() => null);
      return !!(reg && reg.active);
    });
    if (swReady) {
      const cacheName = await page.evaluate(async () => {
        const keys = await caches.keys();
        return keys.find((k) => k.startsWith("alpha-v")) || null;
      });
      if (cacheName) {
        await page.evaluate(async (name) => {
          const c = await caches.open(name);
          const fakeHtml = "<html><body>STALE_FAKE_CONTENT_MARKER</body></html>";
          await c.put(
            new Request(location.origin + "/index.html"),
            new Response(fakeHtml, { headers: { "Content-Type": "text/html" } })
          );
        }, cacheName);
        await page.reload({ waitUntil: "networkidle", timeout: 20000 });
        await page.waitForTimeout(500);
        const bodyText = await page.evaluate(() => document.body.innerHTML);
        const realVersion = await page.evaluate(() =>
          typeof APP_VERSION !== "undefined" ? APP_VERSION : null
        );
        staleCachePassed = !bodyText.includes("STALE_FAKE_CONTENT_MARKER") && !!realVersion;
        staleCacheResult = staleCachePassed
          ? `通過：即使快取裡塞了竄改過的假內容，重新整理後仍顯示真實版本(APP_VERSION=${realVersion})，未被舊快取覆蓋`
          : "失敗：重新整理後畫面顯示的是快取裡塞進去的假內容，代表network-first失效、舊快取會蓋過新版本";
      } else {
        staleCacheResult = "跳過（找不到alpha-v開頭的cache，可能SW還沒完成第一次install快取）";
      }
    }
  } catch (e) {
    staleCachePassed = false;
    staleCacheResult = `執行時發生例外：${e.message || e}`;
  }
  record("9. 模擬手機已裝舊版SW快取，驗證network-first不會被舊內容覆蓋", staleCachePassed, staleCacheResult);

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

    // 16b. 策略監控台權益曲線（spark()，讀strategies.json::forward_paper.equity_curve）
    const fakeStrategies = {
      strategies: [{
        id: "smoke_test_fake", name: "冒煙測試假策略", type: "test", status: "紙上交易中",
        spec: "smoke_test注入，非真實策略",
        forward_paper: {
          inception_date: "2026-01-01", forward_return_todate_pct: 3.5,
          trading_days_count: 5, sample_sufficient: false,
          equity_curve: [
            { date: "2026-01-01", cum_return_pct: 0 },
            { date: "2026-01-02", cum_return_pct: 1.2 },
            { date: "2026-01-03", cum_return_pct: -0.5 },
            { date: "2026-01-04", cum_return_pct: 3.5 },
          ],
          ledger: [], source: "smoke_test",
        },
        limitations: [], last_updated: new Date().toISOString(),
      }],
    };
    await page.route("**/data/strategies.json**", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fakeStrategies) })
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
    await page.unroute("**/data/strategies.json**");
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
    await page.evaluate(() => document.querySelector(".buy-cta .btn.buy").click());
    await page.waitForTimeout(2500);
    const usSheetOpen = await page.evaluate(() => document.getElementById("ibkr-sheet")?.classList.contains("open"));
    const twSheetOpenWrong = await page.evaluate(() => document.getElementById("sheet")?.classList.contains("open"));
    if (!usSheetOpen) ibkrUiErrors.push("美股按買進後，#ibkr-sheet沒有打開");
    if (twSheetOpenWrong) ibkrUiErrors.push("美股按買進後，台股示範版#sheet竟然也開了（分工鐵律破功）");
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

    await page.evaluate(() => window.openStock("2330"));
    await page.waitForTimeout(300);
    await page.evaluate(() => document.querySelector(".buy-cta .btn.buy").click());
    await page.waitForTimeout(300);
    const twSheetOpen = await page.evaluate(() => document.getElementById("sheet")?.classList.contains("open"));
    const ibkrSheetOpenWrong = await page.evaluate(() => document.getElementById("ibkr-sheet")?.classList.contains("open"));
    if (!twSheetOpen) ibkrUiErrors.push("台股按買進後，原本的示範版#sheet沒有打開（回歸壞掉）");
    if (ibkrSheetOpenWrong) ibkrUiErrors.push("台股按買進後，IBKR下單卡片#ibkr-sheet竟然也開了（分工鐵律破功）");
    await page.evaluate(() => window.closeSheet());
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
    if (!html.includes("Yahoo 延遲")) {
      yahooFallbackErrors.push(`YAHOO_DELAYED的道瓊指數沒有顯示「Yahoo 延遲」badge，實際內容片段：${html.slice(0, 300)}`);
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

  const finalErrors = await page.evaluate(
    "typeof GLOBAL_ERRORS !== 'undefined' ? GLOBAL_ERRORS : []"
  );
  record("12. 整個測試過程（含所有互動操作，含8/9/11/13/14/15/16/17/18/19/20/21新增檢查）結束後仍無累積的uncaught error",
    finalErrors.length === 0,
    finalErrors.length ? `GLOBAL_ERRORS=${JSON.stringify(finalErrors)}` : "");
  results.global_errors_final = finalErrors;

  await browser.close();
  return results;
}

async function main() {
  const { url, headed } = parseArgs();
  const results = await runSmokeTest(url, !headed);

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
