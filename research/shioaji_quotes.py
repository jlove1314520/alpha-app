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
- **2026-09-01新增交易時段閘門**：永豐模擬環境服務時段是台股營業日
  8:00–21:00，但這支腳本若打算掛每幾分鐘一次的排程，收盤後到21:00這段
  完全沒必要每次都登入永豐去查已經不會再變的收盤資料——會浪費API用量。
  改成`_is_tw_trading_window()`把「要不要真的登入」收緊到**週一至五
  08:30–13:45**（涵蓋盤前到收盤後一小段緩衝），非這個時段直接跳過、
  **完全不呼叫`login()`**，見`_write_market_closed()`：保留
  `data/quotes_sinopac.json`裡最後一次真正抓到的`quotes`資料不變，只把
  `market_status`欄位標成`"closed"`，`fetched_at`維持最後一次真正抓到
  資料的時間戳（不會被更新成現在，前端才能正確判斷資料實際上多舊），
  另外多一個`checked_at`欄位記錄「這次確認非交易時段」發生的時間。
  **已知簡化，誠實揭露**：跟`fetch_quotes_tw.py::is_tw_trading_window()`
  同一個限制——沒有扣除國定假日（找不到現成、可信賴的台股假日行事曆
  免費資料源），假日當天會被誤判成「該登入」，頂多多耗一次配額查到
  上一個交易日的收盤資料，不會塞假資料造成誤導。
- **data_type說明**：Shioaji（永豐證券自家經紀商報價）不像IBKR對海外
  交易所報價那樣有「即時/延遲」分層訂閱制度——這是台灣券商API的自家
  行情，沒有額外的市場數據延遲層級，統一標記`"REALTIME"`，不是隨便寫的
  樂觀值。
- **TAIEX指數合約代碼**：`api.Contracts.Indexs.TSE.IX0001`（"發行量加權
  股價指數"，2026-09-01已用真實模擬環境連線驗證過這個代碼存在且能拿到
  snapshot）。**期貨近月合約**（2026-09-01補齊App「期貨」頁
  `FUT_CONTRACTS`追蹤的四個商品，見`FUTURES_NEAR_MONTH`）：台指期
  `Futures.TXF.TXFR1`、小型台指期`Futures.MXF.MXFR1`、電子期
  `Futures.EXF.EXFR1`、金融期`Futures.FXF.FXFR1`——Shioaji對每個期貨
  群組都提供這個"XXXR1"別名代表「近月」，不用自己算最近交割日，四組都
  已用真實模擬環境連線逐一驗證過存在且能拿到snapshot。

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

# App「期貨」頁FUT_CONTRACTS追蹤的四個近月合約（index.html::FUT_CONTRACTS），
# 對應Shioaji的TAIFEX期貨群組代碼+「R1」近月別名（跟TXFR1同一套命名慣例，
# 2026-09-01已用真實模擬環境連線逐一驗證過這四組都存在且能拿到snapshot）。
FUTURES_NEAR_MONTH = {
    "TXF_NEAR": {"group": "TXF", "code": "TXFR1", "label": "台指期近月"},
    "MXF_NEAR": {"group": "MXF", "code": "MXFR1", "label": "小型台指期近月"},
    "EXF_NEAR": {"group": "EXF", "code": "EXFR1", "label": "電子期近月"},
    "FXF_NEAR": {"group": "FXF", "code": "FXFR1", "label": "金融期近月"},
}

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


def _is_tw_trading_window(now: datetime) -> bool:
    """粗略判斷：週一至五08:30–13:45台北時間（涵蓋台股現貨盤前~盤後緩衝、
    也涵蓋TAIFEX期貨日盤約08:45–13:45，兩者用同一組閘門，不用分開判斷——
    這支腳本本來就把股票+指數+期貨放在同一次snapshots()呼叫裡，沒有必要
    為了「期貨比股票早開15分鐘」這種小差異拆成兩套時窗，反而增加維護
    負擔）。**節流閘門，不是精確市場狀態判斷**：目的是避免收盤到21:00
    這段服務時段內、資料已經不會再變的時候還一直登入永豐浪費API用量，
    見模組docstring「2026-09-01新增交易時段閘門」。
    **已知簡化，誠實揭露**：跟`fetch_quotes_tw.py::is_tw_trading_window()`
    同一個限制——沒有扣除國定假日。"""
    wd = now.weekday()  # 0=Mon .. 6=Sun
    minutes = now.hour * 60 + now.minute
    return wd <= 4 and 8 * 60 + 30 <= minutes < 13 * 60 + 45


def _write_market_closed() -> None:
    """非交易時段：保留data/quotes_sinopac.json裡最後一次真正抓到的
    quotes資料不變，只把market_status標成"closed"，fetched_at維持最後
    一次真正抓到資料的時間戳（不更新成現在，前端才能正確判斷資料實際
    多舊），另外用checked_at記錄「這次確認非交易時段」發生的時間。
    第一次執行就在非交易時段（沒有既有檔案可以保留）就誠實寫空quotes，
    不是失敗，是「還沒有任何一次盤中資料」。"""
    existing = {}
    if OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    payload = {
        "fetched_at": existing.get("fetched_at"),
        "checked_at": datetime.now(TW_TZ).isoformat(),
        "connected": existing.get("connected", False),
        "market_status": "closed",
        "error": None,
        "quotes": existing.get("quotes", {}),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("非交易時段（週一至五08:30-13:45外），不登入永豐，保留最後一次盤中資料，market_status=closed")


def main():
    now = datetime.now(TW_TZ)
    if not _is_tw_trading_window(now):
        _write_market_closed()
        return

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

        for key, meta in FUTURES_NEAR_MONTH.items():
            try:
                group = getattr(api.Contracts.Futures, meta["group"])
                contract = getattr(group, meta["code"])
                contracts_and_meta.append((key, contract, "TAIFEX", meta["label"]))
            except Exception as e:
                print(f"  [{meta['label']}] 合約無法解析，跳過：{e}")

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
            "market_status": "open",
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
