"""先.五十七-A3：交易日前一晚的唯讀自檢＋未入金提醒（只查詢、絕不送單）。

跑一次 --preflight（結果照常寫進本機 status），若第 19 項「可用餘額足夠下一批」FAIL，
推播一則「明天 09:05 首批將因未入金而擋單」。推播只寫結果，不寫金額。失敗只記警告。
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "research"))
import auto_rebalance_bb90 as A  # noqa: E402


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    now = datetime.now(A.TW)
    paths = A.Paths()
    out = A.preflight(paths, now)
    item = next((i for i in out["items"] if i["id"] == "cash_ready"), None)
    print(f"preflight PASS {out['pass']}／FAIL {out['fail']}；第 19 項：{item['result'] if item else '無'}", flush=True)
    if item and item["result"] == "FAIL":
        ok = A.push_notify(paths, "明天首批將被擋單",
                           "唯讀自檢：永豐交割戶可用餘額不足下一批（尚未入金或餘額不足）。"
                           "明天 09:05 首批將因未入金而擋單；入金後下一個交易日 09:05 會自動重跑，不需任何操作。", "info")
        print(f"提醒推播：{'送達' if ok else '未送達（只記警告）'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
