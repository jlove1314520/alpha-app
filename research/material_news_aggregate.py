"""`HYPOTHESIS_QUEUE.md` #52 事件反應速度 — 彙總 `data/raw_mops_material_news/`
逐日parquet，套用`material_news_classify.py`事前綁定分類規則，輸出：
1. 全樣本合併事件表（stock_id/stock_name/date/announce_time/subject/type）
   存成單一parquet供下一輪gate1直接讀取，不必每次重新掃2607個小檔案。
2. 純描述性統計（各類別在TRAIN(<=2020-12-31)/VAL(2021-01-01~2024-12-31)
   期間的事件數），用來判斷樣本量是否足以支撐gate1的CAR檢定，**不做任何
   報酬/CAR計算**，純粹是「資料能不能撐得住這個問題」的地基檢查。

2026-09-09 hypothesis_queue排程接續新增。`is_holdout_consumed()`開工/
收工前皆確認`False`，本輪零新增外部API呼叫，只讀取既有本機parquet快取。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from material_news_classify import classify_material_news_type
from validation import holdout

RAW_DIR = Path(__file__).parent / "data" / "raw_mops_material_news"
OUT_PATH = Path(__file__).parent / "data" / "mops_material_news_events_classified.parquet"


def _load_all() -> pd.DataFrame:
    files = sorted(RAW_DIR.glob("MATNEWS_*.parquet"))
    if not files:
        raise SystemExit(f"找不到任何回補檔案，先跑 backfill_material_news.py（目錄：{RAW_DIR}）")
    frames = []
    for f in files:
        try:
            df = pd.read_parquet(f)
        except Exception as e:  # noqa: BLE001 -- 單檔壞掉不應中止整批彙總
            print(f"  警告：{f.name} 讀取失敗，略過（{e}）")
            continue
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["date"] = out["date"].astype(str)
    return out, len(files)


def main() -> None:
    all_df, n_files = _load_all()
    print(f"回補天數檔案數：{n_files}，合併事件筆數（去重前）：{len(all_df)}")

    holdout.assert_no_holdout_leakage(all_df, context="material_news_aggregate raw")

    all_df["type"] = all_df["subject"].map(classify_material_news_type)

    dup_key = ["stock_id", "date", "announce_time", "subject"]
    before = len(all_df)
    all_df = all_df.drop_duplicates(subset=dup_key).reset_index(drop=True)
    if before != len(all_df):
        print(f"  去重：{before} -> {len(all_df)}（重複{before - len(all_df)}筆，多半是同批次重跑的正常重疊）")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    all_df.to_parquet(OUT_PATH, index=False)
    print(f"已存：{OUT_PATH}（{len(all_df)}筆，供下一輪gate1直接載入）")

    dates = pd.to_datetime(all_df["date"])
    train_mask = dates <= pd.Timestamp(holdout.TRAIN_END)
    val_mask = (dates > pd.Timestamp(holdout.TRAIN_END)) & (dates <= pd.Timestamp(holdout.VAL_END))
    train_df = all_df[train_mask]
    val_df = all_df[val_mask]

    print(f"\nTRAIN期（<= {holdout.TRAIN_END}）事件數：{len(train_df)}")
    print(f"VAL期（{holdout.TRAIN_END} ~ {holdout.VAL_END}）事件數：{len(val_df)}")

    print("\n各類別事件數（TRAIN / VAL），依#52規格8大類 + 其他（其他不進gate1）：")
    from material_news_classify import PRIORITY_ORDER
    cats = PRIORITY_ORDER + ["其他"]
    rows = []
    for cat in cats:
        n_train = int((train_df["type"] == cat).sum())
        n_val = int((val_df["type"] == cat).sum())
        rows.append((cat, n_train, n_val))
        print(f"  {cat:6s}  TRAIN={n_train:6d}  VAL={n_val:6d}")

    summary_path = Path(__file__).parent / "data" / "mops_material_news_type_counts.csv"
    pd.DataFrame(rows, columns=["type", "train_n", "val_n"]).to_csv(
        summary_path, index=False, encoding="utf-8-sig"
    )
    print(f"\n已存分類統計摘要：{summary_path}")

    n_unique_stocks = all_df["stock_id"].nunique()
    print(f"\n涉及不重複股票代號數：{n_unique_stocks}")
    print("（本輪純描述性統計，不含任何股價/CAR計算，供下一輪判斷樣本量是否足夠開始gate1）")

    holdout.assert_no_holdout_leakage(all_df, context="material_news_aggregate final")


if __name__ == "__main__":
    main()
