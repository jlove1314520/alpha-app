"""#75続14：2018+子樣本第1關cheap IC gate（(i)僅有價格 vs (ii)悲觀填補版並列）。
事前綁定（照#75続10 SPEC）：訊號=net_usd（主）/n_buyers（同家族，僅供對照，不獨立算發現），
方向=正，逐月橫斷面Spearman IC，train=[2018-01,2020-12]、val=(2020-12,2024-11]（既有
validation/holdout.py TRAIN_END/VAL_END邊界，樣本本身2018+已由G0-a/b事前綁定）。
null：逐月內打散訊號值N=200次（保留當月fwd20不動），重算平均IC，percentile>=90且
train/val同號（正）才算過。net_usd與n_buyers相關係數若|r|>0.7同家族只算一個獨立發現，
判定以net_usd為準，n_buyers僅供對照列印。
零外部請求，僅讀本地panel_opt.csv/panel_pes.csv/issuer_month_net.csv。"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

H = Path(__file__).parent
TRAIN_END = "2020-12"
VAL_END = "2024-11"  # 面板本身止於2024-11（fwd20需20日空間，見insider_dera_panel.py）
N_SHUFFLE = 200
SEED = 20260920
REQUIRED_PCT = 90.0
EXPECTED_SIGN = 1  # 事前綁定：net_usd/n_buyers越高 -> 未來20日報酬應偏正


def _load(version_file: str) -> pd.DataFrame:
    m = pd.read_csv(H / "data/dera_insider" / "issuer_month_net.csv", dtype={"issuer_cik": str})
    p = pd.read_csv(H / "data/dera_insider" / version_file, dtype={"issuer_cik": str})
    p["issuer_cik"] = p["issuer_cik"].astype(str).str.zfill(10)
    m["issuer_cik"] = m["issuer_cik"].astype(str).str.zfill(10)
    out = p.merge(m[["issuer_cik", "month", "net_usd", "n_buyers"]], on=["issuer_cik", "month"], how="left")
    return out


def _monthly_ic(df: pd.DataFrame, signal_col: str) -> pd.Series:
    """逐月橫斷面Spearman IC，回傳index=month的Series（NaN月份代表該月樣本<5剔除）。"""
    ics = {}
    for mo, g in df.groupby("month"):
        g = g[[signal_col, "fwd20"]].dropna()
        if len(g) < 5 or g[signal_col].nunique() < 2:
            continue
        r, _ = spearmanr(g[signal_col], g["fwd20"])
        if not np.isnan(r):
            ics[mo] = r
    return pd.Series(ics)


def _shuffle_null_mean_ic(df: pd.DataFrame, signal_col: str, months: list[str], rng: np.random.Generator) -> float:
    """對指定月份區間，逐月內打散signal_col後計算平均IC（單次抽樣的結果）。"""
    total, n = 0.0, 0
    for mo in months:
        g = df[df["month"] == mo][[signal_col, "fwd20"]].dropna()
        if len(g) < 5 or g[signal_col].nunique() < 2:
            continue
        shuffled = rng.permutation(g[signal_col].to_numpy())
        r, _ = spearmanr(shuffled, g["fwd20"].to_numpy())
        if not np.isnan(r):
            total += r
            n += 1
    return total / n if n else np.nan


def _gate_one(df: pd.DataFrame, signal_col: str, label: str) -> dict:
    train_df = df[df["month"] <= TRAIN_END]
    val_df = df[(df["month"] > TRAIN_END) & (df["month"] <= VAL_END)]
    train_ic = _monthly_ic(train_df, signal_col)
    val_ic = _monthly_ic(val_df, signal_col)
    train_mean = float(train_ic.mean()) if len(train_ic) else np.nan
    val_mean = float(val_ic.mean()) if len(val_ic) else np.nan

    rng = np.random.default_rng(SEED)
    val_months = sorted(val_df["month"].unique().tolist())
    null_means = np.array([
        _shuffle_null_mean_ic(val_df, signal_col, val_months, rng) for _ in range(N_SHUFFLE)
    ])
    null_means = null_means[~np.isnan(null_means)]
    pct = float(100.0 * np.mean(null_means <= val_mean)) if len(null_means) and not np.isnan(val_mean) else float("nan")

    same_sign = (not np.isnan(train_mean) and not np.isnan(val_mean)
                 and np.sign(train_mean) == np.sign(val_mean) and np.sign(val_mean) == EXPECTED_SIGN)
    passed = same_sign and pct >= REQUIRED_PCT
    return {
        "label": label, "signal": signal_col,
        "n_train_months": int(len(train_ic)), "n_val_months": int(len(val_ic)),
        "train_mean_ic": round(train_mean, 4) if not np.isnan(train_mean) else None,
        "val_mean_ic": round(val_mean, 4) if not np.isnan(val_mean) else None,
        "null_percentile": round(pct, 1) if not np.isnan(pct) else None,
        "same_sign_positive": bool(same_sign),
        "passed": bool(passed),
    }


def main():
    results = {}
    corr_by_version = {}
    for version, fname in (("i_optimistic", "panel_opt.csv"), ("ii_pessimistic", "panel_pes.csv")):
        df = _load(fname)
        both = df[["net_usd", "n_buyers"]].dropna()
        corr = float(both["net_usd"].corr(both["n_buyers"], method="spearman")) if len(both) > 5 else None
        corr_by_version[version] = corr
        r_net = _gate_one(df, "net_usd", f"{version}/net_usd")
        r_nb = _gate_one(df, "n_buyers", f"{version}/n_buyers(對照,同家族不獨立算)")
        results[version] = {"net_usd": r_net, "n_buyers": r_nb, "net_usd_vs_n_buyers_spearman": corr}
        print(f"\n=== {version} ===")
        print(f"  net_usd  : train_IC={r_net['train_mean_ic']} val_IC={r_net['val_mean_ic']} "
              f"null_pct={r_net['null_percentile']} same_sign_pos={r_net['same_sign_positive']} PASS={r_net['passed']}")
        print(f"  n_buyers : train_IC={r_nb['train_mean_ic']} val_IC={r_nb['val_mean_ic']} "
              f"null_pct={r_nb['null_percentile']} same_sign_pos={r_nb['same_sign_positive']} PASS={r_nb['passed']} (對照，非獨立判定)")
        print(f"  net_usd vs n_buyers 同月相關係數(spearman)={corr}")

    overall_pass = all(results[v]["net_usd"]["passed"] for v in results)
    verdict = "CHEAP_PASS" if overall_pass else "FAIL"
    print(f"\n判定：{verdict}（判準=net_usd在(i)(ii)兩版本皆須過；n_buyers僅供對照）")

    import json
    (H / "insider_dera_gate1_result.json").write_text(
        json.dumps({"results": results, "verdict": verdict}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return verdict, results


if __name__ == "__main__":
    main()
