# -*- coding: utf-8 -*-
"""IBKR paper帳戶下單本機伺服器（2026-09-01新增，使用者原話：「AI只擬計畫，
送單永遠使用者親按」）。

**架構決策（使用者選定）**：App是純前端PWA（GitHub Pages），沒有辦法主動
觸發使用者本機電腦上的程式——這支伺服器就是補這個缺口：在本機開一個輕量
HTTP伺服器（FastAPI+uvicorn，兩者這台機器上都已經裝了，不用額外裝套件），
只監聽`127.0.0.1`（**刻意不監聽`0.0.0.0`**，只有這台電腦自己的瀏覽器能連得
到，手機/其他裝置連不到——這是刻意的保守選擇，使用者選項時知道「同一
網路」在技術上可行，但那需要開放LAN存取+沒有額外驗證機制會有安全疑慮，
先只做最安全的「同一台電腦」版本，之後真的需要手機遠端下單再另外討論
要不要加驗證機制開放LAN）。App（`index.html`）用瀏覽器`fetch()`打
`http://127.0.0.1:8793/...`（HTTPS頁面對localhost的HTTP請求，瀏覽器有
特別放行，不算mixed content——這是瀏覽器規範既有的例外，不是繞過安全
機制）。

**四層安全防護（鐵律：paper only，真實帳戶一律不接，見`CLAUDE.md`
「安全紅線」+使用者這次的明確裁示）**：
1. **共享密鑰(token)驗證**：每個會改變狀態的請求（`/submit_order`）都要帶
   正確的`X-Alpha-Local-Token`標頭，token在這支伺服器第一次啟動時亂數
   產生、印在終端機給使用者手動複製貼到App設定頁（存localStorage，不會
   被commit進公開repo——如果直接寫進repo任何人都看得到，等於沒有驗證）。
   **這一層防的是「瀏覽器裡開著的其他分頁/惡意網頁的JS也對localhost打
   fetch」這個真實存在的攻擊面（DNS rebinding/localhost port scanning），
   不是防使用者自己**。
2. **每次下單前都重新驗證帳戶ID是"DU"開頭**（跟`ibkr_quotes.py`同一套
   邏輯，獨立實作，不共用連線狀態，因為每個請求都是全新的HTTP請求，
   不能假設先前檢查過的連線還有效/還是同一個帳戶）——不是paper帳戶就
   拒絕，回傳明確錯誤，不下任何單。
3. **只有`/submit_order`會真的下單，其他所有endpoint都是唯讀查詢**
   （`/health`、`/account_summary`）——降低意外觸發下單的表面積。
4. **每次下單前後都寫進log檔**（呼叫前先記「意圖」，收到最終狀態後補記
   結果，即使中途程式當掉，至少留下「有嘗試過這個意圖」的紀錄，不會完全
   無聲無息）。**命名澄清**：使用者原話要求寫進`paper_trades.json`，但
   查證後那個檔名**已經被既有功能佔用**——`data/paper_trades.json`是
   `PAPER_TRADING_ARCHITECTURE.md`規劃的「已上架策略」績效追蹤，schema是
   `{strategies:[...]}`（目前空陣列，因為還沒有策略通過完整驗證），
   跟這裡要記的「使用者手動觸發的單筆下單意圖/結果」完全不是同一種東西
   （前者是自動化策略的長期績效紀錄，後者是互動式的單次操作日誌），
   直接沿用同一個檔名會破壞既有`loadStrategies()`的解析邏輯。改用
   `data/paper_order_log.json`（新檔案），避免撞名，這裡先誠實記錄這個
   命名調整，不是自己偷改需求。

**不是這支伺服器職責的部分**：報價本身（App用既有`data/quotes_ibkr.json`
或FinMind/Yahoo來源當參考價，見使用者原話「參考價IBKR即時或現有來源」，
不需要這支伺服器另外提供）、下單計畫卡片的UI（`index.html`負責）。

**啟動方式**：`python research/ibkr_order_server.py`（前景執行，不是排程
背景任務——下單是需要使用者當下在App操作才會發生的，不需要像報價那樣
定期輪詢，使用者要用的時候自己啟動這支伺服器，不用時關掉更安全）。
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ib_async import IB, MarketOrder, LimitOrder, Stock

REPO_ROOT = Path(__file__).resolve().parent.parent
PAPER_TRADES_PATH = REPO_ROOT / "data" / "paper_order_log.json"  # 不是paper_trades.json，見模組docstring「命名澄清」
TOKEN_PATH = Path(__file__).parent / ".ibkr_order_token"  # gitignored，見.gitignore
TW_TZ = timezone(timedelta(hours=8))

IB_HOST = "127.0.0.1"
IB_PAPER_PORT = 4002
IB_CLIENT_ID = 49  # 跟ibkr_quotes.py(47)/測試腳本(48)不同，避免clientId撞號
SERVER_PORT = 8793
ORDER_FILL_WAIT_SEC = 10  # 等成交/最終狀態的上限秒數，paper市價單通常瞬間成交


def _load_or_create_token() -> str:
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(24)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    return token


LOCAL_TOKEN = _load_or_create_token()

app = FastAPI(title="Alpha IBKR Paper Order Server (本機限定)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jlove1314520.github.io", "http://localhost:8792", "http://127.0.0.1:8792"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _connect() -> IB:
    """每個請求各自開一條新連線，用完即斷——避免長駐連線的clientId
    衝突/狀態污染問題，下單頻率本來就很低，這個開銷可以接受。"""
    ib = IB()
    ib.connect(IB_HOST, IB_PAPER_PORT, clientId=IB_CLIENT_ID, timeout=8, readonly=False)
    return ib


def _verify_paper_account(ib: IB) -> str:
    """回傳帳戶ID字串；不是paper帳戶就丟例外，呼叫端要接住轉成HTTP錯誤。
    每次下單前都重新查，不信任任何快取狀態（見模組docstring第2層防護）。"""
    accounts = ib.managedAccounts()
    if not accounts:
        raise RuntimeError("查不到任何帳戶，無法確認是否為paper帳戶，安全起見拒絕")
    non_paper = [a for a in accounts if not a.startswith("DU")]
    if non_paper:
        raise RuntimeError(f"偵測到非paper帳戶（{non_paper}），鐵律只能操作paper帳戶，拒絕執行")
    return accounts[0]


def _check_token(x_alpha_local_token: str | None) -> None:
    if x_alpha_local_token != LOCAL_TOKEN:
        raise HTTPException(status_code=401, detail="token不正確或缺少X-Alpha-Local-Token標頭")


def _sanitize_nan(obj):
    """NaN不是合法JSON語法（RFC 8259），json.dumps預設allow_nan=True會偷偷
    寫出裸露的NaN token，Python自己讀得回來但瀏覽器JS的JSON.parse()會
    直接拋SyntaxError——2026-09-01一次性下單管線測試已經真的踩到這個坑
    （市場數據沒有即時權限時ticker.last是NaN，一路帶進limit_price寫進
    log），寫檔前統一轉成None，這裡是正式服務也要補的防呆。"""
    if isinstance(obj, float) and obj != obj:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nan(v) for v in obj]
    return obj


def _append_paper_trade(entry: dict) -> None:
    """append-only寫入data/paper_order_log.json，讀不到既有檔案就從空list開始。
    這裡只負責寫本機檔案，commit+push是使用者手動或另外的排程機制的事，
    不是這支伺服器自己做git操作（下單是即時互動流程，不適合像quotes那樣
    在request處理過程中還跑git push可能拖慢回應）。"""
    data = []
    if PAPER_TRADES_PATH.exists():
        try:
            data = json.loads(PAPER_TRADES_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = []
    data.append(_sanitize_nan(entry))
    PAPER_TRADES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAPER_TRADES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class OrderRequest(BaseModel):
    symbol: str
    action: str  # "BUY" or "SELL"
    quantity: int
    order_type: str = "MKT"  # "MKT" or "LMT"
    limit_price: float | None = None


@app.get("/health")
def health():
    try:
        ib = _connect()
        try:
            account = _verify_paper_account(ib)
            return {"ok": True, "connected": True, "account_type": "paper", "account_id": account}
        finally:
            ib.disconnect()
    except Exception as e:
        return {"ok": False, "connected": False, "error": str(e)}


@app.get("/account_summary")
def account_summary(symbol: str | None = None):
    try:
        ib = _connect()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"連線失敗：{e}")
    try:
        _verify_paper_account(ib)
        tags = ib.accountSummary()
        summary = {t.tag: t.value for t in tags if t.tag in
                   ("AvailableFunds", "NetLiquidation", "BuyingPower", "TotalCashValue")}
        position_qty = 0
        if symbol:
            for pos in ib.positions():
                if pos.contract.symbol == symbol.upper():
                    position_qty = pos.position
                    break
        return {"summary": summary, "position_qty": position_qty}
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    finally:
        ib.disconnect()


@app.post("/submit_order")
def submit_order(req: OrderRequest, x_alpha_local_token: str | None = Header(default=None)):
    _check_token(x_alpha_local_token)

    if req.action not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="action必須是BUY或SELL")
    if req.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity必須是正整數")
    if req.order_type == "LMT" and req.limit_price is None:
        raise HTTPException(status_code=400, detail="LMT單必須帶limit_price")

    attempt_id = secrets.token_hex(8)
    _append_paper_trade({
        "attempt_id": attempt_id,
        "phase": "intent",
        "at": datetime.now(TW_TZ).isoformat(),
        "symbol": req.symbol, "action": req.action, "quantity": req.quantity,
        "order_type": req.order_type, "limit_price": req.limit_price,
        "note": "模擬交易，非投資建議",
    })

    try:
        ib = _connect()
    except Exception as e:
        _append_paper_trade({"attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
                              "status": "CONNECT_FAILED", "error": str(e)})
        raise HTTPException(status_code=503, detail=f"連線失敗：{e}")

    try:
        try:
            _verify_paper_account(ib)
        except RuntimeError as e:
            _append_paper_trade({"attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
                                  "status": "REJECTED_NOT_PAPER", "error": str(e)})
            raise HTTPException(status_code=403, detail=str(e))

        contract = Stock(req.symbol.upper(), "SMART", "USD")
        qualified = ib.qualifyContracts(contract)
        if not qualified:
            _append_paper_trade({"attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
                                  "status": "CONTRACT_NOT_FOUND"})
            raise HTTPException(status_code=400, detail=f"合約無法解析：{req.symbol}")
        contract = qualified[0]

        order = (MarketOrder(req.action, req.quantity) if req.order_type == "MKT"
                 else LimitOrder(req.action, req.quantity, req.limit_price))
        trade = ib.placeOrder(contract, order)

        # 2026-09-01實測抓到的真bug：IBKR paper帳戶對某些訂單會先送一個
        # 非終止性的"Cancelled"狀態（Error 10349，只是「委託單TIF已根據
        # 預置設定至DAY」的資訊性訊息，不是真的取消），之後才接著
        # PreSubmitted→Filled——如果看到Cancelled就提早跳出等待迴圈，會
        # 把「其實已經成交」誤報成「已取消」（親自測過：一張BUY單被誤報
        # Cancelled/filled=0，但帳戶部位真的多了1股、現金真的被扣款）。
        # 修法：只有"Filled"（明確成功）或"ValidationError"（Gateway端
        # 立即拒絕，例如Read-Only API擋下，這個狀態不會再變）才提早結束；
        # 其他狀態（含Cancelled/PreSubmitted）一律等滿整個時間預算，只信賴
        # 最後讀到的狀態，不對中途出現的Cancelled提早下結論。
        for _ in range(ORDER_FILL_WAIT_SEC):
            ib.sleep(1)
            if trade.orderStatus.status in ("Filled", "ValidationError"):
                break

        final_status = trade.orderStatus.status
        if trade.fills and final_status != "Filled":
            # trade.fills有實際成交記錄，但狀態字串卻不是Filled——這種矛盾
            # 不能默默吞掉，誠實把兩者都報給使用者看，不能只看status欄位
            # 就以為沒有任何東西成交（這正是上面那個真bug的防呆版本）。
            final_status = f"{final_status}_但trade.fills顯示有實際成交_請人工核對帳戶部位"

        result = {
            "attempt_id": attempt_id, "phase": "result", "at": datetime.now(TW_TZ).isoformat(),
            "status": final_status,
            "filled": trade.orderStatus.filled,
            "remaining": trade.orderStatus.remaining,
            "avg_fill_price": trade.orderStatus.avgFillPrice,
            "order_id": trade.order.orderId,
            "perm_id": trade.order.permId,
            "log": [f"{e.status}: {e.message}" for e in trade.log],
            "fills": [{"shares": f.execution.shares, "price": f.execution.price, "side": f.execution.side}
                      for f in trade.fills],
        }
        _append_paper_trade(result)

        if trade.orderStatus.status == "ValidationError":
            raise HTTPException(status_code=409,
                                 detail="下單被Gateway拒絕（多半是Read-Only API仍勾選中——"
                                        "要讓下單功能運作，需要在IB Gateway取消勾選Read-Only API）")
        return result
    finally:
        ib.disconnect()


if __name__ == "__main__":
    import uvicorn
    # flush=True：stdout被重導向到檔案/管線時預設是full-buffered，不flush的話
    # 這幾行會卡在緩衝區裡，直到uvicorn.run()那個長駐迴圈某天結束才會真的寫出來
    # ——但使用者要看的正是這裡的token，等到那時候已經沒有意義了。
    print(f"本機下單伺服器啟動於 http://127.0.0.1:{SERVER_PORT}（只監聽本機，其他裝置連不到）", flush=True)
    print(f"App設定頁要填的Token：{LOCAL_TOKEN}", flush=True)
    print("這支伺服器只在你要用下單計畫功能時手動啟動，用完可以直接關掉（Ctrl+C）。", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT)
