// 2026-10-11 先.七十二：前台文案稽核（Playwright 390×844，只看「使用者看得到」的文字）。
// 規則（data/ui_glossary.json 的 rules／forbidden_front）：
//   卡片標題（.card > h3 的主文字）≤8 字且不含括號；按鈕 ≤6 字；.note ≤40 字（超過要改成「ⓘ 說明」點開）；
//   內部代號（Bb-90、紙.一～紙.四、S3-C6、R1-C、LIVE、pp、MDD、唯讀、Phase、XBRL、FinMind、Shioaji、TWSE…）不得出現在前台，
//   只有 [data-ui-advanced] 範圍（設定頁「進階」）可以；免責聲明（「非投資建議」）前台可見處只能一處（頁尾）。
// 匯出 auditPage(page, glossary) 給冒煙用；直接執行則逐頁列出違規。
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const SCREENS = ["home", "market", "picks", "trade", "journal", "settings"];

export function loadGlossary() {
  return JSON.parse(fs.readFileSync(path.join(ROOT, "data", "ui_glossary.json"), "utf8"));
}

// 在頁面內執行：收集目前可見畫面的違規
export async function auditVisible(page, glossary, scope) {
  return page.evaluate(({ g, scope }) => {
    const root = scope ? document.querySelector(scope) : document.body;
    const vis = (el) => {
      if (!el || !el.isConnected) return false;
      if (el.closest("[hidden]")) return false;
      const st = getComputedStyle(el);
      if (st.display === "none" || st.visibility === "hidden") return false;
      for (let p = el; p && p !== document.body; p = p.parentElement) {
        const s = getComputedStyle(p);
        if (s.display === "none" || s.visibility === "hidden") return false;
        if (p.tagName === "DETAILS" && !p.open && !el.closest("summary") && p !== el) return false;
      }
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    const inAdv = (el) => !!el.closest("[data-ui-advanced]");
    const txt = (s) => (s || "").replace(/\s+/g, " ").trim();
    const len = (s) => [...txt(s)].length;
    const out = { titles: [], buttons: [], notes: [], terms: [], disclaimers: 0, disclaimerWhere: [] };
    if (!root) return out;
    // 標題：.card > h3 的主文字（排除 .more／按鈕／連結／徽章等附屬元素）
    for (const h of root.querySelectorAll(".card h3, .card > .card-title")) {
      if (!vis(h) || inAdv(h)) continue;
      const c = h.cloneNode(true);
      c.querySelectorAll(".more, button, a, .badge, .sc-status, .refresh-btn, .mkt-toggle, [data-ui-aux]").forEach(x => x.remove());
      const t = txt(c.textContent);
      if (!t) continue;
      if (len(t) > g.rules.title_max || /[()（）［］\[\]【】]/.test(t)) out.titles.push(t);
    }
    for (const b of root.querySelectorAll("button, .btn, [role=button]")) {
      if (!vis(b) || inAdv(b) || b.id === "new-version-banner") continue;
      const t = txt(b.textContent);
      if (t && len(t) > g.rules.button_max) out.buttons.push(t);
    }
    // 先.八十-5：只檢查說明類（data-ui-explain）；卡片主內容的 .note 不收合、也不受 40 字限制
    for (const n of root.querySelectorAll(".note[data-ui-explain]")) {
      if (!vis(n) || inAdv(n) || n.closest("[data-ui-detail]")) continue;
      const t = txt(n.innerText);  // innerText＝實際畫出來的字：收合的「ⓘ 說明」內容不算
      if (len(t) > g.rules.note_max) out.notes.push(t.slice(0, 60));
    }
    // 內部代號：逐一看可見文字節點
    const re = g.forbidden_front.map(f => [f.term, new RegExp(f.regex, f.flags || "")]);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const seen = new Set();
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const el = n.parentElement;
      if (!el || ["SCRIPT", "STYLE", "NOSCRIPT"].includes(el.tagName) || inAdv(el) || !vis(el)) continue;
      const t = n.textContent;
      for (const [term, r] of re) {
        if (r.test(t)) { const k = term + "|" + txt(t).slice(0, 30); if (!seen.has(k)) { seen.add(k); out.terms.push(`${term}：${txt(t).slice(0, 50)}`); } }
      }
      if (/非投資建議/.test(t) && !el.closest("[data-ui-footer-disclaimer]")) { out.disclaimers++; out.disclaimerWhere.push(txt(t).slice(0, 30)); }
    }
    return out;
  }, { g: glossary, scope });
}

