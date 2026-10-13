# -*- coding: utf-8 -*-
"""手機實機回歸（2026-10-13 總司令【先.八十二】12）：iPhone 尺寸（390×844）逐頁截圖，比對前一版有沒有版面跑掉。

本機排程 AlphaPhoneRegression 每晚 22:30 跑線上網址（GitHub Pages 正式版）：
  每頁（首頁／市場／選股／交易／日誌／設定／個股 2330）截第一屏，並量版面：
    ① 整頁有沒有橫向溢出（scrollWidth > clientWidth，手機上會出現左右捲動）
    ② 本頁每張卡片的左緣與寬度（卡片「位置／寬度」跑掉＝版面跑掉；高度隨資料變，不比）
    ③ 第一屏縮成 39×84 灰階格，算「明顯變化的格子比例」（資料每天會變，所以門檻放寬，只抓整片變樣）
  跟前一晚的結果比：任一頁新出現橫向溢出、或有卡片左緣／寬度差 >8px、或畫面變化格子 >40% → 推播（Web Push）。
截圖與報告存 research/data/phone_regression/<日期>/（.gitignore），保留 14 天。自身失敗只記 log（十二節）。
用法：python scripts/phone_regression.py [--url 網址] [--no-push]
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TW = timezone(timedelta(hours=8))
OUT = ROOT / "research" / "data" / "phone_regression"
URL = "https://jlove1314520.github.io/alpha-app/"
VIEW = {"width": 390, "height": 844}
PAGES = ["home", "market", "picks", "trade", "journal", "settings", "stock"]
CARD_TOL_PX = 8
PIXEL_CELL_DIFF = 32
PIXEL_PCT_ALERT = 40.0
KEEP_DAYS = 14

LAYOUT_JS = """() => {
  const scr = document.querySelector('.screen.active') || document.querySelector('.screen:not([hidden])') || document.body;
  const de = document.documentElement;
  const cards = [...scr.querySelectorAll('.card')].filter(c => c.offsetParent !== null).slice(0, 40)
    .map((c, i) => { const r = c.getBoundingClientRect(); return { key: c.id || ('#' + i), x: Math.round(r.left), w: Math.round(r.width) }; });
  return { overflow_px: Math.max(0, de.scrollWidth - de.clientWidth), cards, title: document.title };
}"""


def capture(url: str, day_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            ctx = b.new_context(viewport=VIEW, device_scale_factor=2, is_mobile=True, has_touch=True,
                                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
                                           "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
            pg = ctx.new_page()
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(5000)
            for name in PAGES:
                try:
                    if name == "stock":
                        pg.evaluate("() => openStock('2330')")
                    else:
                        pg.evaluate(f"() => go('{name}')")
                    pg.wait_for_timeout(4000)
                    pg.evaluate("() => window.scrollTo(0, 0)")
                    shot = day_dir / f"{name}.png"
                    pg.screenshot(path=str(shot))
                    out[name] = {**pg.evaluate(LAYOUT_JS), "png": shot.name}
                except Exception as e:  # noqa: BLE001 — 單頁失敗只記這頁
                    out[name] = {"error": f"{type(e).__name__}: {e}"[:200]}
        finally:
            b.close()
    return out


def pixel_diff_pct(a: Path, b: Path) -> float | None:
    try:
        from PIL import Image
        import numpy as np
        x = np.asarray(Image.open(a).convert("L").resize((39, 84)), dtype=np.int16)
        y = np.asarray(Image.open(b).convert("L").resize((39, 84)), dtype=np.int16)
        return round(float((abs(x - y) > PIXEL_CELL_DIFF).mean() * 100), 1)
    except Exception:  # noqa: BLE001
        return None


def compare(cur: dict, prev: dict, cur_dir: Path, prev_dir: Path) -> list[dict]:
    issues = []
    for name in PAGES:
        c, p = cur.get(name) or {}, prev.get(name) or {}
        if c.get("error"):
            issues.append({"page": name, "kind": "capture_error", "detail": c["error"]})
            continue
        if not p or p.get("error"):
            continue
        why = []
        if c.get("overflow_px", 0) > 2:
            why.append(f"橫向溢出 {c['overflow_px']}px（前一版 {p.get('overflow_px', 0)}px）")
        pc = {x["key"]: x for x in p.get("cards") or []}
        moved = [f"{x['key']} 左緣 {pc[x['key']]['x']}→{x['x']}、寬 {pc[x['key']]['w']}→{x['w']}"
                 for x in c.get("cards") or [] if x["key"] in pc and
                 (abs(x["x"] - pc[x["key"]]["x"]) > CARD_TOL_PX or abs(x["w"] - pc[x["key"]]["w"]) > CARD_TOL_PX)]
        if moved:
            why.append("卡片位置／寬度跑掉：" + "；".join(moved[:3]) + (f" 等 {len(moved)} 張" if len(moved) > 3 else ""))
        pct = pixel_diff_pct(cur_dir / c["png"], prev_dir / p["png"]) if c.get("png") and p.get("png") else None
        if pct is not None and pct > PIXEL_PCT_ALERT:
            why.append(f"第一屏 {pct}% 的區塊明顯變樣")
        if why:
            issues.append({"page": name, "kind": "layout", "detail": "；".join(why), "pixel_diff_pct": pct})
    return issues


def main(argv: list[str], push=None, capture_fn=None) -> dict:
    url = argv[argv.index("--url") + 1] if "--url" in argv else URL
    day = datetime.now(TW).strftime("%Y-%m-%d")
    OUT.mkdir(parents=True, exist_ok=True)
    day_dir = OUT / day
    if day_dir.exists():
        shutil.rmtree(day_dir)
    day_dir.mkdir()
    t0 = time.time()
    cur = (capture_fn or capture)(url, day_dir)
    (day_dir / "layout.json").write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    prev_dirs = sorted(d for d in OUT.iterdir() if d.is_dir() and d.name < day and (d / "layout.json").exists())
    res = {"ts": datetime.now(TW).isoformat(timespec="seconds"), "url": url, "pages": len(cur),
           "seconds": round(time.time() - t0), "baseline": prev_dirs[-1].name if prev_dirs else None}
    if prev_dirs:
        prev = json.loads((prev_dirs[-1] / "layout.json").read_text(encoding="utf-8"))
        issues = compare(cur, prev, day_dir, prev_dirs[-1])
    else:
        issues = [{"page": n, "kind": "capture_error", "detail": v["error"]} for n, v in cur.items() if v.get("error")]
    res["issues"] = issues
    if issues and "--no-push" not in argv:
        body = "；".join(f"{i['page']}：{i['detail']}" for i in issues)[:380]
        try:
            if push is None:
                import web_push
                push = lambda t, b: web_push.send(t, b, kind="phone_regression")  # noqa: E731
            res["pushed"] = push(f"手機版面回歸：{len(issues)} 頁有差異", body).get("ok", 0)
        except Exception as e:  # noqa: BLE001
            res["push_error"] = type(e).__name__
    (day_dir / "report.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    with (OUT / "log.jsonl").open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({k: res[k] for k in ("ts", "pages", "seconds", "baseline")} | {"n_issues": len(issues)}, ensure_ascii=False) + "\n")
    cutoff = (datetime.now(TW) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for d in OUT.iterdir():
        if d.is_dir() and d.name < cutoff:
            shutil.rmtree(d, ignore_errors=True)
    print(json.dumps(res, ensure_ascii=False))
    return res


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        print(f"[warn] phone_regression 失敗：{type(e).__name__}: {e}")
    sys.exit(0)
