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
    for (const n of root.querySelectorAll(".note")) {
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

export async function auditApp(page, baseUrl, glossary, { stockCode = "2330" } = {}) {
  const res = {};
  for (const s of SCREENS) {
    await page.evaluate((s) => { const b = document.querySelector(`nav#nav button[data-scr="${s}"]`); if (b) b.click(); }, s);
    await page.waitForTimeout(1200);
    res[s] = await auditVisible(page, glossary, `#scr-${s}`);
  }
  try {
    await page.evaluate((c) => openStock(c), stockCode);
    await page.waitForTimeout(2500);
    res.stock = await auditVisible(page, glossary, "#scr-stock");
  } catch (e) { res.stock = { error: String(e) }; }
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