// 先.八十-6（2026-10-12）：稽核範圍擴大——每個分頁的預設畫面之外，逐一點開該頁所有子分頁（*-tabs 的 data-sub 按鈕）、
// 市場／選股切換（.mkt-toggle 的選項，含美股、期貨）、個股頁四個子分頁；最後模擬「電腦離線」（本機伺服器連不上）
// 再看首頁／交易／設定一次。同一頁多個狀態的違規合併去重，key 名稱帶狀態（例：trade、trade/sub:monitor、market/opt:US、offline/home）。
function mergeInto(dst, src) {
  if (src.error) { dst.error = (dst.error ? dst.error + "；" : "") + src.error; return; }
  for (const k of ["titles", "buttons", "notes", "terms"]) for (const x of src[k]) if (!dst[k].includes(x)) dst[k].push(x);
  for (const w of src.disclaimerWhere) if (!dst.disclaimerWhere.includes(w)) { dst.disclaimerWhere.push(w); dst.disclaimers++; }
}
const blank = () => ({ titles: [], buttons: [], notes: [], terms: [], disclaimers: 0, disclaimerWhere: [] });

async function clickAll(page, scope, sel) {
  return page.evaluate(({ scope, sel }) => [...document.querySelectorAll(`${scope} ${sel}`)].map((el, i) => i), { scope, sel });
}

async function auditStates(page, glossary, scr) {
  const scope = `#scr-${scr}`;
  const out = blank();
  mergeInto(out, await auditVisible(page, glossary, scope));
  // 子分頁
  const subs = await page.evaluate((scope) => [...document.querySelectorAll(`${scope} [id$="-tabs"] button[data-sub]`)].map(b => b.closest('[id$="-tabs"]').id + "|" + b.dataset.sub), scope);
  for (const k of subs) {
    const [tid, sub] = k.split("|");
    await page.evaluate(({ tid, sub }) => { const b = document.querySelector(`#${tid} button[data-sub="${sub}"]`); if (b) b.click(); }, { tid, sub });
    await page.waitForTimeout(700);
    mergeInto(out, await auditVisible(page, glossary, scope));
  }
  // 市場／榜單切換選項（.mkt-toggle .mtg-opt）
  const opts = await page.evaluate((scope) => [...document.querySelectorAll(`${scope} .mkt-toggle .mtg-opt`)].map((o, i) => i), scope);
  for (const i of opts) {
    await page.evaluate(({ scope, i }) => { const o = document.querySelectorAll(`${scope} .mkt-toggle .mtg-opt`)[i]; if (o && o.offsetParent) o.click(); }, { scope, i });
    await page.waitForTimeout(700);
    mergeInto(out, await auditVisible(page, glossary, scope));
  }
  // 復原：每個切換群組點回第一個選項、子分頁點回第一個
  await page.evaluate((scope) => {
    document.querySelectorAll(`${scope} .mkt-toggle`).forEach(t => { const o = t.querySelector(".mtg-opt"); if (o && o.offsetParent) o.click(); });
    document.querySelectorAll(`${scope} [id$="-tabs"]`).forEach(t => { const b = t.querySelector("button[data-sub]"); if (b) b.click(); });
  }, scope);
  await page.waitForTimeout(400);
  return out;
}

