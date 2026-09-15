// 金流一.6 驗收腳本：抓三張截圖當驗收證據。
//
// 背景：PENDING_QUEUE「金流一」總司令原話第6項要「Playwright 截圖市場頁泡泡圖、
// 一個產業展開排行、2330 個股頁籌碼卡」。金流一.3 已記錄「刻意不畫規格指定的
// SVG 象限散點圖」（Y軸需要20日加速度、半徑需要20日累計，兩者現在都還沒累積
// 足夠交易日），改用依估算金額排序的長條圖頂替，並附理由。所以這裡截的是
// 「市場頁產業金流長條圖」（實際上線的版本），不是規格原文的泡泡圖——這個
// 替代已經是金流一.3當時的既定決策，這裡不重新討論。
//
// 用法：node scripts/sector_flow_screenshots.mjs（預設打 http://localhost:8792，
// 需要先在repo根目錄另開一個終端機跑 `python -m http.server 8792`）。
// 三張圖存在 repo 根目錄，供這次驗收人工檢視，不進版控（跟 kbars_open_check.png
// 同慣例，只是一次性驗收證據，不是原始碼）。
import { chromium } from "@playwright/test";

const BASE_URL = process.env.ALPHA_APP_URL || "http://localhost:8792";

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 393, height: 852 } });
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  await page.goto(`${BASE_URL}/index.html`, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForTimeout(1000);

  // 1. 市場頁「產業金流」卡（依估算金額排序的長條圖，取代規格原文泡泡圖，理由見檔頭）
  await page.evaluate(() => window.go("market"));
  await page.waitForTimeout(2000);
  const flowHost = page.locator("#sector-flow-body");
  await flowHost.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  const bodyText1 = await flowHost.innerText();
  await page.screenshot({ path: "sector_flow_1_market_card.png" });
  console.log("1/3 市場頁產業金流卡截圖完成，卡片內容非空：", bodyText1.trim().length > 0);

  // 2. 展開一個產業的成分股排行（點第一列，觸發 toggleFlowSector）
  const firstRow = flowHost.locator("> div.press").first();
  const rowCount = await flowHost.locator("> div.press").count();
  let expandedOk = false;
  if (rowCount > 0) {
    await firstRow.click();
    await page.waitForTimeout(500);
    const expandedText = await flowHost.innerText();
    expandedOk = /買超前 10|賣超前 10/.test(expandedText);
    await page.screenshot({ path: "sector_flow_2_sector_expand.png" });
  }
  console.log("2/3 產業展開排行截圖完成，展開成功：", expandedOk, `（找到 ${rowCount} 個產業列）`);

  // 3. 2330 個股頁籌碼分頁
  await page.evaluate((code) => window.openStock(code), "2330");
  await page.waitForTimeout(1200);
  await page.evaluate(() => {
    document.querySelector('#stock-tabs button[data-sub="chip"]')?.click();
  });
  await page.waitForTimeout(1000);
  const chipText = await page.evaluate(() => document.getElementById("scr-stock")?.innerText || "");
  await page.screenshot({ path: "sector_flow_3_stock_2330_chips.png" });
  console.log("3/3 2330個股頁籌碼分頁截圖完成，內容非空：", chipText.trim().length > 0);

  console.log("\npageerror 累積數：", pageErrors.length);
  if (pageErrors.length) console.log(pageErrors);

  await browser.close();
}

main().catch((e) => {
  console.error("sector_flow_screenshots.mjs 執行時發生未預期例外：", e);
  process.exit(1);
});
