# -*- coding: utf-8 -*-
"""控制組通過標準（升級版）：贏平均不算，要贏「最大值」或 20/20。

（2026-09-07 `PENDING_QUEUE.md` Cybex.債務4。裁示原話：「控制組標準升級：通過門檻改為
20/20 或超過控制組『最大值』（贏平均不算）；控制組自身參數必須掃過；選點必須事前定義，
不得挑訊號好的格子。」）

**為什麼**：舊做法是「訊號的指標落在隨機控制組分布的第 90/95 百分位以上就算過」。
百分位是相對於**分布**的比較，抽樣次數越少、分布越窄，越容易「看起來贏很多」。
Cybex 457 輪的結論是：真正站得住的機制會贏過控制組的**最好那一次**，
而不是贏過控制組的中位數。所以這支把門檻改成三條同時成立：

1. **量級**：訊號指標 **嚴格大於**所有控制組抽樣的最大值；或配對式檢定 **20/20 全勝**
   （每一組配置都贏，一組都不能輸）。「贏過平均/中位數」不算通過。
2. **控制組自身參數要掃**：控制組不能只有一種參數設定。至少兩個變體，
   比較基準取**所有變體的最大值**——拿訊號去比控制組的最高點，不是比某一個方便的設定。
3. **選點事前定義**：呼叫時必須交出 `selection_spec`（選哪個格子/哪組參數、為什麼，
   一段文字），函式會存下它的 sha256。事後看到結果再回來改選點，雜湊就對不上，
   賴不掉——這是 hash-lock 紀律的執行機制，不是裝飾。

**這支不做統計檢定本身**，只做「拿到數字之後怎麼判」。各關卡腳本（`*_gate*.py`、
`deep_dive_*.py`）算完訊號與控制組抽樣後，把數字交給這裡判，不要各自寫各自的門檻。

**單位方向**：所有指標一律「越大越好」。若你的指標是越小越好（例如 MDD），
先取負號再傳進來，並在 `selection_spec` 裡寫明——不要在這裡加一個方向參數，
方向參數是最容易被事後翻轉的東西。

用法：
    from control_group_standard import evaluate_vs_control
    v = evaluate_vs_control(
        signal_stat=1.83,
        control_draws={"shuffle_seed_a": [...], "shuffle_seed_b": [...]},
        selection_spec="事前綁定：k=8/腳、20日換倉、TRAIN 2015-2020，唯一選點",
    )
    print(v.passed, v.reason)

    python research/control_group_standard.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import statistics
import sys
from dataclasses import dataclass, asdict
from typing import Mapping, Sequence

# 抽樣次數下限：低於這個數，「最大值」本身就沒有意義（3 次抽樣的最大值太容易被贏）。
MIN_DRAWS_PER_VARIANT = 20
# 控制組參數變體下限（裁示：控制組自身參數必須掃過）
MIN_CONTROL_VARIANTS = 2
# 配對式檢定的全勝門檻（裁示：20/20）
PAIRED_ALL_WIN_MIN = 20


@dataclass
class ControlVerdict:
    passed: bool
    reason: str
    signal_stat: float
    control_max: float
    control_mean: float
    control_percentile: float
    n_variants: int
    n_draws_total: int
    paired_wins: int | None
    paired_total: int | None
    selection_sha256: str

    def as_dict(self) -> dict:
        return asdict(self)


def _percentile_of(signal: float, draws: Sequence[float]) -> float:
    """訊號在控制組分布中的百分位（只供記錄與對照舊數字，**不是**通過依據）。"""
    if not draws:
        return float("nan")
    return 100.0 * sum(1 for d in draws if signal > d) / len(draws)


def evaluate_vs_control(
    *,
    signal_stat: float,
    control_draws: Mapping[str, Sequence[float]],
    selection_spec: str,
    paired_results: Sequence[bool] | None = None,
    equivalent_check: str = "",
) -> ControlVerdict:
    """用升級後的標準判「訊號有沒有贏過控制組」。

    `control_draws`：{控制組參數變體名稱: 該變體的抽樣結果}。至少兩個變體。
    `paired_results`：配對式檢定每一組配置的勝負（True=訊號贏）。有給的話，
        20/20 全勝是另一條合法的通過路徑。
    `equivalent_check`：**唯一**能豁免「控制組參數要掃」的方式，且必須寫清楚
        改用哪個等價嚴格的檢定（裁示：豁免任何一關必須換等價嚴格檢定，不是拿掉它）。

    不合格的輸入一律 `raise ValueError`——判不出來就不要回一個看起來像結論的東西。
    """
    if not selection_spec.strip():
        raise ValueError("選點必須事前定義：`selection_spec` 不得留空（不得挑訊號好的格子）")
    if not control_draws:
        raise ValueError("沒有控制組抽樣，無法判定")
    if len(control_draws) < MIN_CONTROL_VARIANTS and not equivalent_check.strip():
        raise ValueError(
            f"控制組只有 {len(control_draws)} 種參數設定（下限 {MIN_CONTROL_VARIANTS}）："
            "控制組自身參數必須掃過，否則等於拿訊號去比一個剛好好比的設定。"
            "真的無法掃就傳 `equivalent_check` 寫明改用哪個等價嚴格的檢定"
        )
    for name, draws in control_draws.items():
        if len(draws) < MIN_DRAWS_PER_VARIANT:
            raise ValueError(
                f"控制組變體 `{name}` 只有 {len(draws)} 次抽樣（下限 {MIN_DRAWS_PER_VARIANT}），"
                "抽樣太少時「最大值」沒有意義"
            )

    flat = [float(x) for draws in control_draws.values() for x in draws]
    control_max = max(flat)
    control_mean = statistics.fmean(flat)
    pct = _percentile_of(signal_stat, flat)
    sel_sha = hashlib.sha256(selection_spec.strip().encode("utf-8")).hexdigest()[:16]

    wins = total = None
    if paired_results is not None:
        wins, total = sum(1 for w in paired_results if w), len(paired_results)

    beats_max = signal_stat > control_max
    all_win = (total is not None and total >= PAIRED_ALL_WIN_MIN and wins == total)

    if beats_max:
        reason = (f"通過：訊號 {signal_stat:.4f} 嚴格大於全部 {len(flat)} 次控制組抽樣的最大值 "
                  f"{control_max:.4f}（{len(control_draws)} 個參數變體合併）")
    elif all_win:
        reason = (f"通過：配對式檢定 {wins}/{total} 全勝（門檻 {PAIRED_ALL_WIN_MIN}/{PAIRED_ALL_WIN_MIN}）；"
                  f"量級上未過控制組最大值 {control_max:.4f}，走的是全勝這條路徑")
    else:
        bits = [f"未過：訊號 {signal_stat:.4f} 沒有超過控制組最大值 {control_max:.4f}"
                f"（控制組平均 {control_mean:.4f}，訊號百分位 {pct:.1f}）"]
        if total is not None:
            bits.append(f"配對式 {wins}/{total}，非全勝")
        bits.append("贏過平均或落在高百分位都不算通過（2026-09-07 標準升級）")
        reason = "；".join(bits)
    if equivalent_check.strip():
        reason += f"｜控制組參數未掃，改用等價嚴格檢定：{equivalent_check.strip()}"

    return ControlVerdict(
        passed=bool(beats_max or all_win), reason=reason, signal_stat=float(signal_stat),
        control_max=control_max, control_mean=control_mean, control_percentile=pct,
        n_variants=len(control_draws), n_draws_total=len(flat),
        paired_wins=wins, paired_total=total, selection_sha256=sel_sha,
    )


def require_pass(**kwargs) -> ControlVerdict:
    """判定沒過就直接 raise——給「沒過就不該繼續往下跑」的關卡用。"""
    v = evaluate_vs_control(**kwargs)
    if not v.passed:
        raise ValueError(v.reason)
    return v


def _self_test() -> int:
    fails: list[str] = []
    base = {"a": [0.0] * 25 + [1.0] * 5, "b": [0.2] * 30}  # max=1.0
    spec = "事前綁定：唯一選點，TRAIN 2015-2020"

    v = evaluate_vs_control(signal_stat=1.5, control_draws=base, selection_spec=spec)
    if not v.passed or "嚴格大於" not in v.reason:
        fails.append(f"贏過最大值應該通過：{v.reason}")

    v = evaluate_vs_control(signal_stat=1.0, control_draws=base, selection_spec=spec)
    if v.passed:
        fails.append("跟最大值相等不該算通過（要求嚴格大於）")

    # 高百分位但沒過最大值 → 舊標準會過，新標準不過
    v = evaluate_vs_control(signal_stat=0.9, control_draws=base, selection_spec=spec)
    if v.passed or v.control_percentile < 80:
        fails.append(f"高百分位但沒贏最大值，應判不過：passed={v.passed} pct={v.control_percentile}")

    v = evaluate_vs_control(signal_stat=0.9, control_draws=base, selection_spec=spec,
                            paired_results=[True] * 20)
    if not v.passed or "全勝" not in v.reason:
        fails.append(f"20/20 全勝應該通過：{v.reason}")

    v = evaluate_vs_control(signal_stat=0.9, control_draws=base, selection_spec=spec,
                            paired_results=[True] * 19 + [False])
    if v.passed:
        fails.append("19/20 不是全勝，不該通過")

    v = evaluate_vs_control(signal_stat=0.9, control_draws=base, selection_spec=spec,
                            paired_results=[True] * 10)
    if v.passed:
        fails.append("配對組數不足 20 組，不該用全勝路徑通過")

    def expect_reject(label: str, **kw) -> None:
        args = {"signal_stat": 1.5, "control_draws": base, "selection_spec": spec}
        args.update(kw)
        try:
            evaluate_vs_control(**args)
        except ValueError:
            return
        fails.append(f"應該被拒卻通過了：{label}")

    expect_reject("選點沒有事前定義", selection_spec="  ")
    expect_reject("控制組只有一個參數變體", control_draws={"a": [0.0] * 30})
    expect_reject("抽樣次數不足", control_draws={"a": [0.0] * 5, "b": [0.0] * 30})

    v = evaluate_vs_control(signal_stat=1.5, control_draws={"a": [0.0] * 30},
                            selection_spec=spec, equivalent_check="改用 leave-one-year-out 全年為正")
    if not v.passed or "等價嚴格檢定" not in v.reason:
        fails.append(f"有等價嚴格檢定時應可豁免參數掃描：{v.reason}")

    s1 = evaluate_vs_control(signal_stat=1.5, control_draws=base, selection_spec=spec).selection_sha256
    s2 = evaluate_vs_control(signal_stat=1.5, control_draws=base,
                             selection_spec=spec + " 改成第 3 格").selection_sha256
    if s1 == s2:
        fails.append("選點雜湊沒有隨 selection_spec 改變，事後改選點會賴掉")

    try:
        require_pass(signal_stat=0.5, control_draws=base, selection_spec=spec)
        fails.append("require_pass 沒過卻沒有 raise")
    except ValueError:
        pass

    for f in fails:
        print("✗", f)
    print("✓ self-test 全過" if not fails else f"✗ self-test {len(fails)} 項失敗")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="控制組通過標準（Cybex.債務4）")
    ap.add_argument("--self-test", action="store_true")
    ap.parse_args()
    return _self_test()


if __name__ == "__main__":
    sys.exit(main())
