# -*- coding: utf-8 -*-
"""`PENDING_QUEUE.md` 外部一改.3（期貨軌）：名家已發表趨勢跟隨機制的第 1 關 cheap gate。

**這支在做什麼**：把五個**公開發表過**的系統化趨勢跟隨機制，搬到台指期（TX）連續
合約上重測。標的選台指期的理由寫在總司令原話裡：可空、無借券限制、有夜盤，
最接近這些機制的原生環境（`CLAUDE.md` 台股偽影家族⑩）。

**紀律：拿機制不拿參數**——但這五個機制的參數是**原文獻明定的規則的一部分**
（海龜的 20/10、55/20、2N 停損、1% 風險部位不是我們調出來的，是 Richard Dennis
公開的訓練規則），所以照原文獻寫死，**不掃參數、不挑好看的格子**。第 1 關只問
「原始規則在這個市場上還站得住嗎」。參數高原是後面的關卡才做的事，不是這裡。

**事前綁定規格（寫在跑數字之前，不得事後調整）**

資料源：`continuous_contract.build_continuous_series()`（TX 日盤，比例回調，
全歷史 2000-2024），零新增 API 呼叫，純讀既有快取。

五個機制（每一個都是「決策只用到當天以前的資料」，部位由 `_terminal_equity`
再 shift(1) 才吃到報酬，避免未來函數）：

1. `turtle_system1_20_10`：海龜法則 System 1 原始規則。20 日高/低突破進場、
   反向 10 日突破出場、2N（N=20 日 ATR）停損、每 0.5N 順勢加碼一次最多 4 單位、
   單位規模以 1% 風險 ÷ 2N 反比配置。**與原文獻的已知偏離**：原規則看盤中價格
   觸價，我們只有日 K，所以用「收盤價突破前 20 日最高/最低」判定，停損也以收盤價
   結算——這會低估停損的即時性，方向上對趨勢跟隨有利，不是保守偏差，必須誠實記錄。
2. `donchian_full_55_20`：海龜 System 2 的長週期版（55 日進場／20 日出場），
   其餘規則與 1 相同。**與 1 屬同一家族**（同一份公開規則的兩個週期），
   依 `CLAUDE.md`「同家族因子只能算一個獨立發現」，兩者不得當成兩個獨立發現，
   本腳本會直接算出兩者部位序列的相關係數並印出來，不留給事後解釋。
3. `keltner_breakout_20_2atr`：Keltner 通道突破。中線 EMA20、通道 ±2×ATR10，
   收盤突破上/下軌進場，收盤穿回中線出場。
4. `vol_breakout_0p5atr`：波動度突破。收盤 > 前一日收盤 + 0.5×ATR20 做多、
   < 前一日收盤 − 0.5×ATR20 做空，未觸發則延續前一日部位。
5. `cta_multi_tf_voltarget`：CTA 多時間框架趨勢＋波動度目標。20/60/120 日動量
   方向取平均（−1..+1 連續曝險），再乘上 min(1, 15% 年化目標波動 ÷ 60 日已實現
   年化波動)。**與既有 `fut_cheap_gate.hyp_trend_multi_tf`（10/20/60 多數決、
   無波動度目標）是同一家族**，同樣會印相關係數。

判定：`control_group_standard.evaluate_vs_control()`（2026-09-07 升級標準）。
控制組兩個變體、各 200 次抽樣，通過門檻是**嚴格大於兩變體合併 400 次的最大值**
——贏平均、贏 90 百分位都不算過。
  (a) `full_shuffle`：完全打散部位在時間軸上的順序，保留活躍度分布、摧毀時序配對。
  (b) `block_shuffle_20d`：以 20 個交易日為區塊打散，保留短期序列相關性，
      測「單純的序列相關性能不能自己生出假訊號」這個更嚴格的虛無假設。

成本：第 1 關與既有 `fut_cheap_gate.py` 一致，**不計成本**（cheap gate 是快速濾網）。
成本 1×/2×/3× 是第 4 關的事。任何在這裡通過的機制，**在成本敏感度做完之前
不得被稱為可用**。

每一個機制都會 `register_trial()` 登記進 `TRIALS_LEDGER.md`（`CLAUDE.md` 七之三：
未登記的候選判定一律無效）。

用法：
    python research/fut_classic_trend_gate_ext13.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from continuous_contract import build_continuous_series
from control_group_standard import evaluate_vs_control
from trial_registry import register_trial
from validation import holdout

N_DRAWS = 200
SEED_FULL = 20260910
SEED_BLOCK = 20260911
BLOCK_SIZE = 20
RISK_FRAC = 0.01        # 海龜原始規則：每單位承擔 1% 風險
MAX_UNITS = 4           # 海龜原始規則：同方向最多加碼到 4 單位
MAX_EXPOSURE = 1.0      # 我們自己加的名目上限（不做槓桿），偏保守，已在報告中揭露
TARGET_ANN_VOL = 0.15   # CTA 波動度目標：年化 15%


# ── 共用工具 ────────────────────────────────────────────────────────────────
def _atr(df: pd.DataFrame, window: int) -> pd.Series:
    """真實區間均值（Wilder 的 N）。只用到當天以前的資料由呼叫端負責 shift。"""
    high, low, prev_close = df["adj_max"], df["adj_min"], df["adj_close"].shift(1)
    tr = pd.concat([(high - low).abs(),
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(window).mean()


def _terminal_equity(position: pd.Series, ret: pd.Series) -> float:
    """position[t] 用當天以前資訊決定，shift(1) 後才吃到 ret[t]，避免未來函數。"""
    pos = position.shift(1)
    valid = pos.notna() & ret.notna()
    return float((1.0 + pos[valid] * ret[valid]).prod())


def _full_shuffle_draws(position: pd.Series, ret: pd.Series, n: int, seed: int) -> list[float]:
    rng = np.random.RandomState(seed)
    pos_values = position.to_numpy()
    r = ret.reset_index(drop=True)
    return [_terminal_equity(pd.Series(pos_values[rng.permutation(len(pos_values))]), r)
            for _ in range(n)]


def _block_shuffle_draws(position: pd.Series, ret: pd.Series, n: int, seed: int,
                         block_size: int) -> list[float]:
    rng = np.random.RandomState(seed)
    pos_values = position.to_numpy()
    n_blocks = len(pos_values) // block_size
    remainder = pos_values[n_blocks * block_size:]  # 尾巴不足一個區塊，留在原位
    r = ret.reset_index(drop=True)
    draws = []
    for _ in range(n):
        order = rng.permutation(n_blocks)
        shuffled = np.concatenate([pos_values[b * block_size:(b + 1) * block_size]
                                   for b in order] + [remainder])
        draws.append(_terminal_equity(pd.Series(shuffled), r))
    return draws


# ── 五個機制的部位序列 ──────────────────────────────────────────────────────
def _turtle_positions(df: pd.DataFrame, entry_window: int, exit_window: int) -> pd.Series:
    """海龜系統的狀態機（System 1 = 20/10、System 2 = 55/20）。

    只用當天收盤與「當天以前」的通道/ATR 做判斷，部位當天收盤決定、隔天才吃報酬。
    """
    close = df["adj_close"].to_numpy()
    atr = _atr(df, 20).shift(1).to_numpy()               # N，排除當日
    entry_hi = df["adj_max"].rolling(entry_window).max().shift(1).to_numpy()
    entry_lo = df["adj_min"].rolling(entry_window).min().shift(1).to_numpy()
    exit_hi = df["adj_max"].rolling(exit_window).max().shift(1).to_numpy()
    exit_lo = df["adj_min"].rolling(exit_window).min().shift(1).to_numpy()

    out = np.zeros(len(df))
    direction = 0        # -1 / 0 / +1
    units = 0
    last_entry_px = np.nan
    unit_exposure = 0.0

    for i in range(len(df)):
        n = atr[i]
        px = close[i]
        if not np.isfinite(n) or n <= 0 or not np.isfinite(px):
            out[i] = 0.0
            continue
        if direction != 0:
            # 停損：反向走了 2N（以收盤結算，見模組說明的已知偏離）
            if (direction > 0 and px < last_entry_px - 2 * n) or \
               (direction < 0 and px > last_entry_px + 2 * n):
                direction, units, unit_exposure = 0, 0, 0.0
            # 出場：反向 exit_window 突破
            elif (direction > 0 and np.isfinite(exit_lo[i]) and px < exit_lo[i]) or \
                 (direction < 0 and np.isfinite(exit_hi[i]) and px > exit_hi[i]):
                direction, units, unit_exposure = 0, 0, 0.0
            # 加碼：順勢每 0.5N 加一單位，最多 MAX_UNITS
            elif units < MAX_UNITS and (
                    (direction > 0 and px >= last_entry_px + 0.5 * n) or
                    (direction < 0 and px <= last_entry_px - 0.5 * n)):
                units += 1
                last_entry_px = px
        if direction == 0:
            # 進場：收盤突破 entry_window 通道
            if np.isfinite(entry_hi[i]) and px > entry_hi[i]:
                direction, units, last_entry_px = 1, 1, px
            elif np.isfinite(entry_lo[i]) and px < entry_lo[i]:
                direction, units, last_entry_px = -1, 1, px
            if direction != 0:
                unit_exposure = RISK_FRAC / (2.0 * n / px)   # 1% 風險 ÷ 2N（以 % 計）
        out[i] = direction * min(units * unit_exposure, MAX_EXPOSURE) if direction else 0.0
    return pd.Series(out, index=df.index)


def _keltner_positions(df: pd.DataFrame) -> pd.Series:
    close = df["adj_close"]
    mid = close.ewm(span=20, adjust=False).mean()
    band = 2.0 * _atr(df, 10)
    upper, lower = (mid + band).shift(1), (mid - band).shift(1)
    mid_prev = mid.shift(1)
    out = np.zeros(len(df))
    direction = 0
    c = close.to_numpy(); up = upper.to_numpy(); lo = lower.to_numpy(); md = mid_prev.to_numpy()
    for i in range(len(df)):
        if not np.isfinite(up[i]) or not np.isfinite(md[i]):
            out[i] = 0.0
            continue
        if direction > 0 and c[i] < md[i]:
            direction = 0
        elif direction < 0 and c[i] > md[i]:
            direction = 0
        if direction == 0:
            if c[i] > up[i]:
                direction = 1
            elif c[i] < lo[i]:
                direction = -1
        out[i] = float(direction)
    return pd.Series(out, index=df.index)


def _vol_breakout_positions(df: pd.DataFrame) -> pd.Series:
    close = df["adj_close"]
    atr = _atr(df, 20).shift(1)
    prev = close.shift(1)
    raw = pd.Series(np.nan, index=close.index)
    raw[close > prev + 0.5 * atr] = 1.0
    raw[close < prev - 0.5 * atr] = -1.0
    return raw.ffill().fillna(0.0)


def _cta_multi_tf_positions(df: pd.DataFrame) -> pd.Series:
    close = df["adj_close"]
    ret = close.pct_change()
    votes = pd.concat([np.sign(close.pct_change(n)) for n in (20, 60, 120)], axis=1)
    direction = votes.mean(axis=1)                       # -1..+1 連續曝險
    realized = ret.rolling(60).std() * np.sqrt(252)
    scale = (TARGET_ANN_VOL / realized).clip(upper=1.0)  # 只降不加，不做槓桿
    return (direction * scale).fillna(0.0)


# ── 執行 ────────────────────────────────────────────────────────────────────
SELECTION_SPEC_COMMON = (
    "事前綁定：五個機制全部照原文獻公開規則寫死參數（海龜 20/10 與 55/20、2N 停損、"
    "0.5N 加碼上限 4 單位、1% 風險反比部位；Keltner EMA20±2ATR10 穿回中線出場；"
    "波動度突破 0.5ATR20 反向才換邊；CTA 20/60/120 動量平均×15% 年化波動度目標），"
    "不掃參數、不挑格子。標的 TX 日盤連續合約全歷史 2000-2024，逐日結算，第1關不計成本。"
    "控制組兩變體 full_shuffle / block_shuffle_20d 各 N=200，門檻取合併最大值。"
)


def _evaluate(name: str, position: pd.Series, ret: pd.Series) -> dict:
    valid = position.notna() & ret.notna()
    pos_v = position[valid].reset_index(drop=True)
    ret_v = ret[valid].reset_index(drop=True)
    real = _terminal_equity(pos_v, ret_v)
    strat = (pos_v.shift(1) * ret_v).dropna()
    draws_full = _full_shuffle_draws(pos_v, ret_v, N_DRAWS, SEED_FULL)
    draws_block = _block_shuffle_draws(pos_v, ret_v, N_DRAWS, SEED_BLOCK, BLOCK_SIZE)
    verdict = evaluate_vs_control(
        signal_stat=real,
        control_draws={"full_shuffle": draws_full, "block_shuffle_20d": draws_block},
        selection_spec=f"{SELECTION_SPEC_COMMON} 本筆機制={name}。",
    )
    sd = float(strat.std())
    sharpe = float(strat.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    equity = (1.0 + strat).cumprod()
    mdd = float((equity / equity.cummax() - 1.0).min())
    return {
        "name": name,
        "n_days": int(valid.sum()),
        "real_terminal_equity": real,
        "sharpe_ann": sharpe,
        "mdd": mdd,
        "skew": float(strat.skew()),
        "kurtosis": float(strat.kurtosis()),
        "n_obs": int(len(strat)),
        "exposure_mean_abs": float(pos_v.abs().mean()),
        "control_full_max": float(max(draws_full)),
        "control_block_max": float(max(draws_block)),
        "control_median": float(np.median(draws_full + draws_block)),
        "verdict": verdict.as_dict(),
    }


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout 必須維持未動用"

    series, skipped = build_continuous_series()
    series = series.sort_values("date").reset_index(drop=True)
    holdout.assert_no_holdout_leakage(series, context="fut_classic_trend_gate_ext13")
    if skipped:
        print(f"  [note] {len(skipped)} 次轉倉沒有乾淨的調整比率（continuous_contract.py 已知缺口），"
              f"那幾段用未調整原始價，照既有慣例繼續")
    series["ret"] = series["adj_close"].pct_change()
    print(f"TX 連續合約：{series['date'].iloc[0]} ~ {series['date'].iloc[-1]}，共 {len(series)} 個交易日")

    positions = {
        "fut_turtle_system1_20_10": _turtle_positions(series, 20, 10),
        "fut_donchian_full_55_20": _turtle_positions(series, 55, 20),
        "fut_keltner_breakout_20_2atr": _keltner_positions(series),
        "fut_vol_breakout_0p5atr": _vol_breakout_positions(series),
        "fut_cta_multi_tf_voltarget": _cta_multi_tf_positions(series),
    }
    # 既有機制的部位序列，拿來算「是不是同一家族」（|r|>0.7 依 CLAUDE.md 只能算一個發現）
    close = series["adj_close"]
    ref = {
        "既有 hyp_trend_multi_tf(10/20/60 多數決)":
            np.sign(pd.concat([np.sign(close.pct_change(n)) for n in (10, 20, 60)], axis=1).sum(axis=1)),
        "既有 hyp_donchian_breakout(20 收盤通道)":
            pd.Series(np.where(close > close.rolling(20).max().shift(1), 1.0,
                      np.where(close < close.rolling(20).min().shift(1), -1.0, np.nan)),
                      index=close.index).ffill().fillna(0.0),
    }

    results = []
    for name, pos in positions.items():
        r = _evaluate(name, pos, series["ret"])
        results.append(r)
        v = r["verdict"]
        print(f"\n=== {name} ===")
        print(f"  n_days={r['n_days']}  平均曝險={r['exposure_mean_abs']:.3f}")
        print(f"  real_terminal_equity={r['real_terminal_equity']:.4f}"
              f"（{(r['real_terminal_equity'] - 1) * 100:+.1f}%，未計成本）"
              f"  年化Sharpe={r['sharpe_ann']:.3f}  MDD={r['mdd'] * 100:.1f}%")
        print(f"  控制組最大值 full={r['control_full_max']:.4f} block={r['control_block_max']:.4f}"
              f"  中位數={r['control_median']:.4f}")
        print(f"  passed={v['passed']}  百分位={v['control_percentile']:.1f}（記錄用，非通過依據）")
        print(f"  reason={v['reason']}")

    # 家族相關係數（事前就決定要算，不是看到結果才補）
    print("\n=== 部位序列相關係數（|r|>0.7 視為同家族，只能算一個獨立發現）===")
    corr_rows = []
    names = list(positions)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            r = float(positions[a].corr(positions[b]))
            corr_rows.append({"a": a, "b": b, "r": r})
            print(f"  {a} vs {b}: r={r:+.3f}{'  ← 同家族' if abs(r) > 0.7 else ''}")
        for label, s in ref.items():
            r = float(positions[a].corr(s))
            corr_rows.append({"a": a, "b": label, "r": r})
            print(f"  {a} vs {label}: r={r:+.3f}{'  ← 同家族' if abs(r) > 0.7 else ''}")

    for r in results:
        v = r["verdict"]
        verdict_str = "CHEAP_PASS" if v["passed"] else "FAIL"
        no_, line = register_trial(
            track="FUT",
            name=r["name"],
            design=("外部一改.3 名家趨勢跟隨機制第1關cheap gate；TX日盤連續合約全歷史"
                    f"(n_days={r['n_days']})；參數照原文獻寫死不掃；控制組"
                    "full_shuffle/block_shuffle_20d各N=200，門檻=合併最大值"),
            result=(f"終值={r['real_terminal_equity']:.4f}，控制組最大值="
                    f"{max(r['control_full_max'], r['control_block_max']):.4f}，"
                    f"百分位={v['control_percentile']:.1f}，年化Sharpe={r['sharpe_ann']:.3f}，"
                    f"MDD={r['mdd'] * 100:.1f}%，n={r['n_obs']}"),
            verdict=verdict_str,
            notes=("cheap gate不計成本；海龜/Donchian兩者同屬一份公開規則的兩個週期，"
                   "依同家族規則不得當成兩個獨立發現；日K資料只能用收盤價判斷突破與停損，"
                   "方向上對趨勢跟隨有利，非保守偏差"),
            round_note=("開發佇列 外部一改.3（不屬於馬拉松輪次，由 dev queue 自走執行）"),
            sharpe=r["sharpe_ann"],
            n_obs=r["n_obs"],
            skew=r["skew"],
            kurtosis=r["kurtosis"],
        )
        print(f"已登記 TRIALS_LEDGER #{no_}：{r['name']} → {verdict_str}")
        r["trial_no"] = no_

    out = Path(__file__).parent / "data" / "fut_classic_trend_gate_ext13_result.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"results": results, "correlations": corr_rows},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n寫入 {out}")


if __name__ == "__main__":
    main()
