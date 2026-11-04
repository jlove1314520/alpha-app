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
    (5, "#133／#136／#137／#384 借券賣出使用率", "19.89%", "個股組合（台股）", "F8（第 2 批，2015～2024，`research/backtest/` 引擎）"),
    (6, "#171 宇宙離散度", "18.42%", "描述性檢驗（非策略）", "不適用，跳過並遞補"),
    (7, "#282 產業金流加速度輪動（#73）", "16.86%", "產業輪動（台股）", "F9（第 2 批，2015～2024，`research/backtest/` 引擎，同 F8 抽樣宇宙）"),
    (8, "#430 R1 信用利差閘門", "15.13%", "ETF＋閘門", "F6"),
    (9, "#413 美股趨勢槓桿", "13.47%", "ETF 擇時", "F4"),
    (10, "#16／#17 f_quality_roe_stability 多空", "13.2%", "個股多空（台股）", "待第二批（含放空腿但書）"),
    (11, "#414／#243 0050 趨勢槓桿", "11.15%", "ETF 擇時", "F3"),
    (12, "#416 趨勢 1.5×／0.5× 跨市場", "5.46%", "ETF 擇時", "F3／F4 格子內含 L＝1.5、空頭曝險 0.5（相乘後為 0.75×，不完全相同）"),
    (13, "#247 已實現波動度 regime", "4.43%", "ETF 擇時", "F5"),
    (14, "#248 全市場廣度 regime", "3.27%", "ETF 擇時（需個股廣度）", "F10（第 2 批，2010-12～2024，0050 曝險）"),
    (15, "#483 ML 價量（2008～2012）", "2.88%", "個股模型", "待第二批"),
    (16, "#253～#261／#349 regime 替代 A（MA×k）", "2.37%", "ETF 擇時", "F3 格子已涵蓋（日均線＋空頭曝險）"),
    (17, "#249 全市場融資餘額 regime", "1.38%", "ETF 擇時（需融資資料）", "F11（第 2 批，2013-11～2024，0050 曝險）"),
    (18, "#11／#393 Weinstein 第二階段", "1.05%", "個股（台股）", "F12（第 2 批，2015～2024，`research/backtest/` 引擎，同 F8 抽樣宇宙）"),
    (19, "#283 core_tilt 市值前 50", "1.0%", "重建 0050 吻合度驗證（非策略）", "不適用，跳過並遞補（同 #171）"),
    (20, "#244／#250～#252 台指期 200MA", "0.25%", "期貨擇時", "F7（第 2 批）"),
]


def pct(x):
    return "—" if x is None or x != x else f"{x * 100:+.1f}%"


