"""先.五十七-A3：交易日前一晚的唯讀自檢＋未入金提醒（只查詢、絕不送單）。

跑一次 --preflight（結果照常寫進本機 status），若第 19 項「可用餘額足夠下一批」FAIL，
推播一則「明天 09:05 首批將因未入金而擋單」。推播只寫結果，不寫金額。失敗只記警告。
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "research"))
import auto_rebalance_bb90 as A  # noqa: E402


def whitelist_price_warning(root: Path = ROOT) -> str | None:
    """先.五十八-A2：讀雲端每日價格更新寫的 data/whitelist_price_status.json（先 git fetch 取遠端版本，
    取不到才用本機檔）。all_ok=False 回傳警告文字；檔案不存在或讀取失敗回 None（無法判斷≠有問題，只印警告）。"""
    raw = None
    try:
        raw = subprocess.run(["git", "-C", str(root), "show", "origin/main:data/whitelist_price_status.json"],
                             capture_output=True, timeout=30).stdout.decode("utf-8") or None
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 讀遠端 whitelist_price_status.json 失敗：{type(e).__name__}", flush=True)
    try:
        if raw is None:
            f = root / "data" / "whitelist_price_status.json"
            raw = f.read_text(encoding="utf-8") if f.exists() else None
        if not raw:
            return None
        d = json.loads(raw)
        return None if d.get("all_ok") is not False else (d.get("warning") or "白名單 ETF 價格缺漏")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 解析 whitelist_price_status.json 失敗：{type(e).__name__}", flush=True)
        return None


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
    try:
        subprocess.run(["git", "-C", str(ROOT), "fetch", "-q", "origin", "main"], capture_output=True, timeout=60)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] git fetch 失敗（改用本機檔）：{type(e).__name__}", flush=True)
    w = whitelist_price_warning()
    print(f"白名單價格狀態：{w or 'OK／無法判斷'}", flush=True)
    if w:
        ok = A.push_notify(paths, "白名單 ETF 價格缺漏", w + "。官方單股端點也補不到，明天自動交易可能因價格不新鮮而擋單。", "info")
        print(f"價格缺漏推播：{'送達' if ok else '未送達（只記警告）'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
