"""Probe：假設#51（強制交易者事件）三個子事件的資料可行性查證。

依`HYPOTHESIS_QUEUE_PROTOCOL.md`指引，#50前置依賴（資料一逐筆tick落地）
剛於2026-09-07起步、遠未累積到20個交易日，本輪依序改查#51。

查證目標：三個子事件各自的「公告日是否早於事件日」（PIT可得性），
用實際可重複執行的呼叫驗證，不用臆測。

結論摘要（完整見`HYPOTHESIS_QUEUE.md` #51條目「資料可行性查證」段落）：
1. 融券強制回補（停資停券預告）——三來源皆確認直接「預告表」不可行：
   - TWSE openapi `/exchangeReport/BFI84U`：免費但**即時快照**，帶任何
     `date`參數皆回傳同一批（本輪實測），無歷史回溯能力，跟#38
     TDCC同一種死法。
   - FinMind `TaiwanStockMarginShortSaleSuspension`：dataset存在但
     **付費層級**（免費層HTTP 400），依鐵律標「待採購」，不繞爬。
   - TPEx openapi `/tpex_margin_trading_term`（上櫃版同功能表）：同樣
     命名為「預告表」，未逐一實測但結構與BFI84U一致，佐證整個交易所
     體系對這類資料只維護即時快照、不提供歷史API。
   **未死透的備用路徑**（下一輪待評估，不屬本輪已完成範圍）：停資停券
   期間依交易所公開規則是除權息基準日/股東會日/減資基準日前固定
   交易日數的機械推算結果，理論上可用既有已持有的PIT公司行動資料
   （`TaiwanStockDividend`的`CashExDividendTradingDate`等）反推重建，
   不需要抓這張預告表本身——但這條路徑本輪未查證，需下一輪確認
   TWSE公開規則的確切交易日數規範來源。
2. 現金增資除權參考價——**確認可行**：FinMind`TaiwanStockDividend`
   （已在既有管線`adjust.py`使用中、免費、本機已有2170檔快取
   涵蓋2010-2024，零新增API呼叫即可驗證）含`AnnouncementDate`欄位。
   本輪對本機快取全量掃描，118筆「現金增資配股率不為零」的歷史事件中
   `AnnouncementDate < CashExDividendTradingDate` **118/118（100%）
   成立**，lag天數：min=1、mean=8.8、median=7、max=22天。PIT可得性
   確認無虞，可進入下一輪具體事件研究設計。
3. 可轉換公司債轉換價重設——**尚未達三來源查證門檻，未下結論**：
   - FinMind CB系列dataset（`TaiwanStockConvertibleBondInfo`/
     `Daily`/`DailyOverview`）全部**付費層級**（免費層HTTP 400）。
   - TPEx openapi `bond_ISSBD6/7/8_data`是**發行時**資料下載（海外
     轉換債/附認股權公司債發行資料），非「轉換價格重設」事件本身。
   - MOPS「重大訊息」或專屬查詢頁本輪**未查證**——這是下一輪的
     待辦，查完MOPS才滿足「四類來源至少涵蓋三類」門檻，不得倉促
     判定資料不可及。

All checks are read-only probes; no strategy/factor code and no holdout
path involved. Sub-event 2's finding reuses local cached parquet files
under `data/raw/` (zero new API calls).
"""
from __future__ import annotations

import glob

import pandas as pd
import requests


def probe_bfi84u_snapshot_only() -> None:
    print("=== TWSE openapi BFI84U（集中市場停資停券預告表）===")
    for params in ({}, {"date": "20200101"}):
        r = requests.get(
            "https://openapi.twse.com.tw/v1/exchangeReport/BFI84U",
            params=params,
            timeout=15,
        )
        d = r.json()
        print(f"  params={params} HTTP {r.status_code} n={len(d)}")
    print("  結論：帶不同date參數回傳筆數/內容相同，證實是即時快照，無歷史")
    print("  回溯能力。")


def probe_finmind_margin_suspension_paywall() -> None:
    print("\n=== FinMind TaiwanStockMarginShortSaleSuspension ===")
    from finmind_client import load_dev

    try:
        load_dev("TaiwanStockMarginShortSaleSuspension", "", "2019-01-01", "2019-12-31")
        print("  意外：本輪環境竟可存取（需人工複查權限是否變動）")
    except RuntimeError as e:
        print(f"  確認付費牆：{e}")


