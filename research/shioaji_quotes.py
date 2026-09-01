# -*- coding: utf-8 -*-
"""台股即時報價擷取（Sinopac Shioaji，2026-09-01新增，使用者原話：「兩券商
即時報價接進App，分工鐵律：台股一律走Shioaji、美股一律走IBKR，不重疊」）。

**這支腳本只做一件事：連Shioaji模擬環境，抓報價，寫JSON，收工前登出。
不下單、不改單。** 沿用跟`ibkr_quotes.py`/`ibkr_order_server.py`同一套
「本機腳本→JSON→App」模式，本機排程觸發，不經GitHub Actions（Actions
連不到使用者本機的.env/secrets/憑證，也不該把金鑰放進CI環境）。

**金鑰讀取（鐵律：只從.env/secrets/讀，絕不寫進任何commit檔案或log）**：
`SINOPAC_API_KEY`/`SINOPAC_SECRET_KEY`（登入用）、`SINOPAC_PERSON_ID`+
`SINOPAC_CA_PATH`+`SINOPAC_CA_PASSWD`（`activate_ca`用，這支腳本只抓
報價不需要下單權限，**刻意不呼叫`activate_ca`**——多一層「就算程式碼
被改壞也無法下單」的防護，跟`ibkr_quotes.py`唯讀連線同一個精神）。

**已知限制，誠實揭露（跟`ibkr_quotes.py`同一套問題，同一個根因）**：
- 「自選股」是`index.html`用`localStorage`存的前端狀態，這支在使用者
  電腦上跑的Python腳本沒辦法讀瀏覽器的localStorage——改用
  `DEFAULT_TW_WATCHLIST`（`index.html`裡`WL`預設值的同一份清單）當代表。
- 永豐模擬環境服務時段是**台股營業日8:00–21:00**，非時段呼叫`login()`/
  `snapshots()`可能回錯或回舊資料——連線/查詢失敗一律誠實寫
  `{"connected": false, "error": "..."}`，不猜、不塞假資料。經實測發現
  即使過了21:00，`snapshots()`對已收盤的當日資料仍可能查得到（回傳當天
  收盤時的快照，不是即時跳動的報價）——這不代表bug，是「非服務時段還能
  查到收盤後的最後快照」這個實際行為，`data_type`統一標`REALTIME`（見
  下方「data_type說明」），前端的`INTRADAY_STALE_MIN`過期判斷會處理
  「數字很久沒變」這件事，不需要這支腳本自己額外判斷是否為即時跳動。
- **data_type說明**：Shioaji（永豐證券自家經紀商報價）不像IBKR對海外
  交易所報價那樣有「即時/延遲」分層訂閱制度——這是台灣券商API的自家
  行情，沒有額外的市場數據延遲層級，統一標記`"REALTIME"`，不是隨便寫的
  樂觀值。
- **TAIEX指數合約代碼**：`api.Contracts.Indexs.TSE.IX0001`（"發行量加權
  股價指數"，2026-09-01已用真實模擬環境連線驗證過這個代碼存在且能拿到
  snapshot）。**台指期近月合約**：`api.Contracts.Futures.TXF.TXFR1`
  （Shioaji本身就用"TXFR1"這個別名代表「近月」，不用自己算最近交割日，
  同樣已實測驗證）。

**掛排程**：跟`ibkr_quotes.py`同一個機制（本機`.ps1`+`.vbs`+Windows工作
排程器，不透過`claude.exe -p`，純機械式抓資料寫檔案），盤中台股營業日
執行，排程檔案另外建立不是這支腳本的職責。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "quotes_sinopac.json"
ENV_PATH = REPO_ROOT / ".env"
TW_TZ = timezone(timedelta(hours=8))

# index.html的WL預設值同一份清單，見模組docstring「已知限制」
DEFAULT_TW_WATCHLIST = ["2330", "2454", "2317", "1513", "3231"]

CONTRACTS_READY_WAIT_SEC = 3  # 登入後合約清單非同步下載，太快存取Indexs/Futures會KeyError

# 2026-09-01已知小事項：api.Contracts（大寫）會印DeprecationWarning，建議改用
# api.contracts（小寫，v2）——這裡先不改，因為v2寫法需要重新登入實測驗證，
# 不值得為了消除一個無害警告多耗一次模擬環境登入配額，功能上完全正常。


def _load_env(path: Path) -> dict[str, str]:
    kv = {}
    if not path.exists():
        return kv
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip()
    return kv


def _write_failure(reason: str) -> None:
    payload = {
        "fetched_at": datetime.now(TW_TZ).isoformat(),
        "connected": False,
        "error": reason,
        "quotes": {},
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"寫入失敗狀態到 {OUT_PATH}：{reason}")


def _clean_positive(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _snapshot_to_quote(snap, exchange: str, label: str | None = None) -> dict:
    last = _clean_positive(snap.close)
    change_price = snap.change_price if snap.change_price else None
    prev_close = (last - change_price) if (last is not None and change_price is not None) else None
    change_pct = float(snap.change_rate) if snap.change_rate else None
    if snap.change_type is not None and str(snap.change_type).endswith("Down") and change_pct is not None:
        change_pct = -abs(change_pct)
    q = {
        "last": last,
        "bid": _clean_positive(snap.buy_price),
        "ask": _clean_positive(snap.sell_price),
        "close": prev_close,
        "change_pct": change_pct,
        "data_type": "REALTIME",  # 見模組docstring「data_type說明」
        "exchange": exchange,
    }
    if label:
        q["label"] = label
    return q


def main():
    env = _load_env(ENV_PATH)
    required = ["SINOPAC_API_KEY", "SINOPAC_SECRET_KEY"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        _write_failure(f".env缺少必要欄位：{missing}（登入需要API_KEY/SECRET_KEY，不需要CA相關欄位——這支只抓報價不下單）")
        return

    import shioaji as sj

    api = sj.Shioaji(simulation=True)
    try:
        accounts = api.login(api_key=env["SINOPAC_API_KEY"], secret_key=env["SINOPAC_SECRET_KEY"])
    except Exception as e:
        _write_failure(f"登入失敗（可能是非永豐模擬環境服務時段08:00-21:00，或金鑰有誤）：{type(e).__name__}: {e}")
        return

    try:
        print(f"登入成功，帳戶數：{len(accounts) if accounts else 0}")
        time.sleep(CONTRACTS_READY_WAIT_SEC)

        quotes: dict[str, dict] = {}
        contracts_and_meta = []

        for code in DEFAULT_TW_WATCHLIST:
            try:
                contract = api.Contracts.Stocks[code]
                contracts_and_meta.append((code, contract, "TSE", None))
            except Exception as e:
                print(f"  [TW個股] {code} 合約無法解析，跳過：{e}")

        try:
            taiex = api.Contracts.Indexs.TSE.IX0001
            contracts_and_meta.append(("TAIEX", taiex, "TSE", "加權指數"))
        except Exception as e:
            print(f"  [TAIEX] 合約無法解析，跳過：{e}")

        try:
            txf_near = api.Contracts.Futures.TXF.TXFR1
            contracts_and_meta.append(("TXF_NEAR", txf_near, "TAIFEX", "台指期近月"))
        except Exception as e:
            print(f"  [台指期近月] 合約無法解析，跳過：{e}")

        if not contracts_and_meta:
            _write_failure("所有標的合約都無法解析，沒有任何東西可以查詢")
            return

        try:
            snapshots = api.snapshots([c for _, c, _, _ in contracts_and_meta])
        except Exception as e:
            _write_failure(f"snapshots()查詢失敗（可能是非服務時段08:00-21:00）：{type(e).__name__}: {e}")
            return

        snap_by_code = {s.code: s for s in snapshots}
        for key, contract, exchange, label in contracts_and_meta:
            snap = snap_by_code.get(contract.code)
            if snap is None:
                print(f"  [{key}] 查無snapshot，跳過")
                continue
            q = _snapshot_to_quote(snap, exchange, label)
            quotes[key] = q
            print(f"  [{key}] last={q['last']} change_pct={q['change_pct']}")

        payload = {
            "fetched_at": datetime.now(TW_TZ).isoformat(),
            "connected": True,
            "error": None,
            "quotes": quotes,
        }
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"寫入 {OUT_PATH}：{len(quotes)} 檔報價")
    finally:
        try:
            api.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
