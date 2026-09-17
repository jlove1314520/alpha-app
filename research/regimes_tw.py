# -*- coding: utf-8 -*-
"""台股多空制度窗口（2026-09-18 總司令裁示【改為多軌並行＋牛熊制度驗證】二.(a)）。

**為什麼要有這支腳本**：總司令原話「Cowork 憑印象記得大約有六段：2008、
2011、2015、2018Q4、2020、2022——這是印象不是資料，實際窗口一律以程式
算出的為準，不准引用這串數字」。這裡從 TAIEX 實際收盤序列算，不用任何
人記憶中的年份清單當輸入或對照基準。

**判準（總司令原話，寫死後不得事後調整）**：峰谷法，從前波高點算起，
跌幅 ≥20% 視為空頭（這是業界常見的「熊市」操作型定義，例如標普/道瓊
財經媒體常用的門檻，不是本專案自創）。**總司令原話只定義了空頭的門檻，
沒有定義「空頭何時結束、下一段多頭何時開始」——這裡採用對稱版本
（trough起算反彈達+20%即視為空頭結束、新一段多頭開始），是這套
peak-trough方法論的標準慣例（不是本專案自創的門檻，是同一套20%規則
對稱套用到兩個方向），寫死後同樣不得事後調整。**

**演算法（標準peak-to-trough，全樣本回顧式，非即時判斷）——第一版
bug記錄（誠實揭露，不悄悄改掉重跑）**：第一版把「空頭結束」定義成
「收盤價重新收復到空頭段起點那個peak的原始價位」，實測結果離譜到
一眼看穿：2000年那次下歷經跌到2001年低點3446點後，因為要等到重新
漲回2000年高點10202點才算「收復」，而TAIEX直到2017年才真的漲回那個
價位，於是2008金融海嘯（-58%）、2011歐債、2015中國股災、2018Q4貿易戰
這幾段**全部被吞進同一個長達17年的「空頭」裡**，完全違反常識。**改用
對稱版本**：
1. 多頭狀態：追蹤自上一個trough以來的running peak。收盤價相對這個peak
   跌幅達到-20%，這個peak的日期定為空頭段起點，轉為空頭狀態。
2. 空頭狀態：追蹤自空頭起點以來的running trough（最低點）。收盤價相對
   這個trough反彈達到+20%，這個trough的日期定為空頭段終點／下一段
   多頭段起點，轉為多頭狀態，peak追蹤從這個反彈點重新起算。
3. 資料結尾時仍在途中（空頭尚未反彈+20%、或多頭段尚未觸發下一次-20%
   跌幅）的最後一段，誠實標記為「未完整走完」，用資料結尾當暫時結算點。
4. 這是**歷史回顧式的描述性regime分段**，不是即時交易訊號——用來把
   既有策略回測結果拆成「這段策略在哪個制度下表現如何」，不是拿來預測
   未來何時進入空頭。

**資料源**：`research/data/raw/TaiwanStockPrice__TAIEX__2000-01-01__
2024-12-31.parquet`（既有本機快取，FinMind額度已滿載2026-09-18當下
無法重新請求，直接讀parquet不經過`finmind_client.load_dev()`的快取比對
邏輯，零新增API呼叫）。涵蓋2000-01-04~2024-12-31，橫跨總司令印象裡
提到的全部年份（2008/2011/2015/2018/2020/2022）。

輸出：`research/REGIME_CONDITIONS.md`新增「台股多空制度窗口（程式算出，
鎖定版）」章節；`research/data/regimes_tw.json`（gitignored，機器可讀版）。

跑法：`python research/regimes_tw.py`（純本機計算，零外部請求，零成本，
可重複執行——但若重跑，輸出以第一次鎖定的版本為準，見docstring最後
一段的鎖定規則）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = Path(__file__).parent / "data" / "raw" / "TaiwanStockPrice__TAIEX__2000-01-01__2024-12-31.parquet"
OUT_JSON = Path(__file__).parent / "data" / "regimes_tw.json"
OUT_MD = Path(__file__).parent / "REGIME_CONDITIONS.md"
TZ = timezone(timedelta(hours=8))

BEAR_DRAWDOWN_THRESHOLD = -0.20  # 總司令原話，寫死，不得事後調整
BULL_RALLY_THRESHOLD = 0.20      # 對稱版本的空頭結束門檻，見上方docstring說明


def compute_regimes(prices: pd.Series) -> list[dict]:
    """`prices`：以日期為index、由舊到新排序的收盤價Series。回傳segments清單，
    每筆為{"type": "bull"/"bear", "start", "end", "start_price", "end_price",
    "return_pct", "complete"}。演算法見模組docstring（對稱版peak-trough，
    trough起算反彈+20%才算空頭結束，不是回到原始高點）。
    """
    dates = prices.index
    vals = prices.values
    n = len(vals)
    segments = []

    state = "bull"
    peak_price, peak_date = vals[0], dates[0]
    trough_price, trough_date = vals[0], dates[0]
    bull_start_date = dates[0]
    bear_start_date = None

    for i in range(1, n):
        price, date = vals[i], dates[i]
        if state == "bull":
            if price > peak_price:
                peak_price, peak_date = price, date
            dd = price / peak_price - 1
            if dd <= BEAR_DRAWDOWN_THRESHOLD:
                # 多頭段結束於這次的peak（bear段起點＝peak本身，不是跌破當天）
                if peak_date > bull_start_date:
                    segments.append({
                        "type": "bull", "start": str(bull_start_date.date()),
                        "end": str(peak_date.date()),
                        "start_price": float(prices.loc[bull_start_date]),
                        "end_price": float(peak_price),
                        "return_pct": round((peak_price / prices.loc[bull_start_date] - 1) * 100, 2),
                        "complete": True,
                    })
                state = "bear"
                bear_start_date = peak_date
                trough_price, trough_date = price, date
        else:  # state == "bear"
            if price < trough_price:
                trough_price, trough_date = price, date
            rally = price / trough_price - 1
            if rally >= BULL_RALLY_THRESHOLD:
                # 空頭段結束於trough本身（對稱版：反彈+20%才確認trough已過，
                # 不是等回到空頭起點的原始高點——第一版就是踩到這個bug，
                # 見模組docstring「第一版bug記錄」）
                segments.append({
                    "type": "bear", "start": str(bear_start_date.date()),
                    "end": str(trough_date.date()),
                    "start_price": float(peak_price), "end_price": float(trough_price),
                    "return_pct": round((trough_price / peak_price - 1) * 100, 2),
                    "complete": True,
                })
                state = "bull"
                bull_start_date = trough_date
                peak_price, peak_date = prices.loc[trough_date], trough_date
                # peak追蹤從trough當天重新起算，本輪price若已高於trough就繼續往上更新
                if price > peak_price:
                    peak_price, peak_date = price, date

    # 資料結尾時的收尾段落（誠實標記未完整）
    if state == "bull" and dates[-1] > bull_start_date:
        segments.append({
            "type": "bull", "start": str(bull_start_date.date()), "end": str(dates[-1].date()),
            "start_price": float(prices.loc[bull_start_date]), "end_price": float(vals[-1]),
            "return_pct": round((vals[-1] / prices.loc[bull_start_date] - 1) * 100, 2),
            "complete": False,
        })
    elif state == "bear":
        segments.append({
            "type": "bear", "start": str(bear_start_date.date()), "end": str(dates[-1].date()),
            "start_price": float(peak_price), "end_price": float(trough_price),
            "return_pct": round((trough_price / peak_price - 1) * 100, 2),
            "complete": False,
        })
    return segments


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(f"{DATA_PATH} 不存在——FinMind額度已滿載，無法重新抓取，"
                          "需要總司令確認是否有其他TAIEX歷史快取來源")
    df = pd.read_parquet(DATA_PATH)
    df = df.sort_values("date")
    df["date"] = pd.to_datetime(df["date"])
    prices = df.set_index("date")["close"]

    segments = compute_regimes(prices)
    bear_segs = [s for s in segments if s["type"] == "bear"]
    bull_segs = [s for s in segments if s["type"] == "bull"]

    payload = {
        "meta": {
            "generated_at": datetime.now(TZ).isoformat(),
            "source": str(DATA_PATH.relative_to(ROOT)),
            "data_range": [str(prices.index.min().date()), str(prices.index.max().date())],
            "n_days": len(prices),
            "bear_drawdown_threshold": BEAR_DRAWDOWN_THRESHOLD,
            "method": "峰谷法：running peak起算跌幅達門檻即入空頭，空頭段終點＝期間最低點，"
                      "空頭段結束於收盤價重新收復段初高點；回顧式描述性分段，非即時訊號。"
                      "判準與門檻寫死，鎖定後不因結果不理想而事後調整。",
            "n_bear_segments": len(bear_segs), "n_bull_segments": len(bull_segs),
        },
        "segments": segments,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"資料範圍：{payload['meta']['data_range'][0]} ~ {payload['meta']['data_range'][1]}"
          f"（{payload['meta']['n_days']}個交易日）")
    print(f"共算出 {len(bear_segs)} 段空頭、{len(bull_segs)} 段多頭：\n")
    for s in segments:
        tag = "" if s["complete"] else "（未完整收復/未完整走完，以資料結尾當暫時結算點）"
        print(f"  {s['type']:>4}  {s['start']} ~ {s['end']}  "
              f"{s['start_price']:.2f}→{s['end_price']:.2f}（{s['return_pct']:+.2f}%）{tag}")

    md_lines = [
        "## 台股多空制度窗口（程式算出，鎖定版，2026-09-18 新增）",
        "",
        "**來源**：`research/regimes_tw.py`，從 TAIEX 實際收盤序列算出，"
        "峰谷法、跌幅 ≥20% 視為空頭，判準寫死，鎖定後不因結果不理想而事後調整。"
        "**不是憑印象列出的年份清單**——Cowork 印象中的「2008/2011/2015/2018Q4/"
        "2020/2022」六段只是猜測基準，下表才是實際算出的權威版本，兩者若有出入"
        "以下表為準。",
        "",
        f"資料範圍：{payload['meta']['data_range'][0]} ~ {payload['meta']['data_range'][1]}"
        f"（{payload['meta']['n_days']} 個交易日，`{payload['meta']['source']}`）。",
        "",
        "| 制度 | 起 | 迄 | 起點指數 | 迄點指數 | 報酬 | 備註 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in segments:
        note = "完整" if s["complete"] else "未完整收復/未完整走完（資料結尾暫時結算）"
        md_lines.append(f"| {'空頭' if s['type']=='bear' else '多頭'} | {s['start']} | {s['end']} | "
                         f"{s['start_price']:.2f} | {s['end_price']:.2f} | {s['return_pct']:+.2f}% | {note} |")
    md_lines += [
        "",
        "**鎖定規則**：本表由 `regimes_tw.py` 一次算出後鎖定，之後任何策略層試驗的"
        "「分制度表」都要對齊這張表切期間，**不得為了讓某個策略的空頭段表現好看"
        "而重新調整窗口邊界或跌幅門檻**。若未來有更長的 TAIEX 歷史快取可用（例如"
        "回補到 2000 年以前），重新產生新版本時要在這裡明確記錄「哪個版本、"
        "何時、為什麼重新產生」，不能悄悄覆蓋。",
        "",
    ]
    header = "\n".join(md_lines) + "\n\n---\n\n"
    if OUT_MD.exists():
        existing = OUT_MD.read_text(encoding="utf-8")
        OUT_MD.write_text(header + existing, encoding="utf-8")
    else:
        OUT_MD.write_text(header, encoding="utf-8")
    print(f"\n已寫入 {OUT_JSON.relative_to(Path(__file__).parent)}"
          f" 與 {OUT_MD.relative_to(Path(__file__).parent)}（新增章節於檔案最上方）")


if __name__ == "__main__":
    main()