def main():
    files = sorted(HERE.glob("data/reaudit_optimized_batch*.json"))
    fams, bench, meta = [], None, None
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or "families" not in d:  # 略過引擎格斷點檔（_cells.json）
            continue
        bench = bench or d.get("benchmark_0050")
        meta = meta or d
        fams += [x for x in d.get("families", []) if "best_by_calmar" in x]
    fams.sort(key=lambda f: (not f["best_by_calmar"]["violates_survival"], f["best_by_calmar"]["calmar"]), reverse=True)
    L = []
    L.append("# REAUDIT_OPTIMIZED.md — 墓園重審：最優化版本總表（先.一五〇-1，Cowork 收件匣 039 已定案）\n")
    L.append("> **性質：樣本內最優化（描述性），不是判定。** 每一列都是「在 2003-07～2024-12 這段資料上掃參數後挑最好的一組」，"
             "所以數字**一定偏樂觀**（挑格子本身就是過擬合來源）；下一步照方針直接上紙上測試，用前向數據說話。"
             "2025 以後資料（holdout）本批完全沒讀。非投資建議。\n")
    L.append(f"資料期間：{meta['data_start']}～{meta['data_end']}；產生：{meta['generated_at']}；程式 `research/reaudit_optimized_batch1.py`（F1～F6）、`research/reaudit_optimized_batch2_tx.py`（F7，台指期連續合約，期間同樣從 2003-07-01 起以對齊無風險利率資料）、`research/reaudit_optimized_batch2_ssu.py`（F8，台股個股，期間 2015-01～2024-12，同 #133 抽樣宇宙 300 檔）、`research/reaudit_optimized_batch2_sector.py`（F9，同 F8 宇宙與期間）、`research/reaudit_optimized_batch2_breadth.py`（F10，期間 2010-12-31～2024-12-31，廣度暖身後才有訊號）、`research/reaudit_optimized_batch2_margin.py`（F11，期間 2013-11-25～2024-12-31，融資餘額 2012-05 起、暖身 52 週）、`research/reaudit_optimized_batch2_weinstein.py`（F12，同 F8 宇宙與期間）。**注意：各家族期間不同，綜合分數跨家族比較要看期間**（F1～F7 從 2003-07、F8／F9／F12 從 2015、F10 從 2011、F11 從 2013-11）。**曲線 png 與明細 JSON 在本機 `research/data/`（該目錄依 .gitignore 不進公開 repo），連結只在本機有效。**\n")
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
             "- F1～F7 是 ETF／指數／期貨層級，沒有個股下市與漲跌停問題；個股層級家族（第二批）用 `research/backtest/` 引擎處理下市與漲跌停。\n"
             "- F8（個股）：`research/backtest/` 引擎＝下一交易日成交、漲跌停鎖住不成交、缺價／下市照引擎處理、手續費＋0.3% 證交稅＋滑價；"
             "槓桿＝融資，借款部分 6.5%/年〔自行裁量〕、融資上限約 2.5×，**3× 台股個股實務上做不到、只當參考**；追繳以權益歸零近似（偏樂觀）。"
             "只做多頭鏡像半邊（買融券使用率最低），沒有放空腿。宇宙是當下抽樣的 300 檔，存活者偏誤未完全排除（偏樂觀）。"
             "交易次數＝個股賣出筆數、勝率＝賣出已實現損益>0 比例。對照組是同期加權價格指數（不含息）。\n"
             "- F9（產業金流加速度）：同 F8 引擎、宇宙、成本與融資假設；訊號＝三大法人產業淨買賣加速度（換股日當天收盤以前，隔日開盤成交），"
             "取前 top_frac 產業、產業內以產業加速度當分數挑前 N 檔等權。產業分類是 `data/company_info.json` 靜態快照（非 PIT，偏樂觀）；"
             "抽樣宇宙下每個產業只剩抽到的個股（和 #282 用全部成分股不同）。另外 N 檔名額常常湊不滿（選中的產業在抽樣裡個股不夠），沒用到的名額放現金，年化與回撤都因此偏低。\n"
             "- F10（全市場廣度）：回測、成本、槓桿、止損與 F3 同一套 simulate()；廣度＝本機 `data/raw` 4 位數代號個股站上 MA 的比例"
             "（今天仍在的名冊、未還原價，存活者偏誤未修正，偽影⑦）；另掃「月底才更新訊號」變體（#248 原版死在一年切換 9.5 次的成本）。"
             "**F10 第 1 名的但書**：它是 3× 槓桿、MDD −48.2%，只比天條一 50% 上限少 1.8 個百分點；回測期間 2010-12 起、**不含 2008 年**"
             "（廣度快取從 2010 起），遇到 2008 那種跌法很可能直接越線；只有 11 筆交易、1,152 格裡挑出來的，過擬合風險最高，不能當成它真的最好。\n"
             "- F11（全市場融資餘額）：同 F3／F10 的 simulate()；訊號＝TWSE MI_MARGN 週頻融資餘額 k 週成長率對自己的 expanding 百分位（PIT），"
             "週五收盤後已知、隔日生效；另掃原版沒測過的反向「去槓桿（成長率偏低）才降曝險」。"
             "**F11 第 1 名的但書**：它是 3× 槓桿＋反向「去槓桿」方向、MDD −44.3%；期間 2013-11 起是長多頭（0050 同期年化 +15.5%），"
             "**不含 2008**；防禦曝險 0.25 不歸零所以只算 5 筆、勝率 100% 沒有意義；2,304 格挑出來，過擬合風險高。"
             "只開 1×、無止損時最好的一組（12 週、去槓桿、月頻）年化 +15.7%、MDD −21.3%，和 0050 同期 +15.5%／−34.0% 比，主要好處在回撤。\n"
             "- F12（Weinstein 第二階段）：同 F8 引擎、宇宙、成本與融資假設；還原收盤 > MA_n 且 MA_n 比 10 日前高、以 60 日報酬排序，可選大盤 200 日均線閘門；引擎第一層出場線同步改成 MA_n。最好的一組沒開大盤閘門、2× 融資、組合止損 10%；2× 以上融資在台股個股屬實務上限邊緣，追繳以權益歸零近似（偏樂觀）；宇宙為抽樣 300 檔、存活者偏誤未完全排除。\n"
             "- 美股（VTI）結論附但書：**存活者偏誤未完全修正：已下市股約 97%（抽樣 55／57）無價格來源。**（VTI 為指數 ETF，影響較小，但書照附。）\n")
    out = HERE / "REAUDIT_OPTIMIZED.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"寫入 {out}（{len(fams)} 個家族）")


if __name__ == "__main__":
    main()
