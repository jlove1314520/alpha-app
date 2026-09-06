# -*- coding: utf-8 -*-
"""候選報告閘門：DSR 必須與原始指標並列，未登記的判定一律無效。

（2026-09-07 `PENDING_QUEUE.md` Cowork.債務2.4。裁示原話：「規則升級：**報告任何候選時，
DSR 必須與原始指標並列**。未經登記（未寫進 TRIALS_LEDGER）的判定一律無效，不得寫進
LEADS、不得提請審核。」）

**為什麼要一支程式，而不是只在文件裡多寫一條規則**：規則寫在 `MARATHON_PROTOCOL.md`
已經一天了（Cybex.債務3 的登記強制化），真正擋下違規的是 `trial_registry.py --check`
那個閘門，不是那段文字。同理，「DSR 要並列」如果只是文件裡的一句話，下一輪馬拉松
在凌晨三點自動跑的時候不會有人記得——它必須是「不照做就 raise」的函式。

這支提供三件事：

1. `deflated_sharpe()`：Bailey & López de Prado (2014) 的 DSR。**方法照抄，參數不抄**
   ——公式本身是統計學，沒有市場相依的參數可抄（`CLAUDE.md` 七之三移植原則）。
2. `report_candidate()`：產生候選報告區塊的**唯一合法出口**。它會先呼叫
   `trial_registry.assert_registered()`（未登記直接 raise），再強制輸出裡同時有
   原始指標與 DSR。DSR 算不出來時**不准省略那一行**，必須寫明為什麼算不出來，
   且該候選一律標成「不得提請審核」——這是 `SELECTION_BIAS_LEDGER.md` 第 5 節
   「不編數字」原則的延伸：算不出來要說算不出來，不是安靜地不寫。
3. `--audit`：掃 `*_LEADS.md`，強制期（2026-09-07 起）內判定為
   PASS/CHEAP_PASS/EXPERIMENTAL 的列若沒有並列 DSR，回報違規並 exit 1。

**限制誠實揭露**：目前 `TRIALS_REGISTRY.jsonl` 裡幾乎沒有 Sharpe 欄位，所以絕大多數
既有候選的 DSR **仍然算不出來**（債務2.3 已經照實記過這件事）。本輪不回頭替歷史候選
編造 Sharpe，只做兩件事：把新候選的出口卡死，並讓 `register_trial()` 能收下
Sharpe/T/skew/kurt 四個 DSR 必要輸入，讓「往後算得出來」成為可能。

用法：
    python research/candidate_report.py --audit      # 稽核閘門，違規 exit 1
    python research/candidate_report.py --self-test  # 自我測試（不碰正式帳本）

程式內：
    from candidate_report import report_candidate, deflated_sharpe, CandidateStats
    blk = report_candidate(key="f_low_vol", headline={"隨機控制組百分位": "100.0"},
                           stats=CandidateStats(sharpe=0.06, n_obs=1200, skew=-0.3, kurtosis=4.1),
                           var_sr_trials=0.25)
    print(blk["markdown"])
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# 同目錄模組。`norm_cdf`/`expected_max_sharpe` 不重寫一份——同一個經濟量正負號
# 只能記一次（`CLAUDE.md` 七之三工程紀律），兩份實作遲早會漂移。
try:
    from selection_bias_ledger import expected_max_sharpe, norm_cdf
    from trial_registry import ENFORCE_FROM, VALID_VERDICTS, assert_registered, registry_records
except ImportError:  # 從別的工作目錄執行時
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from selection_bias_ledger import expected_max_sharpe, norm_cdf
    from trial_registry import ENFORCE_FROM, VALID_VERDICTS, assert_registered, registry_records

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
LEADS_FILES = ("LEADS.md", "TW_LEADS.md", "US_LEADS.md", "FUT_LEADS.md")

# DSR 是「這個 Sharpe 在扣掉搜尋次數的膨脹後，仍然大於 0 的機率」。
# 0.95 是 Bailey & López de Prado 原文用的慣例門檻，不是從別的市場調出來的參數。
DSR_MIN = 0.95
# 「報告候選」才受這條規則管——FAIL 不是候選，不需要並列 DSR。
CANDIDATE_VERDICTS = ("CHEAP_PASS", "PASS", "EXPERIMENTAL")


@dataclass(frozen=True)
class CandidateStats:
    """DSR 的四個必要輸入。四個要嘛全給、要嘛全不給，不接受給一半。

    `sharpe` 與 `n_obs` 必須是**同一個頻率**：日資料就給日 Sharpe 與日數，
    不要給年化 Sharpe 配日數——那會讓 DSR 高到離譜。年化值請先用
    `deannualize()` 轉回單期，並在報告裡註明頻率。
    `kurtosis` 是**非超額**峰態（常態分布 = 3.0），不是 excess kurtosis。
    """

    sharpe: float
    n_obs: int
    skew: float
    kurtosis: float
    freq_label: str = "每期"


def deannualize(annual_sharpe: float, periods_per_year: int) -> float:
    """年化 Sharpe → 單期 Sharpe。DSR 公式吃的是單期值。"""
    if periods_per_year <= 0:
        raise ValueError("periods_per_year 必須為正整數")
    return annual_sharpe / math.sqrt(periods_per_year)


def trials_sharpe_variance() -> tuple[float | None, int]:
    """從 `TRIALS_REGISTRY.jsonl` 已登記的 Sharpe 估試驗間變異數 V。

    回傳 `(V, 樣本數)`；不足兩筆時回 `(None, n)`——**不回一個猜的數字**。
    V 是 E[max SR] 的必要輸入，猜錯會直接讓 DSR 失去意義。
    """
    vals = [
        r["dsr_inputs"]["sharpe"]
        for r in registry_records()
        if isinstance(r.get("dsr_inputs"), dict) and r["dsr_inputs"].get("sharpe") is not None
    ]
    if len(vals) < 2:
        return None, len(vals)
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return var, len(vals)


def default_n_trials() -> tuple[int, str]:
    """DSR 的分母 N：取兩個現存口徑的**較大者**（較保守），並把兩個數字都說出來。

    這裡有一個 2026-09-07 稽核當下發現、**尚未裁示**的分歧，不能靜默挑一個用：

    - `trial_registry.trial_rows()`：190 列，**排除** 2026-08-25 那張 FDR 重新評分對照表
      （33 列），理由是那張表是對既有試驗的重新評分，不是新的試驗。
    - `selection_bias_ledger.parse()`：223 列，**包含**那 33 列（190+33=223），
      `TRIALS_LEDGER.md` 檔頭與 `SELECTION_BIAS_LEDGER.md` 目前寫的就是這個數。

    改用哪一個會直接動到 Cowork.債務2.2 已經產出的「撐住 3、倒下 5」結論，
    依 `PENDING_QUEUE.md` 那一條的註記，**該由總司令裁示**，不是這支程式自己決定。
    在裁示之前取較大者：N 越大 → SR0 越高 → DSR 越低 → 判定越嚴。
    寧可嚴到誤殺，不可鬆到放行（`CLAUDE.md`「最高投資原則」）。
    """
    from trial_registry import trial_rows  # 延後匯入：自我測試會改寫 LEDGER，要抓當下的值

    import selection_bias_ledger as sbl

    n_reg = len(trial_rows())
    try:
        n_led = len(sbl.parse())
    except Exception as e:  # noqa: BLE001 — 解析失敗不能靜默當成 0，那會讓門檻整個垮掉
        raise RuntimeError(f"算不出 selection_bias_ledger 口徑的 N：{e!r}") from e
    n = max(n_reg, n_led)
    return n, (f"取兩口徑較大者（較保守）：trial_registry {n_reg} 列（排除 FDR 對照表）／"
               f"selection_bias_ledger {n_led} 列（含對照表）；口徑分歧待總司令裁示")


def deflated_sharpe(stats: CandidateStats, n_trials: int, var_sr_trials: float) -> dict:
    """Deflated Sharpe Ratio（Bailey & López de Prado 2014）。

    SR0 = sqrt(V) · [(1−γ)·Φ⁻¹(1−1/N) + γ·Φ⁻¹(1−1/(N·e))]
    DSR = Φ[ (SR̂ − SR0)·√(T−1) / √(1 − γ3·SR̂ + (γ4−1)/4·SR̂²) ]

    參數不合法一律 raise，不回一個看起來像數字的東西——靜默的錯誤數字比沒有數字糟。
    """
    if n_trials < 2:
        raise ValueError(f"DSR 需要 N≥2 次試驗才有意義（收到 {n_trials}）")
    if not (var_sr_trials > 0):
        raise ValueError(f"試驗間 Sharpe 變異數 V 必須為正（收到 {var_sr_trials}）")
    if stats.n_obs < 2:
        raise ValueError(f"DSR 需要 T≥2 期觀測（收到 {stats.n_obs}）")
    if stats.kurtosis <= 0:
        raise ValueError(f"kurtosis 是非超額峰態（常態=3.0），不得 ≤0（收到 {stats.kurtosis}）")

    sr = float(stats.sharpe)
    sr0 = expected_max_sharpe(n_trials, var_sr_trials)
    denom_sq = 1.0 - stats.skew * sr + (stats.kurtosis - 1.0) / 4.0 * sr * sr
    if denom_sq <= 0:
        raise ValueError(
            f"DSR 分母平方為非正（{denom_sq:.6g}）：skew/kurtosis 與 Sharpe 的組合不合法，"
            "先檢查是不是把年化 Sharpe 當單期 Sharpe 傳進來了"
        )
    z = (sr - sr0) * math.sqrt(stats.n_obs - 1) / math.sqrt(denom_sq)
    return {
        "dsr": norm_cdf(z),
        "sr_observed": sr,
        "sr0_threshold": sr0,
        "n_trials": n_trials,
        "var_sr_trials": var_sr_trials,
        "n_obs": stats.n_obs,
        "z": z,
        "freq_label": stats.freq_label,
    }


def report_candidate(
    *,
    key: str,
    headline: dict,
    stats: CandidateStats | None = None,
    n_trials: int | None = None,
    var_sr_trials: float | None = None,
    dsr_blocked_reason: str = "",
    track: str = "",
) -> dict:
    """產生候選報告區塊。這是報告候選的**唯一合法出口**。

    `key`：因子/策略代碼（`f_low_vol`）或帳本編號（`#123`）。帳本裡找不到就 raise
    ——「未登記的判定一律無效」在這裡是可執行的，不是一句口號。
    `headline`：原始指標（例：`{"隨機控制組百分位": "100.0", "VAL 年化": "+4.8%"}`）。
    留空 raise：DSR「並列」的前提是原始指標也在，只報 DSR 不算並列。
    `stats`：DSR 四輸入。給不出來就必須填 `dsr_blocked_reason`，該候選標成
    **不得提請審核**——不是靜默省略那一行。

    回傳 `{"markdown", "admissible", "trial_id", "dsr", ...}`。
    """
    tid = assert_registered(key)  # 未登記 → ValueError

    if not isinstance(headline, dict) or not headline:
        raise ValueError(
            "報告被拒：`headline`（原始指標）不得留空——規則是「DSR 與原始指標並列」，"
            "少了原始指標就不是並列"
        )
    clean_headline = {}
    for k, v in headline.items():
        ks, vs = str(k).strip(), str(v).strip()
        if not ks or not vs:
            raise ValueError(f"報告被拒：原始指標 `{k}` 的名稱或數值是空的，禁止靜默記 None")
        clean_headline[ks] = vs

    n = n_trials
    n_src = "呼叫端指定"
    if n is None:
        n, n_src = default_n_trials()

    dsr_res: dict | None = None
    blocked = ""
    if stats is None:
        blocked = dsr_blocked_reason.strip()
        if not blocked:
            raise ValueError(
                "報告被拒：沒有 `stats`（Sharpe/T/skew/kurtosis）就必須填 `dsr_blocked_reason` "
                "說明 DSR 為什麼算不出來。**不准直接省略 DSR 那一行**"
            )
    else:
        v = var_sr_trials
        v_src = "呼叫端指定"
        if v is None:
            v, n_v = trials_sharpe_variance()
            v_src = f"由 TRIALS_REGISTRY.jsonl 的 {n_v} 筆已登記 Sharpe 估得"
            if v is None:
                blocked = dsr_blocked_reason.strip() or ""
                if not blocked:
                    raise ValueError(
                        f"報告被拒：算不出試驗間 Sharpe 變異數 V（登記簿只有 {n_v} 筆 Sharpe，"
                        "需要 ≥2 筆）。請明確傳 `var_sr_trials`，或填 `dsr_blocked_reason` "
                        "說明為什麼這一輪算不出 DSR——不准用猜的 V 硬算一個數字出來"
                    )
        if not blocked:
            dsr_res = deflated_sharpe(stats, n, v)
            dsr_res["var_source"] = v_src

    admissible = dsr_res is not None and dsr_res["dsr"] >= DSR_MIN

    L = [f"**候選 `{key}`**（TRIALS_LEDGER #{tid}{('，' + track + ' 軌') if track else ''}）"]
    L.append("")
    L.append("| 項目 | 數值 |")
    L.append("|---|---|")
    for k, v in clean_headline.items():
        L.append(f"| {k}（原始指標） | {v} |")
    if dsr_res is not None:
        L.append(f"| **Deflated Sharpe (DSR)** | **{dsr_res['dsr']:.4f}**"
                 f"（門檻 {DSR_MIN}，{'通過' if admissible else '**未通過**'}） |")
        L.append(f"| 觀測 Sharpe（{dsr_res['freq_label']}） | {dsr_res['sr_observed']:.4f} |")
        L.append(f"| 期望最大 Sharpe SR0（N={dsr_res['n_trials']}） | {dsr_res['sr0_threshold']:.4f} |")
        L.append(f"| 試驗次數 N 的來源 | {n_src} |")
        L.append(f"| 觀測期數 T | {dsr_res['n_obs']} |")
        L.append(f"| 試驗間 Sharpe 變異數 V | {dsr_res['var_sr_trials']:.4f}"
                 f"（{dsr_res['var_source']}） |")
    else:
        L.append(f"| **Deflated Sharpe (DSR)** | **無法計算**：{blocked} |")
    L.append("")
    if admissible:
        L.append(f"→ DSR {dsr_res['dsr']:.4f} ≥ {DSR_MIN}，**可提請審核**。")
    elif dsr_res is not None:
        L.append(f"→ DSR {dsr_res['dsr']:.4f} < {DSR_MIN}：原始指標再漂亮也只是搜尋次數的產物，"
                 "**不得提請審核、不得寫進 LEADS 為有效候選**。")
    else:
        L.append("→ DSR 算不出來 = **不得提請審核**。算不出來不等於通過，"
                 "補齊 Sharpe/T/skew/kurtosis 後重報。")

    return {
        "markdown": "\n".join(L) + "\n",
        "admissible": admissible,
        "trial_id": tid,
        "dsr": dsr_res["dsr"] if dsr_res else None,
        "sr0_threshold": dsr_res["sr0_threshold"] if dsr_res else None,
        "n_trials": n,
        "n_trials_source": n_src,
        "blocked_reason": blocked or None,
        "headline": clean_headline,
    }


def assert_reportable(**kw) -> dict:
    """`report_candidate()` 的嚴格版：不可提請審核就直接 raise。

    寫進 `*_LEADS.md`／提交審核／納入組合成分之前呼叫這支，不要自己看數字判斷。
    """
    res = report_candidate(**kw)
    if not res["admissible"]:
        why = res["blocked_reason"] or f"DSR {res['dsr']:.4f} < {DSR_MIN}"
        raise ValueError(f"候選 `{kw.get('key')}` 不得提請審核：{why}")
    return res


# ── 稽核閘門 ────────────────────────────────────────────────────────────────
DSR_MENTION = re.compile(r"DSR|[Dd]eflated\s*Sharpe")


def audit() -> dict:
    """掃 LEADS：強制期內的候選判定必須並列 DSR（或明寫 DSR 為何算不出來）。"""
    violations: list[str] = []
    legacy: list[str] = []
    checked = 0
    for fname in LEADS_FILES:
        path = RESEARCH / fname
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            # 判定欄：從右往左找第一個候選判定關鍵字；CHEAP_PASS 要先於 PASS 比對。
            verdict = ""
            for cell in reversed(cells):
                hit = next((v for v in VALID_VERDICTS if v in cell), "")
                if hit:
                    verdict = hit
                    break
            if verdict not in CANDIDATE_VERDICTS:
                continue  # FAIL/ABANDONED/REFUTED 不是「報告候選」，不受這條規則管
            date = next((x for x in cells if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)), "")
            checked += 1
            if DSR_MENTION.search(line):
                continue
            item = f"{fname}:{i} 判定 {verdict} 但沒有並列 DSR"
            (violations if date >= ENFORCE_FROM else legacy).append(item)
    return {
        "candidate_rows_checked": checked,
        "violations": violations,
        "legacy_missing_dsr": legacy,
        "enforce_from": ENFORCE_FROM,
        "dsr_min": DSR_MIN,
    }


def _print_audit(res: dict) -> int:
    print(f"LEADS 候選列（PASS/CHEAP_PASS/EXPERIMENTAL）：{res['candidate_rows_checked']} 列")
    print(f"存量未並列 DSR：{len(res['legacy_missing_dsr'])} 列"
          f"（{res['enforce_from']} 之前，只報不擋——歷史列沒留 Sharpe，回頭補等於編數字）")
    if res["violations"]:
        print(f"\n✗ FAIL：{len(res['violations'])} 筆 {res['enforce_from']} 起的候選沒有並列 DSR：")
        for v in res["violations"]:
            print("   -", v)
        return 1
    print(f"\n✓ PASS：沒有任何強制期內的候選漏掉 DSR（門檻 DSR ≥ {res['dsr_min']}）")
    return 0


# ── 自我測試 ────────────────────────────────────────────────────────────────
def _self_test() -> int:
    import tempfile

    import trial_registry as tr

    fails: list[str] = []

    def near(a, b, tol=1e-9):
        return abs(a - b) < tol

    # 用**單期** Sharpe 與相稱的試驗間變異數（V=0.0025 即試驗 Sharpe 標準差 0.05）。
    # 第一版拿 V=0.25 配單期 Sharpe 0.10，SR0≈1.25 遠高於觀測值，DSR 全部下溢成 0.0，
    # 三個單調性檢查變成「0 跟 0 比」——測了等於沒測。
    base = CandidateStats(sharpe=0.10, n_obs=1000, skew=0.0, kurtosis=3.0)
    V = 0.0025

    # 1) SR̂ 恰等於 SR0 時，z=0 → DSR 必須剛好 0.5（決定性檢查，不是靠眼睛看）
    sr0 = expected_max_sharpe(50, V)
    r = deflated_sharpe(CandidateStats(sharpe=sr0, n_obs=1000, skew=0.0, kurtosis=3.0), 50, V)
    if not near(r["dsr"], 0.5, 1e-12):
        fails.append(f"SR̂=SR0 時 DSR 應為 0.5，得到 {r['dsr']}")

    # 2) 搜尋次數越多，同一個 Sharpe 的 DSR 必須越低（DSR 的全部意義就在這件事）
    d_small = deflated_sharpe(base, 5, V)["dsr"]
    d_big = deflated_sharpe(base, 500, V)["dsr"]
    if not d_big < d_small:
        fails.append(f"N 變大 DSR 沒有下降：N=5 {d_small:.4f} vs N=500 {d_big:.4f}")

    # 3) 觀測期數越長，同一個（贏過 SR0 的）Sharpe 越可信 → DSR 應上升。
    #    刻意取 0.15 > SR0(N=50)≈0.114：SR̂ 低於 SR0 時 T 變大反而讓 DSR 下降，
    #    那是正確行為，不能拿來當這條檢查的樣本。
    if not deflated_sharpe(CandidateStats(0.15, 5000, 0.0, 3.0), 50, V)["dsr"] > \
           deflated_sharpe(CandidateStats(0.15, 200, 0.0, 3.0), 50, V)["dsr"]:
        fails.append("T 變大 DSR 沒有上升")

    # 4) 負偏態（左尾風險）必須讓 DSR 變差，不是變好
    d_neg = deflated_sharpe(CandidateStats(0.15, 1000, -1.0, 3.0), 50, V)["dsr"]
    d_pos = deflated_sharpe(CandidateStats(0.15, 1000, +1.0, 3.0), 50, V)["dsr"]
    if not d_neg < d_pos:
        fails.append(f"負偏態沒有壓低 DSR：neg {d_neg:.4f} vs pos {d_pos:.4f}")

    def expect_raise(label, fn):
        try:
            fn()
        except ValueError:
            return
        except Exception as e:  # noqa: BLE001
            fails.append(f"{label}：拋了非 ValueError 的例外 {e!r}")
            return
        fails.append(f"應該被拒卻通過了：{label}")

    expect_raise("N<2", lambda: deflated_sharpe(base, 1, V))
    expect_raise("V≤0", lambda: deflated_sharpe(base, 50, 0.0))
    expect_raise("T<2", lambda: deflated_sharpe(CandidateStats(0.1, 1, 0.0, 3.0), 50, V))
    expect_raise("kurtosis≤0", lambda: deflated_sharpe(CandidateStats(0.1, 100, 0.0, 0.0), 50, V))
    expect_raise("分母平方非正（年化 Sharpe 誤當單期）",
                 lambda: deflated_sharpe(CandidateStats(3.0, 1000, 2.0, 1.0), 50, V))

    # 5) 報告出口：未登記 → 一律無效
    expect_raise("未登記的候選", lambda: report_candidate(
        key="#999999", headline={"百分位": "100.0"}, dsr_blocked_reason="測試"))

    # 6) 走完整寫入路徑，但**只碰暫存帳本**
    real_ledger, real_jsonl = tr.LEDGER, tr.JSONL
    tmp = Path(tempfile.mkdtemp(prefix="candidate_report_selftest_"))
    try:
        tr.LEDGER, tr.JSONL = tmp / "L.md", tmp / "R.jsonl"
        tr.LEDGER.write_text(
            "| # | 日期 | 軌道 | 假說名稱 | 型態 | 關卡結果 | 判定 | 備註 |\n"
            "|---|---|---|---|---|---|---|---|\n"
            "| 1 | 2026-09-07 | TW | `f_selftest` | 因子 | 99.0 百分位 | CHEAP_PASS | x |\n"
            f"{tr.INSERT_ANCHOR}\n",
            encoding="utf-8")

        expect_raise("原始指標留空（只報 DSR 不算並列）", lambda: report_candidate(
            key="f_selftest", headline={}, dsr_blocked_reason="測試"))
        expect_raise("沒有 stats 也沒說明 DSR 為何算不出來", lambda: report_candidate(
            key="f_selftest", headline={"百分位": "99.0"}))
        expect_raise("登記簿 Sharpe 不足又沒指定 V", lambda: report_candidate(
            key="f_selftest", headline={"百分位": "99.0"},
            stats=CandidateStats(0.1, 1000, 0.0, 3.0)))

        blocked = report_candidate(key="f_selftest", headline={"百分位": "99.0"},
                                   dsr_blocked_reason="帳本未記 Sharpe")
        if blocked["admissible"]:
            fails.append("DSR 算不出來卻被判可提請審核")
        if "Deflated Sharpe" not in blocked["markdown"] or "無法計算" not in blocked["markdown"]:
            fails.append("DSR 算不出來時，報告裡沒有留下那一行")
        if "99.0" not in blocked["markdown"]:
            fails.append("報告裡沒有並列原始指標")

        good = report_candidate(key="f_selftest", headline={"百分位": "99.0"},
                                stats=CandidateStats(0.30, 2000, 0.0, 3.0),
                                n_trials=50, var_sr_trials=0.01)
        if not good["admissible"] or good["dsr"] < DSR_MIN:
            fails.append(f"高 Sharpe 低 V 應可提請審核，卻得到 dsr={good['dsr']}")
        bad = report_candidate(key="f_selftest", headline={"百分位": "99.0"},
                               stats=CandidateStats(0.01, 2000, 0.0, 3.0),
                               n_trials=500, var_sr_trials=0.25)
        if bad["admissible"]:
            fails.append("低 Sharpe 高搜尋次數不該可提請審核")
        expect_raise("assert_reportable 對不合格候選沒擋下", lambda: assert_reportable(
            key="f_selftest", headline={"百分位": "99.0"},
            stats=CandidateStats(0.01, 2000, 0.0, 3.0), n_trials=500, var_sr_trials=0.25))

        # 7) 預設分母要由帳本推導（且取兩口徑較大者），不是寫死
        import selection_bias_ledger as sbl

        real_sbl_ledger = sbl.LEDGER
        try:
            sbl.LEDGER = tr.LEDGER
            auto = report_candidate(key="f_selftest", headline={"百分位": "99.0"},
                                    dsr_blocked_reason="測試分母來源")
            if auto["n_trials"] != 1:
                fails.append(f"預設分母沒有由帳本推導：{auto['n_trials']} != 1")
            if "兩口徑較大者" not in auto["n_trials_source"]:
                fails.append(f"分母來源沒有誠實揭露口徑分歧：{auto['n_trials_source']}")
        finally:
            sbl.LEDGER = real_sbl_ledger

        # 8) register_trial 收下 DSR 四輸入後，V 要能從登記簿估出來
        for s in (0.05, 0.15):
            tr.register_trial(track="TW", name="`f_selftest_v`", design="因子",
                              result="99.0 百分位", verdict="FAIL", notes="自我測試",
                              round_no=999, sharpe=s, n_obs=1000, skew=0.0, kurtosis=3.0)
        v, nv = trials_sharpe_variance()
        if nv != 2 or v is None or not near(v, 0.005, 1e-12):
            fails.append(f"從登記簿估 V 錯：n={nv} v={v}")
    except Exception as e:  # noqa: BLE001 — 測試自己爆掉也要如實報
        fails.append(f"暫存帳本路徑爆掉：{e!r}")
    finally:
        tr.LEDGER, tr.JSONL = real_ledger, real_jsonl
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    for f in fails:
        print("✗", f)
    print("✓ self-test 全過" if not fails else f"✗ self-test {len(fails)} 項失敗")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="候選報告閘門（Cowork.債務2.4）")
    ap.add_argument("--audit", action="store_true", help="稽核 LEADS：候選必須並列 DSR")
    ap.add_argument("--self-test", action="store_true", help="自我測試（只碰暫存檔）")
    ap.add_argument("--json", action="store_true", help="--audit 改輸出 JSON")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    res = audit()
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 1 if res["violations"] else 0
    return _print_audit(res)


if __name__ == "__main__":
    sys.exit(main())
