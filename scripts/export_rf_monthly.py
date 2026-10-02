"""每月由本機排程呼叫：從央行開放資料抓定存利率月序列，輸出 data/rf_monthly.json（先.十-一）。

runner（GitHub Actions）上的紙.一只讀這個檔，不連央行網站、不需要 pyarrow。
抓取失敗時不覆蓋舊檔、exit 1（由呼叫端記錄），不寫任何半成品。
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "research"))
from cbc_rf_rate_client import SOURCE_URL, RATE_COL, load_risk_free_rate_series  # noqa: E402

OUT = REPO / "data" / "rf_monthly.json"
TZ = timezone(timedelta(hours=8))


def main() -> int:
    monthly = load_risk_free_rate_series(force=True)
    monthly = monthly.dropna(subset=["rf_rate_pct"])
    if len(monthly) < 12:
        print(f"筆數異常偏少({len(monthly)})，不覆蓋舊檔")
        return 1
    doc = {
        "source": SOURCE_URL,
        "column": f"{RATE_COL}（六家銀行算術平均，年化%）",
        "fetched_at": datetime.now(TZ).isoformat(),
        "n": int(len(monthly)),
        "last_month": monthly["date"].iloc[-1].strftime("%Y-%m"),
        "monthly": [{"date": d.strftime("%Y-%m-%d"), "rf_rate_pct": round(float(v), 6)}
                    for d, v in zip(monthly["date"], monthly["rf_rate_pct"])],
    }
    fd, tmp = tempfile.mkstemp(dir=str(OUT.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, OUT)
    print(f"寫入 {OUT}：{doc['n']} 個月，最新 {doc['last_month']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
