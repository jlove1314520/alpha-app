// 2026-10-14 先.九十六-R2：淺色模式「半透明混色底」上的文字 WCAG 對比掃描。
// 393×852、淺色、凍結時鐘、擋外部請求、不註冊 service worker（同 css_token_shots.mjs）。
// 做法：逐一找有直接文字的可見元素，從自己往上把每一層背景色（含 rgba 半透明）合成到
// 第一個不透明底為止（漸層底取每個色標各算一次、取最差），只列出「路徑上有半透明底」的組合。
// 文字色本身若是 rgba 也先跟合成底混色；元素 opacity 連乘進文字 alpha。
// 用法：node scripts/light_mix_contrast.mjs <標籤> [網址]
//   輸出 research/ux_shots/light_mix/<標籤>/report.json＋各分頁截圖（不進 repo）
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { launchGuarded } from "./pw_guard.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tag = process.argv[2] || "before";
const url = process.argv[3] || "http://localhost:8792/index.html";
const outDir = path.join(ROOT, "research", "ux_shots", "light_mix", tag);
fs.mkdirSync(outDir, { recursive: true });
const PAGES = ["home", "market", "picks", "trade", "journal", "settings"];

function scan() {
  const parse = (s) => {
    const m = /rgba?\(([^)]+)\)/.exec(s || "");
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const gradColors = (img) => (img.match(/rgba?\([^)]+\)/g) || []).map(parse);
  const over = (fg, bg) => { const a = fg[3]; return [0, 1, 2].map((i) => fg[i] * a + bg[i] * (1 - a)).concat(1); };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const hex = (c) => "#" + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, "0")).join("");
  const out = [];
  for (const el of document.querySelectorAll("body *")) {
    if (["SCRIPT", "STYLE", "SVG", "svg", "path", "NOSCRIPT"].includes(el.tagName)) continue;
    const txt = [...el.childNodes].filter((n) => n.nodeType === 3).map((n) => n.textContent.trim()).join("").trim();
    if (!txt) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden") continue;
    // 往上收集背景層
    const layers = []; let opacity = 1; let semi = false; let node = el; let semiSel = "";
    while (node && node.nodeType === 1) {
      const s = getComputedStyle(node);
      opacity *= parseFloat(s.opacity || "1");
      if (s.display === "none") { opacity = 0; break; }
      const bc = parse(s.backgroundColor);
      const gi = s.backgroundImage && s.backgroundImage.includes("gradient") ? gradColors(s.backgroundImage) : [];
      if (gi.length) {
        const opaque = gi.every((c) => c[3] >= 0.999);
        layers.push({ grad: gi });
        if (!opaque) { semi = true; semiSel = semiSel || (node.className || node.tagName); }
        if (opaque) break;
      }
      if (bc && bc[3] > 0) {
        layers.push({ color: bc });
        if (bc[3] < 0.999) { semi = true; semiSel = semiSel || (node.className || node.tagName); }
        else break;
      }
      node = node.parentElement;
    }
    if (!semi || opacity < 0.05) continue;
    // 由底往上合成（底端若沒有不透明層，用 body 的頁面底色）
    const pageBg = parse(getComputedStyle(document.body).backgroundColor) || [255, 255, 255, 1];
    let bases = [pageBg];
    for (let i = layers.length - 1; i >= 0; i--) {
      const L = layers[i];
      if (L.color) bases = bases.map((b) => over(L.color, b));
      else bases = L.grad.flatMap((g) => bases.map((b) => over(g, b)));
    }
    const fc = parse(cs.color);
    if (!fc) continue;
    let worst = null;
    for (const b of bases) {
      const f = over([fc[0], fc[1], fc[2], fc[3] * opacity], b);
      const q = ratio(f, b);
      if (!worst || q < worst.q) worst = { q, bg: hex(b), fg: hex(f) };
    }
    const fs = parseFloat(cs.fontSize), fw = parseInt(cs.fontWeight, 10);
    const large = fs >= 24 || (fs >= 18.66 && fw >= 700);
    out.push({ sel: (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).join(".") : el.tagName.toLowerCase()),
      semiLayer: String(semiSel).slice(0, 60), text: txt.slice(0, 24), color: cs.color, fontSize: fs, fontWeight: fw,
      ratio: Math.round(worst.q * 100) / 100, bg: worst.bg, fg: worst.fg, need: large ? 3 : 4.5 });
  }
  return out;
}

