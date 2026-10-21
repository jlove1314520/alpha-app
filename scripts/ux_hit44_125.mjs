// 先.一二五-2（2026-10-21，總司令核准 先.一二二-5 甲案）：點擊熱區放大驗收。393×852 深／淺色，畫面同 ux_shots_122.mjs
// （今日、研究室、交易、日誌、設定、頁首、個股 1303／3661／4977 研究分頁）。每個畫面做兩件事：
//   ①外觀不變：同一次載入裡，先把 app.css「先.一二五-2」那兩條規則從 CSSOM 拿掉截一張（off），放回去再截一張（on），
//     頁首時鐘區遮罩；兩張由 scripts/ux_hit44_compare.py 逐像素比對。
//   ②熱區量測（small）：每個可點元素捲到畫面中央，用 elementFromPoint 打「以元素中心為準、至少 44×44 的方框」四角＋四邊中點，
//     任一點打到的不是它自己（或它的子元素、或它的 <label>）就列入 small，附「打到誰」。
//     smallBox＝舊定義（元素外框 <44，同 ux_shots_122.mjs 的 small），只供對照。
//   ③stolen：每個可點元素的中心點如果被別的元素（例如大容器的 ::before）搶走，列入 stolen——這項必須是 0。
// 截圖與 metrics.json 存 research/ux_shots_122/<標籤>/（.gitignore）。用法：python scripts/ensure_smoke_server.py 後
// node scripts/ux_hit44_125.mjs [標籤，預設 hit44]，再 python scripts/ux_hit44_compare.py research/ux_shots_122/<標籤>
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { launchGuarded } from "./pw_guard.mjs";

const base = process.env.BASE_URL || "http://127.0.0.1:8792";
const tag = process.argv[2] || "hit44";
const out = path.join("research", "ux_shots_122", tag);
fs.mkdirSync(out, { recursive: true });
const metrics = {};
const { browser, close } = await launchGuarded(chromium, {}, { label: "ux_hit44_125", hardTimeoutMs: 20 * 60 * 1000 });

async function hitAudit(rootSel) {
  const root = document.querySelector(rootSel);
  if (!root) return { error: `找不到 ${rootSel}` };
  const main = document.getElementById("main");
  const keepScroll = main ? main.scrollTop : 0;
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const label = (e) => !e ? "（無）" : (e.id ? `#${e.id}` : e.tagName.toLowerCase() + (e.className && typeof e.className === "string" ? "." + e.className.trim().split(/\s+/).slice(0, 2).join(".") : "")) + `「${(e.innerText || e.getAttribute?.("aria-label") || "").trim().replace(/\s+/g, " ").slice(0, 20)}」`;
  const clickSel = "button, a[href], [onclick], .press, [role=button], input, select";
  const isClick = (e) => e && e.matches && e.matches(clickSel);
  const ok = (e, h) => !!h && (h === e || e.contains(h) || (h.closest && h.closest("label") && h.closest("label").control === e));
  const frame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  // 收合的 <details> 裡的列（摘要以外）畫面上看不到、點不到，getBoundingClientRect 卻仍有大小，不列入
  const inClosedDetails = (e) => { const d = e.closest("details:not([open])"); return !!d && !(e.matches("summary") && e.parentElement === d); };
  const els = [...root.querySelectorAll(clickSel)].filter(vis).filter((e) => !inClosedDetails(e));
  const small = [], smallBox = [], stolen = [];
  for (const e of els) {
    e.scrollIntoView({ block: "center", inline: "nearest" });
    await frame();
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    // ③ 中心點被搶：打到的不是自己／子元素／自己的 label，而且打到的東西（或它的可點祖先）不是自己的子孫
    const hc = document.elementFromPoint(cx, cy);
    if (hc && !ok(e, hc)) {
      const hClick = hc.closest(clickSel);
      if (!(hClick && e.contains(hClick))) stolen.push(`${label(e)} 中心被 ${label(hc)} 搶走`);
    }
    if (r.width >= 44 && r.height >= 44) continue;
    smallBox.push(`${label(e)} ${Math.round(r.width)}×${Math.round(r.height)}`);
    // 內縮 2px：相鄰相接的分段鈕（.mtg-opt）共用 1px 邊框，邊框那一像素歸誰都合理，不拿它判定
    const hw = Math.max(r.width, 44) / 2 - 2, hh = Math.max(r.height, 44) / 2 - 2;
    const pts = [[cx, cy - hh], [cx, cy + hh], [cx - hw, cy], [cx + hw, cy], [cx - hw, cy - hh], [cx + hw, cy - hh], [cx - hw, cy + hh], [cx + hw, cy + hh]];
    const miss = [];
    for (const [x, y] of pts) {
      if (x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) { miss.push("超出畫面"); continue; }
      const h = document.elementFromPoint(x, y);
      if (!ok(e, h)) miss.push(label(h));
    }
    if (miss.length) small.push(`${label(e)} ${Math.round(r.width)}×${Math.round(r.height)} 熱區被：${[...new Set(miss)].slice(0, 3).join("、")}`);
  }
  if (main) main.scrollTop = keepScroll;
  return { small, smallCount: small.length, smallBox, smallBoxCount: smallBox.length, stolen, stolenCount: stolen.length, clickables: els.length };
}

