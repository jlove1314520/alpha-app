"""`HYPOTHESIS_QUEUE.md` #64 台指期貨基差(TX Futures-Spot Basis)regime訊號 — 第1關cheap gate。

背景/經濟機制/資料可行性查證見`HYPOTHESIS_QUEUE.md` #64條目（地基determinism前置
檢查已通過，本輪正式進第1關）。本腳本把該條目的規格轉成可執行的cheap gate。

**事前綁定規格（跑數字前定案，不得事後調整）**：

1. **資料源**：`fut_basis_series.build_basis_series()`（已驗證的既有模組，零新增
   API呼叫），逐日basis_pct + spot_close，全歷史範圍（2000-2024）。

2. **訊號**：`deviation = basis_pct - basis_pct.rolling(60).mean().shift(1)`
   （shift(1)排除當天自己，只用當天以前的觀測當「近期常態」基準，同
   `hyp_basis_mean_reversion`既有no-lookahead精神）。`position = sign(deviation)`
   ——**直接取號，不像`hyp_basis_mean_reversion`(#38/#43)取負號**：那個假說賭
   basis本身會回歸均值，這個假說賭的是**TAIEX現貨的未來報酬**跟着偏離方向走
   （深度逆價差=更負的deviation→預期未來報酬為負；升水擴大=更正的deviation→
   預期未來報酬為正），是完全不同的預測目標，不是同一機制換皮。

3. **目標變數**：TAIEX現貨次日報酬`spot_ret = spot_close.pct_change()`——
   **不是期貨自身報酬**（`fut_close`的報酬），刻意避開`#35`/`#36`/`#38`已死的
   「期貨自身timing」機制家族，這是`#64`跟basis家族前三個假說最核心的差異。

4. **持倉/換倉頻率**：逐日換倉（`position.shift(1) * spot_ret`每日結算，
   複利到全歷史終值）——採**連續exposure timing框架**（非事件研究框架），
   理由：basis_pct每個交易日都有觀測值（不像借券費率/鉅額交易只在少數
   事件日才有觀測），適用連續timing比事件研究更貼合資料本身的性質，
   這是`HYPOTHESIS_QUEUE.md` #64條目「下一輪視basis連續/離散性質擇一並
   寫死理由」的具體執行——選連續，理由如上，不得事後改選事件研究。

5. **控制組（`control_group_standard.py` 2026-09-07升級標準，2個參數變體，
   各200次抽樣）**：
   (a) `full_shuffle`：完全打散position在時間序上的順序（`np.random.permutation`），
       保留真實策略的活躍度分布（多空比例、部位大小），摧毀時序配對關係——
       跟`fut_cheap_gate.py`既有`_permutation_test`同款精神。
   (b) `block_shuffle_20d`：以20個交易日為一個區塊，打散區塊順序（區塊內部
       順序不變），保留短期序列相關性結構，測試「單純的序列相關性本身能否
       製造出假訊號」這個更嚴格的虛無假設。
   兩個變體皆N=200抽樣，比較基準取兩者合併後的最大值（`evaluate_vs_control`
   內部處理）。

6. **判定路徑**：訊號（真實策略終值）嚴格大於兩個控制組變體合併400次抽樣的
   最大值，或20/20配對式全勝（本輪不做配對式版本，只走第一條路徑）。

**零新增API呼叫**：完全複用`fut_basis_series.build_basis_series()`既有快取
（round66/69已驗證）。

2026-09-09 馬拉松第484輪（銜接`hypothesis_queue`排程設計的#64地基工作）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

import fut_basis_series
from control_group_standard import evaluate_vs_control
from validation import holdout

WINDOW = 60
N_DRAWS = 200
SEED_FULL = 20260909
SEED_BLOCK = 20260910
BLOCK_SIZE = 20

SELECTION_SPEC = (
    "事前綁定：basis_pct相對自身60日移動平均偏離(shift(1)排除當日)，direct sign"
    "（非負號），全歷史(2000-2024)單一視窗設定WINDOW=60，唯一選點；訊號逐日換倉"
    "預測TAIEX現貨次日報酬spot_close.pct_change()（非期貨自身報酬），"
    "避免混淆#35/#36/#38已死的期貨自身timing機制家族。控制組兩變體："
    "full_shuffle(完全打散順序)/block_shuffle_20d(20日區塊打散)，各N=200，"
    "取兩者合併最大值為通過門檻。"
)


def _terminal_equity(position: pd.Series, ret: pd.Series) -> float:
    """position[t]用當天以前資訊決定，shift(1)後才吃到ret[t]，避免未來函數。"""
    pos = position.shift(1)
    valid = pos.notna() & ret.notna()
    daily = 1.0 + pos[valid] * ret[valid]
    return float(daily.prod())


def _full_shuffle_draws(position: pd.Series, ret: pd.Series, n: int, seed: int) -> list[float]:
    rng = np.random.RandomState(seed)
    pos_values = position.to_numpy()
    draws = []
    for i in range(n):
        shuffled = pos_values[rng.permutation(len(pos_values))]
        draws.append(_terminal_equity(pd.Series(shuffled), ret.reset_index(drop=True)))
    return draws


def _block_shuffle_draws(
    position: pd.Series, ret: pd.Series, n: int, seed: int, block_size: int
) -> list[float]:
    rng = np.random.RandomState(seed)
    pos_values = position.to_numpy()
    n_rows = len(pos_values)
    n_blocks = n_rows // block_size
    draws = []
    for i in range(n):
        block_order = rng.permutation(n_blocks)
        shuffled_blocks = [pos_values[b * block_size:(b + 1) * block_size] for b in block_order]
        remainder = pos_values[n_blocks * block_size:]  # tail shorter than one block, kept in place
        shuffled = np.concatenate(shuffled_blocks + [remainder])
        draws.append(_terminal_equity(pd.Series(shuffled), ret.reset_index(drop=True)))
    return draws


def main() -> None:
    assert holdout.is_holdout_consumed() is False, "holdout must remain untouched"

    basis = fut_basis_series.build_basis_series().sort_values("date").reset_index(drop=True)
    holdout.assert_no_holdout_leakage(basis, context="fut_basis_regime_gate64")
    basis["spot_ret"] = basis["spot_close"].pct_change()

    trailing_mean = basis["basis_pct"].rolling(WINDOW).mean().shift(1)
    deviation = basis["basis_pct"] - trailing_mean
    position = np.sign(deviation)
    ret = basis["spot_ret"]

    valid = position.notna() & ret.notna()
    position_v = position[valid].reset_index(drop=True)
    ret_v = ret[valid].reset_index(drop=True)
    n_days = int(valid.sum())
    print(f"usable rows after WINDOW={WINDOW} warm-up + spot_ret first-diff: {n_days}")

    real_equity = _terminal_equity(position_v, ret_v)
    print(f"real_terminal_equity={real_equity:.4f} ({(real_equity - 1) * 100:+.1f}% cumulative, no costs)")

    draws_full = _full_shuffle_draws(position_v, ret_v, N_DRAWS, SEED_FULL)
    draws_block = _block_shuffle_draws(position_v, ret_v, N_DRAWS, SEED_BLOCK, BLOCK_SIZE)
    print(f"full_shuffle: n={len(draws_full)}, median={np.median(draws_full):.4f}, max={max(draws_full):.4f}")
    print(f"block_shuffle_20d: n={len(draws_block)}, median={np.median(draws_block):.4f}, max={max(draws_block):.4f}")

    verdict = evaluate_vs_control(
        signal_stat=real_equity,
        control_draws={"full_shuffle": draws_full, "block_shuffle_20d": draws_block},
        selection_spec=SELECTION_SPEC,
    )
    print(f"\n=== fut_basis_regime_gate64 ===")
    print(f"passed={verdict.passed}")
    print(f"reason={verdict.reason}")
    print(f"control_percentile={verdict.control_percentile:.1f} (記錄用，非通過依據)")

    result = {
        "name": "fut_basis_regime_gate64",
        "n_days": n_days,
        "window": WINDOW,
        "real_terminal_equity": real_equity,
        "verdict": verdict.as_dict(),
    }
    out_path = Path(__file__).parent / "data" / "fut_basis_regime_gate64_result.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n寫入 {out_path}")


if __name__ == "__main__":
    main()
