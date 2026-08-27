"""題材動能榜（scoring-momentum-v1）：JSON-only上線評分路徑，2026-08-27新增。

**背景（使用者裁示，策略層面重要決定，逐字照抄不重新詮釋）**：
「AI供應鏈族群（光通訊/矽光子/CoWoS先進封裝/散熱/PCB/CCL/探針卡/廠務設備/
被動元件/BBU電供/AOI/低軌衛星/伺服器/導線架/連接器/矽晶圓/ASIC-IP/記憶體/
特用化學/電線電纜/BMC/機器人/石英/PMIC）幾乎不上榜。根因不是bug，是權重
設計：財報回顧類（earnings_growth 18%+revenue_momentum 18%+growth_quality
12%）=48%；valuation_adj(PEG) 12%會因為股價漲多、PE升高而扣分→反向懲罰
題材股；合計60%權重在對抗『股價領先財報』的成長題材股；唯二能捕捉這類
股票的analyst(8%)與catalyst(8%)恰好都未實作。」

**決定：拆成兩個獨立榜單，不要用單一分數通吃**——這支腳本是第二個榜單
「題材動能榜」，跟`generate_scores_live.py`（價值成長榜，完全不動）物理
分離、各自版本控管（見`score_live_momentum.py`）。輸出寫`scores_momentum.json`
（repo根目錄，跟`scores.json`分開檔案，不互相覆蓋）。

**因子設計（使用者原話逐條列出，這裡是JSON-only路徑下的具體實作）**：
- `relative_strength`（相對強度/價格動能）：近20/60日報酬率相對大盤
  （`data/market_tw.json`的taiex.sparkline/sparkline_60d），兩個窗口取平均。
- `volume_breakout`（量能突破）：今日成交值相對自身近20日均量倍數
  （`data/price_history.json`的turnover欄位）。
- `chip_concentration`（籌碼集中）：法人連續買超天數+買超張數加總
  （`data/stock_detail.json`的institutional.history，目前每日排程才剛開始
  累積，可能只有1-5天，隨時間自然加深）。**簡化揭露**：用「買超張數」而非
  使用者原話「買超佔股本比」——沒有現成的已發行股數資料源，是刻意的範圍
  縮減，不是忘記做（跟generate_scores_live.py的chips因子同一個既有簡化）。
- `group_breadth`（族群齊漲度）：同產業上漲家數比例，扣掉「漲幅集中前2檔」
  的濃縮度懲罰（用`data/company_info.json`的industry分類+
  `data/quotes_all_tw.json`的change_pct分組計算）。
- `sector_capital_flow`（產業資金流入）：產業成交值佔全市場比例的近期趨勢
  （近5日均值 vs 再前15日均值，用`data/price_history.json`90天turnover
  歷史+company_info.json的industry分組聚合算出）。
- **財報權重大幅調降，只當排除地雷用**：不計入加權總分，改成
  `financial_risk_flag`（最近財報虧損或營收年減劇烈惡化）獨立標記顯示，
  不是加分項。
- **估值不扣分**：完全不計算PE/PEG，題材股本來就貴，用PEG扣分等於自相矛盾
  （使用者原話）。

**【最重要，使用者原話，逐字照抄】**：「在回測完成前，兩個榜單頁面都要
標明：本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤。」
`index.html`的題材動能榜UI必須顯示這段話（跟價值成長榜共用同一段警語）。
BACKLOG.md的B16（兩榜回測驗證）已提升為P0，回測完成、使用者同意前，
這支腳本產生的分數不得被宣稱「有效」。

**跟generate_scores_live.py共用的部分**：同一份`data/fundamentals.json`+
`data/stock_detail.json`+`data/price_history.json`+`data/company_info.json`+
`data/quotes_all_tw.json`+`data/market_tw.json`，同一套流動性門檻
（`LIQUIDITY_FLOOR_20D_VALUE`，from score_v2.py，兩榜共用同一個常數，這是
使用者原話「兩榜共用同一份資料與同一套流動性門檻」的字面實作）。因子/權重
完全獨立，不共用score_v2.FACTOR_DEFS。
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from score_v2 import LIQUIDITY_FLOOR_20D_VALUE, _pct_score, _r
from score_live_momentum import load_frozen_weights_momentum

REPO_ROOT = Path(__file__).parent.parent
FUNDAMENTALS_PATH = REPO_ROOT / "data" / "fundamentals.json"
STOCK_DETAIL_PATH = REPO_ROOT / "data" / "stock_detail.json"
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
COMPANY_INFO_PATH = REPO_ROOT / "data" / "company_info.json"
QUOTES_ALL_TW_PATH = REPO_ROOT / "data" / "quotes_all_tw.json"
MARKET_TW_PATH = REPO_ROOT / "data" / "market_tw.json"
OUT_PATH = REPO_ROOT / "scores_momentum.json"
TW_TZ = timezone(timedelta(hours=8))

FACTOR_LABELS = {
    "relative_strength": "相對強度/價格動能",
    "volume_breakout": "量能突破",
    "new_high_breakout": "創新高",
    "volume_price_coordination": "量價配合度",
    "chip_concentration": "籌碼集中",
    "group_breadth": "族群齊漲度",
    "sector_capital_flow": "產業資金流入",
}
NEW_HIGH_WINDOW = 60  # "近60日內價格創階段高"，使用者原話
VOL_AVG_WINDOW = 20
SECTOR_FLOW_RECENT_DAYS = 5
SECTOR_FLOW_PRIOR_DAYS = 15
FINANCIAL_RISK_REVENUE_YOY_FLOOR = -0.30  # 營收年減超過這個比例才視為地雷警示
# 2026-08-27新增：company_info.json的industry分類裡，這幾種不是「個股」，是
# ETF/ETN/存託憑證/大盤指數本身等，不該混進個股動能排行榜（實測發現槓桿型
# ETF的量能/動能因子數字特別極端，會洗掉真正的個股）。
NON_STOCK_INDUSTRIES = {
    "ETF", "ETN", "上櫃ETF", "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
    "受益證券", "存託憑證", "Index", "大盤", "所有證券",
}
# 2026-08-27新增：有些ETF代碼（例如00411A/00987D）根本不在company_info.json
# 裡（該檔案讀FinMind TaiwanStockInfo快取，可能還沒收錄這些較新上市的ETF），
# 光靠industry分類過濾不夠——台股/上櫃證券代碼慣例：0開頭(00XXX)保留給ETF/
# ETN/受益證券，不是普通股票（普通股從1開頭的4位數代碼開始），用這個代碼
# 格式當補充過濾，不用等company_info.json收錄。
_NON_STOCK_CODE_PATTERN = re.compile(r"^00\d{2,4}[A-Z]?$")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"{path} 不存在——這支腳本只讀repo內已commit的JSON，不會自己去產生。")
    return json.loads(path.read_text(encoding="utf-8"))


def _has_calendar_gap(dates: list[str], max_ratio: float = 3.0) -> bool:
    """2026-08-28新增（真bug，B23實測親自抓到）：`len(price_rows)>=N`只保證
    「有N筆資料」，不保證這N筆是「最近N個連續交易日」——實測發現1,649/2,270檔
    （超過七成！）的price_history.json在90列的視窗裡藏著巨大的日曆天缺口
    （典型樣態：research端FinMind快取停在2024-12-31、後面緊接daily排程當天
    新增的1筆2026年資料，中間20個月完全空白）。用這種「表面上60列，其實
    只有2個真實交易日+58列一年多前舊資料」的視窗算報酬率/創新高，會算出
    荒謬的數字（實測2337算出「創新高+375%」，其實是拿2024年20元的股價跟
    2026年125元的股價相減，兩個時間點根本不相鄰）。這裡用「日曆天跨度是否
    遠超過trading-day筆數合理應該對應的天數」當守門：60個交易日正常對應
    約84個日曆天（含週末），這裡用3倍(約180天/半年)當寬鬆容忍度（涵蓋國定
    假日/連假），超過就判定為「這個視窗裡混進了不連續的舊資料」，回傳True
    讓呼叫端拒絕使用這個視窗（回傳None，不硬算一個可能是假訊號的數字）。"""
    if len(dates) < 2:
        return False
    d0 = datetime.strptime(dates[0], "%Y-%m-%d")
    d1 = datetime.strptime(dates[-1], "%Y-%m-%d")
    return (d1 - d0).days > len(dates) * max_ratio


def _relative_strength(price_rows: list[dict], taiex_20d: list[float], taiex_60d: list[float]) -> float | None:
    """2026-08-27修正（真bug，本機測試親自抓到：0/2374檔算出這個因子）：原本
    要求`len(taiex_20d)>=21`才計算「20日報酬率」，但`market_tw.json`的
    `taiex.sparkline`固定就是20個點（給App畫圖用的既有欄位，不為了這個因子
    改動它的長度）——用index[-1]和[-21]需要21個點，21一定大於20，這個條件
    永遠不成立，60日版本同理(要求61卻只有60個點)。改成用[-1]比[-20]/[-60]，
    即「近19/59個交易日」的報酬率，跟嚴格的「20/60個交易日」差1天，這個
    近似對動能因子的用途來說可忽略，不值得為了這1天去改動taiex.sparkline
    的既有長度定義。"""
    if len(price_rows) < 20:
        return None
    rows = sorted(price_rows, key=lambda r: r["date"])
    # 2026-08-27修正（P0 bug，使用者回報）：改用adj_close（還原權息收盤價，
    # 見price_history.json meta.backfill_note）——用原始close的話，除息當天
    # 跳空下跌會被這個因子誤判成真實下跌，除息季會系統性扭曲排名。舊資料
    # 若還沒有adj_close欄位（尚未套用過還原）就退回close，不會比修正前更差。
    closes = [r.get("adj_close", r["close"]) for r in rows]
    dates = [r["date"] for r in rows]
    parts = []
    # 2026-08-28新增：日曆缺口守門（見_has_calendar_gap()說明），20/60日兩腳
    # 各自獨立檢查各自用到的那段視窗，其中一腳有缺口就只跳過那一腳，不用
    # 整個因子都放棄（例如20日視窗是連續的、60日視窗混進舊資料，20日腳
    # 仍然可用）。
    if len(closes) >= 20 and len(taiex_20d) >= 20 and closes[-20] and taiex_20d[-20] and not _has_calendar_gap(dates[-20:]):
        stock_ret20 = closes[-1] / closes[-20] - 1
        mkt_ret20 = taiex_20d[-1] / taiex_20d[-20] - 1
        parts.append(stock_ret20 - mkt_ret20)
    if len(closes) >= 60 and len(taiex_60d) >= 60 and closes[-60] and taiex_60d[-60] and not _has_calendar_gap(dates[-60:]):
        stock_ret60 = closes[-1] / closes[-60] - 1
        mkt_ret60 = taiex_60d[-1] / taiex_60d[-60] - 1
        parts.append(stock_ret60 - mkt_ret60)
    if not parts:
        return None
    return sum(parts) / len(parts)


def _volume_breakout(price_rows: list[dict]) -> float | None:
    rows = [r for r in price_rows if r.get("turnover") is not None]
    if len(rows) < 6:
        return None
    rows = sorted(rows, key=lambda r: r["date"])
    # 2026-08-28新增：日曆缺口守門（見_has_calendar_gap()），避免均量被摻進
    # 舊資料稀釋/扭曲。
    if _has_calendar_gap([r["date"] for r in rows[-(VOL_AVG_WINDOW + 1):]]):
        return None
    today = rows[-1]["turnover"]
    window = rows[-(VOL_AVG_WINDOW + 1):-1] or rows[:-1]
    avg = sum(r["turnover"] for r in window) / len(window)
    if not avg:
        return None
    return today / avg


def _new_high_breakout(price_rows: list[dict]) -> float | None:
    """創新高因子（2026-08-28新增，B23第二步，使用者原話：「創新高＋量價配合度
    高→兩者相乘（最強組合）；創新高但量價配合度低→創新高因子分數打折，不讓
    假突破拿高分」——這裡先算「創新高強度」本身，跟量價配合度的聯動在
    build_rows()合併時處理，見該處說明）。今日adj_close相對「今日以前」
    NEW_HIGH_WINDOW日內最高adj_close的比值減1：正值＝今天真的創了新高，數值
    是突破幅度；負值＝還沒創新高，數值是離前波高點的距離（百分比，越接近0
    代表越接近前高）。用adj_close（還原權息收盤價）而非原始close，避免除息
    跳空被誤判成假的「創新低」。"""
    rows = sorted(price_rows, key=lambda r: r["date"])
    rows = [r for r in rows if r.get("adj_close", r.get("close")) is not None]
    if len(rows) < NEW_HIGH_WINDOW + 1:
        return None
    window_rows = rows[-(NEW_HIGH_WINDOW + 1):]
    if _has_calendar_gap([r["date"] for r in window_rows]):
        return None  # 見_has_calendar_gap()：這個視窗混進了不連續的舊資料，不硬算
    closes = [r.get("adj_close", r.get("close")) for r in window_rows]
    prior_high = max(closes[:-1])
    if not prior_high:
        return None
    return closes[-1] / prior_high - 1


def _volume_price_coordination(price_rows: list[dict]) -> tuple[float | None, list[str]]:
    """量價配合度因子（0-10分尺度，2026-08-28新增，B23第三步）。使用者原話
    逐條實作，門檻全部是經驗值、未經統計驗證（B24回測時要做±30%參數敏感度
    掃描，見weights_frozen_momentum.json的note）。

    **簡化揭露（誠實聲明，不是嚴謹技術分析）**：「突破段」/「回檔段」/
    「上漲段」/「前波高點」這幾個概念真正的技術分析需要更嚴謹的轉折點偵測
    演算法，這裡用簡化的操作型定義：
    - 突破段＝近60日收盤序列裡，從最後一天往前數，收盤價連續在60日高點97%
      以上的天數；突破前20日＝緊接在突破段開始前的20個交易日。
    - 回檔段＝從最後一天往前數，收盤價連續較前一日下跌的天數；上漲段＝
      緊接在回檔段開始前、收盤價連續不創新低的天數。
    回傳(raw_score, flags)——raw_score越高代表量價配合度越健康（會再經
    _pct_score()百分位化），flags是警訊字串list（可能為空，合併進該股的
    flags欄位顯示在UI）。資料不足20天就誠實回傳(None, [])，不是硬湊一個
    可能不可靠的數字。"""
    rows = sorted(price_rows, key=lambda r: r["date"])
    rows = [r for r in rows if r.get("adj_close", r.get("close")) is not None and r.get("volume") is not None]
    if len(rows) < 25:
        return None, []
    if _has_calendar_gap([r["date"] for r in rows]):
        return None, []  # 見_has_calendar_gap()：這批資料混進了不連續的舊資料，不硬算
    closes = [r.get("adj_close", r.get("close")) for r in rows]
    vols = [r["volume"] for r in rows]
    changes = [None] + [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    score = 0.0
    flags: list[str] = []

    # (a) 吸收比：近20日「上漲日均量÷下跌日均量」>1.3加分
    n = min(20, len(closes) - 1)
    idx0 = len(closes) - n
    up_vols = [vols[i] for i in range(idx0, len(closes)) if changes[i] and changes[i] > 0]
    down_vols = [vols[i] for i in range(idx0, len(closes)) if changes[i] and changes[i] <= 0]
    if up_vols and down_vols:
        avg_down = sum(down_vols) / len(down_vols)
        if avg_down and (sum(up_vols) / len(up_vols)) / avg_down > 1.3:
            score += 2.5

    # 60日高點 + 突破段判定（供b/d使用）
    window60 = closes[-60:] if len(closes) >= 60 else closes
    high60 = max(window60)
    near_high = [c >= high60 * 0.97 for c in window60] if high60 else [False] * len(window60)
    breakout_len = 0
    for flag in reversed(near_high):
        if flag:
            breakout_len += 1
        else:
            break
    breakout_len = max(breakout_len, 1)
    b_start = len(closes) - breakout_len
    breakout_vols = vols[b_start:]
    pre_start = max(0, b_start - 20)
    pre_breakout_vols = vols[pre_start:b_start]

    # (b) 量能梯度：突破段均量÷突破前20日均量，1.5~3倍為健康區
    if breakout_vols and pre_breakout_vols:
        avg_pre = sum(pre_breakout_vols) / len(pre_breakout_vols)
        if avg_pre:
            gradient = (sum(breakout_vols) / len(breakout_vols)) / avg_pre
            if 1.5 <= gradient <= 3.0:
                score += 2.5

    # 回檔段/上漲段判定（供c使用）：從尾端往前數連續下跌天數＝回檔段，
    # 緊接其前的連續（不下跌）天數＝上漲段
    pullback_len = 0
    for i in range(len(closes) - 1, 0, -1):
        if closes[i] < closes[i - 1]:
            pullback_len += 1
        else:
            break
    upmove_len = 0
    j = len(closes) - 1 - pullback_len
    while j > 0 and closes[j] >= closes[j - 1]:
        upmove_len += 1
        j -= 1

    # (c) 回檔量縮：回檔段均量÷上漲段均量<0.6（洗盤特徵）加分
    if pullback_len > 0 and upmove_len > 0:
        pullback_vols = vols[len(vols) - pullback_len:]
        upmove_vols = vols[len(vols) - pullback_len - upmove_len: len(vols) - pullback_len]
        if upmove_vols:
            avg_upmove = sum(upmove_vols) / len(upmove_vols)
            if avg_upmove and (sum(pullback_vols) / len(pullback_vols)) / avg_upmove < 0.6:
                score += 2.5

    # (d) 價漲量縮背離：目前在60日高點附近，但今天量能<前波高點量能的0.7倍
    if near_high[-1] and len(window60) > breakout_len:
        pre_section = window60[:len(window60) - breakout_len]
        if pre_section:
            prior_peak_val = max(pre_section)
            offset = len(closes) - len(window60)
            try:
                prior_peak_idx = offset + window60.index(prior_peak_val)
                prior_peak_vol = vols[prior_peak_idx]
                if prior_peak_vol and vols[-1] < prior_peak_vol * 0.7:
                    score -= 2.5
                    flags.append("量價背離，續航存疑")
            except (ValueError, IndexError):
                pass

    # (e) 高檔爆量不漲：單日量>20日均量2.5倍且當日漲幅<1%或收黑，且股價位於
    # 近60日高檔區(>80百分位) → 重扣＋標警語
    if len(vols) >= 21:
        avg20 = sum(vols[-21:-1]) / 20
        today_change_pct = (closes[-1] / closes[-2] - 1) if closes[-2] else None
        pct_rank_60 = None
        if len(window60) >= 2 and (max(window60) - min(window60)) > 0:
            pct_rank_60 = (closes[-1] - min(window60)) / (max(window60) - min(window60))
        if avg20 and today_change_pct is not None and pct_rank_60 is not None:
            if vols[-1] > avg20 * 2.5 and today_change_pct < 0.01 and pct_rank_60 > 0.80:
                score -= 4.0
                flags.append("⚠️ 高檔爆量滯漲，出貨嫌疑")

    # (f) 派發訊號：近10日下跌日均量>上漲日均量1.3倍 → 扣分＋標警語
    n10 = min(10, len(closes) - 1)
    idx10 = len(closes) - n10
    up_vols10 = [vols[i] for i in range(idx10, len(closes)) if changes[i] and changes[i] > 0]
    down_vols10 = [vols[i] for i in range(idx10, len(closes)) if changes[i] and changes[i] <= 0]
    if up_vols10 and down_vols10:
        avg_up10 = sum(up_vols10) / len(up_vols10)
        if avg_up10 and (sum(down_vols10) / len(down_vols10)) > avg_up10 * 1.3:
            score -= 2.0
            flags.append("下跌放量")

    return score, flags


def _chip_concentration(institutional: dict | None) -> float | None:
    if not institutional:
        return None
    history = institutional.get("history") or [institutional]
    daily_nets = []
    for day in history:
        vals = [day.get(k) for k in ("foreign_lots", "trust_lots", "dealer_lots")]
        vals = [v for v in vals if v is not None]
        if vals:
            daily_nets.append(sum(vals))
    if not daily_nets:
        return None
    streak = 0
    for net in reversed(daily_nets):
        if net > 0:
            streak += 1
        else:
            break
    streak_ratio = streak / len(daily_nets)
    total_net = sum(daily_nets)
    return total_net * (1 + streak_ratio)


def _financial_risk_flag(fin_quarters: list[dict], rev_rows: list[dict]) -> bool:
    if fin_quarters:
        recent = sorted(fin_quarters, key=lambda q: (q["year"], q["quarter"]))[-2:]
        if recent and all((q.get("net_income_parent") or 0) < 0 for q in recent):
            return True
    if rev_rows:
        latest = max(rev_rows, key=lambda r: (r["year"], r["month"]))
        if latest.get("yoy") is not None and latest["yoy"] < FINANCIAL_RISK_REVENUE_YOY_FLOOR:
            return True
    return False


def build_sector_aggregates(price_history: dict, industry_map: dict[str, str]) -> pd.DataFrame:
    """回傳 index=date, columns=industry 的每日產業成交值加總表，供
    sector_capital_flow跟group_breadth共用（後者其實用quotes_all_tw.json的
    當日change_pct，不是這張表，但兩者都需要「這檔股票屬於哪個產業」的
    join，寫在同一個函式方便理解資料流）。"""
    rows = []
    for code, price_rows in price_history.items():
        industry = industry_map.get(code)
        if not industry:
            continue
        for r in price_rows:
            if r.get("turnover") is not None:
                rows.append({"date": r["date"], "industry": industry, "turnover": r["turnover"]})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.groupby(["date", "industry"])["turnover"].sum().unstack(fill_value=0.0)


def compute_sector_flow_trend(sector_daily: pd.DataFrame) -> dict[str, float]:
    """每個產業：近5日均turnover佔全市場比例 vs 再前15日均比例，差值當
    「資金流入趨勢」（正值＝佔比正在提高）。要求至少20天資料才計算，不足
    誠實跳過（回傳的dict不會有該產業的key，呼叫端對應到None）。"""
    if sector_daily.empty or len(sector_daily) < SECTOR_FLOW_RECENT_DAYS + SECTOR_FLOW_PRIOR_DAYS:
        return {}
    market_total = sector_daily.sum(axis=1)
    share = sector_daily.div(market_total.replace(0, np.nan), axis=0)
    recent_avg = share.tail(SECTOR_FLOW_RECENT_DAYS).mean()
    prior = share.iloc[-(SECTOR_FLOW_RECENT_DAYS + SECTOR_FLOW_PRIOR_DAYS):-SECTOR_FLOW_RECENT_DAYS]
    prior_avg = prior.mean()
    trend = (recent_avg - prior_avg).dropna()
    return trend.to_dict()


def compute_group_breadth(quotes_all: dict, industry_map: dict[str, str]) -> dict[str, float]:
    """同產業上漲家數比例，扣掉「漲幅集中前2檔」的濃縮度懲罰。回傳
    {industry: breadth_score}，呼叫端對應各股所屬產業。"""
    by_industry: dict[str, list[float]] = {}
    for code, q in quotes_all.items():
        industry = industry_map.get(code)
        pct = q.get("change_pct")
        if industry and pct is not None:
            by_industry.setdefault(industry, []).append(pct)
    out = {}
    for industry, pcts in by_industry.items():
        if len(pcts) < 3:
            continue
        pct_positive = sum(1 for p in pcts if p > 0) / len(pcts)
        positive_gains = sorted((p for p in pcts if p > 0), reverse=True)
        total_gain = sum(positive_gains)
        top2_gain = sum(positive_gains[:2])
        concentration = (top2_gain / total_gain) if total_gain > 0 else 0.0
        concentration_penalty = max(0.0, concentration - 0.5)  # 前2檔吃掉超過一半漲幅才罰
        out[industry] = pct_positive * (1 - concentration_penalty)
    return out


def build_rows() -> pd.DataFrame:
    fundamentals = _load_json(FUNDAMENTALS_PATH).get("fundamentals", {})
    stock_detail = _load_json(STOCK_DETAIL_PATH).get("stocks", {})
    price_history = _load_json(PRICE_HISTORY_PATH).get("prices", {}) if PRICE_HISTORY_PATH.exists() else {}
    company_info = _load_json(COMPANY_INFO_PATH).get("companies", {}) if COMPANY_INFO_PATH.exists() else {}
    quotes_all = _load_json(QUOTES_ALL_TW_PATH).get("quotes", {}) if QUOTES_ALL_TW_PATH.exists() else {}
    market_tw = _load_json(MARKET_TW_PATH) if MARKET_TW_PATH.exists() else {}
    taiex_20d = (market_tw.get("taiex") or {}).get("sparkline") or []
    taiex_60d = (market_tw.get("taiex") or {}).get("sparkline_60d") or []

    industry_map = {code: v.get("industry") for code, v in company_info.items() if v.get("industry")}
    sector_daily = build_sector_aggregates(price_history, industry_map)
    sector_flow_trend = compute_sector_flow_trend(sector_daily)
    group_breadth_by_industry = compute_group_breadth(quotes_all, industry_map)

    # 2026-08-27修正（真bug，本機測試才發現）：一開始沒過濾ETF，導致排行榜前段
    # 幾乎全是ETF代碼（例如00400A「主動國泰動能高息」）——這是題材動能榜「量能
    # 突破」/「相對強度」這類價格類因子對ETF特別友善（槓桿型ETF尤其容易有極端
    # 動能數字，不是真的個股題材強度），不是我們要的東西。用company_info.json
    # 的industry分類過濾掉非個股證券（同一份清單也適用generate_scores_live.py，
    # 那邊也有這個bug，一併修正）。
    candidate_codes = set(fundamentals) | set(stock_detail) | set(price_history)
    non_stock_codes = {code for code, ind in industry_map.items() if ind in NON_STOCK_INDUSTRIES}
    non_stock_codes |= {code for code in candidate_codes if _NON_STOCK_CODE_PATTERN.match(code)}
    all_codes = sorted(candidate_codes - non_stock_codes)
    rows = []
    for code in all_codes:
        sd = stock_detail.get(code, {})
        fd = fundamentals.get(code, {})
        price_rows = price_history.get(code) or []
        industry = industry_map.get(code)

        rel_strength = _relative_strength(price_rows, taiex_20d, taiex_60d)
        vol_breakout = _volume_breakout(price_rows)
        new_high = _new_high_breakout(price_rows)
        vp_raw, vp_flags = _volume_price_coordination(price_rows)
        # 2026-08-28新增（使用者原話，逐字照抄）：「創新高但量價配合度低（無量
        # 創高/高檔爆量）→創新高因子的分數打折，不讓假突破拿高分——寧可漏掉，
        # 不要騙自己」。只在「真的創了新高(new_high>0)且量價配合度數字為負
        # (代表d/e/f扣分規則觸發、量能配合不健康)」才打折；資料不足
        # (vp_raw is None)時不處理，不對缺資料的股票做無根據的懲罰。
        if new_high is not None and new_high > 0 and vp_raw is not None and vp_raw < 0:
            new_high = new_high * 0.3
        chip_conc = _chip_concentration(sd.get("institutional"))
        group_breadth = group_breadth_by_industry.get(industry) if industry else None
        sector_flow = sector_flow_trend.get(industry) if industry else None
        liquidity_20d = None
        turnover_rows = [r for r in price_rows if r.get("turnover") is not None]
        if turnover_rows:
            recent = sorted(turnover_rows, key=lambda r: r["date"])[-20:]
            liquidity_20d = sum(r["turnover"] for r in recent) / len(recent)
        financial_risk = _financial_risk_flag(
            (sd.get("financials") or {}).get("quarters") or [],
            fd.get("revenue_history_scoring") or fd.get("month_revenue") or [],
        )

        rows.append({
            "stock_id": code,
            "raw_relative_strength": rel_strength,
            "raw_volume_breakout": vol_breakout,
            "raw_new_high_breakout": new_high,
            "raw_volume_price_coordination": vp_raw,
            "raw_chip_concentration": chip_conc,
            "raw_group_breadth": group_breadth,
            "raw_sector_capital_flow": sector_flow,
            "liquidity_20d": liquidity_20d,
            "financial_risk_flag": financial_risk,
            "vp_flags": vp_flags,
        })

    return pd.DataFrame(rows).set_index("stock_id")


def compute_scores_momentum(weights: dict[str, float]) -> pd.DataFrame:
    cs = build_rows()
    if cs.empty:
        return cs

    raw_col = {
        "relative_strength": "raw_relative_strength",
        "volume_breakout": "raw_volume_breakout",
        "new_high_breakout": "raw_new_high_breakout",
        "volume_price_coordination": "raw_volume_price_coordination",
        "chip_concentration": "raw_chip_concentration",
        "group_breadth": "raw_group_breadth",
        "sector_capital_flow": "raw_sector_capital_flow",
    }
    for key, col in raw_col.items():
        sc, pct = _pct_score(cs[col], higher_better=True)  # 全部「越高越好」，估值不扣分故不需方向反轉
        cs[f"{key}_score"], cs[f"{key}_pct"] = sc, pct

    totals, covs = [], []
    for _, row in cs.iterrows():
        num, den = 0.0, 0.0
        for key, w in weights.items():
            sc = row.get(f"{key}_score")
            if pd.notna(sc):
                num += sc * w
                den += w
        if den == 0:
            totals.append(np.nan)
            covs.append(0.0)
        else:
            totals.append(round(num / den, 1))
            covs.append(round(den, 2))
    cs["total_score"] = totals
    cs["coverage"] = covs
    cs = cs.dropna(subset=["total_score"]).copy()
    return cs


def _raw_dict(key: str, row: pd.Series) -> dict:
    col_map = {
        "relative_strength": "raw_relative_strength",
        "volume_breakout": "raw_volume_breakout",
        "new_high_breakout": "raw_new_high_breakout",
        "volume_price_coordination": "raw_volume_price_coordination",
        "chip_concentration": "raw_chip_concentration",
        "group_breadth": "raw_group_breadth",
        "sector_capital_flow": "raw_sector_capital_flow",
    }
    return {"value": _r(row.get(col_map[key]))}


def _reason(key: str, row: pd.Series) -> str:
    pct = row.get(f"{key}_pct")
    front = max(1, round((1 - pct) * 100)) if pd.notna(pct) else None
    v = row.get(f"raw_{key}")
    if key == "relative_strength":
        return f"近20/60日報酬率相對大盤 {v*100:+.1f}%（平均），居全市場前 {front}%。"
    if key == "volume_breakout":
        return f"今日成交值為近20日均量的 {v:.2f} 倍，居全市場前 {front}%。"
    if key == "new_high_breakout":
        if v > 0:
            return f"今日收盤價創近{NEW_HIGH_WINDOW}日新高，突破前波高點 {v*100:+.1f}%，居全市場前 {front}%。（參數未驗證）"
        return f"今日收盤價距近{NEW_HIGH_WINDOW}日高點 {v*100:.1f}%，尚未創新高，居全市場前 {front}%。（參數未驗證）"
    if key == "volume_price_coordination":
        return f"量價配合度綜合指標 {v:+.1f}（吸收比/量能梯度/回檔量縮/背離扣分等規則加總），居全市場前 {front}%。（參數未驗證，見weights_frozen_momentum.json）"
    if key == "chip_concentration":
        return f"三大法人買超張數×連續買超天數加成指標 {v:+.0f}，居全市場前 {front}%。"
    if key == "group_breadth":
        return f"同產業上漲家數比例（已扣除前2檔濃縮度懲罰）{v*100:.0f}%，居全市場前 {front}%。"
    if key == "sector_capital_flow":
        return f"所屬產業近5日成交值佔全市場比例，較再前15日提升 {v*100:+.2f} 個百分點，居全市場前 {front}%。"
    return ""


def main():
    frozen = load_frozen_weights_momentum()
    weights = frozen["weights"]
    print(f"已套用題材動能榜初始設計權重 weights_frozen_momentum.json"
          f"（frozen_at={frozen['frozen_at']}，sha256={frozen['weights_sha256'][:12]}...，"
          f"**尚未回測驗證**）")

    company_info = _load_json(COMPANY_INFO_PATH).get("companies", {}) if COMPANY_INFO_PATH.exists() else {}
    cs = compute_scores_momentum(weights)
    as_of = datetime.now(TW_TZ).strftime("%Y-%m-%d")

    if cs.empty:
        payload = {
            "meta": {
                "engine_version": "scoring-momentum-v1", "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW", "weights_hash": frozen["weights_sha256"],
                "backtest_status": "尚未回測驗證",
                "disclaimer": "本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤。這次沒有任何股票算出分數。",
            },
            "weights": weights, "stocks": [],
        }
    else:
        cs["liquidity_insufficient"] = (
            cs["liquidity_20d"].isna() | (cs["liquidity_20d"] < LIQUIDITY_FLOOR_20D_VALUE)
        )
        ranked = cs.sort_values(["liquidity_insufficient", "total_score"], ascending=[True, False]).copy()
        liquidity_ok_mask = ~ranked["liquidity_insufficient"]
        ranked.loc[liquidity_ok_mask, "display_rank"] = range(1, int(liquidity_ok_mask.sum()) + 1)

        stocks = []
        for sid, row in ranked.iterrows():
            present = [k for k in FACTOR_LABELS if pd.notna(row.get(f"{k}_score"))]
            missing = [k for k in FACTOR_LABELS if k not in present]
            factors_obj = {
                k: {
                    "score": round(float(row[f"{k}_score"]), 1),
                    "percentile": round(float(row[f"{k}_pct"]), 2),
                    "raw": _raw_dict(k, row),
                    "reason": _reason(k, row),
                } for k in present
            }
            flags = []
            if row["liquidity_insufficient"]:
                flags.append("流動性不足")
            if row.get("financial_risk_flag"):
                flags.append("財報地雷警示（近期虧損或營收年減劇烈惡化）")
            # 2026-08-28新增：量價配合度因子的(d)/(e)/(f)警訊規則，使用者要求
            # 「直接反映在分數並顯示標籤」——分數面已經在build_rows()裡扣過，
            # 這裡把對應的警語字串併入flags讓UI顯示。
            for vf in (row.get("vp_flags") or []):
                if vf not in flags:
                    flags.append(vf)
            display_rank = row.get("display_rank")
            info = company_info.get(sid) or {}
            stocks.append({
                "code": sid, "name": info.get("name"), "industry": info.get("industry"),
                "rank": int(display_rank) if pd.notna(display_rank) else None,
                "total_score": round(float(row["total_score"]), 1),
                "coverage": round(float(row["coverage"]), 2),
                "missing_factors": missing,
                "liquidity_20d": _r(row.get("liquidity_20d")),
                "data_asof": as_of,
                "factors": factors_obj,
                "flags": flags,
                "news_warning": None,
            })
        payload = {
            "meta": {
                "engine_version": "scoring-momentum-v1",
                "generated_at": datetime.now(TW_TZ).isoformat(),
                "data_asof": as_of, "market": "TW",
                "universe_size": len(cs),
                "avg_coverage": round(float(cs["coverage"].mean()), 3),
                "liquidity_floor_20d_value": LIQUIDITY_FLOOR_20D_VALUE,
                "weights_hash": frozen["weights_sha256"],
                "backtest_status": "尚未回測驗證",
                "source": "只讀repo內data/fundamentals.json+data/stock_detail.json+data/price_history.json"
                           "+data/company_info.json+data/quotes_all_tw.json+data/market_tw.json"
                           "（不讀parquet、不呼叫FinMind），供GitHub Actions每日排程使用。",
                "disclaimer": (
                    "⚠ 本榜為資料排序，尚未經過組合策略回測驗證，不代表能贏大盤。"
                    "因子設計聚焦股價領先財報的題材動能（相對強度/量能突破/籌碼集中/"
                    "族群齊漲度/產業資金流入），財報只當地雷排除用（financial_risk_flag），"
                    "不計入加權總分；完全不計算PE/PEG估值，題材股本來就貴，用估值扣分"
                    "等於自相矛盾。權重是初始設計值，不是回測最佳化結果，見"
                    "weights_frozen_momentum.json的note欄位。"
                ),
            },
            "weights": weights,
            "stocks": stocks,
        }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False, default=float), encoding="utf-8")
    print(f"寫入 {OUT_PATH}，{len(payload['stocks'])} 檔（樣本共 {len(cs)} 檔有任一因子資料）")
    if not cs.empty:
        print(cs[["total_score", "coverage"]].head(10).to_string())


if __name__ == "__main__":
    main()
