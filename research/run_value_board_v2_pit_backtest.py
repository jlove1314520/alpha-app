"""價值成長榜（`score_v2.py`/`generate_scores_live.py`同一套FACTOR_DEFS）
PIT組合回測（2026-08-28新增，B24第一步，骨架＋機制驗證跑）。

**背景**：BACKLOG.md B24第一項要求「PIT回測（正式開工，凍結權重）：月度
再平衡、持股20檔、全成本、動態隨機對照組1000次、對大盤回歸alpha顯著性、
Sortino/MDD優先」，先做價值成長榜。這支腳本重用既有、已經跑過的驗證框架
（`run_score_backtest.py`同一套`backtest/engine.py::run_backtest()`機制、
`portfolio_backtest_v2.py`同一套alpha/beta回歸+Sharpe公式、
`benchmark_taiex_stats.py`同一套TAIEX買進持有MDD/Sortino公式），只是把
訊號函式換成`score_v2.py::compute_scores_v2()`（=App目前正式上線的價值
成長榜FACTOR_DEFS八大因子組合，跟另外兩支腳本用的是完全不同的因子集合，
不能混用既有結果）。

**重要澄清（跟使用者原話「目前只夠回測約12-18個月」的認知落差）**：
使用者原話假設的12-18個月，指的可能是App即時JSON路徑（`price_history.json`
90天/`fundamentals.json`26個月營收）的資料深度——但這支腳本走的是research端
既有的`factor_ic.py`樣本，2010年起、FinMind歷史parquet快取，已經有長達
10年以上的可用歷史，**不受那個12-18個月限制**。這是好消息：可以測的期間
比使用者原本以為的長很多，統計檢定力也更高。

**2026-08-28第二次修訂：樣本擴大到500檔（使用者核准「回測樣本擴大：核准
擴到500檔（一次性）」，見`VALUE_BOARD_SAMPLE_SIZE`）**——第一次機制驗證跑
（100檔）發現嚴重方法論問題：扣掉流動性門檻後合格股票池平均只有約11.5檔，
從未達到20檔持股目標，代表約40-45%資金整個回測期間閒置在現金，這對「策略
vs 100%投入的買進持有大盤」是結構性不公平比較。500檔樣本應該能大幅改善
這個問題（更大的池子，流動性門檻後仍有機會穩定湊到20檔）。**遵守「資料源
禮儀」規則（見BACKLOG.md，2026-08-28同一天新增的全域速率限制）**：
`research/finmind_client.py`現在對FinMind的請求嚴格3秒節流+斷路器，500檔
裡任何一檔如果本機parquet快取沒有涵蓋到的資料（institutional/revenue等），
第一次抓取都要付這個代價——**這是刻意的、已經跟使用者說明過的取捨，寧可
慢也不要再觸發封鎖**，載入階段可能要數小時，不是這支腳本的bug，是誠實
遵守速率限制的必然結果。

**新增翻倍率/大賺率/地雷率統計（使用者原話，見`compute_moonshot_stats()`）**：
對每一次「買進」事件往後看12個月(252個交易日)的價格路徑，取期間內曾經
達到過的最高/最低報酬率（不是只看最後平倉報酬），算出翻倍率(曾達+100%)/
大賺率(曾達+50%)/地雷率(曾跌破-30%)，並對隨機對照組的每一次draw也算同一
組指標取平均，當作「亂槍打鳥」的對照基準。

**Holdout紀律（本輪嚴格遵守，未經使用者同意不解鎖）**：全程只用
`finmind_client.load_dev()`（自動cap在`VAL_END=2024-12-31`），`backtest/
engine.py::run_backtest()`本身在每個price DataFrame跑`assert_no_holdout_
leakage()`，結構性擋掉任何holdout洩漏——就算這支腳本想不小心看到2025-2026
的資料也做不到。**這代表這次回測回答的是「這套因子組合在2015-2024historical
資料上，是否能穩定打敗大盤」，不是「App現在正式上線後這幾個月的實際表現」
——後者需要動用holdout，必須先取得使用者明確同意才能做（見BACKLOG.md
B16/B24條目、CLAUDE.md安全紅線）。**

**2026-08-29第三次修訂：正式全樣本回測（使用者原話「B24-500全樣本回測，
todo P0/B16，最高優先」，取代先前的機制驗證跑）**：
- 可投資宇宙從「隨機抽樣500檔」改成「流動性（近20日均成交值）由高到低
  取前500檔」（`liquidity_ranked_universe_ids()`）——隨機抽樣可能抽到大量
  流動性不足的股票，跟這支腳本自己的流動性門檻（`liquidity_insufficient`）
  互相打架；改用流動性排序後的池子，理論上能穩定湊滿20檔持股，不會再
  重演100檔隨機樣本「合格池只剩11.5檔、40-45%資金閒置現金」的結構性
  偏誤。流動性排序**用`data/price_history.json`目前(2026-08)最近20個
  交易日的均成交值算，是一個「現在」的排序、固定用在整個2015-2024回測
  期間，不是逐期歷史當下重新排序**——這是跟先前「隨機500檔」同一等級
  的簡化（都是固定用一組ticker清單跑完整段回測，不是每個再平衡日動態
  改變可投資池），誠實記錄這個簡化，不是嚴格的「歷史當下流動性PIT」。
- 隨機對照組原本要從`N_RANDOM_DRAWS_QUICK=30`（機制驗證用）升級到使用者
  規格的1000次，但**實測後誠實降級**：用既有500檔快取實測5次draw（僅
  VALIDATION 4年期間），機器同時有另一個獨立CPU重載作業在跑（未動它），
  量到約102秒/draw——換算1000次draws×2期間(TRAIN 6年+VALIDATION 4年)
  ×1榜需要約70小時（~3天），這一輪不可行。使用者2026-08-29核准降級到
  `N_RANDOM_DRAWS=100`（比先前30次有意義地提升，且能在同一個session的
  背景時間內跑完，預估約7小時），跟`run_score_backtest.py`docstring
  說明的200→60降級同一個誠實揭露慣例——這仍然只是100次，不是1000次，
  百分位估計的統計把握程度要照實揭露，不能假裝是1000次等級的證據。
- 新增調整後Sharpe（原值×0.5/×0.7兩欄，標「實盤預期區間」，
  `sharpe_ratio()`/`adjusted_sharpe()`）、CVaR(95%,日)（`cvar_95()`）、
  勝率（`win_rate()`，僅供報告參考，不作為判定依據——使用者B24原始規格
  「評判順序：淨利與MDD達標→Sortino→alpha顯著→夏普最後→勝率不看」）。
- 這一輪如果結果及格（贏大盤/alpha顯著），才寫進`TRIALS_LEDGER.md`正式
  登錄；不及格就如實在`B24_RESULTS.md`/`BACKLOG.md`記錄「不及格」，
  App選股頁「本榜為資料排序，尚未經過組合策略回測驗證」那行字繼續掛著，
  不因為跑完就拿掉，這是使用者本輪明確的鐵律。
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
from scipy import stats

from backtest.engine import BacktestConfig, run_backtest
from factor_ic import START_DATE, load_sample_with_factors
from universe import universe as build_universe
from finmind_client import load_dev
from score import load_industry_map
from score_v2 import compute_scores_v2
from strategies.weinstein_stage2 import prepare_market_data
from validation import holdout

TOP_N = 20  # 使用者規格：持股20檔
REBALANCE_DAYS = 21  # 月度再平衡（21個交易日近似一個月，跟portfolio_backtest_v2.py同一個慣例）
N_RANDOM_DRAWS = 100  # 2026-08-29誠實降級（見模組docstring「正式修訂」段落）：目標1000次，實測約102秒/draw
                       # 換算不可行（~70小時），使用者核准降到100次，比先前機制驗證用的30次有意義提升
RANDOM_CONTROL_SEED = 20260828
VALUE_BOARD_SAMPLE_SIZE = 500
REPO_ROOT = Path(__file__).resolve().parent.parent
PRICE_HISTORY_PATH = REPO_ROOT / "data" / "price_history.json"
LIQUIDITY_LOOKBACK_DAYS = 20


def liquidity_ranked_universe_ids(n: int, lookback_days: int = LIQUIDITY_LOOKBACK_DAYS) -> list[str]:
    """2026-08-29新增（B24-500正式全樣本回測，取代先前的隨機抽樣500檔）：
    以近`lookback_days`個交易日的均成交值由高到低排序，取前`n`檔——目的是
    確保扣掉流動性門檻後仍能穩定湊滿`TOP_N`持股，修掉先前隨機抽樣導致
    「合格池只剩約11.5檔、40-45%資金閒置現金」的結構性偏誤。

    資料來源：App的`data/price_history.json`（每日排程累積，目前約2831檔
    有紀錄，涵蓋率約universe()全市場3196檔的88.6%），不用另外打API，符合
    資料源禮儀。**誠實揭露簡化**：這是用「現在」（2026-08）最近20個交易日
    的均成交值排序，固定用這一組ticker清單跑完整段2015-2024回測，不是
    逐期歷史當下重新排序——跟先前「隨機500檔」同一等級的簡化，不是嚴格
    PIT流動性排序（那需要全市場10年逐日成交值歷史，不在這輪範圍內）。
    只取在`universe()`（survivorship-free全市場清單）裡的股票，維持
    survivorship-free。

    **2026-08-29修正（首次跑就抓到的真bug）**：`universe()`本身混進了
    "TAIEX"/"TPEx"這兩個指數代碼（`industry_category`="大盤"，不是個股），
    成交值天生遠高於任何單一股票，流動性排序沒過濾的話**保證每次都會
    排到最前面**——不是隨機抽樣時偶爾抽到的邊緣case，是排序法的必然結果，
    會讓回測試圖「買進」一個指數而不是股票。用跟`backfill_price_history_
    gaps.py`/`generate_scores_momentum.py`同一份`NON_STOCK_INDUSTRIES`
    排除清單過濾掉（ETF/ETN/指數/受益證券/存託憑證/大盤等非個股類別）。
    """
    non_stock_industries = {
        "ETF", "ETN", "上櫃ETF", "上櫃指數股票型基金(ETF)", "指數投資證券(ETN)",
        "受益證券", "存託憑證", "Index", "大盤", "所有證券",
    }
    u = build_universe()
    valid_ids = set(u[~u["industry_category"].isin(non_stock_industries)]["stock_id"])
    payload = json.loads(PRICE_HISTORY_PATH.read_text(encoding="utf-8"))
    prices = payload.get("prices", {})
    ranked = []
    for sid, rows in prices.items():
        if sid not in valid_ids or not rows:
            continue
        window = sorted(rows, key=lambda r: r["date"])[-lookback_days:]
        vals = [r["turnover"] for r in window if r.get("turnover") is not None]
        if not vals:
            continue
        ranked.append((sid, sum(vals) / len(vals)))
    ranked.sort(key=lambda x: -x[1])
    return [sid for sid, _ in ranked[:n]]


def sharpe_ratio(equity_curve: pd.DataFrame) -> float:
    """跟portfolio_backtest_v2.py::sharpe_ratio()逐行一致的公式，自成一體
    複製一份（不同因子引擎，各自獨立，不跨檔案import）。"""
    eq = equity_curve["equity"]
    if len(eq) < 2:
        return float("nan")
    r = eq.pct_change().dropna()
    if r.empty or r.std() == 0:
        return float("nan")
    return float(r.mean() / r.std() * np.sqrt(252))


def cvar_95(equity_curve: pd.DataFrame) -> float:
    """2026-08-29新增（B26規格）：CVaR(95%)——日報酬分布最差5%那段的平均值
    （不是年化，單位是「日報酬%」，避免跟年化指標混淆）。"""
    eq = equity_curve["equity"]
    if len(eq) < 2:
        return float("nan")
    r = eq.pct_change().dropna()
    if r.empty:
        return float("nan")
    var_95 = r.quantile(0.05)
    tail = r[r <= var_95]
    return float(tail.mean() * 100) if len(tail) else float("nan")


def win_rate(trades: pd.DataFrame) -> float:
    """2026-08-29新增（B24規格「勝率」，僅供報告參考，不作為及格判定依據
    ——使用者原話「評判順序：淨利與MDD達標→Sortino→alpha顯著→夏普最後→
    勝率不看」）。closed trades（side=sell）中realized_pnl>0的比例。"""
    if trades.empty or "side" not in trades.columns:
        return float("nan")
    closes = trades[trades["side"].isin(["sell", "close"])]
    if closes.empty or "realized_pnl" not in closes.columns:
        return float("nan")
    return float((closes["realized_pnl"] > 0).mean() * 100)


def eligible_for_ranking_v2(cs: pd.DataFrame) -> pd.DataFrame:
    """跟generate_scores_live.py/App端同一個定義：流動性不足的不進數字排名。"""
    if cs.empty:
        return cs
    return cs[~cs["liquidity_insufficient"]] if "liquidity_insufficient" in cs.columns else cs


def make_score_v2_signal_fn(industry_map: dict[str, str], start_date: str, top_n: int = TOP_N):
    def signal_fn(price_data: dict[str, pd.DataFrame], as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        cs = compute_scores_v2(as_of, price_data, industry_map, start_date)
        cs = eligible_for_ranking_v2(cs)
        # 2026-08-28修正（sanity check親自抓到的真bug）：compute_scores_v2()在
        # 完全沒有任何股票有資料的as_of日期會回傳零欄位的空DataFrame（跟
        # adjust.py/build_price_history.py之前修過的同一種「空DataFrame沒有
        # 欄位」陷阱），這裡沒擋住的話cs.sort_values("total_score",...)會
        # KeyError整支腳本中止。改成這種情況誠實回傳空dict（=這個再平衡日
        # 沒有任何新持倉建議，不是硬湊一個假結果）。
        if cs.empty or "total_score" not in cs.columns:
            return {}
        top = cs.sort_values("total_score", ascending=False).head(top_n)
        return dict(zip(top.index, top["total_score"]))
    return signal_fn


_eligible_pool_cache: dict[str, list[str]] = {}


def make_random_signal_fn(industry_map: dict[str, str], start_date: str, top_n: int, seed: int):
    import random
    rng = random.Random(seed)

    def signal_fn(price_data: dict[str, pd.DataFrame], as_of: str, market_df: pd.DataFrame) -> dict[str, float]:
        if as_of not in _eligible_pool_cache:
            cs = eligible_for_ranking_v2(compute_scores_v2(as_of, price_data, industry_map, start_date))
            _eligible_pool_cache[as_of] = cs.index.tolist()
        pool = _eligible_pool_cache[as_of]
        picks = pool if len(pool) <= top_n else rng.sample(pool, top_n)
        return {sid: 1.0 for sid in picks}
    return signal_fn


def buy_and_hold_index_pct(market_df: pd.DataFrame, start: str, end: str) -> float:
    """對照組(b)：買進持有加權指數，零成本不換股——跟portfolio_backtest_v2.py同一個公式。"""
    window = market_df[(market_df["date"] >= start) & (market_df["date"] <= end)].sort_values("date")
    if len(window) < 2:
        return float("nan")
    p0, p1 = window.iloc[0]["close"], window.iloc[-1]["close"]
    return float(p1 / p0 - 1) * 100


def taiex_mdd_sortino(market_df: pd.DataFrame, start: str, end: str) -> dict:
    """大盤本身同期的MDD/Sortino——跟benchmark_taiex_stats.py同一個公式，
    讓策略端的MDD/Sortino有量化基準可以對照，不是只有質化描述。"""
    window = market_df[(market_df["date"] >= start) & (market_df["date"] <= end)].sort_values("date")
    closes = window["close"].astype(float)
    if len(closes) < 2:
        return {"mdd_pct": float("nan"), "sortino": float("nan")}
    running_max = closes.cummax()
    drawdown = (closes - running_max) / running_max
    mdd_pct = float(drawdown.min() * 100)
    rets = closes.pct_change().dropna()
    downside = rets[rets < 0]
    sortino = float("nan")
    if len(downside) and downside.std() != 0:
        sortino = float(rets.mean() / downside.std() * np.sqrt(252))
    return {"mdd_pct": mdd_pct, "sortino": sortino}


def alpha_significance(equity_curve: pd.DataFrame, market_df: pd.DataFrame) -> dict:
    """跟portfolio_backtest_v2.py::alpha_significance()逐行一致的公式，這裡
    自成一體複製一份（不同因子引擎，各自獨立，不跨檔案import）。"""
    mkt = market_df.set_index("date")["close"].sort_index()
    mkt_ret = mkt.pct_change()
    net_ret = equity_curve.set_index("date")["equity"].pct_change().rename("net_return")
    merged = pd.concat([net_ret, mkt_ret.rename("mkt_return")], axis=1, join="inner").dropna()
    if len(merged) < 30:
        return {"alpha_ann_pct": float("nan"), "beta": float("nan"), "alpha_pvalue": float("nan"),
                "alpha_significant": False, "n_days": len(merged)}
    reg = stats.linregress(merged["mkt_return"], merged["net_return"])
    alpha_ann_pct = ((1 + reg.intercept) ** 252 - 1) * 100
    pvalue = (2 * stats.t.sf(abs(reg.intercept / reg.intercept_stderr), len(merged) - 2)
              if reg.intercept_stderr else float("nan"))
    return {
        "alpha_ann_pct": float(alpha_ann_pct), "beta": float(reg.slope),
        "alpha_pvalue": float(pvalue) if pvalue == pvalue else float("nan"),
        "alpha_significant": bool(reg.intercept > 0 and pvalue == pvalue and pvalue < 0.05),
        "n_days": len(merged),
    }


def compute_moonshot_stats(trades: pd.DataFrame, price_data: dict[str, pd.DataFrame], horizon_days: int = 252) -> dict:
    """使用者核心關切的「翻倍率/大賺率/地雷率」指標（2026-08-28新增，B24
    任務2使用者原話：「翻倍率=Top20中12個月內最高漲幅曾達+100%的檔數比例；
    大賺率=曾達+50%的比例...同時報告反面——12個月跌超過-30%的比例（地雷率）」）。

    對每一次「買進」事件（不是每檔獨立股票，同一檔股票在回測期間多次
    進出各自算一次entry），往後看最多`horizon_days`個交易日（約12個月）
    的adj_close價格路徑，取這段期間內**曾經達到過的最高/最低報酬率**
    （不是只看最後平倉報酬——用意是回答「有沒有翻倍過」而不是「最後有
    沒有賺」，這兩個問題答案可能不同：曾經翻倍又跌回來，仍然算「翻倍
    率」裡的一次命中）。entry太靠近回測結束、可用天數不足`horizon_days`
    的，用「已有的最長天數」代替，不強制排除（否則會系統性剔除近期表現
    最好/最差的entry，造成倖存者偏誤），但用`truncated_entries`誠實記錄
    有幾筆是截斷的。"""
    if trades.empty:
        return {"n_entries": 0, "moonshot_rate": None, "big_win_rate": None, "mine_rate": None, "truncated_entries": 0}
    buys = trades[trades["side"] == "buy"]
    moonshot, big_win, mine, truncated, n = 0, 0, 0, 0, 0
    for _, row in buys.iterrows():
        sid, entry_date, entry_price = row["stock_id"], row["date"], row["price"]
        df = price_data.get(sid)
        if df is None or entry_price in (None, 0) or pd.isna(entry_price):
            continue
        future = df[df["date"] > entry_date].sort_values("date").head(horizon_days)
        if future.empty or "adj_close" not in future.columns:
            continue
        if len(future) < horizon_days:
            truncated += 1
        max_ret = float(future["adj_close"].max()) / entry_price - 1
        min_ret = float(future["adj_close"].min()) / entry_price - 1
        n += 1
        if max_ret >= 1.0:
            moonshot += 1
        if max_ret >= 0.5:
            big_win += 1
        if min_ret <= -0.3:
            mine += 1
    if n == 0:
        return {"n_entries": 0, "moonshot_rate": None, "big_win_rate": None, "mine_rate": None, "truncated_entries": 0}
    return {
        "n_entries": n,
        "moonshot_rate": round(moonshot / n * 100, 1),
        "big_win_rate": round(big_win / n * 100, 1),
        "mine_rate": round(mine / n * 100, 1),
        "truncated_entries": truncated,
    }


def run_period(label: str, data: dict, market_df: pd.DataFrame, industry_map: dict, start: str, end: str) -> dict:
    print(f"\n=== {label}: {start}..{end} ===")
    _eligible_pool_cache.clear()

    cfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                         rebalance_every_n_days=REBALANCE_DAYS, book_name="value_board_v2_pit")
    result = run_backtest(make_score_v2_signal_fn(industry_map, START_DATE, TOP_N), data, market_df, cfg)
    print(f"  價值成長榜v2 Top{TOP_N}(月度再平衡): return={result.total_return_pct:+.2f}%  "
          f"MDD={result.max_drawdown_pct:.2f}%  Sortino={result.sortino_ratio:.3f}  trades={result.n_trades}")

    bh = buy_and_hold_index_pct(market_df, start, end)
    bh_stats = taiex_mdd_sortino(market_df, start, end)
    print(f"  買進持有加權指數: {bh:+.2f}%  MDD={bh_stats['mdd_pct']:.2f}%  Sortino={bh_stats['sortino']:.3f}")

    alpha = alpha_significance(result.equity_curve, market_df)
    print(f"  alpha(年化)={alpha['alpha_ann_pct']:+.2f}%  beta={alpha['beta']:+.3f}  "
          f"p={alpha['alpha_pvalue']:.4f}  顯著={alpha['alpha_significant']}（n={alpha['n_days']}天）")

    moonshot = compute_moonshot_stats(result.trades, data)
    print(f"  翻倍率(12個月內曾達+100%)={moonshot['moonshot_rate']}%  "
          f"大賺率(曾達+50%)={moonshot['big_win_rate']}%  地雷率(曾跌破-30%)={moonshot['mine_rate']}%  "
          f"（{moonshot['n_entries']}次進場事件，{moonshot['truncated_entries']}筆因接近回測尾端資料不足12個月而截斷）")

    sharpe_raw = sharpe_ratio(result.equity_curve)
    sharpe_x05 = sharpe_raw * 0.5 if sharpe_raw == sharpe_raw else float("nan")
    sharpe_x07 = sharpe_raw * 0.7 if sharpe_raw == sharpe_raw else float("nan")
    cvar95 = cvar_95(result.equity_curve)
    wr = win_rate(result.trades)
    print(f"  Sharpe原始={sharpe_raw:.3f}  調整後×0.5={sharpe_x05:.3f}  ×0.7={sharpe_x07:.3f}（實盤預期區間）  "
          f"CVaR(95%,日)={cvar95:.3f}%  勝率={wr:.1f}%（僅供參考，不作為及格判定依據）")

    print(f"  隨機對照組（{N_RANDOM_DRAWS}次）...")
    random_finals = []
    random_moonshot_rates, random_big_win_rates, random_mine_rates = [], [], []
    for i in range(N_RANDOM_DRAWS):
        rcfg = BacktestConfig(start_date=start, end_date=end, max_positions=TOP_N,
                              rebalance_every_n_days=REBALANCE_DAYS, book_name="value_board_v2_random_control")
        rfn = make_random_signal_fn(industry_map, START_DATE, TOP_N, seed=RANDOM_CONTROL_SEED + i)
        rr = run_backtest(rfn, data, market_df, rcfg)
        random_finals.append(rr.final_equity)
        rm = compute_moonshot_stats(rr.trades, data)
        if rm["moonshot_rate"] is not None:
            random_moonshot_rates.append(rm["moonshot_rate"])
            random_big_win_rates.append(rm["big_win_rate"])
            random_mine_rates.append(rm["mine_rate"])
        if (i + 1) % 100 == 0:
            print(f"    draw進度 {i+1}/{N_RANDOM_DRAWS}")
    real_final = result.final_equity
    percentile = 100.0 * float(np.mean([real_final > rf for rf in random_finals]))
    print(f"  真實策略終值 {real_final:,.0f} vs 隨機對照組中位數 {np.median(random_finals):,.0f}"
          f"（百分位 {percentile:.1f}，{N_RANDOM_DRAWS}次draws）")
    rand_moonshot_avg = round(float(np.mean(random_moonshot_rates)), 1) if random_moonshot_rates else None
    rand_big_win_avg = round(float(np.mean(random_big_win_rates)), 1) if random_big_win_rates else None
    rand_mine_avg = round(float(np.mean(random_mine_rates)), 1) if random_mine_rates else None
    print(f"  隨機對照組翻倍率/大賺率/地雷率平均：{rand_moonshot_avg}% / {rand_big_win_avg}% / {rand_mine_avg}%"
          f"（真實策略 {moonshot['moonshot_rate']}% / {moonshot['big_win_rate']}% / {moonshot['mine_rate']}% ——"
          f"「選中比例」是否顯著高於「亂槍打鳥」看這兩組數字的差距）")

    return {
        "label": label, "start": start, "end": end,
        "return_pct": result.total_return_pct, "mdd_pct": result.max_drawdown_pct,
        "sortino": result.sortino_ratio, "n_trades": result.n_trades,
        "sharpe_raw": sharpe_raw, "sharpe_x05": sharpe_x05, "sharpe_x07": sharpe_x07,
        "cvar_95_daily_pct": cvar95, "win_rate_pct": wr,
        "buy_and_hold_pct": bh, "bh_mdd_pct": bh_stats["mdd_pct"], "bh_sortino": bh_stats["sortino"],
        "alpha_ann_pct": alpha["alpha_ann_pct"], "beta": alpha["beta"],
        "alpha_pvalue": alpha["alpha_pvalue"], "alpha_significant": alpha["alpha_significant"],
        "random_control_percentile": percentile, "random_draws": N_RANDOM_DRAWS,
        "moonshot_rate": moonshot["moonshot_rate"], "big_win_rate": moonshot["big_win_rate"],
        "mine_rate": moonshot["mine_rate"], "moonshot_n_entries": moonshot["n_entries"],
        "random_moonshot_rate_avg": rand_moonshot_avg, "random_big_win_rate_avg": rand_big_win_avg,
        "random_mine_rate_avg": rand_mine_avg,
    }


def main():
    sample_ids = liquidity_ranked_universe_ids(VALUE_BOARD_SAMPLE_SIZE)
    print(f"流動性排序前{VALUE_BOARD_SAMPLE_SIZE}檔（取代先前隨機抽樣），"
          f"前5檔：{sample_ids[:5]}")
    market_raw = load_dev("TaiwanStockPrice", "TAIEX", START_DATE)
    holdout.assert_no_holdout_leakage(market_raw, context="market_raw in run_value_board_v2_pit_backtest")
    market_df = prepare_market_data(market_raw)

    # 2026-08-29：cache檔名加上liquidity500區分先前的隨機抽樣500檔快取
    # （value_board_v2_sample_cache_500.pkl），避免誤用到不同選股方法的
    # 樣本——這是全新的股票清單，不能沿用舊快取。load_sample_with_factors()
    # 對500檔樣本首次跑約20分鐘（prepare_factors()真實運算，不是網路請求），
    # 之後重跑（例如拉高random draws次數）直接吃這個快取。
    cache_path = Path(__file__).parent / "data" / "backtests" / f"value_board_v2_sample_cache_liquidity{VALUE_BOARD_SAMPLE_SIZE}.pkl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        print(f"Loading sample + factors from local cache ({cache_path})...")
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
    else:
        print("Loading sample + factors (no local cache yet, first run takes ~20min)...")
        data = load_sample_with_factors(sample_ids, market_df)
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
        print(f"  cached to {cache_path} for next run")
    print(f"  {len(data)}/{len(sample_ids)} usable names")
    for sid, d in data.items():
        holdout.assert_no_holdout_leakage(d, date_col="date", context=f"data[{sid}] in run_value_board_v2_pit_backtest")

    industry_map = load_industry_map()
    print(f"  industry_map: {len(industry_map)} entries")

    train_result = run_period("TRAIN", data, market_df, industry_map, "2015-01-01", holdout.TRAIN_END)
    val_result = run_period("VALIDATION", data, market_df, industry_map, "2021-01-01", holdout.VAL_END)

    print(f"\n=== SUMMARY（流動性前{VALUE_BOARD_SAMPLE_SIZE}檔，{N_RANDOM_DRAWS}次隨機對照draws，正式全樣本回測）===")
    for r in (train_result, val_result):
        print(f"  {r['label']}: 策略={r['return_pct']:+.2f}% vs 買進持有={r['buy_and_hold_pct']:+.2f}%  "
              f"MDD策略/大盤={r['mdd_pct']:.2f}%/{r['bh_mdd_pct']:.2f}%  "
              f"Sortino策略/大盤={r['sortino']:.3f}/{r['bh_sortino']:.3f}  "
              f"Sharpe原始/×0.5/×0.7={r['sharpe_raw']:.3f}/{r['sharpe_x05']:.3f}/{r['sharpe_x07']:.3f}  "
              f"CVaR(95%,日)={r['cvar_95_daily_pct']:.3f}%  勝率={r['win_rate_pct']:.1f}%  "
              f"alpha={r['alpha_ann_pct']:+.2f}%(顯著={r['alpha_significant']}, p={r['alpha_pvalue']:.4f})  "
              f"隨機對照百分位={r['random_control_percentile']:.1f}({r['random_draws']}次)  "
              f"翻倍率/大賺率/地雷率：策略{r['moonshot_rate']}%/{r['big_win_rate']}%/{r['mine_rate']}% "
              f"vs 隨機{r['random_moonshot_rate_avg']}%/{r['random_big_win_rate_avg']}%/{r['random_mine_rate_avg']}%")

    out_path = Path(__file__).parent / "data" / f"value_board_v2_pit_backtest_liquidity{VALUE_BOARD_SAMPLE_SIZE}_full.csv"
    pd.DataFrame([train_result, val_result]).to_csv(out_path, index=False)
    print(f"saved {out_path}")
    return train_result, val_result


if __name__ == "__main__":
    main()