// 開關「先.一二五-2」兩條規則（同一份 CSSOM 拿掉／放回），回傳動到幾條
function setHit(on) {
  window.__hit44 = window.__hit44 || [];
  if (window.__hit44Locked) return 2;  // HIT44_OFF＝1：整輪都在「規則拿掉」的狀態，量測對照用
  if (!on) {
    let n = 0;
    for (const sh of document.styleSheets) {
      let rules; try { rules = sh.cssRules; } catch { continue; }
      for (let i = rules.length - 1; i >= 0; i--) {
        if ((rules[i].selectorText || "").includes("label.setting-input")) { window.__hit44.push({ sh, text: rules[i].cssText, i }); sh.deleteRule(i); n++; }
      }
    }
    return n;
  }
  const back = window.__hit44.splice(0).reverse();
  for (const b of back) b.sh.insertRule(b.text, b.i);
  return back.length;
}

const OFF_INIT = `window.setHitOff = function(){ const f = ${setHit.toString()}; f(false); window.__hit44Locked = true; };`;
for (const scheme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, colorScheme: scheme, serviceWorkers: "block" });
  const page = await ctx.newPage();
  if (process.env.HIT44_OFF === "1") await page.addInitScript(OFF_INIT);
  const pe = [];
  page.on("pageerror", (e) => pe.push(String(e)));
  await page.goto(`${base}/index.html`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2500);
  if (process.env.HIT44_OFF === "1") await page.evaluate(() => { setHitOff(); });
  const m = {};
  const pairs = async (name, n = 5) => {
    const total = await page.evaluate(() => { const mm = document.getElementById("main"); mm.scrollTop = 0; return { h: mm.scrollHeight, c: mm.clientHeight }; });
    const steps = Math.min(n, Math.max(1, Math.ceil(total.h / (total.c - 80))));
    const mask = [page.locator("header.top")];
    for (let i = 0; i < steps; i++) {
      await page.evaluate((y) => { document.getElementById("main").scrollTop = y; }, i * (total.c - 80));
      await page.waitForTimeout(300);
      const off = await page.evaluate(setHit, false);
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(out, `${name}_${scheme}_${i + 1}_off.png`), mask, animations: "disabled" });
      await page.evaluate(setHit, true);
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(out, `${name}_${scheme}_${i + 1}_on.png`), mask, animations: "disabled" });
      if (off !== 2) pe.push(`setHit 拿掉 ${off} 條（預期 2）`);
    }
    await page.evaluate(() => { document.getElementById("main").scrollTop = 0; });
  };
  await page.waitForTimeout(1500);
  await pairs("home", 6);
  m.home = await page.evaluate(hitAudit, "#scr-home");
  await page.click('#nav button[data-scr="lab"]');
  await page.waitForFunction(() => document.querySelectorAll("#lab-deep-list .lab-deep").length > 0, null, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await pairs("lab", 8);
  m.lab = await page.evaluate(hitAudit, "#scr-lab");
  await page.click('#nav button[data-scr="trade"]');
  await page.waitForTimeout(1500);
  await pairs("trade", 4);
  m.trade = await page.evaluate(hitAudit, "#scr-trade");
  await page.click('#trade-tabs button[data-sub="journal"]');
  await page.waitForTimeout(1500);
  await pairs("journal", 4);
  m.journal = await page.evaluate(hitAudit, "#scr-journal");
  await page.click("#hdr-settings");
  await page.waitForTimeout(1500);
  await pairs("settings", 6);
  m.settings = await page.evaluate(hitAudit, "#scr-settings");
  m.header = await page.evaluate(hitAudit, "header.top");
  for (const code of ["1303", "3661", "4977"]) {
    await page.evaluate((c) => openStock(c), code);
    await page.waitForTimeout(2500);
    await page.click('#stock-tabs button[data-sub="research"]').catch(() => {});
    await page.waitForTimeout(3000);
    await pairs(`stock${code}_research`, 6);
    m[`stock${code}`] = await page.evaluate(hitAudit, "#scr-stock");
  }
  m.pageerrors = pe.slice(0, 5);
  metrics[scheme] = m;
  await ctx.close();
}
await close();
// 說得了原因的項目（每條都是看過畫面後寫的；其餘留在 small）
const REASONS = [
  [/span\.sdot/, "自選列的資料來源小點：本身在可點的整列裡，擴大會吃掉整列「開個股」的點擊，刻意不擴"],
  [/#alert-hub-dot/, "頁首告警小點緊貼設定齒輪左側，兩者距離不夠各自 44px，刻意不擴（擴了會蓋掉齒輪）"],
  [/button\.back「/, "上緣緊貼固定頁首，往上的熱區被頁首蓋住（頁首永遠在最上層）；左右下三邊已達 44px"],
  [/button(\.on)?「(常用|進階)」/, "設定頁最上方的分段鈕，上緣就是捲動區頂端，往上沒有空間；左右下已達 44px"],
  [/#(home-lab-line|journal-offline-line|home-offline-line)/, "畫面最上方的整行提示，上緣就是捲動區頂端；本身 361px 寬、39px 高"],
  [/span\.press\.wl-tab|span\.press「＋」/, "自選籤列下緣離第一列自選股只有 8px（要 9.5px），差的 1.5px 讓給自選列，不搶它的點擊"],
  [/^a「[^」]+」|span\.press「前往 →」|a「WIN_PROBABILITY/, "句子裡的文字連結（行內、可能折成兩行），WCAG 2.5.8 對句中連結不設目標尺寸"],
  [/span\.press「[^」]+」 \d+×29 熱區被：span\.press/, "研究紀錄的籤折成兩排、上下只隔 6px，重疊的 6px 歸下排；兩顆中心與左右兩側都點得到"],
  [/summary\.press/, "「展開看全文／看全部」摘要列上下緊鄰可點的整列（系統健康、資料新鮮度），擴大會搶鄰列的點擊"],
];
for (const m of Object.values(metrics)) for (const v of Object.values(m)) {
  if (!v || typeof v !== "object" || Array.isArray(v) || !v.small) continue;
  const left = [], explained = [];
  for (const it of v.small) { const r = REASONS.find(([re]) => re.test(it.replace(/^\S+ /, (x) => x.startsWith("a「") ? x : x))); if (r) explained.push(`${it} ⇒ ${r[1]}`); else left.push(it); }
  v.smallRaw = v.small; v.small = left; v.smallCount = left.length; v.smallExplained = explained;
}
fs.writeFileSync(path.join(out, "metrics.json"), JSON.stringify(metrics, null, 2));
for (const [s, m] of Object.entries(metrics)) {
  for (const [k, v] of Object.entries(m)) {
    if (!v || typeof v !== "object" || Array.isArray(v)) continue;
    console.log(`${s}/${k}: 熱區不足${v.smallCount}（另有說得了原因 ${v.smallExplained.length}；外框<44：${v.smallBoxCount}） 中心被搶${v.stolenCount} 可點${v.clickables}${v.error ? " " + v.error : ""}`);
  }
  console.log(`${s} pageerrors: ${m.pageerrors.length}${m.pageerrors.length ? " " + m.pageerrors.join(" | ") : ""}`);
}