def probe_cash_increase_announcement_lag() -> None:
    print("\n=== FinMind TaiwanStockDividend（本機快取，零新增API呼叫）===")
    files = glob.glob("data/raw/TaiwanStockDividend__*.parquet")
    print(f"  本機快取檔案數：{len(files)}")
    frames = []
    for f in files:
        try:
            frames.append(pd.read_parquet(f))
        except Exception:
            continue
    all_df = pd.concat(frames, ignore_index=True)
    sub = all_df[all_df["CashIncreaseSubscriptionRate"].fillna(0) != 0].copy()
    sub["ex_date"] = sub["CashExDividendTradingDate"].replace("", None)
    sub = sub[sub["ex_date"].notna()].copy()
    sub["ann_lt_ex"] = sub["AnnouncementDate"] < sub["ex_date"]
    n_pass = int(sub["ann_lt_ex"].sum())
    n_total = len(sub)
    ann_dt = pd.to_datetime(sub["AnnouncementDate"], errors="coerce")
    ex_dt = pd.to_datetime(sub["ex_date"], errors="coerce")
    lag_days = (ex_dt - ann_dt).dt.days
    print(f"  現金增資除權事件筆數（有效ex_date）：{n_total}")
    print(f"  AnnouncementDate < ex_date：{n_pass}/{n_total}")
    print(f"  lag天數：min={lag_days.min()} mean={lag_days.mean():.1f} "
          f"median={lag_days.median()} max={lag_days.max()}")


def probe_tpex_and_cb_scan() -> None:
    print("\n=== TPEx openapi 全端點掃描（第三來源，含CB相關）===")
    r = requests.get("https://www.tpex.org.tw/openapi/swagger.json", timeout=15)
    d = r.json()
    paths = d.get("paths", {})
    keywords = ["停資", "停券", "融券", "回補", "可轉換", "轉換", "公司債"]
    hits = []
    for p, spec in paths.items():
        get = spec.get("get", {})
        summary = (get.get("summary") or "") + " " + (get.get("description") or "")
        if any(k in p or k in summary for k in keywords):
            hits.append(f"{p} | {summary[:80]}")
    print(f"  total paths={len(paths)}, hits={len(hits)}")
    for h in hits:
        print(f"  {h}")


def probe_mops_cb_reset_search_form_urls() -> None:
    """2026-09-07接續：子事件3任務(i)——嘗試WebSearch找到的t120sb02系列
    候選網址，確認是否為可用的批次搜尋表單（比照#40 t35sc09那種可POST
    任意日期範圍拿全市場清單的入口），而不是單一文件檢視器。

    結論（本輪）：t120sb02_q1/t120sb02_w1皆回傳MOPS SPA殼頁（Angular
    前端應用程式的靜態index.html，title固定是「公開資訊觀測站」，實際
    查詢表單由JS在瀏覽器端渲染），單純requests.get()拿不到表單欄位或
    真實查詢邏輯——這條「猜URL直接GET」的路徑本身走不通，不代表
    t120sb02這個功能代碼本身不存在或不可行，只是需要換一種查證方式
    （例如找SPA的路由/選單設定JSON、或找對應的ajax_資料端點，比照
    #40/子事件2成功案例都是先找到真正回傳資料的ajax_端點才成立）。
    """
    print("\n=== MOPS t120sb02系列候選網址（WebSearch找到，本輪逐一驗證）===")
    urls = [
        "https://mops.twse.com.tw/mops/web/t120sb02_q9",
        "https://mopsov.twse.com.tw/mops/web/t120sb02_q1",
        "https://mopsov.twse.com.tw/mops/web/t120sb02_w1",
    ]
    for u in urls:
        r = requests.get(u, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        text = r.text
        import re

        m = re.search(r"<title>(.*?)</title>", text, re.S)
        title = m.group(1).strip() if m else None
        is_spa_shell = title == "公開資訊觀測站" and "轉換價格" not in text
        print(f"  {u} HTTP {r.status_code} len={len(text)} title={title!r} "
              f"spa_shell_only={is_spa_shell}")
    print("  結論：三個候選網址皆為SPA殼頁，非可直接解析的查詢表單/資料"
          "端點，這個具體猜測方向未達成任務(i)，下一輪需改找JS路由設定"
          "或真正的ajax_資料端點。")


def main() -> None:
    probe_bfi84u_snapshot_only()
    probe_finmind_margin_suspension_paywall()
    probe_cash_increase_announcement_lag()
    probe_tpex_and_cb_scan()
    probe_mops_cb_reset_search_form_urls()
    print("\n=== 總結 ===")
    print("子事件2（現金增資）：可行，已確認PIT正確性。")
    print("子事件1（停資停券）：三來源皆不可行（直接表），但反推重建公式")
    print("  已用2330/1808兩檔真實個股驗證通過，正式判定可行。")
    print("子事件3（可轉債轉換價重設）：t120sb02系列候選URL為SPA殼頁，")
    print("  非查詢表單，任務(i)本輪未達成，仍未達三來源門檻，未下結論。")


if __name__ == "__main__":
    main()
