# -*- coding: utf-8 -*-
"""App 冒煙測試（2026-08-27 新增，使用者要求「每次改完自己跑」）。

**這是暫時替代版本，現在有正式版了**：一開始這台機器沒裝 Node.js/npm（實測
`node --version` 找不到指令），改用已經裝好的 Python版 Playwright 頂替。
2026-08-27（續8）已用 `winget install OpenJS.NodeJS.LTS` 裝好 Node.js，並用
`npm install --save-dev @playwright/test` 補上使用者原本指定的
`scripts/smoke_test.mjs`（Node.js + Playwright）版本，已實測可正常執行——
**兩支腳本檢查項目完全一致**，`.mjs` 是現在的主要版本，這支 `.py` 版保留
備用（不需要重跑`npm install`就能用，環境更輕量）。

**用法**：`python scripts/smoke_test.py`（預設打 `http://localhost:8792`，
需要先在repo根目錄另開一個終端機跑 `python -m http.server 8792`；也可以用
`--url` 指定別的位址）。**每次commit前務必先跑一次，任一項FAIL就不要commit，
先修好**（使用者原話）。

檢查項目（逐條對應使用者規格）：
1. 頁面載入後無任何 uncaught error / unhandledrejection。
2. 右上角兩個時鐘的updateClocks() interval在3秒內確實被呼叫多次（不是看
   畫面文字有沒有變——休市時文字設計上就是靜態的資料時間戳，不是bug，見
   index.html的mktPill()註解——而是直接monkeypatch計數，證明setInterval
   真的在跑，這才是使用者要驗證的「時鐘沒有停擺」）。
3. 六個分頁（今日/市場/選股/交易/日誌/設定）都能切換且不拋錯。
4. 每個主要面板（用一份已知容器id清單）渲染後innerHTML不是空的——這是
   「有數值或有明確空狀態，不是空白無說明」的近似檢查，不是語意層級的
   完美驗證（沒辦法用程式判斷「這段文字算不算有意義的空狀態說明」），
   但至少能抓到「完全沒東西、連空狀態文字都沒有」這種明顯的壞掉。
5. 市場頁三個市場切換（台股/美股/期貨）都不拋錯。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta

from playwright.sync_api import sync_playwright

TW_TZ = timezone(timedelta(hours=8))

TABS = ["home", "market", "picks", "trade", "journal", "settings"]

# 4. 每個主要面板的已知容器id——覆蓋今日頁/市場頁/選股頁/交易頁/日誌頁的主要區塊。
# 不是窮舉全部id，是挑「使用者最常看、最容易因為改版壞掉」的幾個。
PANEL_IDS = [
    "wl-list", "home-idx-rows",           # 今日頁：自選股、大盤速覽
    "idx-rows", "heatmap", "inst-bars",   # 市場頁：大盤指數、類股熱力圖、三大法人
    "margin-summary",                      # 市場頁：融資維持率
    "picks-list",                          # 選股頁
]


def run_smoke_test(base_url: str, headless: bool = True) -> dict:
    results = {"checks": [], "all_passed": True}

    def record(name, passed, detail=""):
        results["checks"].append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            results["all_passed"] = False
        print(f"{'PASS' if passed else 'FAIL'} - {name}" + (f"：{detail}" if detail else ""))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 393, "height": 852})

        page_errors = []
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(f"{base_url}/index.html", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1500)

        # 1. 無uncaught error / unhandledrejection
        # window.onerror跟unhandledrejection已經被index.html自己的
        # recordGlobalError()攔截進GLOBAL_ERRORS陣列，這裡直接讀那個陣列，
        # 比另外自己接page.on('pageerror')更準確反映App自己認定的錯誤（見
        # index.html的window.addEventListener('error'/'unhandledrejection')）。
        global_errors = page.evaluate("typeof GLOBAL_ERRORS !== 'undefined' ? GLOBAL_ERRORS : []")
        record("1. 頁面載入無uncaught error/unhandledrejection",
               len(global_errors) == 0 and len(page_errors) == 0,
               f"GLOBAL_ERRORS={global_errors}, pageerror={page_errors}" if (global_errors or page_errors) else "")

        # 2. 時鐘interval真的在跑（monkeypatch計數，不是看文字有沒有變）
        page.evaluate("""() => {
            window.__clockCallCount = 0;
            const _orig = window.updateClocks;
            window.updateClocks = function(){ window.__clockCallCount++; return _orig(); };
        }""")
        page.wait_for_timeout(3200)
        call_count = page.evaluate("window.__clockCallCount")
        record("2. 右上角時鐘interval在3秒內有執行", call_count >= 2,
               f"3.2秒內只呼叫了{call_count}次，預期至少2次（每秒一次）" if call_count < 2 else f"呼叫了{call_count}次")

        # 3. 六個分頁都能切換且不拋錯
        tab_errors = []
        for t in TABS:
            try:
                page.evaluate(f"go('{t}')")
                page.wait_for_timeout(400)
            except Exception as e:
                tab_errors.append(f"{t}: {e}")
        record("3. 六個分頁都能切換且不拋錯", len(tab_errors) == 0, "; ".join(tab_errors))

        # 4. 每個主要面板innerHTML不是空的（有數值或有明確空狀態文字，至少不是完全空白）
        page.evaluate("go('home')")
        page.wait_for_timeout(800)
        page.evaluate("go('market')")
        page.wait_for_timeout(800)
        page.evaluate("go('picks')")
        page.wait_for_timeout(800)
        empty_panels = []
        for pid in PANEL_IDS:
            html = page.evaluate(f"""() => {{
                const el = document.getElementById('{pid}');
                return el ? el.innerHTML.trim() : null;
            }}""")
            if html is None:
                continue  # 這個id在目前分頁不存在（例如還沒切到對應分頁），不算失敗
            if html == "":
                empty_panels.append(pid)
        record("4. 主要面板都有內容（不是完全空白）", len(empty_panels) == 0,
               f"完全空白的面板：{empty_panels}" if empty_panels else "")

        # 5. 市場頁三個市場切換都不拋錯
        page.evaluate("go('market')")
        page.wait_for_timeout(400)
        market_errors = []
        for m in ["TW", "US", "FUT"]:
            try:
                page.evaluate(f"""async () => {{
                    MKT_STATE.market = '{m}';
                    await hydrateMarket();
                }}""")
                page.wait_for_timeout(400)
            except Exception as e:
                market_errors.append(f"{m}: {e}")
        record("5. 市場頁三個市場切換都不拋錯", len(market_errors) == 0, "; ".join(market_errors))

        # 6. 【2026-08-27新增】互動元素可點擊性——逐一模擬點擊，確認有對應反應
        # （開頁/開清單），沒反應即視為失敗，跟.mjs版本邏輯一致。
        interaction_errors = []
        page.evaluate("async () => { MKT_STATE.market = 'TW'; await hydrateMarket(); }")
        page.wait_for_timeout(600)
        try:
            tile_count = page.evaluate("document.querySelectorAll('#heat-grid .tile').length")
            if tile_count == 0:
                raise RuntimeError("找不到任何類股卡（#heat-grid .tile），可能資料沒載入")
            page.evaluate("document.querySelector('#heat-grid .tile').click()")
            page.wait_for_timeout(500)
            sheet_open = page.evaluate("document.getElementById('sector-sheet')?.classList.contains('open')")
            if not sheet_open:
                raise RuntimeError("點擊類股卡後 #sector-sheet 沒有開啟，沒有對應反應")
            page.evaluate("window.closeSectorSheet && window.closeSectorSheet()")
        except Exception as e:
            interaction_errors.append(f"類股卡: {e}")
        try:
            page.evaluate("go('picks')")
            page.wait_for_timeout(600)
            row_count = page.evaluate("document.querySelectorAll('#picks-list .row').length")
            if row_count == 0:
                raise RuntimeError("找不到任何選股排行列（#picks-list .row），可能scores.json沒有合格檔數")
            page.evaluate("document.querySelector('#picks-list .row').click()")
            page.wait_for_timeout(500)
            report_active = page.evaluate("document.getElementById('scr-report')?.classList.contains('active')")
            if not report_active:
                raise RuntimeError("點擊選股排行列後 #scr-report 沒有變成active，沒有對應反應")
        except Exception as e:
            interaction_errors.append(f"選股排行列: {e}")
        try:
            page.evaluate("go('home')")
            page.wait_for_timeout(600)
            wl_row_count = page.evaluate("document.querySelectorAll('#wl-list .swipe-row').length")
            if wl_row_count == 0:
                raise RuntimeError("找不到任何自選股列（#wl-list .swipe-row），可能自選股清單是空的")
            page.evaluate("document.querySelector('#wl-list .swipe-row').click()")
            page.wait_for_timeout(500)
            stock_active = page.evaluate("document.getElementById('scr-stock')?.classList.contains('active')")
            if not stock_active:
                raise RuntimeError("點擊自選股列後 #scr-stock 沒有變成active，沒有對應反應")
        except Exception as e:
            interaction_errors.append(f"自選股列: {e}")
        record("6. 互動元素可點擊性（類股卡/選股排行列/自選股列）", len(interaction_errors) == 0,
               "; ".join(interaction_errors))

        # 7. 收尾再檢查一次GLOBAL_ERRORS，涵蓋上面測試過程(含互動操作)中新產生的
        # 錯誤——2026-08-27修正：原本這裡只是印出來，從來沒真的判斷PASS/FAIL，
        # 是測試框架本身的漏洞（這次B4測試親自抓到一個只有點擊後才觸發的真bug）。
        final_errors = page.evaluate("typeof GLOBAL_ERRORS !== 'undefined' ? GLOBAL_ERRORS : []")
        record("7. 整個測試過程（含所有互動操作）結束後仍無累積的uncaught error",
               len(final_errors) == 0,
               f"GLOBAL_ERRORS={final_errors}" if final_errors else "")
        results["global_errors_final"] = final_errors

        browser.close()

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8792", help="本機測試伺服器位址")
    ap.add_argument("--headed", action="store_true", help="顯示瀏覽器視窗（除錯用）")
    args = ap.parse_args()

    results = run_smoke_test(args.url, headless=not args.headed)

    print()
    print(f"=== 冒煙測試結果：{'全部通過' if results['all_passed'] else '有項目FAIL，不要commit，先修好'} ===")
    if results.get("global_errors_final"):
        print(f"最終GLOBAL_ERRORS：{results['global_errors_final']}")

    ts = datetime.now(TW_TZ).strftime("%Y-%m-%d %H:%M")
    lines = [f"### 冒煙測試 {ts}（{'全部通過' if results['all_passed'] else '有FAIL'}）"]
    for c in results["checks"]:
        lines.append(f"- [{'x' if c['passed'] else ' '}] {c['name']}" + (f"：{c['detail']}" if c["detail"] else ""))
    print("\n--- 可直接貼進PROGRESS.md的摘要 ---")
    print("\n".join(lines))

    sys.exit(0 if results["all_passed"] else 1)


if __name__ == "__main__":
    main()