export async function auditApp(page, baseUrl, glossary, { stockCode = "2330", usCode = "AAPL", offline = true } = {}) {
  const res = {};
  for (const s of SCREENS) {
    await page.evaluate((s) => { const b = document.querySelector(`nav#nav button[data-scr="${s}"]`); if (b) b.click(); }, s);
    await page.waitForTimeout(1200);
    try { res[s] = await auditStates(page, glossary, s); } catch (e) { res[s] = { ...blank(), error: String(e) }; }
  }
  for (const [key, code] of [["stock", stockCode], ["stock/us", usCode]]) {
    try {
      // 不等 openStock 的 promise（稽核只看畫面；冒煙實測偶發「promise was garbage collected」），啟動後固定等畫面穩定
      await page.evaluate((c) => { Promise.resolve(openStock(c)).catch(e => console.warn("[audit openStock]", e)); }, code);
      await page.waitForTimeout(3000);
      res[key] = await auditStates(page, glossary, "stock");
    } catch (e) { res[key] = { ...blank(), error: String(e) }; }
  }
  if (offline) {
    // 電腦離線：另開一個獨立的瀏覽器環境（新 context）模擬本機伺服器連不上，稽核完就關掉，不污染呼叫端的分頁狀態
    // （冒煙實測：在同一分頁裡改 LIVE／window.fetch 再還原，後續 openStock 的 promise 會永遠不 resolve）。
    const ctx2 = await page.context().browser().newContext({ viewport: page.viewportSize() || { width: 390, height: 844 } });
    const p2 = await ctx2.newPage();
    try {
      await p2.goto(page.url(), { waitUntil: "domcontentloaded" });
      await p2.waitForTimeout(1500);
      await p2.evaluate(() => {
        LIVE.url = "https://audit-offline.invalid"; LIVE.configured = true;
        const f = window.fetch;
        window.fetch = (u, o) => (String(u).startsWith("https://audit-offline.invalid") ? Promise.reject(new TypeError("Failed to fetch")) : f(u, o));
      });
      for (const s of ["home", "trade", "settings"]) {
        await p2.evaluate((s) => { const b = document.querySelector(`nav#nav button[data-scr="${s}"]`); if (b) b.click(); }, s);
        await p2.evaluate(async (s) => {
          const fns = { home: ["loadHomeExecCard", "loadHomeBrokerCard"], trade: ["loadTradeBots"], settings: ["loadAutoTrading", "loadRiskLimits"] }[s] || [];
          for (const n of fns) { try { const fn = typeof window[n] === "function" ? window[n] : eval(n); if (typeof fn === "function") await fn(); } catch (e) { console.warn("[audit offline]", n, e); } }
        }, s);
        await p2.waitForTimeout(800);
        res["offline/" + s] = await auditVisible(p2, glossary, `#scr-${s}`);
      }
    } catch (e) { res.offline = { ...blank(), error: String(e) }; }
    finally { await ctx2.close(); }
  }
  return res;
}

if (process.argv[1] && process.argv[1].endsWith("ux_copy_audit.mjs")) {
  const { chromium } = await import("@playwright/test");
  const { launchGuarded } = await import("./pw_guard.mjs");
  const url = process.argv[2] || "http://localhost:8792/index.html";
  const g = loadGlossary();
  const { browser, close } = await launchGuarded(chromium, {}, { label: "ux_copy_audit", hardTimeoutMs: 5 * 60 * 1000 });
  let res;
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
    await page.waitForTimeout(2000);
    res = await auditApp(page, url, g);
  } finally { await close(); }
  let total = 0;
  for (const [pg, r] of Object.entries(res)) {
    if (r.error) { console.log(`## ${pg}：${r.error}`); continue; }
    const n = r.titles.length + r.buttons.length + r.notes.length + r.terms.length + Math.max(0, r.disclaimers);
    total += n;
    console.log(`## ${pg}：標題 ${r.titles.length}、按鈕 ${r.buttons.length}、說明 ${r.notes.length}、內部代號 ${r.terms.length}、免責 ${r.disclaimers}`);
    for (const k of ["titles", "buttons", "notes", "terms"]) for (const x of r[k]) console.log(`  [${k}] ${x}`);
    for (const x of r.disclaimerWhere) console.log(`  [disclaimer] ${x}`);
  }
  console.log(`合計 ${total} 處`);
  if (process.argv.includes("--json")) fs.writeFileSync(path.join(ROOT, "research", "ux_copy_audit.json"), JSON.stringify(res, null, 1));
}
