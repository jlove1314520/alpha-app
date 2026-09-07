"""`HYPOTHESIS_QUEUE.md` #53 全市場報酬離散度速度（Cross-Sectional Return
Dispersion Velocity）第1關 sanity（2026-09-07 hypothesis_queue排程接續）。

**佇列脈絡**：`【2026-09-07 Cowork 更正一】#53～#57 市場總開關假設軸」`
訂了三個維度：(a) 訊號來源=全市場橫斷面「二階」統計量（截面標準差，不是
一階的平均/比例）、(b) 變數型態=水位版與速度版並列對照（不得只用「Cybex
速度版較好」當理由）、(c) 作用方式=連續曝險縮放（本輪尚未做，見下）。
「五條的執行順序」明訂 #53 排第一，因為資料完全就緒、無新API呼叫。

**這一輪只做 sanity（GATE_SEQUENCE 第1關）**，不是完整PASS/FAIL判定：
確認訊號非退化、在三個已知危機期間方向正確、簡單條件式前瞻報酬方向正確。
完整的連續曝險規則+控制組(`control_group_standard.py`)+相位敏感度+
`trial_registry.register_trial()`正式登記留給下一輪，比照
`breadth_divergence_sanity.py`（#28）同一個「先sanity再上完整關卡」節奏。

**資料源**：`data/raw/TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet`
（既有快取，零新增API呼叫）。**本輪發現且必須排除的資料衛生問題**（先前
查證表未提到）：這批快取裡混了6個非個股的產業/指數聚合列——`stock_id`
分別是`TAIEX`(加權指數本身)、`TPEx`(櫃買指數)、`Cement`/`Food`/`Rubber`/
`Other`(TWSE產業分類指數)，是FinMind`TaiwanStockPrice`對這些特殊代碼
回傳指數層級資料的既有特性，不是個股。若不排除，會把大盤指數自己也算進
「個股橫斷面」，而且用來預測的目標變數正是TAIEX本身，會構成資料洩漏
（用含有TAIEX自己歷史的截面去預測TAIEX未來報酬）。過濾規則：只保留
`stock_id`開頭是數字的檔案（TW個股/ETF/權證代碼皆以數字開頭，這6個
特例全部是純英文字母），另外file size<2000 bytes判定為空快取（多為
權證/特殊代碼，`326`檔，跟先前查證表`327`檔數字接近但非完全一致——因為
先前查證把上述6個非個股列也算進了2,441這個分母，實際個股候選池比原估計
少6檔，不影響「1,384檔涵蓋TRAIN起點前」這個結論的量級）。

**未還原股價的已知限制（誠實揭露，本輪不解決）**：這批快取是原始收盤價，
未做除權息還原（`adjust.py::adjusted_price_series()`走FinMind/yfinance
逐檔還原,對2,000+檔全部重算成本過高,不是這輪sanity範圍）。個股除息造成的
單日跳空會混進當天的橫斷面報酬分布，對「截面標準差」這個二階統計量是
雜訊來源，但因為全市場除息日期分散在全年（尤其Q3旺季），且截面標準差是
用N>=300檔計算，單一/少數個股的除息跳空對整體std的影響有限、不構成系統性
方向偏誤（不像`#8`月營收公布事件那種要看單一標的CAR的研究，這裡看的是
橫斷面離散度整體水準）。若sanity後續進入cheap gate/portfolio層，需要
重新評估這個限制是否足夠小可以忽略。

**曝險方向（事前綁定，跟`HYPOTHESIS_QUEUE.md` #53條目一致，不得事後翻號）**：
離散度/離散度速度異常偏高 -> 未來報酬應偏低（風險上升->該降曝險）。
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data" / "raw"
MIN_FILE_BYTES = 2000
MIN_STOCKS_PER_DATE = 300
VEL_WINDOW = 20
PCTILE_WARMUP = 60
FORWARD_HORIZON = 20

# 跟regime_overlay.py（#10）同一組已知危機期間定義，不重新發明，維持全佇列
# 一致的sanity檢查基準。
KNOWN_CRISIS_WINDOWS = {
    "2018Q4貿易戰急跌": ("2018-10-01", "2018-12-31"),
    "2020Q1新冠崩盤": ("2020-02-01", "2020-04-30"),
    "2022全年空頭": ("2022-01-01", "2022-12-31"),
}


def _discover_stock_files() -> list[tuple[str, Path]]:
    """回傳(stock_id, path)清單，已排除：非數字開頭的產業/指數聚合列
    （TAIEX/TPEx/Cement/Food/Rubber/Other）、file size<MIN_FILE_BYTES的
    空快取（多為權證/特殊代碼）。"""
    out = []
    excluded_non_numeric = []
    excluded_empty = 0
    for f in sorted(DATA_DIR.glob("TaiwanStockPrice__*__2010-01-01__2024-12-31.parquet")):
        parts = f.name.split("__")
        if len(parts) < 4:
            continue
        sid = parts[1]
        if not re.match(r"^[0-9]", sid):
            excluded_non_numeric.append(sid)
            continue
        if f.stat().st_size < MIN_FILE_BYTES:
            excluded_empty += 1
            continue
        out.append((sid, f))
    print(f"排除非個股聚合列({len(excluded_non_numeric)}檔): {sorted(excluded_non_numeric)}")
    print(f"排除空快取(<{MIN_FILE_BYTES} bytes): {excluded_empty} 檔")
    print(f"納入橫斷面計算的個股候選池: {len(out)} 檔")
    return out


def _load_return_long() -> pd.DataFrame:
    """回傳long-form DataFrame(columns=date, stock_id, ret)，逐檔算簡單日報酬
    （未還原股價，見模組docstring已知限制段落）。"""
    files = _discover_stock_files()
    frames = []
    n_ok, n_err, n_short = 0, 0, 0
    for i, (sid, path) in enumerate(files):
        try:
            df = pd.read_parquet(path, columns=["date", "close"])
        except Exception as e:  # noqa: BLE001 -- 跟factor_ic.py同一套容錯，單檔壞掉不拖垮整體
            print(f"  [{i + 1}/{len(files)}] {sid}: read ERROR ({e}), dropping")
            n_err += 1
            continue
        if df.empty or len(df) < 30:
            n_short += 1
            continue
        df = df.dropna(subset=["date", "close"]).sort_values("date")
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates(subset="date", keep="last")
        ret = df["close"].pct_change()
        sub = pd.DataFrame({"date": df["date"].to_numpy(), "stock_id": sid, "ret": ret.to_numpy()})
        sub = sub.dropna(subset=["ret"])
        # 除權息/資料錯誤造成的離譜單日報酬（>500%）視為壞值，不納入截面統計，
        # 避免單一髒資料點主導std（TW個股正常單日報酬受10%漲跌停限制，
        # 遠超此範圍必為資料問題,不是真實報酬）。
        sub = sub[sub["ret"].abs() < 5.0]
        frames.append(sub)
        n_ok += 1
    print(f"逐檔載入結果: ok={n_ok} err={n_err} too_short(<30列)={n_short}")
    if not frames:
        raise RuntimeError("no valid stock return series loaded")
    return pd.concat(frames, ignore_index=True)


def build_dispersion_series() -> pd.DataFrame:
    """回傳index=date的DataFrame，欄位disp/n_t/vel/level_pctile/vel_pctile。
    全程只用截至當下(含當日)的資料，不看未來（expanding percentile、
    trailing mean都只往回看）。"""
    long_df = _load_return_long()
    grouped = long_df.groupby("date")["ret"].agg(disp="std", n_t="count").reset_index()
    grouped = grouped.sort_values("date").reset_index(drop=True)

    n_unusable = int((grouped["n_t"] < MIN_STOCKS_PER_DATE).sum())
    print(
        f"\n總交易日數={len(grouped)}，其中n_t<{MIN_STOCKS_PER_DATE}判定不可用的"
        f"天數={n_unusable}（{100 * n_unusable / len(grouped):.1f}%），標NaN不靜默丟棄"
    )
    grouped.loc[grouped["n_t"] < MIN_STOCKS_PER_DATE, "disp"] = np.nan

    disp = grouped["disp"].to_numpy()
    n = len(disp)

    # 速度版：vel_t = disp_t / mean(disp_{t-20..t-1}) - 1，嚴格只用t之前
    # （不含t）的20個有效值，湊不滿20個有效值就是NaN，不用部分窗口湊數。
    vel = np.full(n, np.nan)
    for t in range(n):
        if np.isnan(disp[t]):
            continue
        window = disp[max(0, t - VEL_WINDOW) : t]
        window = window[~np.isnan(window)]
        if len(window) < VEL_WINDOW:
            continue
        m = window.mean()
        if m <= 0:
            continue
        vel[t] = disp[t] / m - 1.0

    grouped["vel"] = vel
    grouped["level_pctile"] = _expanding_percentile(disp, PCTILE_WARMUP)
    grouped["vel_pctile"] = _expanding_percentile(vel, PCTILE_WARMUP)
    return grouped


def _expanding_percentile(values: np.ndarray, warmup: int) -> np.ndarray:
    """對每個位置t，回傳values[t]在values[0..t]（只採用非NaN值,含t自己）
    這個expanding視窗內的百分位排名（0~1）。warmup:視窗內有效值數量少於此
    門檻時回傳NaN（避免早期樣本太少造成噪音百分位）。expanding而非rolling
    ——符合#53共同規格「z為訊號對其擴張視窗分位數標準化」的要求，不看未來
    也不用全樣本統計量。"""
    n = len(values)
    out = np.full(n, np.nan)
    seen: list[float] = []
    for t in range(n):
        v = values[t]
        if not np.isnan(v):
            seen.append(v)
        if len(seen) < warmup or np.isnan(v):
            continue
        arr = np.asarray(seen)
        out[t] = float((arr <= v).sum() - 1) / (len(arr) - 1)
    return out


def _load_taiex_close() -> pd.DataFrame:
    """直接用本機已快取的TAIEX指數列（跟個股同一個parquet來源，零新增
    API呼叫），不透過yf_price_client避免任何潛在網路呼叫。"""
    path = DATA_DIR / "TaiwanStockPrice__TAIEX__2010-01-01__2024-12-31.parquet"
    df = pd.read_parquet(path, columns=["date", "close"])
    df["date"] = pd.to_datetime(df["date"])
    return df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def sanity_check_1_descriptive(df: pd.DataFrame) -> dict:
    valid_disp = df["disp"].dropna()
    valid_vel = df["vel"].dropna()
    stats = {
        "n_days_total": len(df),
        "n_days_valid_disp": len(valid_disp),
        "disp_mean": float(valid_disp.mean()),
        "disp_std": float(valid_disp.std()),
        "disp_min": float(valid_disp.min()),
        "disp_max": float(valid_disp.max()),
        "n_t_min": int(df["n_t"].min()),
        "n_t_mean": float(df["n_t"].mean()),
        "n_t_max": int(df["n_t"].max()),
        "n_days_valid_vel": len(valid_vel),
        "vel_mean": float(valid_vel.mean()),
        "vel_std": float(valid_vel.std()),
    }
    print("\n=== sanity 1: 描述統計（非退化性） ===")
    for k, v in stats.items():
        print(f"  {k} = {v}")
    non_degenerate = stats["disp_std"] > 0 and stats["vel_std"] > 0 and stats["n_days_valid_vel"] > 500
    print(f"  非退化判定: {non_degenerate}")
    stats["pass"] = bool(non_degenerate)
    return stats


def sanity_check_2_crisis_windows(df: pd.DataFrame) -> dict:
    print("\n=== sanity 2: 已知危機期間 level/vel 百分位是否偏高 ===")
    unconditional_level = df["level_pctile"].mean()
    unconditional_vel = df["vel_pctile"].mean()
    print(f"  無條件基準: level_pctile_mean={unconditional_level:.3f}  vel_pctile_mean={unconditional_vel:.3f}")
    results = {}
    hits = 0
    for name, (start, end) in KNOWN_CRISIS_WINDOWS.items():
        mask = (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
        window = df.loc[mask]
        lvl = window["level_pctile"].mean()
        vel = window["vel_pctile"].mean()
        hit = bool(vel > unconditional_vel)
        hits += int(hit)
        print(
            f"  {name} ({start}~{end}, n={len(window)}): "
            f"level_pctile={lvl:.3f} vel_pctile={vel:.3f}  "
            f"vel高於基準={hit}"
        )
        results[name] = {"n": len(window), "level_pctile": float(lvl), "vel_pctile": float(vel), "vel_above_baseline": hit}
    print(f"  三個危機窗口中vel_pctile高於無條件基準的窗口數: {hits}/3")
    results["hits"] = hits
    results["unconditional_level"] = float(unconditional_level)
    results["unconditional_vel"] = float(unconditional_vel)
    results["pass"] = hits >= 2  # 比照#28 breadth sanity：3個裡至少2個方向正確才算通過
    return results


def sanity_check_3_forward_return(df: pd.DataFrame) -> dict:
    print("\n=== sanity 3: 條件式前瞻20日TAIEX報酬（tertile切分） ===")
    taiex = _load_taiex_close()
    tw_dates = taiex["date"].to_numpy()
    tw_close = taiex["close"].to_numpy()

    rows = []
    for _, r in df.iterrows():
        if np.isnan(r["level_pctile"]) or np.isnan(r["vel_pctile"]):
            continue
        sig_date = np.datetime64(r["date"])
        start_idx = int(np.searchsorted(tw_dates, sig_date, side="right"))
        end_idx = start_idx + FORWARD_HORIZON - 1
        if start_idx >= len(tw_dates) or end_idx >= len(tw_dates):
            continue
        fwd_ret = tw_close[end_idx] / tw_close[start_idx] - 1.0
        rows.append({"date": r["date"], "level_pctile": r["level_pctile"], "vel_pctile": r["vel_pctile"], "fwd_ret": fwd_ret})
    aligned = pd.DataFrame(rows)
    print(f"  對齊後樣本數: {len(aligned)}")

    out = {"n_aligned": len(aligned)}
    for col in ("level_pctile", "vel_pctile"):
        q1, q2 = aligned[col].quantile([1 / 3, 2 / 3])
        low = aligned[aligned[col] <= q1]["fwd_ret"]
        high = aligned[aligned[col] >= q2]["fwd_ret"]
        direction_ok = bool(high.mean() < low.mean())
        print(
            f"  {col}: 低tertile(n={len(low)}) fwd_ret_mean={low.mean():+.4f}  "
            f"高tertile(n={len(high)}) fwd_ret_mean={high.mean():+.4f}  "
            f"方向正確(高<低)={direction_ok}"
        )
        out[col] = {
            "low_mean": float(low.mean()),
            "high_mean": float(high.mean()),
            "direction_ok": direction_ok,
        }
    out["pass"] = out["level_pctile"]["direction_ok"] or out["vel_pctile"]["direction_ok"]
    return out


def main():
    print("=== #53 全市場報酬離散度速度 第1關 sanity ===")
    df = build_dispersion_series()
    df.to_csv(Path(__file__).parent / "data" / "cross_sectional_dispersion_gate53.csv", index=False)

    s1 = sanity_check_1_descriptive(df)
    s2 = sanity_check_2_crisis_windows(df)
    s3 = sanity_check_3_forward_return(df)

    overall_pass = s1["pass"] and s2["pass"] and s3["pass"]
    print(f"\n=== 三項sanity皆PASS: {overall_pass} ===")
    print("**這是sanity，不是最終PASS/FAIL判定**——下一輪視結果進第2關（隨機控制組，")
    print("依`control_group_standard.py`統一標準+`trial_registry.register_trial()`正式登記）")
    print("或若sanity方向不對則直接判FAIL並記錄。")
    return {"sanity1": s1, "sanity2": s2, "sanity3": s3, "sanity_pass": overall_pass}


if __name__ == "__main__":
    main()
