"""#73 (b2)：補齊 T86 出現過但缺 FinMind TaiwanStockPrice 原始收盤快取的股票。
有界批次（預設 MAX_PER_RUN 檔）、遇 402/429 或連續失敗立即停止（資料源禮儀，見 HYPOTHESIS_QUEUE_PROTOCOL 第2節），
只走 load_dev（強制截 VAL_END，不碰 holdout）。已快取者自動略過，可重複呼叫接續。"""
import sys, re, glob, os, time
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from finmind_client import load_dev
MAX_PER_RUN = int(sys.argv[1]) if len(sys.argv) > 1 else 60
MAX_CONSEC_FAIL = 4
DATA = Path(__file__).parent / "data"
have = set()
for p in glob.glob(str(DATA / "raw" / "TaiwanStockPrice__*.parquet")):
    m = re.match(r"TaiwanStockPrice__(\w+)__", os.path.basename(p))
    if m: have.add(m.group(1))
ids = set()
for p in glob.glob(str(DATA / "raw_twse_t86" / "T86_*.parquet")):
    d = pd.read_parquet(p, columns=["stock_id"])
    ids |= set(x for x in d["stock_id"].unique() if re.match(r"^\d{4}$", str(x)))
todo = sorted(ids - have)
print(f"缺價格 {len(todo)} 檔，本次上限 {MAX_PER_RUN}")
ok = fail = consec = 0
for sid in todo[:MAX_PER_RUN]:
    try:
        df = load_dev("TaiwanStockPrice", sid, start_date="2012-01-01")
        ok += 1; consec = 0
        print(f"{sid} rows={len(df)}")
    except Exception as e:
        fail += 1; consec += 1
        print(f"{sid} FAIL {type(e).__name__}: {str(e)[:120]}")
        if any(t in str(e) for t in ("402", "429", "limit", "Limit")) or consec >= MAX_CONSEC_FAIL:
            print("觸發停損，停止本批"); break
    time.sleep(1.0)
print(f"完成 ok={ok} fail={fail} 剩餘約 {len(todo)-ok}")
