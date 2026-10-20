// 先.一二二-5 新版面第二輪人因檢查：393×852 深／淺色——今日、研究室（深度卡＋雷達＋產業營收熱度）、交易→日誌、右上齒輪設定、
// 個股 1303／3661／4977 研究分頁。每個畫面依 #main 捲動分段截圖，並自動量測：
//   水平溢出（元素右緣 > 視窗寬，排除本身在可水平捲動容器內者）、文字截斷（ellipsis 且 scrollWidth > clientWidth）、
//   空白區塊（.card 高 > 60px 但文字 < 4 字）、可點元素太小（< 44px）、深淺色對比（WCAG，一般字 < 4.5、大字 < 3）、
//   卡片沒有任何日期標示（MM/DD、YYYY-MM-DD、HH:MM 都算）。
// 存 research/ux_shots_122/<標籤>/（.gitignore，不進公開 repo），量測寫 metrics.json。
// 用法：python scripts/ensure_smoke_server.py 後 node scripts/ux_shots_122.mjs [標籤，預設 before]
import { chromium } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { launchGuarded } from "./pw_guard.mjs";

const base = process.env.BASE_URL || "http://127.0.0.1:8792";
const tag = process.argv[2] || "before";
const out = path.join("research", "ux_shots_122", tag);
fs.mkdirSync(out, { recursive: true });
const metrics = {};
const { browser, close } = await launchGuarded(chromium, {}, { label: "ux_shots_122", hardTimeoutMs: 15 * 60 * 1000 });

// 在頁面內量測目前 active 畫面（傳入根節點選擇器）
function audit(rootSel) {
  const W = window.innerWidth;
  const root = document.querySelector(rootSel);
  if (!root) return { error: `找不到 ${rootSel}` };
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const label = (e) => (e.id ? `#${e.id}` : e.tagName.toLowerCase() + (e.className && typeof e.className === "string" ? "." + e.className.trim().split(/\s+/).slice(0, 2).join(".") : "")) + `「${(e.innerText || e.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ").slice(0, 24)}」`;
  const inHScroll = (e) => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const ox = getComputedStyle(p).overflowX; if ((ox === "auto" || ox === "scroll" || ox === "hidden") && p.scrollWidth > p.clientWidth + 1) return true; } return false; };
  const all = [...root.querySelectorAll("*")].filter(vis);
  const overflow = all.filter((e) => { const r = e.getBoundingClientRect(); return r.right > W + 1 && !inHScroll(e); }).map((e) => `${label(e)} right=${Math.round(e.getBoundingClientRect().right)}`);
  const trunc = all.filter((e) => getComputedStyle(e).textOverflow === "ellipsis" && e.scrollWidth > e.clientWidth + 1).map(label);
  const empty = [...root.querySelectorAll(".card")].filter(vis).filter((c) => c.getBoundingClientRect().height > 60 && (c.innerText || "").replace(/\s/g, "").length < 4).map(label);
  const clickSel = "button, a[href], [onclick], .press, [role=button], input, select";
  const small = [...root.querySelectorAll(clickSel)].filter(vis).filter((e) => { const r = e.getBoundingClientRect(); return r.height < 44 || r.width < 44; })
    .map((e) => { const r = e.getBoundingClientRect(); return `${label(e)} ${Math.round(r.width)}×${Math.round(r.height)}`; });
  // 對比：取每個有直接文字的元素
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (e) => { const stack = []; for (let p = e; p; p = p.parentElement) { const c = parse(getComputedStyle(p).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a >= 1) break; } } let res = parse(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 }; for (let i = stack.length - 1; i >= 0; i--) { const c = stack[i]; res = { r: c.r * c.a + res.r * (1 - c.a), g: c.g * c.a + res.g * (1 - c.a), b: c.b * c.a + res.b * (1 - c.a), a: 1 }; } return res; };
  const lowContrast = [];
  for (const e of all) {
    const txt = [...e.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join("");
    if (!txt) continue;
    const s = getComputedStyle(e);
    const fg = parse(s.color); if (!fg) continue;
    const op = Number(s.opacity) || 1;
    const bg = bgOf(e);
    const a = fg.a * op;
    const mix = { r: fg.r * a + bg.r * (1 - a), g: fg.g * a + bg.g * (1 - a), b: fg.b * a + bg.b * (1 - a) };
    const L1 = lum(mix), L2 = lum(bg);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(s.fontSize); const bold = Number(s.fontWeight) >= 700;
    const need = px >= 24 || (bold && px >= 18.66) ? 3 : 4.5;
    if (ratio < need) lowContrast.push(`${label(e)} ${ratio.toFixed(2)}<${need} ${px}px ${s.color}`);
  }
  const dateRe = /\d{1,2}\/\d{1,2}|20\d\d[-/]\d{1,2}|\d{1,2}:\d{2}|\d{1,2}月|資料日|更新/;
  const noDate = [...root.querySelectorAll(".card")].filter(vis).filter((c) => c.getBoundingClientRect().height > 80 && !dateRe.test(c.innerText || "")).map(label);
  return { docScrollW: document.documentElement.scrollWidth, overflow: overflow.slice(0, 30), trunc: trunc.slice(0, 30), empty, small: small.slice(0, 60), smallCount: small.length,
    lowContrast: lowContrast.slice(0, 60), lowContrastCount: lowContrast.length, noDate };
}

