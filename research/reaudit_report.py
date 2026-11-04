# -*- coding: utf-8 -*-
"""先.一五〇-1：把 reaudit_optimized_batch*.json 彙整成 research/REAUDIT_OPTIMIZED.md（依綜合分數排名）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 前 20 個家族（依 TRIALS_LEDGER／TRIALS_REGISTRY 文字裡記錄的最高「年化 X%」排序後去重；抽取規則見 md 第 1 節）
TOP20 = [
    (1, "#64／#151 f_us_low_vol 小型股", "280%／121%", "個股橫斷面（美股）", "待第二批；原數字當時已判經濟上不可信"),
    (2, "#128／#144 f_us_value_bm", "121%", "個股橫斷面（美股）", "待第二批；原數字當時已判經濟上不可信"),
    (3, "#418／#420／#425 Bb-90 核心配置", "38.36%（#425 為 2025 OOS，不用）", "ETF 配置", "F1"),
    (4, "#424／#426／#428 危機閘門 × 槓桿 Bb-90", "22.23%（#428 為 2025 OOS，不用）", "ETF 配置＋閘門", "F2"),
    (5, "#133／#136／#137／#384 借券賣出使用率", "19.89%", "個股組合（台股）", "待第二批"),
    (6, "#171 宇宙離散度", "18.42%", "描述性檢驗（非策略）", "不適用，跳過並遞補"),
    (7, "#282 產業金流加速度輪動（#73）", "16.86%", "產業輪動（台股）", "待第二批"),
    (8, "#430 R1 信用利差閘門", "15.13%", "ETF＋閘門", "F6"),
    (9, "#413 美股趨勢槓桿", "13.47%", "ETF 擇時", "F4"),
    (10, "#16／#17 f_quality_roe_stability 多空", "13.2%", "個股多空（台股）", "待第二批（含放空腿但書）"),
    (11, "#414／#243 0050 趨勢槓桿", "11.15%", "ETF 擇時", "F3"),
    (12, "#416 趨勢 1.5×／0.5× 跨市場", "5.46%", "ETF 擇時", "F3／F4 格子內含 L＝1.5、空頭曝險 0.5（相乘後為 0.75×，不完全相同）"),
    (13, "#247 已實現波動度 regime", "4.43%", "ETF 擇時", "F5"),
    (14, "#248 全市場廣度 regime", "3.27%", "ETF 擇時（需個股廣度）", "待第二批"),
    (15, "#483 ML 價量（2008～2012）", "2.88%", "個股模型", "待第二批"),
    (16, "#253～#261／#349 regime 替代 A（MA×k）", "2.37%", "ETF 擇時", "F3 格子已涵蓋（日均線＋空頭曝險）"),
    (17, "#249 全市場融資餘額 regime", "1.38%", "ETF 擇時（需融資資料）", "待第二批"),
    (18, "#11／#393 Weinstein 第二階段", "1.05%", "個股（台股）", "待第二批"),
    (19, "#283 core_tilt 市值前 50", "1.0%", "個股組合", "待第二批"),
    (20, "#244／#250～#252 台指期 200MA", "0.25%", "期貨擇時", "待第二批"),
]


def pct(x):
    return "—" if x is None or x != x else f"{x * 100:+.1f}%"


def main():
    files = sorted(HERE.glob("data/reaudit_optimized_batch*.json"))
    fams, bench, meta = [], None, None
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        bench = bench or d.get("benchmark_0050")
        meta = meta or d
        fams += [x for x in d["families"] if "best_by_calmar" in x]
    fams.sort(key=lambda f: (not f["best_by_calmar"]["violates_survival"], f["best_by_calmar"]["calmar"]), reverse=True)
    L = []
    L.append("# REAUDIT_OPTIMIZED.md — 墓園重審：最優化版本總表（先.一五〇-1，Cowork 收件匣 039 已定案）\n")
    L.append("> **性質：樣本內最優化（描述性），不是判定。** 每一列都是「在 2003-07～2024-12 這段資料上掃參數後挑最好的一組」，"
             "所以數字**一定偏樂觀**（挑格子本身就是過擬合來源）；下一步照方針直接上紙上測試，用前向數據說話。"
             "2025 以後資料（holdout）本批完全沒讀。非投資建議。\n")
    L.append(f"資料期間：{meta['data_start']}～{meta['data_end']}；產生：{meta['generated_at']}；程式 `research/reaudit_optimized_batch1.py`。**曲線 png 與明細 JSON 在本機 `research/data/`（該目錄依 .gitignore 不進公開 repo），連結只在本機有效。**\n")
    L.append("## 0. 總表（依綜合分數＝年化報酬÷|最大回撤| 排名；MDD 超過 50% 的排最後並標天條一）\n")
    L.append("| 排名 | 家族 | 最好的一組參數 | 年化 | MDD | Sharpe | 勝率 | 交易次數 | 綜合分數 | 掃描格數（多重比較參考） | 曲線 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for i, f in enumerate(fams, 1):
        b = f["best_by_calmar"]
        keys = [k for k in b if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")]
        p = "，".join(f"{k}={b[k]}" for k in keys)
        flag = "（⚠️ VIOLATES_SURVIVAL）" if b["violates_survival"] else ""
        L.append(f"| {i} | {f['id']} {f['title']}{flag} | {p} | {pct(b['cagr'])} | {pct(b['mdd'])} | {b['sharpe']:.2f} | "
                 f"{pct(b['win_rate'])} | {b['trades']} | {b['calmar']:.2f} | {f['n_grid']}（其中 {f['n_violates']} 格 MDD>50%） | "
                 f"[png]({f["curve_png"].removeprefix("research/")}) |")
    if bench:
        L.append(f"| 對照 | 0050 買進持有（含息） | — | {pct(bench['cagr'])} | {pct(bench['mdd'])} | {bench['sharpe']:.2f} | — | — | "
                 f"{bench['calmar']:.2f} | — | — |")
    L.append("\n### 同一家族裡「MDD≤50% 前提下年化最高」的一組（給想看報酬上限的人）\n")
    L.append("| 家族 | 參數 | 年化 | MDD | Sharpe | 交易次數 |")
    L.append("|---|---|---|---|---|---|")
    for f in fams:
        b = f.get("best_by_cagr_within_mdd50")
        if not b:
            continue
        keys = [k for k in b if k not in ("cagr", "mdd", "sharpe", "trades", "win_rate", "calmar", "violates_survival")]
        L.append(f"| {f['id']} | {'，'.join(f'{k}={b[k]}' for k in keys)} | {pct(b['cagr'])} | {pct(b['mdd'])} | {b['sharpe']:.2f} | {b['trades']} |")
    L.append("\n## 1. 前 20 個家族怎麼挑的、目前做到哪\n")
    L.append("抽取規則〔自行裁量〕：TRIALS_LEDGER.md 表格列與 TRIALS_REGISTRY.jsonl 的 result／notes 文字裡，用「年化…X%」樣式抓數字，"
             "每列取最大值；457 列中只有 47 列有可抓的年化數字（其餘多是 IC／百分位檢定，沒記報酬）。同一機制的網格／重跑列併成一個家族。"
             "#425／#428 的高數字是 2025 年 OOS（holdout 期），只拿來排序、不拿來回測。\n")
    L.append("| 序 | 家族（來源試驗） | 當時記錄的最高年化 | 類型 | 本批狀態 |")
    L.append("|---|---|---|---|---|")
    for r in TOP20:
        L.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |")
    L.append("\n## 2. 回測規則（照實算）\n")
    L.append("- 訊號只用當天收盤以前看得到的資料，隔一個交易日生效；月頻閘門在月底收盤決定。\n"
             "- 槓桿＝每日再平衡合成（L×r −(L−1)×無風險利率 − 1%/年），同 #421；權益跌到 0 就停在 0。\n"
             "- 成本：台股腿買賣各 0.1% 滑價＋0.0855% 手續費、賣出加 0.1% ETF 證交稅；美股腿 0.3% 匯兌；配息扣 30% 預扣稅（沿用 #418）。\n"
             "- 止損：淨值從持倉高點回落超過 s 全數退現金，21 個交易日後才依訊號重新進場。\n"
             "- 勝率／交易次數定義：一次「從空手到有風險部位、再回到空手」算一筆；一直持有的配置型策略只算 1 筆（勝率意義有限）。\n"
             "- 本批全是 ETF／指數層級，沒有個股下市與漲跌停問題；個股層級家族（第二批）要用 `research/backtest/` 引擎處理下市與漲跌停。\n"
             "- 美股（VTI）結論附但書：**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。**（VTI 為指數 ETF，影響較小，但書照附。）\n")
    out = HERE / "REAUDIT_OPTIMIZED.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"寫入 {out}（{len(fams)} 個家族）")


if __name__ == "__main__":
    main()