const { browser, close } = await launchGuarded(chromium, {}, { label: "light_mix_contrast", hardTimeoutMs: 6 * 60 * 1000 });
const report = {};
try {
  const ctx = await browser.newContext({ viewport: { width: 393, height: 852 }, deviceScaleFactor: 1,
    serviceWorkers: "block", colorScheme: "light", reducedMotion: "reduce" });
  await ctx.route("**/*", (r) => { const u = r.request().url(); return /^https?:\/\/(localhost|127\.0\.0\.1)[:/]/.test(u) ? r.continue() : r.abort(); });
  const page = await ctx.newPage();
  await page.clock.install({ time: new Date("2026-10-14T03:00:00Z") });
  await page.goto(url, { waitUntil: "load", timeout: 60000 });
  await page.clock.runFor(4000);
  await page.waitForTimeout(2500);
  const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
  if (theme !== "light") throw new Error(`data-theme 不是 light（${theme}）`);
  // 平常隱藏的警示橫幅／錯誤 log 也要量：強制顯示並塞一段示範字（只在這個測試頁面裡，不寫任何檔）
  const reveal = () => page.evaluate(() => {
    for (const id of ["auto-banner", "diag-banner", "claude-auth-banner", "paper-tracking-banner", "error-log", "report-extreme-warning"]) {
      const el = document.getElementById(id); if (!el) continue;
      el.style.display = "block"; if (el.tagName === "DETAILS") el.open = true;
      if (!el.textContent.trim()) el.textContent = `【掃描用示範字】${id}`;
    }
  });
  for (const g of PAGES) {
    await page.evaluate((g) => { const b = document.querySelector(`nav#nav button[data-scr="${g}"]`); if (b) b.click(); }, g);
    await page.clock.runFor(1500);
    await page.waitForTimeout(1500);
    const all = [];
    await reveal();
    for (const y of [0, 760, 1520, 2280]) {
      await page.evaluate((y) => { for (const el of [document.scrollingElement, document.getElementById("main"), document.getElementById("app")]) if (el) el.scrollTop = y; }, y);
      await page.waitForTimeout(250);
      if (y === 0) await page.screenshot({ path: path.join(outDir, `light-${g}.png`), animations: "disabled", caret: "hide" });
      all.push(...(await page.evaluate(scan)));
    }
    const seen = new Set();
    report[g] = all.filter((x) => { const k = `${x.sel}|${x.text}|${x.ratio}`; if (seen.has(k)) return false; seen.add(k); return true; });
    await page.evaluate(() => { for (const el of [document.scrollingElement, document.getElementById("main"), document.getElementById("app")]) if (el) el.scrollTop = 0; });
  }
  await ctx.close();
} finally { await close(); }
fs.writeFileSync(path.join(outDir, "report.json"), JSON.stringify(report, null, 1));
// 摘要：依（選擇器＋顏色＋底）去重，列出未達標的
const agg = new Map();
for (const [g, rows] of Object.entries(report)) for (const x of rows) {
  const k = `${x.sel}|${x.fg}|${x.bg}`;
  if (!agg.has(k)) agg.set(k, { ...x, pages: new Set() });
  agg.get(k).pages.add(g);
}
const rows = [...agg.values()].sort((a, b) => a.ratio - b.ratio);
let fail = 0;
for (const x of rows) {
  const bad = x.ratio < x.need;
  if (bad) fail++;
  console.log(`${bad ? "✗" : "✓"} ${x.ratio.toFixed(2)} need${x.need} ${x.sel} 「${x.text}」 字${x.fg} 底${x.bg} 半透明層=${x.semiLayer} ${x.fontSize}px [${[...x.pages].join(",")}]`);
}
console.log(`共 ${rows.length} 組混色底文字，未達標 ${fail} 組；輸出 ${outDir}`);