for (const scheme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, colorScheme: scheme, serviceWorkers: "block" });
  const page = await ctx.newPage();
  const pe = [];
  page.on("pageerror", (e) => pe.push(String(e)));
  await page.goto(`${base}/index.html`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForTimeout(2500);
  const m = {};
  // 依 #main 捲動分段截圖（最多 n 張）
  const shots = async (name, n = 5) => {
    const total = await page.evaluate(() => { const mm = document.getElementById("main"); mm.scrollTop = 0; return { h: mm.scrollHeight, c: mm.clientHeight }; });
    const steps = Math.min(n, Math.max(1, Math.ceil(total.h / (total.c - 80))));
    for (let i = 0; i < steps; i++) {
      await page.evaluate((y) => { document.getElementById("main").scrollTop = y; }, i * (total.c - 80));
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(out, `${name}_${scheme}_${i + 1}.png`) });
    }
    await page.evaluate(() => { document.getElementById("main").scrollTop = 0; });
  };
  // 今日
  await page.waitForTimeout(1500);
  await shots("home", 6);
  m.home = await page.evaluate(audit, "#scr-home");
  // 研究室
  await page.click('#nav button[data-scr="lab"]');
  await page.waitForFunction(() => document.querySelectorAll("#lab-deep-list .lab-deep").length > 0, null, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await shots("lab", 8);
  m.lab = await page.evaluate(audit, "#scr-lab");
  m.lab.deepCards = await page.evaluate(() => document.querySelectorAll("#lab-deep-list .lab-deep").length);
  // 交易 → 日誌
  await page.click('#nav button[data-scr="trade"]');
  await page.waitForTimeout(1500);
  await shots("trade", 4);
  m.trade = await page.evaluate(audit, "#scr-trade");
  await page.click('#trade-tabs button[data-sub="journal"]');
  await page.waitForTimeout(1500);
  await shots("journal", 4);
  m.journal = await page.evaluate(audit, "#scr-journal");
  // 右上設定
  await page.click("#hdr-settings");
  await page.waitForTimeout(1500);
  await shots("settings", 6);
  m.settings = await page.evaluate(audit, "#scr-settings");
  m.header = await page.evaluate(audit, "header.top");
  // 個股研究分頁
  for (const code of ["1303", "3661", "4977"]) {
    await page.evaluate((c) => openStock(c), code);
    await page.waitForTimeout(2500);
    await page.click('#stock-tabs button[data-sub="research"]').catch(() => {});
    await page.waitForTimeout(3000);
    await shots(`stock${code}_research`, 6);
    m[`stock${code}`] = await page.evaluate(audit, "#scr-stock");
  }
  m.pageerrors = pe.slice(0, 5);
  metrics[scheme] = m;
  await ctx.close();
}
await close();
fs.writeFileSync(path.join(out, "metrics.json"), JSON.stringify(metrics, null, 2));
for (const [s, m] of Object.entries(metrics)) {
  for (const [k, v] of Object.entries(m)) {
    if (!v || typeof v !== "object" || Array.isArray(v)) continue;
    console.log(`${s}/${k}: 溢出${v.overflow?.length} 截斷${v.trunc?.length} 空白${v.empty?.length} 小按鈕${v.smallCount} 低對比${v.lowContrastCount} 無日期卡${v.noDate?.length} docW=${v.docScrollW}${v.error ? " " + v.error : ""}`);
  }
  console.log(`${s} pageerrors: ${m.pageerrors.length}`);
}
